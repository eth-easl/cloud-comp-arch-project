import argparse
import shutil
from pathlib import Path

SUBMISSION_DIR_NAME = "part_3_openevolve"


def get_logs_dir(output_dir: Path) -> Path:
    return output_dir / "logs"


def ask_correct_log_file(log_files: list[Path]) -> Path:
    for i, log_file in enumerate(log_files):
        print(f"[{i}] {log_file}")
    while True:
        try:
            choice = int(input("Enter the number of the correct log file: "))
            if 0 <= choice < len(log_files):
                print()
                return log_files[choice]
            else:
                print("Invalid choice.")
        except ValueError:
            print("Invalid input. Please enter a number.")


def find_last_checkpoint_dir(log_file: Path) -> Path:
    checkpoint_str = None
    with log_file.open() as f:
        for line in f:
            if "Saved checkpoint at iteration" in line:
                try:
                    checkpoint_str = (
                        line.split("Saved checkpoint at iteration")[1]
                        .split("to")[1]
                        .strip()
                    )
                except IndexError:
                    continue

    if checkpoint_str is None:
        raise ValueError(
            f'No checkpoint directory found in {log_file}. Did you remove "checkpoint_interval" from the config file?'
        )

    return Path(checkpoint_str)


def can_overwrite(path: Path) -> bool:
    if not path.exists():
        return True
    choice = input(
        f"Warning: {path} already exists. Do you want to overwrite it? [y/N] "
    ).lower()
    return choice == "y"


def collect_results(submission_dir: Path, log_file: Path, checkpoint_dir: Path):
    openevolve_submission_dir = submission_dir / SUBMISSION_DIR_NAME
    openevolve_submission_dir.mkdir(exist_ok=True)

    dest_log_path = openevolve_submission_dir / "log.log"
    dest_checkpoint_path = openevolve_submission_dir / "checkpoint_latest"

    if can_overwrite(dest_log_path):
        shutil.copy(log_file, dest_log_path)
    else:
        print(f"Skipping copying log file to {dest_log_path}")

    if can_overwrite(dest_checkpoint_path):
        shutil.copytree(checkpoint_dir, dest_checkpoint_path, dirs_exist_ok=True)
    else:
        print(f"Skipping copying checkpoint directory to {dest_checkpoint_path}")

    print(f"Results collected in {openevolve_submission_dir}")


def main(output_dir: Path, submission_dir: Path):
    log_dir = get_logs_dir(output_dir)
    if not log_dir.exists():
        print(
            f"Logs directory {log_dir} does not exist. Please check whether the output directory path is correct."
        )
        return

    log_files = list(log_dir.glob("*.log"))
    if not log_files:
        print(f"No log files found in {log_dir}. Did you run OpenEvolve?")
        return

    if len(log_files) > 1:
        print(
            f"Multiple files were found in {log_dir}. This is likely caused by multiple runs of OpenEvolve using the same output directory. You could have lost important data for the submission. Proceed with care. Please indicate the log file corresponding to the run you want to submit results for."
        )
        log_file = ask_correct_log_file(log_files)
    else:
        log_file = log_files[0]

    print(f"Using log file: {log_file}")

    try:
        raw_checkpoint_path = find_last_checkpoint_dir(log_file)
        if raw_checkpoint_path.is_absolute():
            checkpoint_dir = raw_checkpoint_path
        else:
            checkpoint_dir = output_dir.parent / raw_checkpoint_path
    except ValueError as e:
        print(e)
        return

    print(f"Using checkpoint directory: {checkpoint_dir}.")
    collect_results(submission_dir, log_file, checkpoint_dir)
    print("Done!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=f"""Collects results from OpenEvolve for project submission. Please use with care, and double-check the results before submission. If you encounter any issues, please get in touch with the course staff.
        As a last resort, manual collection of the results is also possible by copying the log file and the latest checkpoint directory to the {SUBMISSION_DIR_NAME}/ directory in your submission folder. Take extra care to ensure that the correct log file and checkpoint directory are copied, especially when multiple runs of OpenEvolve were conducted using the same output directory. If in doubt, ask the course staff for help."""
    )
    parser.add_argument(
        "output_dir",
        type=str,
        help="The output directory of OpenEvolve",
    )
    parser.add_argument(
        "submission_dir",
        type=str,
        help="Path to the root of the project submission directory",
    )
    args = parser.parse_args()

    main(Path(args.output_dir), Path(args.submission_dir))
