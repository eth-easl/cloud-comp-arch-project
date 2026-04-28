from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import traceback
from datetime import datetime
from pathlib import Path


try:
    from openevolve.evaluation_result import EvaluationResult
except Exception:
    class EvaluationResult:  # local fallback for syntax checks before pip install openevolve
        def __init__(self, metrics, artifacts=None):
            self.metrics = metrics
            self.artifacts = artifacts or {}


ROOT = Path(__file__).resolve().parents[1]
RESULT_DIR = ROOT / "part_3_2_results_group_000"


def _parse_pods(path: Path) -> tuple[float, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    starts = []
    ends = []
    for item in data["items"]:
        statuses = item.get("status", {}).get("containerStatuses", [])
        if not statuses:
            continue
        container = statuses[0]
        if container.get("name") == "memcached":
            continue
        terminated = container.get("state", {}).get("terminated")
        if not terminated:
            continue
        starts.append(datetime.strptime(terminated["startedAt"], "%Y-%m-%dT%H:%M:%SZ"))
        ends.append(datetime.strptime(terminated["finishedAt"], "%Y-%m-%dT%H:%M:%SZ"))
    if len(starts) != 7 or len(ends) != 7:
        raise RuntimeError(f"expected 7 completed PARSEC pods, found {len(starts)}")
    return (max(ends) - min(starts)).total_seconds(), len(starts)


def _parse_mcperf(path: Path) -> tuple[float, int]:
    max_p95 = 0.0
    violations = 0
    rows = 0
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.startswith("read"):
            continue
        cols = line.split()
        if len(cols) < 12:
            continue
        rows += 1
        p95 = float(cols[11])
        max_p95 = max(max_p95, p95)
        if p95 > 1000.0:
            violations += 1
    if rows == 0:
        raise RuntimeError("mcperf produced no read rows")
    return max_p95, violations


def evaluate(program_path: str) -> EvaluationResult:
    """
    Run one real Part 3 trial for an evolved policy and score it.

    The main fitness metric is combined_score. Higher is better:
    - policies with all jobs completed and p95 <= 1 ms are rewarded by low makespan
    - SLO violations are heavily penalized
    """
    if RESULT_DIR.exists():
        shutil.rmtree(RESULT_DIR)

    timeout = int(os.environ.get("OPENEVOLVE_EVAL_TIMEOUT", "1800"))
    command = [
        sys.executable,
        str(ROOT / "part3_runner.py"),
        "--task",
        "2",
        "--group",
        "000",
        "--runs",
        "1",
        "--policy-file",
        program_path,
    ]

    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        if completed.returncode != 0:
            return EvaluationResult(
                metrics={"combined_score": 0.0, "correctness": 0.0, "slo_ok": 0.0, "makespan_seconds": timeout},
                artifacts={"failure_stage": "runner", "stdout": completed.stdout[-6000:]},
            )

        makespan, completed_jobs = _parse_pods(RESULT_DIR / "pods_1.json")
        max_p95, violations = _parse_mcperf(RESULT_DIR / "mcperf_1.txt")
        slo_ok = 1.0 if violations == 0 and max_p95 <= 1000.0 else 0.0
        correctness = 1.0 if completed_jobs == 7 else 0.0
        makespan_score = max(0.0, 1.0 - (makespan / 600.0))
        slo_penalty = min(1.0, violations / 10.0 + max(0.0, max_p95 - 1000.0) / 5000.0)
        combined = max(0.0, correctness * (0.75 * makespan_score + 0.25 * slo_ok) - slo_penalty)

        return EvaluationResult(
            metrics={
                "combined_score": combined,
                "correctness": correctness,
                "slo_ok": slo_ok,
                "makespan_seconds": makespan,
                "max_p95_us": max_p95,
                "slo_violations": float(violations),
            },
            artifacts={
                "stdout": completed.stdout[-6000:],
                "llm_feedback": "Keep all seven jobs valid, reserve node-a core 0 for memcached, and reduce makespan without p95 > 1000 us.",
            },
        )
    except Exception:
        return EvaluationResult(
            metrics={"combined_score": 0.0, "correctness": 0.0, "slo_ok": 0.0, "makespan_seconds": timeout},
            artifacts={"failure_stage": "exception", "traceback": traceback.format_exc()},
        )
