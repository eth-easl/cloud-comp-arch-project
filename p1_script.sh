#!/bin/bash

# Create results directory
mkdir -p memcached_results

# List of interference types
INTERFERENCE_TYPES=("cpu" "l1d" "l1i" "l2" "llc" "membw")

# Function to run mcperf test remotely
run_mcperf_test() {
    local interference=$1
    local result_file="memcached_results/${interference}.txt"

    echo "Running mcperf for $interference..."
    echo -e "\n===== $interference TEST RUN =====\n" >> "$result_file"

    for run in {1..3}; do
        echo -e "\n>>> Run $run <<<\n" >> "$result_file"
        gcloud compute ssh --ssh-key-file ~/.ssh/cloud-computing ubuntu@client-measure-51hq --zone europe-west1-b --command "
            cd memcache-perf && ./mcperf -s 100.96.3.2 -a 10.0.16.6 --noload -T 8 -C 8 -D 4 -Q 1000 -c 8 -t 5 -w 2 --scan 5000:80000:5000
        " >> "$result_file"
    done
}

# Loop through each interference type
for interference in "${INTERFERENCE_TYPES[@]}"; do
    echo "Starting interference: $interference..."
    kubectl create -f "interference/ibench-${interference}.yaml"

    # Wait for interference pod to be ready
    while [[ $(kubectl get pods -o jsonpath="{.items[?(@.metadata.name=='ibench-${interference}')].status.phase}") != "Running" ]]; do
        sleep 5
    done

    # Run mcperf test 3 times and save all results in one file
    run_mcperf_test "$interference"

    # Stop interference after all runs are complete
    echo "Stopping interference: $interference..."
    kubectl delete pods "ibench-${interference}"
done

echo "All tests completed. Results saved in memcached_results/"
