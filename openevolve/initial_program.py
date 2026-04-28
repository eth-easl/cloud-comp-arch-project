def get_schedule():
    """
    Return a complete Part 3 scheduling policy.

    Each item describes one PARSEC batch job:
    - name: benchmark name without the parsec- prefix
    - yaml: source YAML file from parsec-benchmarks/part2b
    - node: node-a-8core or node-b-4core
    - cores: CPU cores used by taskset inside the container
    - threads: PARSEC -n value; must not exceed len(cores)
    """
    # EVOLVE-BLOCK-START
    return [
        {"name": "streamcluster", "yaml": "parsec-streamcluster.yaml", "node": "node-a-8core", "cores": [1, 2, 3, 4], "threads": 4},
        {"name": "canneal", "yaml": "parsec-canneal.yaml", "node": "node-a-8core", "cores": [5, 6], "threads": 2},
        {"name": "radix", "yaml": "parsec-radix.yaml", "node": "node-a-8core", "cores": [7], "threads": 1},
        {"name": "freqmine", "yaml": "parsec-freqmine.yaml", "node": "node-b-4core", "cores": [0, 1, 2, 3], "threads": 4},
        {"name": "vips", "yaml": "parsec-vips.yaml", "node": "node-b-4core", "cores": [0, 1, 2, 3], "threads": 4},
        {"name": "blackscholes", "yaml": "parsec-blackscholes.yaml", "node": "node-b-4core", "cores": [0, 1, 2, 3], "threads": 4},
        {"name": "barnes", "yaml": "parsec-barnes.yaml", "node": "node-a-8core", "cores": [5, 6, 7], "threads": 3},
    ]
    # EVOLVE-BLOCK-END
