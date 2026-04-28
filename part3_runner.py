#!/usr/bin/env python3
"""
Automation runner for CCA Part 3.

It starts memcached, starts mcperf at 30K QPS, schedules all seven PARSEC jobs,
and stores the required pods_i.json and mcperf_i.txt outputs.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ZONE = os.environ.get("GCP_ZONE", "europe-west1-b")
SSH_KEY = os.environ.get("CCA_SSH_KEY", "~/.ssh/cloud-computing")
MCPERF_BIN = os.environ.get("MCPERF_BIN", "~/memcache-perf-dynamic/mcperf")
MCPERF_SECONDS = int(os.environ.get("MCPERF_SECONDS", "1200"))


@dataclass(frozen=True)
class BatchJob:
    name: str
    yaml: str
    node: str
    cores: tuple[int, ...]
    threads: int


def run(cmd: list[str], *, check: bool = True, capture: bool = False) -> subprocess.CompletedProcess:
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(
        cmd,
        cwd=ROOT,
        check=check,
        text=True,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None,
    )


def kubectl(*args: str, capture: bool = False, check: bool = True) -> subprocess.CompletedProcess:
    return run(["kubectl", *args], check=check, capture=capture)


def gcloud_ssh(node: str, command: str, *, capture: bool = False) -> subprocess.CompletedProcess:
    return run(
        [
            "gcloud",
            "compute",
            "ssh",
            "--ssh-key-file",
            SSH_KEY,
            f"ubuntu@{node}",
            "--zone",
            ZONE,
            "--command",
            command,
        ],
        capture=capture,
    )


def gcloud_ssh_popen(node: str, command: str, out_file: Path) -> subprocess.Popen:
    print(f"+ gcloud compute ssh ubuntu@{node} --zone {ZONE} --command {command!r}", flush=True)
    out = out_file.open("w", encoding="utf-8")
    return subprocess.Popen(
        [
            "gcloud",
            "compute",
            "ssh",
            "--ssh-key-file",
            SSH_KEY,
            f"ubuntu@{node}",
            "--zone",
            ZONE,
            "--command",
            command,
        ],
        cwd=ROOT,
        stdout=out,
        stderr=subprocess.STDOUT,
        text=True,
    )


def handcrafted_schedule() -> list[dict]:
    return [
        {"name": "streamcluster", "yaml": "parsec-streamcluster.yaml", "node": "node-a-8core", "cores": [1, 2, 3, 4], "threads": 4},
        {"name": "canneal", "yaml": "parsec-canneal.yaml", "node": "node-a-8core", "cores": [5, 6], "threads": 2},
        {"name": "radix", "yaml": "parsec-radix.yaml", "node": "node-a-8core", "cores": [7], "threads": 1},
        {"name": "freqmine", "yaml": "parsec-freqmine.yaml", "node": "node-b-4core", "cores": [0, 1, 2, 3], "threads": 4},
        {"name": "vips", "yaml": "parsec-vips.yaml", "node": "node-b-4core", "cores": [0, 1, 2, 3], "threads": 4},
        {"name": "blackscholes", "yaml": "parsec-blackscholes.yaml", "node": "node-b-4core", "cores": [0, 1, 2, 3], "threads": 4},
        {"name": "barnes", "yaml": "parsec-barnes.yaml", "node": "node-a-8core", "cores": [5, 6, 7], "threads": 3},
    ]


def load_schedule(policy_file: str | None) -> list[dict]:
    if not policy_file:
        return handcrafted_schedule()

    path = Path(policy_file).resolve()
    spec = importlib.util.spec_from_file_location("part3_policy", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import policy file: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not hasattr(module, "get_schedule"):
        raise RuntimeError(f"{path} must define get_schedule()")
    return module.get_schedule()


def normalize_schedule(raw_schedule: list[dict]) -> list[BatchJob]:
    jobs: list[BatchJob] = []
    seen = set()
    for item in raw_schedule:
        name = str(item["name"]).replace("parsec-", "")
        yaml_name = str(item.get("yaml", f"parsec-{name}.yaml"))
        node = str(item["node"])
        cores = tuple(int(c) for c in item["cores"])
        threads = int(item["threads"])
        if name in seen:
            raise ValueError(f"duplicate job in schedule: {name}")
        if node == "node-a-8core" and any(c == 0 for c in cores):
            raise ValueError(f"{name} uses node-a core 0, reserved for memcached")
        if node == "node-a-8core" and any(c < 1 or c > 7 for c in cores):
            raise ValueError(f"{name} has invalid node-a cores: {cores}")
        if node == "node-b-4core" and any(c < 0 or c > 3 for c in cores):
            raise ValueError(f"{name} has invalid node-b cores: {cores}")
        if threads < 1 or threads > len(cores):
            raise ValueError(f"{name} threads must be between 1 and allocated cores")
        seen.add(name)
        jobs.append(BatchJob(name, yaml_name, node, cores, threads))

    expected = {"barnes", "blackscholes", "canneal", "freqmine", "radix", "streamcluster", "vips"}
    actual = {j.name for j in jobs}
    if actual != expected:
        raise ValueError(f"schedule must contain exactly {sorted(expected)}, got {sorted(actual)}")
    return jobs


def node_name(label_value: str) -> str:
    out = kubectl(
        "get",
        "nodes",
        "-l",
        f"cca-project-nodetype={label_value}",
        "-o",
        "jsonpath={.items[0].metadata.name}",
        capture=True,
    ).stdout.strip()
    if not out:
        raise RuntimeError(f"no node found for cca-project-nodetype={label_value}")
    return out


def node_internal_ip(label_value: str) -> str:
    out = kubectl(
        "get",
        "nodes",
        "-l",
        f"cca-project-nodetype={label_value}",
        "-o",
        "jsonpath={.items[0].status.addresses[?(@.type=='InternalIP')].address}",
        capture=True,
    ).stdout.strip()
    if not out:
        raise RuntimeError(f"no internal IP found for {label_value}")
    return out


def cleanup() -> None:
    kubectl("delete", "jobs", "--all", "--ignore-not-found", check=False)
    kubectl("delete", "pods", "--all", "--ignore-not-found", check=False)
    time.sleep(5)


def write_memcached_yaml(tmpdir: Path) -> Path:
    path = tmpdir / "memcached-part3.yaml"
    path.write_text(
        """apiVersion: v1
