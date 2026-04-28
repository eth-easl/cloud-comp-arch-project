#!/usr/bin/env bash
set -euo pipefail

GROUP="${GROUP:-XXX}"
RUNS="${RUNS:-3}"

if [[ "$GROUP" == "XXX" ]]; then
  echo "Set your three-digit group number first, for example: GROUP=001 $0" >&2
  exit 1
fi

python3 part3_runner.py --task 1 --group "$GROUP" --runs "$RUNS"
