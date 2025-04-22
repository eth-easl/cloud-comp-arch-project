import subprocess, time, json
import os
from utils import run_command

# node-a-2core : e2-highmem-2
# node-b-2core : n2-highcpu-2
# node-c-4core : c3-highcpu-4
# node-d-4core : n2-standard-4

def modify_yaml_for_scheduling(
        benchmark,
        node_type,
        threads,
        cpuset,
        workdir
    ):
    """
    Reads the PARSEC job template for `benchmark`, applies scheduling parameters,
    and writes a modified YAML into `workdir`.
    
    Parameters
    ----------
    benchmark : str
        Name of the PARSEC benchmark (e.g., "radix").
    node_type : str
        Node label to schedule the job onto (e.g., "node-a-2core").
    threads : int
        Number of threads to request.
    cpuset : str
        CPU set to pin the job to (e.g., "0-3"). Set to "" to disable CPU
        pinning.
    workdir : str
        Directory to write the modified YAML file to.
    
    Returns
    -------
    str
        Path to the modified YAML file.
    """
    template_path = os.path.join(
        "./parsec-benchmarks",
        f"parsec-{benchmark}.yaml"
    )
    with open(template_path) as f:
        content = f.read()

    # Substitute placeholders in the YAML:
    content = content.replace("NODE_TYPE", node_type)
    content = content.replace("THREAD_COUNT", f"{threads}")
    if cpuset != "":
        content = content.replace("CPUSET_PREFIX", f"taskset -c {cpuset} ")
    else:
        content = content.replace("CPUSET_PREFIX", "")

    # Write modified YAML into workdir
    os.makedirs(workdir, exist_ok=True)
    out_path = os.path.join(
        workdir,
        f"parsec-{benchmark}-{node_type}-{threads}.yaml"
    )
    with open(out_path, "w") as f:
        f.write(content)
    return out_path

def launch_jobs(configs, workdir):
    """
    Launches multiple PARSEC jobs with specified scheduling parameters.
    
    Parameters
    ----------
    configs : list of tuples
        Each tuple is (benchmark, node_type, threads, cpuset).
    workdir : str
        Directory where modified YAMLs will be written.
    
    Returns
    -------
    list of str
        List of job names launched (metadata.name from each YAML).
    """
    job_names = []

    # Prepare the launch times file
    launch_times_path = os.path.join(workdir, "launch_times.txt")
    # Overwrite any existing file
    with open(launch_times_path, "w") as _:
        pass

    for bench, node_type, thr, cpu in configs:
        yaml_path = modify_yaml_for_scheduling(
            bench,
            node_type,
            thr,
            cpu,
            workdir
        )
        run_command(f"kubectl create -f {yaml_path}", check = True)
        print(
            f"[STATUS] launch_jobs: Launched {bench} on {node_type} with " + 
            f"{thr} threads"
        )

        # Assuming each YAML defines a Job named `parsec-<benchmark>`
        job_name = f"parsec-{bench}"
        
        # Record the launch timestamp in milliseconds
        start_ms = int(time.time() * 1000)
        with open(launch_times_path, "a") as lt:
            lt.write(f"Job:  {job_name}\n")
            lt.write(f"Start time:  {start_ms}\n")
        job_names.append(job_name)
        
    return job_names

def wait_for_jobs(jobs, poll_interval=5):
    """
    Polls the Kubernetes API until all specified Jobs have completed
    successfully.
    
    This function:
    1) Periodically retrieves the list of Job objects in JSON format.
    2) Filters for the provided `jobs` whose `.status.succeeded` count is at
       least 1.
    3) Repeats the check every `poll_interval` seconds until all jobs are done.
    
    Parameters
    ----------
    jobs : list of str
        Names of the Kubernetes Job resources to wait for.
    poll_interval : int, optional
        Number of seconds to wait between successive polls (default is 5).
    
    Returns
    -------
    None
    """
    print("[STATUS] wait_for_jobs: Waiting for jobs to complete...")
    last_status_time = time.time() - 30

    while True:
        out = subprocess.check_output(["kubectl","get","jobs","-o","json"])
        data = json.loads(out)
        done = [j for j in data["items"] 
                if j["metadata"]["name"] in jobs 
                and j["status"].get("succeeded",0) >= 1]
        if len(done) == len(jobs):
            break

        # Periodically print job status every 30 seconds
        now = time.time()
        if now - last_status_time >= 30:
            print("[STATUS] wait_for_jobs: Current job status:")
            run_command("kubectl get jobs", check = False)
            last_status_time = now

        time.sleep(poll_interval)

def collect_parsec_times(output_dir):
    """
    Gathers start and completion times for all pods and parses them into a
    summary file.
    
    This function:
    1) Executes `kubectl get pods -o json` and writes the full output to
       'pods.json'.
    2) Invokes the provided `get_time.py` script to parse timing information
       from 'pods.json'.
    3) Writes the parsed timing results to the specified `output_file`.
    
    Parameters
    ----------
    output_dir : str
        Path to the directory where pods.json and the parsed timing results will
        be saved.
    
    Returns
    -------
    None
    """
    json_file = os.path.join(output_dir, "pods.json")
    output_file = os.path.join(output_dir, "parsec_times.txt")

    # Make sure the output directory exists
    os.makedirs(output_dir, exist_ok=True)

    subprocess.run(
        ["kubectl","get","pods","-o","json"],
        stdout = open(json_file, "w")
    )
    subprocess.run(
        ["python3","../get_time.py",json_file],
        stdout = open(output_file, "w")
    )
    print(
        f"[STATUS] collect_parsec_times: Collected PARSEC times into " +
        f"{output_file}"
    )

def delete_all_parsec_jobs():
    """
    Deletes all PARSEC jobs from the Kubernetes cluster.
    
    This function:
    1) Executes `kubectl delete jobs --all` to remove all parsec jobs.
    2) Executes `kubectl delete pods --all` to remove all parsec pods.
    
    Returns
    -------
    None
    """
    print(
        "[STATUS] delete_all_parsec_jobs: Deleting all PARSEC jobs and pods..."
    )
    run_command("kubectl delete jobs -l app=parsec", check = True)
    run_command("kubectl delete pods -l app=parsec", check = True)