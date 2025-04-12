#!/bin/bash
# run_all_workloads.sh
# This script runs all PARSEC workloads (from parsec-benchmarks/part2a)
# first without any interference, and then under each interference (from interference/)
# for part2a. It waits for interference to be up before starting a job and ensures
# it is down before moving to the next interference.
# Each experiment is repeated 3 times, and logs are saved to the results/ folder.

# Define the interference files (without .yaml extension)
INTERFERENCES=("ibench-cpu" "ibench-l1d" "ibench-l1i" "ibench-l2" "ibench-llc" "ibench-membw")

# Define the workload job files (without .yaml extension)
WORKLOADS=("parsec-blackscholes" "parsec-canneal" "parsec-dedup" "parsec-ferret" "parsec-freqmine" "parsec-radix" "parsec-vips")

# Number of repetitions per measurement
REPS=2


########################################
# Run benchmarks with interferences
########################################
for interference in "${INTERFERENCES[@]}"; do
    echo "Starting interference: $interference"
    kubectl create -f interference/${interference}.yaml

    echo "Waiting for interference $interference to be running..."
    # Wait until a pod with the interference name shows up as Running
    while ! kubectl get pods | grep "$interference" | grep -q Running; do
        sleep 2
    done
    echo "Interference $interference is up."

    for workload in "${WORKLOADS[@]}"; do
        for rep in $(seq 1 $REPS); do
            echo "Running workload $workload with $interference (rep $rep)"
            # Launch the workload job
            kubectl create -f parsec-benchmarks/part2a/${workload}.yaml

            # Wait until the job completes (assumes job name equals workload name)
            kubectl wait --for=condition=complete job/"$workload" --timeout=600s

            # Get the pod name for the job (assumes only one pod per job)
            POD=$(kubectl get pods | grep "$workload" | awk '{print $1}')
            # Save logs to a file with a name that encodes workload, interference and repetition
            kubectl logs "$POD" > p2a_results/"${workload}_${interference}_rep${rep}.log"

            # Clean up the job
            kubectl delete job "$workload"
        done
    done

    echo "Deleting interference: $interference"
    kubectl delete pod ${interference}

    echo "Waiting for interference $interference to terminate..."
    # Wait until no pod with the interference name is present
    while kubectl get pods | grep -q "$interference"; do
        sleep 2
    done
    echo "Interference $interference terminated."
done

echo "All experiments completed."