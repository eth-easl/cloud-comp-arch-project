import os
import subprocess
import re
import time
from datetime import datetime

env = os.environ.copy()

env["PROJECT"] = "cca-eth-2025-group-008"
env["KOPS_STATE_STORE"] = "gs://cca-eth-2025-group-008-dbociat"

intereferences = [None, "cpu", "l1d", "l1i", "l2", "llc", "membw"]
jobs = ["blackscholes", "canneal", "dedup", "ferret", "freqmine", "radix", "vips"] 

NUM_RUNS = 1

def is_job_completed(kubectl_output):
    lines = kubectl_output.strip().splitlines()
    if len(lines) < 2:
        return False 

    job_info = lines[1]
    parts = job_info.split()

    completions = parts[2]

    return completions == "1/1"

def is_pod_ready(kubectl_output):
    lines = kubectl_output.strip().splitlines()
    if len(lines) < 2:
        return False 

    pod_info = lines[1]
    parts = pod_info.split()

    readiness = parts[1]

    return readiness == "1/1"

def extract_times(output):
    match = re.search(r"real\s+(\d+)m([\d.]+)s\s+user\s+(\d+)m([\d.]+)s\s+sys\s+(\d+)m([\d.]+)s", output)

    real_time = int(match.group(1)) * 60 + float(match.group(2))
    user_time = int(match.group(3)) * 60 + float(match.group(4))
    sys_time = int(match.group(5)) * 60 + float(match.group(6))
    
    print(f"Real time: {real_time} seconds")
    print(f"User time: {user_time} seconds")
    print(f"Sys time: {sys_time} seconds")

    return real_time, user_time, sys_time

def write_run_data(filename, interference, job_name, real_time, user_time, sys_time):
    line = f"{interference},{job_name},{real_time},{user_time},{sys_time}\n"
    with open(filename, "a") as f:
        f.write(line)

if __name__ == '__main__':
    # Init steps

    # subprocess.run(["gcloud", "auth", "application-default", "login"], check=True)
    # subprocess.run(["gcloud", "init"], check=True)
    # subprocess.run(["kops", "create", "-f", "part2a.yaml"], env=env, check=True)
    # subprocess.run(["kops", "update", "cluster", "part2a.k8s.local", "--yes", "--admin"], env=env, check=True)
    # subprocess.run(["kops", "validate", "cluster", "--wait", "10m"],  env=env, check=True)
    # subprocess.run(["kubectl", "get", "nodes", "-o", "wide"], env=env, check=True)

    # output = subprocess.check_output(["kubectl", "get", "nodes", "-o", "wide"], env=env, text=True)
    # lines = output.strip().split("\n")
    # for line in lines[1:]:
    #     if "parsec-server" in line:
    #         parsec_node_name = line.split()[0]
    #         break

    # subprocess.run(["kubectl", "label", "nodes", parsec_node_name, "cca-project-nodetype=parsec"], env=env, check=True)

    current_time = datetime.now()
    formatted_time = current_time.strftime("%d-%m-%Y-%H-%M")    

    # Run the processes
    for interference in intereferences:
        if interference is not None:
            int_name = f"ibench-{interference}" 
            subprocess.run(["kubectl", "create", "-f" f"interference_parsec/ibench-{interference}.yaml"], env=env, check=True)

            output = subprocess.check_output(["kubectl", "get", "pods", "--selector=name="+int_name], env=env, text=True)
            while not is_pod_ready(output):
                print("Interference not ready yet...")
                time.sleep(30)
                output = subprocess.check_output(["kubectl", "get", "pods", "--selector=name="+int_name], env=env, text=True)

        for job in jobs:
            job_name = f"parsec-{job}"

            for i in range(NUM_RUNS):
                
                subprocess.run(["kubectl", "create", "-f", f"parsec-benchmarks/part2a/{job_name}.yaml"], env=env, check=True)

                output = subprocess.check_output(["kubectl", "get", "jobs"], env=env, text=True)
                while not is_job_completed(output):
                    print("Job not completed yet...")
                    time.sleep(30)
                    output = subprocess.check_output(["kubectl", "get", "jobs"], env=env, text=True)

                pod_name = subprocess.check_output([
                        "kubectl", "get", "pods",
                        "--selector=job-name=" + job_name,
                        "--output=jsonpath={.items[*].metadata.name}"
                    ], env=env, text=True).strip()
                metrics_output = subprocess.check_output(["kubectl", "logs", pod_name], env=env, text=True)
                
                r,u,s = extract_times(metrics_output) # here the run times are returned

                subprocess.run(["kubectl", "delete", "job", job_name], env=env, check=True)
                
                write_run_data(f"part2-output-{formatted_time}.csv", interference, job, r, u, s)
             
        if interference is not None:
            subprocess.run(["kubectl", "delete", "pod", int_name], env=env, check=True)

    # Make sure there are no witnesses
    subprocess.run(["kubectl", "delete", "jobs", "--all"])
    subprocess.run(["kubectl", "delete", "pods", "--all"])
