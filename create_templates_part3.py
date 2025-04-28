import os

jobs = ["blackscholes", "canneal", "dedup", "ferret", "freqmine", "radix", "vips"] 

for job in jobs:
    jobname = f"parsec-{job}"

    script_dir = os.path.dirname(__file__)
    rel_path = f"parsec-benchmarks/part3/{jobname}.yaml"
    abs_file_path = os.path.join(script_dir, rel_path)

    with open(abs_file_path) as f:
        schemas = f.read()

    schemas = schemas.replace("-n 8", "-n <n>")
    schemas = schemas.replace("\"parsec\"", "<node_label>")

    script_dir = os.path.dirname(__file__)
    rel_path = f"parsec-benchmarks/part3/{jobname}-template.yaml"
    abs_file_path = os.path.join(script_dir, rel_path)

    with open(abs_file_path, "w") as f:
        f.write(schemas)