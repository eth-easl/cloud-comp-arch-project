import subprocess

def run_command(
        command,
        shell = True,
        check = True,
        capture_output = False,
        verbose = False
    ):
    """
    Executes a shell command and optionally captures its output.

    Parameters
    ----------
    command (str)
        The shell command to execute. This can be a string representing the
        command to run.
    shell (bool, optional)
        Whether to execute the command through the shell. If True, the command
        will be executed in a shell environment. Defaults to True.
    check (bool, optional)
        If True, raises a subprocess.CalledProcessError if the command exits
        with a non-zero status. Defaults to True.
    capture_output (bool, optional)
        If True, captures the command's standard output and returns it as a 
        string. If False, the output is not captured. Defaults to False.
    verbose (bool, optional)
        If True, prints the command being executed. Defaults to False.

    Returns
    -------
    str or None
        If `capture_output` is True, returns the standard output of the
        command as a stripped string. If `capture_output` is False, returns
        None.
    """
    if verbose:
        print(f"[EXECUTING] {command}")

    result = subprocess.run(command, shell=shell, check=check, capture_output=capture_output, text=True)
    if capture_output:
        return result.stdout.strip()
    return None