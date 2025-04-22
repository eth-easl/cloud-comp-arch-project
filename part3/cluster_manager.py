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
    print(f"[STATUS] setup_cluster: Set KOPS_STATE_STORE to {state_store}")
    
    # Get the project name
    project = run_command("gcloud config get-value project", capture_output=True)
    print(f"[STATUS] setup_cluster: Project name: {project}")
    
    # Create the cluster
    run_command(f"kops create -f {cluster_config_yaml}")
    
    # Update the cluster
    run_command("kops update cluster --name part3.k8s.local --yes --admin")
    
    # Validate the cluster (wait up to 10 minutes)
    run_command("kops validate cluster --wait 10m")
    
    # Get the nodes
    nodes_info = run_command("kubectl get nodes -o wide", capture_output=True)
    print(f"[STATUS] setup_cluster: Cluster nodes:\n{nodes_info}")

def get_memcached_ip():
    """Get the memcached pod IP if it exists."""
    # Check if memcached pod exists
    pod_check = run_command(
        "kubectl get pods -o wide | grep memcached",
        capture_output=True,
        check=False
    )
    
    if pod_check:
        pod_info_lines = pod_check.split("\n")
        pod_ip = None
        for line in pod_info_lines:
            if "memcached" in line:
                pod_ip = line.split()[5]  # IP should be in the 6th column
                break
        
        if pod_ip:
            print(
                f"[STATUS] get_memcached_ip: Found existing memcached pod " + 
                f"IP: {pod_ip}"
            )
            return pod_ip
    
    print("[ERROR] get_memcached_ip: No existing memcached pod found")
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
            f"[STATUS] deploy_memcached: Memcached already up at " +
            f"{existing_ip}, applying update"
        )
    else:
        print(
            f"[STATUS] deploy_memcached: No existing memcached pod, creating " +
            f"new deployment"
        )
    
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
    run_command(f"kubectl apply -f {deploy_path}")
    run_command(
        "kubectl expose pod memcached "
        "--name memcached-11211 --type LoadBalancer --port 11211 --protocol TCP"
        " --dry-run=client -o yaml | kubectl apply -f -"
    )

    # Wait for the memcached pod to report Ready
    print("[STATUS] deploy_memcached: Waiting for memcached to be ready...")
    run_command(
        "kubectl wait --for=condition=Ready pod/memcached --timeout=120s",
        check=True
    )
    pod_info = run_command("kubectl get pods -o wide", capture_output=True)
    for line in pod_info.splitlines():
        if line.startswith("memcached"):
            ip = line.split()[5]
            print(f"[STATUS] deploy_memcached: Memcached pod IP: {ip}")
            return ip

    print("[ERROR] deploy_memcached: Could not find memcached IP after deploy")
    return None

def delete_all_jobs():
    """Delete all jobs in the Kubernetes cluster."""
    run_command("kubectl delete jobs --all", check=False)
    print("[STATUS] delete_all_jobs: Deleted all jobs in the cluster")