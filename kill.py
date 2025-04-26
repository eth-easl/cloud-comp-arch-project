import subprocess
import sys
 
n = int(sys.argv[1])

if __name__ == '__main__':
    subprocess.run(["kops", "delete", "cluster", "--name", f"part{n}a.k8s.local", "--yes"], check=True)