kind: Pod
metadata:
  name: some-memcached
  labels:
    name: some-memcached
spec:
  containers:
  - image: anakli/memcached:t1
    name: memcached
    imagePullPolicy: Always
    command: ["/bin/sh"]
    args: ["-c", "taskset -c 0 ./memcached -t 1 -u memcache"]
  nodeSelector:
    cca-project-nodetype: "node-a-8core"
""",
        encoding="utf-8",
    )
    return path


def rewrite_job_yaml(job: BatchJob, run_id: int, tmpdir: Path) -> tuple[str, Path]:
    src = ROOT / "parsec-benchmarks" / "part2b" / job.yaml
    text = src.read_text(encoding="utf-8")
    unique_name = f"parsec-{job.name}-r{run_id}"
    text = re.sub(r"(?m)^  name: parsec-[a-z]+$", f"  name: {unique_name}", text, count=1)
    text = re.sub(r"-n\s+\d+", f"-n {job.threads}", text)
    text = re.sub(r"(\./run [^\"]+)", f"taskset -c {','.join(map(str, job.cores))} \\1", text, count=1)
    text = re.sub(r'cca-project-nodetype: "parsec"', f'cca-project-nodetype: "{job.node}"', text)
    dst = tmpdir / f"{unique_name}.yaml"
    dst.write_text(text, encoding="utf-8")
    return unique_name, dst


def start_mcperf(result_file: Path, memcached_ip: str) -> subprocess.Popen:
    agent_a = node_name("client-agent-a")
    agent_b = node_name("client-agent-b")
    measure = node_name("client-measure")
    agent_a_ip = node_internal_ip("client-agent-a")
    agent_b_ip = node_internal_ip("client-agent-b")

    gcloud_ssh(agent_a, f"pkill -f mcperf || true; nohup {MCPERF_BIN} -T 2 -A >/tmp/mcperf-agent.log 2>&1 &")
    gcloud_ssh(agent_b, f"pkill -f mcperf || true; nohup {MCPERF_BIN} -T 4 -A >/tmp/mcperf-agent.log 2>&1 &")
    time.sleep(5)
    gcloud_ssh(measure, f"pkill -f mcperf || true; nohup {MCPERF_BIN} -s {memcached_ip} --loadonly >/tmp/mcperf-loadonly.log 2>&1 &")
    time.sleep(5)

    command = (
        f"timeout {MCPERF_SECONDS}s {MCPERF_BIN} -s {memcached_ip} "
        f"-a {agent_a_ip} -a {agent_b_ip} --noload -T 6 -C 4 -D 4 "
        "-Q 1000 -c 4 -t 10 --scan 30000:30500:5"
    )
    return gcloud_ssh_popen(measure, command, result_file)


def stop_mcperf() -> None:
    for label in ("client-agent-a", "client-agent-b", "client-measure"):
        try:
            gcloud_ssh(node_name(label), "pkill -f mcperf || true")
        except Exception as exc:
            print(f"warning: failed to stop mcperf on {label}: {exc}", file=sys.stderr)


def job_done(job_name: str) -> bool:
    out = kubectl("get", "job", job_name, "-o", "json", capture=True, check=False).stdout
    if not out:
        return False
    data = json.loads(out)
    if int(data.get("status", {}).get("failed", 0) or 0) > 0:
        raise RuntimeError(f"{job_name} failed; inspect kubectl describe job/{job_name}")
    return int(data.get("status", {}).get("succeeded", 0) or 0) >= 1


def save_job_log(job_name: str, log_dir: Path) -> None:
    pod = kubectl(
        "get",
        "pods",
        "--selector",
        f"job-name={job_name}",
        "-o",
        "jsonpath={.items[0].metadata.name}",
        capture=True,
    ).stdout.strip()
    if pod:
        out = kubectl("logs", pod, capture=True, check=False).stdout
        (log_dir / f"{job_name}.log").write_text(out, encoding="utf-8")


def schedule_batch_jobs(jobs: list[BatchJob], run_id: int, tmpdir: Path, log_dir: Path) -> None:
    pending = list(jobs)
    running: dict[str, tuple[BatchJob, set[int]]] = {}
    busy = {"node-a-8core": set(), "node-b-4core": set()}
    name_to_yaml: dict[str, Path] = {}

    while pending or running:
        launched = False
        for job in list(pending):
            cores = set(job.cores)
            if busy[job.node].isdisjoint(cores):
                job_name, yaml_path = rewrite_job_yaml(job, run_id, tmpdir)
                name_to_yaml[job_name] = yaml_path
                kubectl("apply", "-f", str(yaml_path))
                busy[job.node].update(cores)
                running[job_name] = (job, cores)
                pending.remove(job)
                launched = True
                print(f"launched {job_name} on {job.node} cores {sorted(cores)}", flush=True)

        for job_name, (job, cores) in list(running.items()):
            if job_done(job_name):
                save_job_log(job_name, log_dir)
                busy[job.node].difference_update(cores)
                del running[job_name]
                print(f"completed {job_name}", flush=True)

        if not launched:
            time.sleep(10)


def run_one(run_id: int, jobs: list[BatchJob], results_dir: Path) -> None:
    run_dir = results_dir / f"logs_run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    temp_root = ROOT / ".part3_tmp"
    temp_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"run-{run_id}-", dir=temp_root) as td:
        tmpdir = Path(td)
        cleanup()
        kubectl("apply", "-f", str(write_memcached_yaml(tmpdir)))
        kubectl("wait", "--for=condition=Ready", "pod/some-memcached", "--timeout=180s")
        memcached_ip = kubectl(
            "get",
            "pod",
            "some-memcached",
            "-o",
            "jsonpath={.status.podIP}",
            capture=True,
        ).stdout.strip()
        if not memcached_ip:
            raise RuntimeError("memcached pod has no IP")

        mcperf_file = results_dir / f"mcperf_{run_id}.txt"
        mcperf = start_mcperf(mcperf_file, memcached_ip)
        start = time.monotonic()
        try:
            schedule_batch_jobs(jobs, run_id, tmpdir, run_dir)
        finally:
            kubectl("get", "pods", "-o", "json", capture=True).stdout
            pods_json = kubectl("get", "pods", "-o", "json", capture=True).stdout
            (results_dir / f"pods_{run_id}.json").write_text(pods_json, encoding="utf-8")
            time.sleep(5)
            if mcperf.poll() is None:
                mcperf.send_signal(signal.SIGTERM)
                try:
                    mcperf.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    mcperf.kill()
            stop_mcperf()
            elapsed = time.monotonic() - start
            print(f"run {run_id} finished in {elapsed:.1f}s", flush=True)
            cleanup()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task", choices=["1", "2"], required=True, help="Part 3 subtask: 1=hand-crafted, 2=OpenEvolve")
    parser.add_argument("--group", required=True, help="three-digit group number, e.g. 001")
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--policy-file", help="Python file defining get_schedule(); omit for hand-crafted policy")
    args = parser.parse_args()

    if not re.fullmatch(r"\d{3}", args.group):
        raise SystemExit("--group must be a three-digit value such as 001")

    raw_schedule = load_schedule(args.policy_file)
    jobs = normalize_schedule(raw_schedule)
    results_dir = ROOT / f"part_3_{args.task}_results_group_{args.group}"
    results_dir.mkdir(exist_ok=True)

    for run_id in range(1, args.runs + 1):
        run_one(run_id, jobs, results_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
