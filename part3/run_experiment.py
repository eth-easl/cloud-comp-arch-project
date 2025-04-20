#!/usr/bin/env python3

from utils import run_command
import os
import subprocess
import re
from datetime import datetime
from pathlib import Path

# node-a-2core : e2-highmem-2
# node-b-2core : n2-highcpu-2
# node-c-4core : c3-highcpu-4
# node-d-4core : n2-standard-4

# Path of the parsec benchmarks YAML files
PARSEC_YAML_DIR = "./parsec-benchmarks"

# Create a new subdirectory for the experiment files
timestamp = datetime.now().strftime("%m-%d-%H-%M-%S")
experiment_dir = Path(f"./experiments/{timestamp}")
experiment_dir.mkdir(parents=True, exist_ok=True)
print(f"[STATUS] Created experiment directory: {experiment_dir}")

def modify_yaml_for_scheduling(benchmark, node_type, threads, cpuset=None):
    """Modify the benchmark YAML file for our scheduling policy."""
    yaml_path = os.path.join(PARSEC_YAML_DIR, f"parsec-{benchmark}.yaml")
    if not os.path.exists(yaml_path):
        print(f"Error: Could not find YAML file for {benchmark}")
        return None
    
    # Read the original YAML file
    with open(yaml_path, "r") as f:
        yaml_content = f.read()
    
    # Replace the NODE_TYPE placeholder with our specific node type
    yaml_content = yaml_content.replace('"NODE_TYPE"', f'"{node_type}"')
    
    # Replace the THREAD_COUNT placeholder
    yaml_content = yaml_content.replace('THREAD_COUNT', f'{threads}')
    
    # Replace the CPUSET_PREFIX placeholder
    if cpuset:
        # Add taskset command for CPU pinning
        yaml_content = yaml_content.replace('CPUSET_PREFIX', f'taskset -c {cpuset} ')
    else:
        # Remove the placeholder if no CPU pinning
        yaml_content = yaml_content.replace('CPUSET_PREFIX', '')
    
    job_name = f"parsec-{benchmark}"

    # Write the modified YAML to a temporary file
    modified_yaml_path = f"./experiments/{timestamp}/parsec-{benchmark}.yaml"
    with open(modified_yaml_path, "w") as f:
        f.write(yaml_content)
    
    return modified_yaml_path, job_name

def launch_job(benchmark, node_type, threads, cpuset=None):
    """Launch a PARSEC benchmark job with the specified configuration."""
    modified_yaml_path, job_name = modify_yaml_for_scheduling(benchmark, node_type, threads, cpuset)
    if not modified_yaml_path:
        return None
    
    # Launch the job
    run_command(f"kubectl create -f {modified_yaml_path}")
    print(f"Launched job: {job_name} on node {node_type} with {threads} threads")
    
    return job_name

def main():
    
    print("\n=== Executing Scheduling Plan ===")
    print(f"{'Benchmark':<15} {'Node Type':<15} {'Threads':<8} {'CPU Set':<10}")
    print("-" * 55)
        
    launch_job("blackscholes", "node-a-2core", 1)
    launch_job("canneal", "node-b-2core", 2)
    launch_job("dedup", "node-c-4core", 2)
    launch_job("ferret", "node-d-4core", 3)
    launch_job("freqmine", "node-a-2core", 1)
    launch_job("radix", "node-c-4core", 2)
    launch_job("vips", "node-d-4core", 1)

    
    print("\nScheduling complete!")
    print("To monitor jobs: kubectl get jobs")
    print("To get results when done: kubectl get pods -o json > results.json && python3 get_time.py results.json")

if __name__ == "__main__":
    main() 