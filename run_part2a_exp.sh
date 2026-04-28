#!/bin/bash

set -e  # 出错直接停止（避免污染实验）

BASE_DIR=$(pwd)

LOG_DIR="$BASE_DIR/logs_part2a"
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

for b in "${benchmarks[@]}"; do

  echo "====================================="
  echo "Running benchmark: $b"
  echo "====================================="

  # 1. 清理旧任务（非常重要）
  kubectl delete jobs --all --ignore-not-found
  kubectl delete pods --all --ignore-not-found

  sleep 5

  # 2. 启动 interference
  kubectl apply -f "$BASE_DIR/interference/ibench-cpu.yaml"

  sleep 10  # 等 interference 稳定

  # 3. 启动 PARSEC benchmark
  kubectl apply -f "$BASE_DIR/parsec-benchmarks/part2a/$b"

  # 4. 等 job 完成
  JOB_NAME=$(kubectl get jobs -o jsonpath='{.items[0].metadata.name}')

  echo "Waiting for job: $JOB_NAME"

  kubectl wait --for=condition=complete job/$JOB_NAME --timeout=2h

  # 5. 抓 logs
  POD_NAME=$(kubectl get pods --selector=job-name=$JOB_NAME \
    -o jsonpath='{.items[0].metadata.name}')

  kubectl logs "$POD_NAME" > "$LOG_DIR/${b%.yaml}.log"

  echo "Saved log: $LOG_DIR/${b%.yaml}.log"

  # 6. 清理（确保下一轮干净）
  kubectl delete jobs --all --ignore-not-found
  kubectl delete pods --all --ignore-not-found

  sleep 5

done

echo "All benchmarks finished."