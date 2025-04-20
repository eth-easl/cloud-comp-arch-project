#!/usr/bin/env python3

from utils import run_command
import os
import sys
import time
import argparse

def setup_cluster(state_store, cluster_config_yaml):
    """
    Sets up a Kubernetes cluster using kops.
    This function configures the Kubernetes cluster by setting the required 
    environment variables, creating the cluster using a provided configuration 
    file, updating the cluster, validating it, and retrieving information about 
    the cluster nodes.

    Parameters
    ----------
    state_store (str)
        The GCS bucket URI to be used as the KOPS state store.
        This is where kops stores its configuration and state files.
    cluster_config_yaml (str)
        The file path to the YAML configuration file that defines the cluster 
        specifications.

    Returns
    -------
    None
    """
    # Set the KOPS_STATE_STORE environment variable
    os.environ["KOPS_STATE_STORE"] = state_store
    print(f"[STATUS] Set KOPS_STATE_STORE to {state_store}")
    
    # Get the project name
    project = run_command("gcloud config get-value project", capture_output=True)
    print(f"[INFO] Project name: {project}")
    
    # Create the cluster
    run_command(f"kops create -f {cluster_config_yaml}")
    
    # Update the cluster
    run_command("kops update cluster --name part3.k8s.local --yes --admin")
    
    # Validate the cluster (wait up to 10 minutes)
    run_command("kops validate cluster --wait 10m")
    
    # Get the nodes
    nodes_info = run_command("kubectl get nodes -o wide", capture_output=True)
    print(f"[STATUS] Cluster nodes:\n{nodes_info}")

def get_memcached_ip():
    """Get the memcached pod IP if it exists."""
    # Check if memcached pod exists
    pod_check = run_command("kubectl get pods -o wide | grep memcached", capture_output=True, check=False)
    
    if pod_check:
        pod_info_lines = pod_check.split("\n")
        pod_ip = None
        for line in pod_info_lines:
            if "memcached" in line:
                pod_ip = line.split()[5]  # IP should be in the 6th column
                break
        
        if pod_ip:
            print(f"[STATUS] Found existing memcached pod IP: {pod_ip}")
            return pod_ip
    
    print("[STATUS] No existing memcached pod found")
    return None

def deploy_memcached(node_type, thread_count, cpuset, output_dir="."):
    """
    Deploys memcached on a Kubernetes node with specified resources.
    This function checks if memcached is already deployed and returns its IP;
    otherwise it renders the memcached-p3.yaml template with the given
    node_type, thread_count, and cpuset, writes it into the specified output_dir,
    applies it, exposes the service, waits for it, and returns the pod IP.
    
    Parameters
    ----------
    node_type (str)
        The nodetype label to schedule memcached onto (e.g. "node-a-2core").
    thread_count (int)
        The number of threads memcached should use.
    cpuset (str)
        A comma-delimited list of CPU cores to pin memcached to (e.g. "0,1").
    output_dir : str, optional
        Directory where memcached-deploy.yaml will be written (default: 
        current dir).
    
    Returns
    -------
    str or None
        The IP address of the memcached pod if deployment succeeded, or None on
        failure.
    """
    # Make sure the experiment folder exists
    os.makedirs(output_dir, exist_ok=True)

    # Check if memcached is already running
    existing_ip = get_memcached_ip()
    if existing_ip:
        print(
            f"[STATUS] Memcached already up at {existing_ip}, applying update"
        )
    else:
        print("[STATUS] No existing memcached pod, creating new deployment")
    
    # Read & template out YAML
    with open("memcache/memcached-p3.yaml", "r") as f:
        y = f.read()
    y = y.replace("NODETYPE", node_type)
    y = y.replace("THREADCOUNT", str(thread_count))
    y = y.replace("CPUSET", cpuset)
    
    # Write config YAML to experiment folder
    deploy_path = os.path.join(output_dir, "memcached-deploy.yaml")
    with open(deploy_path, "w") as f:
        f.write(y)

    # Apply & expose
    run_command(f"kubectl create -f {deploy_path}")
    run_command(
        "kubectl expose pod memcached "
        "--name memcached-11211 --type LoadBalancer --port 11211 --protocol TCP"
        " --dry-run=client -o yaml | kubectl apply -f -"
    )

    # Wait, then fetch IP
    print("[STATUS] Waiting for memcached to be ready...")
    time.sleep(60)
    pod_info = run_command("kubectl get pods -o wide", capture_output=True)
    for line in pod_info.splitlines():
        if line.startswith("memcached"):
            ip = line.split()[5]
            print(f"[STATUS] Memcached pod IP: {ip}")
            return ip

    print("[ERROR] Could not find memcached IP after deploy")
    return None

def delete_all_jobs():
    """Delete all jobs in the Kubernetes cluster."""
    run_command("kubectl delete jobs --all", check=False)
    


def main():
    parser = argparse.ArgumentParser(description="Setup script for Part 3 of the CCA project")
    parser.add_argument("--state-store", default="gs://cca-eth-2025-group-092-fbaldin/", help="GCP state store for kops (gs://...)")
    parser.add_argument("--part3-yaml", default="part3.yaml", help="Path to part3.yaml file")
    parser.add_argument("--node-type", default="node-a-2core", choices=["node-a-2core", "node-b-2core", "node-c-4core", "node-d-4core"], help="Node type to run memcached on")
    parser.add_argument("--thread-count", type=int, default=2, help="Number of memcached threads")
    parser.add_argument("--cpuset", default="0", help="CPU cores to pin memcached to (e.g., '0,1')")
    parser.add_argument("--setup-cluster", action="store_true", help="Setup the Kubernetes cluster")
    parser.add_argument("--setup-mcperf", action="store_true", help="Setup mcperf on client nodes")
    parser.add_argument("--restart-mcperf", action="store_true", help="Restart mcperf agents to fix synchronization issues")
    
    args = parser.parse_args()
    
    # Setup the cluster if requested
    if args.setup_cluster:
        setup_cluster(args.state_store, args.part3_yaml)
    
    # Variable to hold memcached_ip
    memcached_ip = None
    
    # Deploy memcached
    memcached_ip = deploy_memcached(args.node_type, args.thread_count, args.cpuset)
    
    # Variable to hold clients_info
    clients_info = None
    
    # Setup mcperf if requested
    if args.setup_mcperf:
        # If we didn't set up memcached in this run, try to get the IP
        if not memcached_ip:
            memcached_ip = get_memcached_ip()
            
        # Make sure we have the memcached IP before proceeding
        if not memcached_ip:
            print("Error: Could not determine memcached IP. Make sure memcached is deployed before setting up mcperf.")
            sys.exit(1)
            
        clients_info = setup_mcperf_clients()
        if clients_info:
            start_mcperf_load(clients_info, memcached_ip)
    
    # Restart mcperf agents if requested
    if args.restart_mcperf:
        # Get client info if not already available
        if not clients_info:
            clients_info = setup_mcperf_clients()
            
        if clients_info:
            restart_mcperf_agents(clients_info)

if __name__ == "__main__":
    main()