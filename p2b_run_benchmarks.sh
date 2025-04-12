#!/bin/bash
# p2b_run_benchmarks.sh
# This script runs PARSEC workloads for part2b with different thread counts using pre-generated YAML files

# Define the workload job files (without .yaml extension)
WORKLOADS=("parsec-blackscholes" "parsec-canneal" "parsec-dedup" "parsec-ferret" "parsec-freqmine" "parsec-radix" "parsec-vips")

# Number of threads to test
THREADS=(1 2 4 8)

# Number of repetitions per measurement
REPS=3


# Create results directory if it doesn't exist
mkdir -p p2b_results

# Loop through all thread counts
for thread_count in "${THREADS[@]}"; do
    echo "==============================================="
    echo "Running benchmarks with $thread_count thread(s)"
    echo "==============================================="
    
    for workload in "${WORKLOADS[@]}"; do
        for rep in $(seq 1 $REPS); do
            echo "Running $workload with $thread_count thread(s) (rep $rep)"
            
            # Use the pre-generated YAML file
            YAML_FILE="parsec-benchmarks/part2b/${workload}_${thread_count}threads.yaml"
            
            if [ ! -f "$YAML_FILE" ]; then
                echo "Error: YAML file $YAML_FILE not found"
                continue
            fi
            
            # Launch the workload job with the modified YAML
            kubectl create -f "$YAML_FILE"
            
            # Job name is the same as the workload name
            JOB_NAME="$workload"
            
            echo "Waiting for job $JOB_NAME to complete..."
            # Wait until the job completes with longer timeout (30 minutes)
            kubectl wait --for=condition=complete job/"$JOB_NAME" --timeout=1800s
            
            # Get the pod name for the job
            POD=$(kubectl get pods | grep "$JOB_NAME" | awk '{print $1}')
            
            if [ -z "$POD" ]; then
                echo "Error: Pod for job $JOB_NAME not found"
                continue
            fi
            
            # Save logs to a file with a name that encodes the workload, thread count and repetition
            LOG_FILE="p2b_results/${workload}_${thread_count}threads_rep${rep}.log"
            echo "Saving logs to $LOG_FILE"
            kubectl logs "$POD" > "$LOG_FILE"
            
            # Clean up the job
            kubectl delete job "$JOB_NAME"
            
            # Small delay between runs
            sleep 5
        done
    done
done

echo "All experiments completed. Results are in the p2b_results directory." 