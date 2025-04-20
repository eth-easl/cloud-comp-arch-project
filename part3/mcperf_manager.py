from utils import run_command
import subprocess, os
from datetime import datetime
import json
import time

def start_mcperf_agents():
    """
    Discovers the client-agent-a, client-agent-b, and client-measure nodes in the
    Kubernetes cluster and installs & builds the dynamic mcperf client on each.
    
    This function:
    1) Uses `kubectl get nodes -o json` to locate nodes whose names contain
       "client-agent-a", "client-agent-b", and "client-measure".
    2) SSHes into each matching node via `gcloud compute ssh` and runs a series
       of setup commands (adding deb-src, installing dependencies, cloning
       the memcache-perf-dynamic repository, and running `make`).
    3) Returns a dictionary with keys "client_agent_a", "client_agent_b",
       and "client_measure", each mapping to a dict containing "name",
       "internal_ip", and "external_ip".
    
    Returns
    -------
    client_info : dict or None
        A dict of node information if all three clients were found and set up,
        or None if any required node could not be located.
    """
    # Get node information
    nodes_output = run_command("kubectl get nodes -o json", capture_output=True)
    nodes_data = json.loads(nodes_output)
    
    client_agent_a = None
    client_agent_b = None
    client_measure = None
    
    # Find the client nodes
    for node in nodes_data["items"]:
        node_name = node["metadata"]["name"]
        if "client-agent-a" in node_name:
            client_agent_a = {
                "name": node_name,
                "internal_ip": node["status"]["addresses"][0]["address"],
                "external_ip": node["status"]["addresses"][1]["address"]
            }
        elif "client-agent-b" in node_name:
            client_agent_b = {
                "name": node_name,
                "internal_ip": node["status"]["addresses"][0]["address"],
                "external_ip": node["status"]["addresses"][1]["address"]
            }
        elif "client-measure" in node_name:
            client_measure = {
                "name": node_name,
                "internal_ip": node["status"]["addresses"][0]["address"],
                "external_ip": node["status"]["addresses"][1]["address"]
            }
    
    if not (client_agent_a and client_agent_b and client_measure):
        print("[ERROR] Could not find all required client nodes")
        return None
    
    print(f"[INFO] Client Agent A: {client_agent_a}")
    print(f"[INFO] Client Agent B: {client_agent_b}")
    print(f"[INFO] Client Measure: {client_measure}")
    
    # Setup mcperf on each node
    setup_commands = [
        "sudo sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources",
        "sudo apt-get update",
        "sudo apt-get install libevent-dev libzmq3-dev git make g++ --yes",
        "sudo apt-get build-dep memcached --yes",
        "cd && git clone https://github.com/eth-easl/memcache-perf-dynamic.git",
        "cd ~/memcache-perf-dynamic && make"
    ]
    
    ssh_key_path = os.path.expanduser("~/.ssh/cloud-computing")
    
    for node in [client_agent_a, client_agent_b, client_measure]:
        for cmd in setup_commands:
            ssh_cmd = (
                f"gcloud compute ssh --ssh-key-file {ssh_key_path} " +
                f"ubuntu@{node['name']} --zone europe-west1-b --command " + 
                f"\"{cmd}\""
            )
            run_command(ssh_cmd, check=False)  # Don't check as some commands might fail but still be ok
    
    return {
        "client_agent_a": client_agent_a,
        "client_agent_b": client_agent_b,
        "client_measure": client_measure
    }

def restart_mcperf_agents(clients_info):
    """
    Restarts mcperf agent processes across all client VMs to resolve stale or
    mis-synchronized agents.
    
    This function performs the following steps:
    1) Validates that a non-empty clients_info dict is provided.
    2) Issues a remote kill command (`pkill -f mcperf`) on client-agent-a,
       client-agent-b, and client-measure nodes to terminate any lingering
       mcperf processes.
    3) Waits briefly for processes to exit and resources to free up.
    4) SSHes into client-agent-a and relaunches the mcperf agent with 2 threads.
    5) SSHes into client-agent-b and relaunches the mcperf agent with 4 threads.
    6) Prints status messages to indicate progress.
    
    Parameters
    ----------
    clients_info : dict
        A dict containing keys 'client_agent_a', 'client_agent_b', and
        'client_measure', each mapping to a dict with at least a 'name' field
        indicating the VM hostname.
    
    Returns
    -------
    None
    """
    if not clients_info:
        print("[ERROR] No client_info dictionary provided")
        return
         
    ssh_key_path = os.path.expanduser("~/.ssh/cloud-computing")
    
    # Kill any running mcperf processes
    kill_cmd = "pkill -f mcperf || true"
    
    # Restart agents on both client-agent nodes
    for agent_key in ['client_agent_a', 'client_agent_b']:
        # Kill any existing mcperf processes
        ssh_cmd = f"gcloud compute ssh --ssh-key-file {ssh_key_path} ubuntu@{clients_info[agent_key]['name']} --zone europe-west1-b --command \"{kill_cmd}\""
        run_command(ssh_cmd, check=False)
        
    # Also kill on measure node to be safe
    ssh_cmd = f"gcloud compute ssh --ssh-key-file {ssh_key_path} ubuntu@{clients_info['client_measure']['name']} --zone europe-west1-b --command \"{kill_cmd}\""
    run_command(ssh_cmd, check=False)
    
    print("[STAUTS] Killed existing mcperf processes, waiting for cleanup...")
    time.sleep(5)
    
    # Restart the mcperf agent on client-agent-a
    agent_a_cmd = f"cd ~/memcache-perf-dynamic && ./mcperf -T 2 -A"
    ssh_cmd = f"gcloud compute ssh --ssh-key-file {ssh_key_path} ubuntu@{clients_info['client_agent_a']['name']} --zone europe-west1-b --command \"{agent_a_cmd}\" &"
    run_command(ssh_cmd, check=False)
    
    # Restart the mcperf agent on client-agent-b
    agent_b_cmd = f"cd ~/memcache-perf-dynamic && ./mcperf -T 4 -A"
    ssh_cmd = f"gcloud compute ssh --ssh-key-file {ssh_key_path} ubuntu@{clients_info['client_agent_b']['name']} --zone europe-west1-b --command \"{agent_b_cmd}\" &"
    run_command(ssh_cmd, check=False)
    
    print("[STATUS] Restarted mcperf agents")

