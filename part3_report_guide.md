# Part 3 report guide

## Part 3.1 hand-crafted policy

Describe the policy implemented by `run_part3a.sh` and `part3_runner.py`.

- Memcached placement: `node-a-8core`, pinned to core 0 with one memcached thread.
- Batch resources: `node-a-8core` cores 1-7 and `node-b-4core` cores 0-3.
- Scheduling rule: launch a pending job whenever its pinned cores are free.
- Initial placement:
  - `streamcluster`: node-a cores 1-4, 4 threads
  - `canneal`: node-a cores 5-6, 2 threads
  - `radix`: node-a core 7, 1 thread
  - `freqmine`: node-b cores 0-3, 4 threads
- Follow-up jobs:
  - `vips` then `blackscholes` on node-b cores 0-3
  - `barnes` on node-a cores 5-7

Justify the choices using Part 2:

- `streamcluster`, `canneal`, and `freqmine` are the long jobs, so they start early.
- `radix` is short and fills a leftover core.
- `vips`, `blackscholes`, and `barnes` are shorter and can fill resources after the first completions.
- Memcached keeps a dedicated physical core to reduce tail-latency interference.

For each of the three runs, report:

- total makespan from `python3 get_time.py part_3_1_results_group_XXX/pods_i.json`
- max or representative mcperf p95 latency from `part_3_1_results_group_XXX/mcperf_i.txt`
- whether every reported p95 stays below 1000 us
- whether all seven PARSEC jobs completed successfully

## Part 3.2 OpenEvolve policy

Describe the OpenEvolve setup:

- Initial program: `openevolve/initial_program.py`
- Evaluator: `openevolve/evaluator.py`
- Config: `openevolve/config.yaml`
- Fitness metric: `combined_score`, which rewards lower makespan and strongly penalizes p95 latency above 1000 us.

After evolution, benchmark the selected best policy with `run_part3b.sh`.
Report the same three-run metrics as Part 3.1, using `part_3_2_results_group_XXX`.

Also state:

- output directory used for the OpenEvolve run
- checkpoint containing the selected best program
- log file corresponding to that evolution run
- any manual validation you did before using the evolved policy

## Comparison

Use a small table:

| Policy | Run | Makespan | Max p95 latency | SLO met? |
| --- | --- | ---: | ---: | :---: |
| Hand-crafted | 1 | | | |
| Hand-crafted | 2 | | | |
| Hand-crafted | 3 | | | |
| OpenEvolve | 1 | | | |
| OpenEvolve | 2 | | | |
| OpenEvolve | 3 | | | |

Then discuss:

- which policy has lower average makespan
- whether either policy violates the 1 ms p95 SLO
- whether the evolved policy found a materially different placement or thread allocation
- limitations, such as run-to-run noise, VM heterogeneity, and mcperf measurement variance
