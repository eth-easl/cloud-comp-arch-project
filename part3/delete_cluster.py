#!/usr/bin/env python3
from utils import run_command
import os

def delete_cluster(
        cluster_name = "part3.k8s.local",
        state_store = "gs://cca-eth-2025-group-092-fbaldin/"
    ):
    """ Delete all jobs, pods, and the cluster."""
    # Set the KOPS_STATE_STORE environment variable
    os.environ["KOPS_STATE_STORE"] = state_store

    # Delete all jobs and pods
    run_command("kubectl delete jobs --all")
    run_command("kubectl delete pods --all")

    # Delete the cluster
    run_command(f"kops delete cluster --name {cluster_name} --yes")

if __name__ == "__main__":
    cluster_name = "part3.k8s.local"
    delete_cluster(cluster_name)
    print(f"Deleted all jobs, pods, and the cluster: {cluster_name}")