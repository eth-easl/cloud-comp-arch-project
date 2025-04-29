import csv

from pathlib import Path

import matplotlib.pyplot as plt


DATA_PATH = Path("./data/part2/part2b-output-28-04-2025-19-16.csv")
NUM_THREADS = [1, 2, 4, 8]
MARKERS = {
    "blackscholes": "o",
    "canneal": "s",
    "dedup": "v",
    "ferret": ".",
    "freqmine": "p",
    "radix": "P",
    "vips": "*"
}


def get_data(data_path: Path) -> dict:
    reader = None
    # format:
    # { job_name: [(num_threads: time), ...] }
    data = {}
    with open(data_path) as csv_file:
        reader = csv.reader(csv_file, delimiter=',')
        for row in reader:
            num_threads = row[0]
            job_name = row[1]
            real_time = row[2]
            if job_name not in data:
                data[job_name] = [(int(num_threads), float(real_time))]
            else: # normalized time (Time_1 / Time_n)
                data[job_name].append((int(num_threads), float(data[job_name][0][1]) / float(real_time)))
    
    for job_name in data.keys():
        data[job_name][0] = (1, 1.0)

    return data


def plot(parsed_data: dict):
    plt.figure(figsize=(12, 7))

    for job_name in parsed_data.keys():
        plt.plot(*zip(*parsed_data[job_name]), marker=MARKERS[job_name], label=job_name, linestyle="-")

    plt.xlabel("number of threads")
    plt.ylabel("normalized time")
    plt.title("speedup vs number of threads")
    plt.legend()
    plt.grid(True)
    plt.show()


def main():
    data = get_data(DATA_PATH)
    plot(data)


if __name__ == "__main__":
    main()