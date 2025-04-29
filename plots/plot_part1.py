import json
import matplotlib.pyplot as plt


NUM_RUNS = 3

MARKERS = {
    "Without interference": "o",
    "Ibench-cpu inference": "s",
    "Ibench-l1d interference": "v",
    "ibench-l1i interference": ".",
    "ibench-l2 interference": "p",
    "ibench-llc interference": "P",
    "ibench-membw interference": "*"
}


def parse(data_file_path: str) -> dict:
    raw_data = None
    with open(data_file_path, "r") as f:
        raw_data = f.readlines()
    
    parsed_data = {}
    current_task = None
    for line in raw_data:
        split = line.split()
        if len(split) > 0 and split[0] == "task":
            split = split[1:]
            current_task = " ".join(split)
            parsed_data[current_task] = {"avg": []}
        if len(split) > 0 and split[0] == "read":
            target = split[-1]
            num_q = float(split[-2])
            p95 = float(split[12])
            if target not in parsed_data[current_task].keys():
                parsed_data[current_task][target] = [[p95], [num_q]]
            else:
                parsed_data[current_task][target][0].append(p95)
                parsed_data[current_task][target][1].append(num_q)
    
    for task in parsed_data:
        for target in parsed_data[task]:
            if target != "avg":
                avg_p95 = sum(parsed_data[task][target][0]) / NUM_RUNS
                avg_numq = sum(parsed_data[task][target][1]) / NUM_RUNS

                parsed_data[task]["avg"].append((avg_numq, avg_p95))

    return parsed_data


def plot(parsed_data: dict):
    plt.figure(figsize=(12, 7))
    # print(json.dumps(parsed_data, indent=2))
    
    for task in parsed_data.keys():
        print(f"run: {task}\n{parsed_data[task]}")
        plt.plot(*zip(*parsed_data[task]["avg"]), marker=MARKERS[task], label=task)

    plt.xlabel("QPS")
    plt.ylabel("p95 ")
    plt.title("memcached measured part 1\n3 runs")
    plt.legend()
    plt.grid(True)
    plt.show()
    # plt.savefig("plot_a.png")


def main():
    plot(parse("data.txt"))


if __name__ == "__main__":
    main()