import os
import subprocess

env = os.environ.copy()

env["PROJECT"] = "cca-eth-2025-group-008"
env["KOPS_STATE_STORE"] = "gs://cca-eth-2025-group-008-dbociat"


if __name__ == '__main__':
    # Init steps

    subprocess.run(["gcloud", "auth", "application-default", "login"], check=True)
    subprocess.run(["gcloud", "init"], check=True)
    subprocess.run(["kops", "create", "-f", "part2a.yaml"], env=env, check=True)
    subprocess.run(["kops", "update", "cluster", "part2a.k8s.local", "--yes", "--admin"], env=env, check=True)
    subprocess.run(["kops", "validate", "cluster", "--wait", "10m"],  env=env, check=True)
    subprocess.run(["kubectl", "get", "nodes", "-o", "wide"], env=env, check=True)

    output = subprocess.check_output(["kubectl", "get", "nodes", "-o", "wide"], env=env, text=True)
    lines = output.strip().split("\n")
    for line in lines[1:]:
        if "parsec-server" in line:
            parsec_node_name = line.split()[0]
            break

    subprocess.run(["kubectl", "label", "nodes", parsec_node_name, "cca-project-nodetype=parsec"], env=env, check=True)
