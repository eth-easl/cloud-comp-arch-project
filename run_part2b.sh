#!/bin/bash

set -e

BASE_DIR=$(pwd)
LOG_DIR="$BASE_DIR/logs_part2b"
mkdir -p "$LOG_DIR"

benchmarks=(
  parsec-barnes.yaml
  parsec-blackscholes.yaml
  parsec-canneal.yaml
  parsec-freqmine.yaml
  parsec-radix.yaml
  parsec-streamcluster.yaml
  parsec-vips.yaml
)

threads=(1 2 4 8)

for b in "${benchmarks[@]}"; do

  echo "=============================="
  echo "Benchmark: $b"
  echo "=============================="

  for t in "${threads[@]}"; do

    echo "---- Running $b with $t threads ----"

    kubectl delete jobs --all --ignore-not-found
    kubectl delete pods --all --ignore-not-found

    sleep 10

    sed -E "s#-n[[:space:]]+[0-9]+#-n $t#g" \
      "parsec-benchmarks/part2b/$b" > /tmp/tmp.yaml

    kubectl apply -f /tmp/tmp.yaml

    sleep 5

    JOB=$(kubectl get jobs \
      --sort-by=.metadata.creationTimestamp \
      -o jsonpath='{.items[-1].metadata.name}')

    echo "Job selected: $JOB"

    kubectl wait --for=condition=complete job/$JOB --timeout=2h

    POD=$(kubectl get pods \
      --selector=job-name=$JOB \
      --sort-by=.metadata.creationTimestamp \
      -o jsonpath='{.items[-1].metadata.name}')

    echo "Pod: $POD"

    kubectl logs "$POD" > "$LOG_DIR/${b%.yaml}_t${t}.log"

    echo "Saved: $LOG_DIR/${b%.yaml}_t${t}.log"

    kubectl delete jobs --all --ignore-not-found
    kubectl delete pods --all --ignore-not-found

    sleep 5

  done

done

echo "ALL DONE"