def preload(clients_info, memcached_ip):
    """
    Preloads the memcached database and launches mcperf agents.

    This function:
    1) Validates that a memcached IP is provided.
    2) SSHes into client-agent-a and client-agent-b to start mcperf in agent
       mode.
    3) SSHes into client-measure to run the mcperf load-only command to populate
       the cache.

    Parameters
    ----------
    clients_info : dict
        Must contain keys 'client_agent_a', 'client_agent_b', 'client_measure',
        each mapping to a dict with at least 'name' and 'internal_ip'.
    memcached_ip : str
        The IP address of the memcached server to target.

    Returns
    -------
    None
    """
    if not memcached_ip:
        print("[ERROR] No memcached IP provided")
        return

    ssh_key = os.path.expanduser("~/.ssh/cloud-computing")

    # Start mcperf agents
    for agent_key, threads in [("client_agent_a", 2), ("client_agent_b", 4)]:
        node = clients_info[agent_key]
        cmd = (
            f"gcloud compute ssh --ssh-key-file {ssh_key} ubuntu@{node['name']} "
            f"--zone europe-west1-b --command \"cd ~/memcache-perf-dynamic && "
            f"./mcperf -T {threads} -A &\""
        )
        run_command(cmd, check=False)
        print(
            f"[STATUS] Preload: started agent on {agent_key} with {threads}" + 
            f" threads"
        )

    # Preload memcached database
    measure_node = clients_info["client_measure"]
    load_only = f"cd ~/memcache-perf-dynamic && ./mcperf -s {memcached_ip} --loadonly"
    cmd = (
        f"gcloud compute ssh --ssh-key-file {ssh_key} ubuntu@{measure_node['name']} "
        f"--zone europe-west1-b --command \"{load_only}\""
    )
    run_command(cmd, check=False)
    print("[STATUS] Preload: completed load-only on client-measure")

def run_mcperf_load(
        clients_info,
        memcached_ip,
        output_dir,
        scan = "30000:30500:5",
        duration=10
    ):
    """
    Generates and runs the mcperf load test, saving results locally.

    This function:
    1) Creates an experiment directory if needed.
    2) Writes a remote start_load.sh script with the desired mcperf command.
    3) Copies the script to client-measure and makes it executable.
    4) SSHes into client-measure to run the script, redirecting stdout to a file
       under output_dir.

    Parameters
    ----------
    clients_info : dict
        Contains 'client_agent_a', 'client_agent_b', 'client_measure' with dicts
        holding 'name' and 'internal_ip'.
    memcached_ip : str
        The IP address of the memcached server.
    output_dir : str
        Local directory path where results and the script are stored.
    scan : str, optional
        mcperf --scan range, default "30000:30500:5".
    duration : int, optional
        mcperf -t duration in seconds, default 10.

    Returns
    -------
    str or None
        Path to the local results file, or None on failure.
    """
    if not memcached_ip:
        print("[ERROR] No memcached IP provided")
        return None

    os.makedirs(output_dir, exist_ok=True)
    ssh_key = os.path.expanduser("~/.ssh/cloud-computing")
    agent_a_ip = clients_info["client_agent_a"]["internal_ip"]
    agent_b_ip = clients_info["client_agent_b"]["internal_ip"]
    measure = clients_info["client_measure"]
    remote_script = "start_load.sh"

    # Build start_load.sh locally
    script_path = os.path.join(output_dir, remote_script)
    script_contents = f"""#!/bin/bash
        cd ~/memcache-perf-dynamic
        ./mcperf -s {memcached_ip} -a {agent_a_ip} -a {agent_b_ip} --noload \
        -T 6 -C 4 -D 4 -Q 1000 -c 4 -t {duration} --scan {scan}
    """
    with open(script_path, "w") as f:
        f.write(script_contents)

    # Copy and prepare on client-measure
    scp = (
        f"gcloud compute scp --ssh-key-file {ssh_key} {script_path} "
        f"ubuntu@{measure['name']}:~ --zone europe-west1-b"
    )
    run_command(scp, check=False)
    chmod = (
        f"gcloud compute ssh --ssh-key-file {ssh_key} ubuntu@{measure['name']} "
        f"--zone europe-west1-b --command \"chmod +x ~/{remote_script}\""
    )
    run_command(chmod, check=False)

    # Execute remote load and capture locally
    results_file = os.path.join(output_dir, "mcperf_results_local.txt")
    ssh_run = (
        f"gcloud compute ssh --ssh-key-file {ssh_key} ubuntu@{measure['name']} "
        f"--zone europe-west1-b --command \"~/{remote_script}\""
        f" > {results_file}"
    )
    run_command(ssh_run)

    print(f"[STATUS] mcperf load running, output saved to {results_file}")
    return results_file
