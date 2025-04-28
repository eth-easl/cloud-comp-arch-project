import subprocess
import sys
 
n = sys.argv[1]

if __name__ == '__main__':

    subprocess.run(["kops", "delete", "cluster", "--name", f"part{n}.k8s.local", "--yes"], check=True)
    print("Successfully deleted cluster!")