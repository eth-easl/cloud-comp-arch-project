from utils import run_command
import subprocess, os
from datetime import datetime
import json
import time

def setup_mcperf_agents(force_install = False):
    """
    Discovers client-agent-a, client-agent-b, and client-measure nodes, sets up
    and builds mcperf on each. If mcperf is already installed, it skips
    installation.
    
    This function:
    1) Uses `kubectl get nodes -o json` to find nodes named client-agent-a,
       client-agent-b, and client-measure.
    2) SSHes into each to check if mcperf is already installed and executable.
       If not, it installs dependencies and builds memcache-perf-dynamic.
    3) Returns a dict with keys 'client_agent_a', 'client_agent_b', and
       'client_measure', each mapping to a dict containing 'name',
       'internal_ip', and 'external_ip'.

    Parameters
    ----------
    force_install : bool, optional
        If True, forces reinstallation of mcperf even if it is already
        installed. Default is False.
    
    Returns
    -------
    dict or None
        clients_info mapping node roles to their connection info, or None if
        discovery/setup failed.
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
        print(
            "[ERROR] setup_mcperf_agents: Could not find all required client " +
            "nodes"
        )
        return None
    
    print(f"[STATUS] setup_mcperf_agents: Client Agent A: {client_agent_a}")
    print(f"[STATUS] setup_mcperf_agents: Client Agent B: {client_agent_b}")
    print(f"[STATUS] setup_mcperf_agents: Client Measure: {client_measure}")

    clients_info = {
        "client_agent_a": client_agent_a,
        "client_agent_b": client_agent_b,
        "client_measure": client_measure
    }
    
    # Setup mcperf on each node, skipping if already installed
    setup_commands = [
        "sudo sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources",
        "sudo apt-get update",
        "sudo apt-get install libevent-dev libzmq3-dev git make g++ --yes",
        "sudo apt-get build-dep memcached --yes",
        "cd && git clone https://github.com/eth-easl/memcache-perf-dynamic.git",
        "cd ~/memcache-perf-dynamic && make"
    ]
    
    ssh_key_path = os.path.expanduser("~/.ssh/cloud-computing")
    
    for node_key in ["client_agent_a", "client_agent_b", "client_measure"]:
        node = clients_info[node_key]

        # Check if mcperf is already installed
        if not force_install:
            check_cmd = (
                f"gcloud compute ssh --ssh-key-file {ssh_key_path} "
                f"ubuntu@{node['name']} --zone europe-west1-b --command "
                f"\"test -x ~/memcache-perf-dynamic/mcperf && echo INSTALLED || echo MISSING\""
            )
            result = run_command(check_cmd, capture_output=True).strip()
            if result == "INSTALLED":
                print(
                    f"[STATUS] setup_mcperf_agents: mcperf already installed " +
                    f"on {node['name']}, skipping setup"
                )
                continue

        # Otherwise run setup commands
        print(
            f"[STATUS] setup_mcperf_agents: setting up mcperf on " +
            f"{node['name']}"
        )
        for cmd in setup_commands:
            ssh_cmd = (
                f"gcloud compute ssh --ssh-key-file {ssh_key_path} "
                f"ubuntu@{node['name']} --zone europe-west1-b --command "
                f"\"{cmd}\""
            )
            # Don't check as some commands might fail but still be ok
            run_command(ssh_cmd, check=False)

    # Verification: ensure mcperf was built correctly
    for node_key in ["client_agent_a", "client_agent_b", "client_measure"]:
        node = clients_info[node_key]
        verify_cmd = (
            f"gcloud compute ssh --ssh-key-file {ssh_key_path} "
            f"ubuntu@{node['name']} --zone europe-west1-b --command "
            f"\"test -x ~/memcache-perf-dynamic/mcperf && echo INSTALLED || echo MISSING\""
        )
        output = run_command(verify_cmd, capture_output=True).strip()
        if output != "INSTALLED":
            print(
                f"[ERROR] setup_mcperf_agents: mcperf installation failed on " + 
                f"{node['name']}"
            )
            return None
        else:
            print(
                f"[STATUS] setup_mcperf_agents: mcperf verified on " +
                f"{node['name']}"
            )

    return clients_info

def start_load_agents(clients_info):
    """
    Starts mcperf load-generating agents on client-agent-a and client-agent-b.

    Parameters
    ----------
    clients_info : dict
        Contains 'client_agent_a' and 'client_agent_b' entries, each with
        'name'.

    Returns
    -------
    None
    """
    ssh_key_path = os.path.expanduser("~/.ssh/cloud-computing")
    for agent_key, threads in [("client_agent_a", 2), ("client_agent_b", 4)]:
        node = clients_info[agent_key]
        cmd = (
            f"gcloud compute ssh --ssh-key-file {ssh_key_path} ubuntu@{node['name']} "
            f"--zone europe-west1-b --command \"nohup sh -c 'cd ~/memcache-perf-dynamic && "
            f"./mcperf -T {threads} -A' > /dev/null 2>&1 &\""
        )
        run_command(cmd, check=False)
        print(
            f"[STATUS] start_load_agents: started mcperf agent on {agent_key}" +
            f" with {threads} threads"
        )

def restart_mcperf_agents(clients_info):
    """
    Restarts mcperf agent processes across all client VMs and kills mcperf
    measure process.

    This function:
    1) Validates that a non-empty clients_info dict is provided.
    2) Terminates any lingering mcperf processes on client-agent-a,
       client-agent-b, and client-measure via `pkill -f mcperf`.
    3) Waits briefly for processes to exit.
    4) Relaunches client_agent_a and client_agent_b
    5) Prints a consolidated status message.
    
    Parameters
    ----------
    clients_info : dict
        A dict containing keys 'client_agent_a', 'client_agent_b', and
        'client_measure', each mapping to a dict with at least 'name' indicating
        the VM hostname.
    
    Returns
    -------
    None
    """
    if not clients_info:
        print(
            "[ERROR] restart_mcperf_agents: No client_info dictionary provided"
        )
        return
         
    # Kill existing mcperf processes
    stop_mcperf_agents()
    
    # Poll until no mcperf processes remain on any client node
    print(
        f"[STATUS] restart_mcperf_agents: Killed existing mcperf processes, " +
        f"waiting for cleanup..."
    )
    ssh_key_path = os.path.expanduser("~/.ssh/cloud-computing")
    for node_key in ['client_agent_a', 'client_agent_b', 'client_measure']:
        node = clients_info[node_key]
        while True:
            check_cmd = (
                f"gcloud compute ssh --quiet --ssh-key-file {ssh_key_path} "
                f"ubuntu@{node['name']} --zone europe-west1-b "
                f"--command \"pgrep mcperf || true\""
            )
            output = run_command(check_cmd, capture_output=True).strip()
            if not output:
                break
            time.sleep(1)
    print(
        "[STATUS] restart_mcperf_agents: all previous mcperf processes exited"
    )

    # Restart mcperf agents
    start_load_agents(clients_info)

    print("[STATUS] restart_mcperf_agents: load agents restarted")

def stop_mcperf_agents():
    """
    Stops mcperf agent processes on all client nodes via Kubernetes.

    This function:
    1) Applies the 'kill-mcperf-job.yaml' DaemonSet, which runs a hostPID
       pod on each mcperf-client node to invoke `pkill -f mcperf`.
    2) Waits briefly for the pods to execute (5 seconds).
    3) Deletes the DaemonSet and its pods to clean up.

    Returns
    -------
    None
    """
    # Apply the Kubernetes DaemonSet that kills the mcperf processes
    print("[STATUS] stop_mcperf_agents: applying kill_mcperf_daemonset.yaml")
    run_command("kubectl apply -f kill_mcperf_daemonset.yaml", check=False)

    # Give the DaemonSet pods time to run the kill command
    time.sleep(5)

    # Tear down the DaemonSet and its pods
    print(
        "[STATUS] stop_mcperf_agents: deleting kill-mcperf DaemonSet and pods"
    )
    run_command("kubectl delete daemonset kill-mcperf", check=False)

def preload(clients_info, memcached_ip):
    """
    Preloads the memcached cache on the client-measure node.
 
    This function:
    1) Validates that a memcached IP is provided.
    2) SSHes into the client-measure node to run the mcperf `--loadonly` command,
       populating the memcached cache with key/value pairs.
 
    Parameters
    ----------
    clients_info : dict
        Must contain key 'client_measure' mapping to a dict with at least 'name'.
    memcached_ip : str
        The IP address of the memcached server to target.
 
    Returns
    -------
    None
    """
    if not memcached_ip:
        print("[ERROR] preload: No memcached IP provided")
        return

    ssh_key = os.path.expanduser("~/.ssh/cloud-computing")

    # Preload memcached database
    measure_node = clients_info["client_measure"]
    load_only = f"cd ~/memcache-perf-dynamic && ./mcperf -s {memcached_ip} --loadonly"
    cmd = (
        f"gcloud compute ssh --ssh-key-file {ssh_key} ubuntu@{measure_node['name']} "
        f"--zone europe-west1-b --command \"{load_only}\""
    )
    run_command(cmd, check=False)
    print("[STATUS] preload: memcached preload completed")

def run_mcperf_load(
        clients_info,
        memcached_ip,
        output_dir,
        scan = "30000:30500:5",
        duration = 10
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
        print("[ERROR] run_mcperf_load: No memcached IP provided")
        return None

    ssh_key = os.path.expanduser("~/.ssh/cloud-computing")

    # Setup
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

    # Execute remote load in background via nohup, logging to remote file
    remote_results = "~/mcperf_results_remote.txt"
    ssh_run = (
        f"gcloud compute ssh --ssh-key-file {ssh_key} ubuntu@{measure['name']} "
        f"--zone europe-west1-b --command "
        f"\"nohup ~/{remote_script} > {remote_results} 2>&1 &\""
    )
    run_command(ssh_run, check=False)
    print(
        f"[STATUS] run_mcperf_load: detached mcperf load on {measure['name']}"
    )

    # Tail remote results locally in background
    results_file = os.path.join(output_dir, "mcperf_results_local.txt")
    tail_cmd = (
        f"gcloud compute ssh --quiet --ssh-key-file {ssh_key} " +
        f"ubuntu@{measure['name']} --zone europe-west1-b --command \"tail -F "
        f"{remote_results}\" > {results_file} 2>/dev/null &"
    )
    run_command(tail_cmd, check=False)
    print(f"[STATUS] run_mcperf_load: tailing remote results to {results_file}")

    print(
        f"[STATUS] run_mcperf_load: mcperf load running, output saving to " + 
        f"{results_file}"
    )

    return results_file
