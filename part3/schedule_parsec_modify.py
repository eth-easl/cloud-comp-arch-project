#!/usr/bin/env python3

import os
import subprocess
import re
from datetime import datetime
from pathlib import Path

# ============================================================================
# START OF SCHEDULING POLICY
# ============================================================================

# node-a-2core : e2-highmem-2
# node-b-2core : n2-highcpu-2
# node-c-4core : c3-highcpu-4
# node-d-4core : n2-standard-4

# Format: benchmark_name: (node_type, thread_count, cpuset)
SCHEDULING_PLAN = {
    "blackscholes": ("node-a-2core", 1),      
    "canneal": ("node-b-2core", 2),          
    "dedup": ("node-c-4core", 2),          
    "ferret": ("node-d-4core", 3),          
    "freqmine": ("node-a-2core", 1),          
    "radix": ("node-c-4core", 2),            
    "vips": ("node-d-4core", 1),             
}

# ============================================================================
# END OF SCHEDULING POLICY
# ============================================================================

PARSEC_YAML_DIR = "./parsec-benchmarks"

def run_command(command, shell=True, check=True, capture_output=False):
    """Run a shell command and return the output if capture_output is True."""
    print(f"Running: {command}")
    result = subprocess.run(command, shell=shell, check=check, capture_output=capture_output, text=True)
    if capture_output:
        return result.stdout.strip()
    return None

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
    yaml_content = yaml_content.replace('"NODE_TYPE"', 
                                       f'"{node_type}"')
    
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
    modified_yaml_path = f"modified-parsec-{benchmark}.yaml"
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

def cleanup_jobs():
    """Delete all PARSEC jobs."""
    # Delete jobs
    run_command("kubectl delete jobs")
    # Clean up temporary files
    run_command("rm -f modified-parsec-*.yaml")
    print("Cleaned up all PARSEC jobs and temporary files")

def main():
    # Parse command line arguments
    import argparse
    parser = argparse.ArgumentParser(description="PARSEC scheduler using existing YAML files")
    parser.add_argument("--cleanup", action="store_true", help="Delete all existing PARSEC jobs before starting")
    args = parser.parse_args()
    
    # Clean up existing jobs if requested
    if args.cleanup:
        cleanup_jobs()
    
    # Launch jobs based on the scheduling plan
    job_names = []
    
    print("\n=== Executing Scheduling Plan ===")
    print(f"{'Benchmark':<15} {'Node Type':<15} {'Threads':<8} {'CPU Set':<10}")
    print("-" * 55)
    
    for benchmark, config in SCHEDULING_PLAN.items():
        node_type = config[0]
        threads = config[1]
        cpuset = config[2] if len(config) > 2 else None
        
        print(f"{benchmark:<15} {node_type:<15} {threads:<8} {cpuset if cpuset else 'None':<10}")
        
        job_name = launch_job(benchmark, node_type, threads, cpuset)
        if job_name:
            job_names.append(job_name)
    
    print("\nScheduling complete!")
    print("To monitor jobs: kubectl get jobs")
    print("To get results when done: kubectl get pods -o json > results.json && python3 get_time.py results.json")

if __name__ == "__main__":
    main() 