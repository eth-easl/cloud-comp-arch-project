#!/bin/bash
# p2b_generate_yamls.sh
# This script generates modified YAML files for PARSEC workloads with different thread counts

# Define the workload job files (without .yaml extension)
WORKLOADS=("parsec-blackscholes" "parsec-canneal" "parsec-dedup" "parsec-ferret" "parsec-freqmine" "parsec-radix" "parsec-vips")

# Number of threads to test
THREADS=(1 2 4 8)

# Create directories for temp yaml files and results
mkdir -p temp_yamls
mkdir -p p2b_results

echo "Generating YAML files with modified thread counts..."

for thread_count in "${THREADS[@]}"; do
    echo "Creating YAMLs for $thread_count thread(s)"
    
    for workload in "${WORKLOADS[@]}"; do
        # Create a temporary YAML file with the modified thread count
        TEMP_YAML="temp_yamls/${workload}_${thread_count}threads.yaml"
        
        # Copy the original YAML and update the thread count
        cp parsec-benchmarks/part2b/${workload}.yaml "$TEMP_YAML"
        
        # Update the thread count (-n parameter) in the command
        # The pattern looks for -n followed by a number and replaces just that number
        sed -i "s/-n [0-9]*/-n $thread_count/" "$TEMP_YAML"
        
        echo "Created $TEMP_YAML"
    done
done

echo "All YAML files generated in the temp_yamls directory."
echo "You can now review them and run the p2b_run_benchmarks.sh script when ready." 