import os
import subprocess
import re
import time
from datetime import datetime

env = os.environ.copy()

env["PROJECT"] = "cca-eth-2025-group-008"
env["KOPS_STATE_STORE"] = "gs://cca-eth-2025-group-008-dbociat"

threads = [1, 2, 4, 8]
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

def write_run_data(filename, no_threads, job_name, real_time, user_time, sys_time):
    line = f"{no_threads},{job_name},{real_time},{user_time},{sys_time}\n"
    with open(filename, "a") as f:
        f.write(line)

def update_template(filename, num_threads):
    script_dir = os.path.dirname(__file__)
    rel_path = f"parsec-benchmarks/part3/{filename}-template.yaml"
    abs_file_path = os.path.join(script_dir, rel_path)

    with open(abs_file_path) as f:
        schemas = f.read()

    schemas = schemas.replace("<n>", str(num_threads))

    script_dir = os.path.dirname(__file__)
    rel_path = f"parsec-benchmarks/part3/{filename}.yaml"
    abs_file_path = os.path.join(script_dir, rel_path)

    with open(abs_file_path, "w") as f:
        f.write(schemas)

if __name__ == '__main__':
    # Init steps

    subprocess.run(["gcloud", "auth", "application-default", "login"], check=True)
    subprocess.run(["gcloud", "init"], check=True)
    subprocess.run(["kops", "create", "-f", "part3.yaml"], env=env, check=True)
    subprocess.run(["kops", "update", "cluster", "part3.k8s.local", "--yes", "--admin"], env=env, check=True)
    subprocess.run(["kops", "validate", "cluster", "--wait", "10m"],  env=env, check=True)
    subprocess.run(["kubectl", "get", "nodes", "-o", "wide"], env=env, check=True)

    output = subprocess.check_output(["kubectl", "get", "nodes", "-o", "wide"], env=env, text=True)
    lines = output.strip().split("\n")
    for line in lines[1:]:
        if "client-agent-a-" in line:
            client_agent_a = line.split()[0]
        if "client-agent-b-" in line:
            client_agent_b = line.split()[0]
        if "client-measure" in line:
            client_measure = line.split()[0]


    current_time = datetime.now()
    formatted_time = current_time.strftime("%d-%m-%Y-%H-%M")    

    # Run the processes
    for i in range(NUM_RUNS):
        for job in jobs:
            job_name = f"parsec-{job}"

            subprocess.run(["kubectl", "create", "-f", f"parsec-benchmarks/part3/{job_name}.yaml"], env=env, check=True)
                
        # Get results
        subprocess.run(["kubectl", "get", "pods", "-o", "json", ">", f"results-{i}.json"], check=True)
        subprocess.run(["python3", "get_time.py", f"results-{i}.json"], check=True)

    # Make sure there are no witnesses
    subprocess.run(["kubectl", "delete", "jobs", "--all"])
    subprocess.run(["kubectl", "delete", "pods", "--all"])

    # subprocess.run(["kops", "delete", "cluster", "--name", f"part3.k8s.local", "--yes"], check=True)
    # print("Successfully deleted cluster!")
