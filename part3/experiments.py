import os, json
import shutil
import argparse
import subprocess
import yaml
from datetime import datetime
from cluster_manager import setup_cluster, deploy_memcached, delete_all_jobs
from mcperf_manager import (
   setup_mcperf_agents,
   start_load_agents,
   restart_mcperf_agents,
   preload,
   run_mcperf_load,
   stop_mcperf_agents
)
from parsec_runner import (
    launch_jobs,
    wait_for_jobs,
    collect_parsec_times,
    delete_all_parsec_jobs
)
from delete_cluster import delete_cluster

def load_matrix(path="experiment_matrix.json"):
    return json.load(open(path))

def run_experiments(args):
    matrix = load_matrix(args.experiment_config)
    timestamp = datetime.now().strftime("%y%m%d_T%H%M%S")
    base_dir  = f"results/{timestamp}"
    os.makedirs(base_dir, exist_ok=True)

    # Copy the experiment config into the results folder for reproducibility
    shutil.copy(
        args.experiment_config,
        os.path.join(base_dir, os.path.basename(args.experiment_config))
    )
    print(f"[STATUS] Copied experiment config to {base_dir}")
    
    # Determine cluster name from kops config (supports multi-document YAML)
    with open(args.cluster_config) as f:
        docs = list(yaml.safe_load_all(f))
    if not docs:
        raise ValueError(f"No documents found in {args.cluster_config}")
    # The first document defines the Cluster object
    cluster_cfg = docs[0]
    cluster_name = cluster_cfg.get("metadata", {}).get("name")
    if not cluster_name:
        raise ValueError(f"Could not determine cluster name from {args.cluster_config}")

    if args.reuse_cluster:
        print("[STATUS] Checking if cluster is up and healthy...")
        cp = subprocess.run(
            ["kops", "validate", "cluster",
             "--name", cluster_name,
             "--state", args.state_store,
             "--wait", "1m"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        if cp.returncode != 0:
            print("[STATUS] Cluster not found or unhealthy; creating it now.")
            setup_cluster(args.state_store, args.cluster_config)
        else:
            print("[STATUS] Cluster is up and healthy; reusing.")
    else:
        print("[STATUS] Creating new cluster...")
        setup_cluster(args.state_store, args.cluster_config)

    # Setup and run mcperf agents
    clients_info = setup_mcperf_agents()
    start_load_agents(clients_info)

    # Keep track of the current memcached node to avoid redeploying
    current_mem_node = None
    
    # # Run all experiments
    # for exp in matrix:
    #     experiment_name = exp["experiment_name"]
    #     target_mem_node = exp["mem_node"]
    #     mem_threads = exp["mem_threads"]
    #     mem_cpuset = exp["mem_cpuset"]

    #     print(f"[STATUS] Running experiment: {experiment_name}")

    #     # Create a directory for the experiment
    #     exp_dir = os.path.join(base_dir, experiment_name)

    #     # only redeploy memcached if the target node has changed
    #     if target_mem_node != current_mem_node:
    #         print(f"[STATUS] Moving memcached → {target_mem_node}")
    #         memcached_ip = deploy_memcached(
    #             node = target_mem_node,
    #             threads = mem_threads,
    #             cpuset = mem_cpuset, 
    #             output_dir = exp_dir  # so YAML lives in your experiment folder
    #         )
    #         current_mem_node = target_mem_node
    #     else:
    #         print(
    #             f"[STATUS] Memcached already on {current_mem_node}, skipping " +
    #             f"redeploy"
    #         )

    #     # Preload memcached
    #     preload(clients_info, memcached_ip)

    #     # Start mcperf load
    #     mcperf_results = run_mcperf_load(
    #         clients_info,
    #         memcached_ip,
    #         exp_dir
    #     )

    #     # Launch all PARSEC benchmarks concurrently for this experiment
    #     benchings = exp["benchings"]
    #     configs = [
    #         (b["name"], b["node"], b["threads"], b.get("cpuset", ""))
    #         for b in benchings
    #     ]
    #     # Apply scheduling and launch jobs
    #     job_names = launch_jobs(configs, exp_dir)
    #     # Wait until all batch jobs finish
    #     wait_for_jobs(job_names)
    #     # Collect start/end times for all pods into a results file
    #     collect_parsec_times(os.path.join(exp_dir, "parsec_times.txt"))
    #     # Clean up PARSEC jobs and pods before next run
    #     delete_all_parsec_jobs()
    #     # Restart mcperf agents to avoid synchronization issues
    #     restart_mcperf_agents(clients_info)

    # Stop mcperf agents
    print("[STATUS] Stopping all mcperf agents...")
    stop_mcperf_agents()

    # Teardown cluster if requested
    if args.teardown_cluster:
        print("[STATUS] Tearing down cluster...")
        delete_cluster(cluster_name, args.state_store)
    else:
        print(
            "[STATUS] Cluster not torn down. To do so, run:\n" +
            "python3 delete_cluster.py"
        )

    print("[STATUS] All experiments completed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
       description = "Setup script for Part 3 of the CCA project."
    )
    parser.add_argument(
       "--state-store",
       default = "gs://cca-eth-2025-group-092-fbaldin/",
       help = "GCP state store for kops (gs://...)"
    )
    parser.add_argument(
        "--cluster-config",
        default = "part3.yaml",
        help = "Path to cluster configuration file."
    )
    parser.add_argument(
        "--experiment-config",
        default = "experiment_matrix.json",
        help = "Path to the experiment configuration file (JSON format)."
    )
    parser.add_argument(
        "--reuse-cluster",
        action = "store_true",
        help = (
           "Whether to reuse the cluster or not. Set to true if cluster " +
           "is already up."
        )
    )
    parser.add_argument(
        "--teardown-cluster",
        action = "store_true",
        help = "Teardown the cluster and delete all jobs/pods after completion."
    )

    args = parser.parse_args()

    run_experiments(args)