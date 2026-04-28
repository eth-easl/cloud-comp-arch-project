#!/usr/bin/env bash
set -euo pipefail

GROUP="${GROUP:-XXX}"
RUNS="${RUNS:-3}"
POLICY_FILE="${1:-openevolve/best_program.py}"

if [[ "$GROUP" == "XXX" ]]; then
  echo "Set your three-digit group number first, for example: GROUP=001 $0 openevolve/best_program.py" >&2
  exit 1
fi

python3 part3_runner.py --task 2 --group "$GROUP" --runs "$RUNS" --policy-file "$POLICY_FILE"
