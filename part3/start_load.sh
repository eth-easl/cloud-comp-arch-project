#!/bin/bash
cd ~/memcache-perf-dynamic
./mcperf -s 100.96.8.2 -a 10.0.16.9 -a 10.0.16.8 --noload -T 6 -C 4 -D 4 -Q 1000 -c 4 -t 10 --scan 30000:30500:5 > mcperf_results.txt
