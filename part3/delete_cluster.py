#!/usr/bin/env python3
from utils import run_command
import subprocess

def delete_cluster(cluster_name):
    """ Delete all jobs, pods, and the cluster."""
    run_command("kubectl delete jobs --all")
    run_command("kubectl delete pods --all")
    run_command(f"kops delete cluster --name {cluster_name} --yes")

if __name__ == "__main__":
    cluster_name = "part3.k8s.local"
    delete_cluster(cluster_name)
    print(f"Deleted all jobs, pods, and the cluster: {cluster_name}")