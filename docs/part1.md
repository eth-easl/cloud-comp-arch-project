### Useful Commands

Running memcached

```bash
kubectl create -f memcache-t1-cpuset.yaml

kubectl expose pod some-memcached --name some-memcached-11211 --type LoadBalancer --port 11211 --protocol TCP
```

```bash
gcloud compute ssh --ssh-key-file ~/.ssh/id_ed25519 ubuntu@client-agent-fbhx --zone europe-west3-a

gcloud compute ssh --ssh-key-file ~/.ssh/id_ed25519 ubuntu@client-measure-k5pf --zone europe-west3-a
```

Assuming MEMCACHED_IP=100.96.2.2; INTERNAL_AGENT_IP=10.0.16.3

```bash
sudo apt-get update
sudo apt-get install libevent-dev libzmq3-dev git make g++ --yes
sudo sed -i 's/^Types: deb$/Types: deb deb-src/' /etc/apt/sources.list.d/ubuntu.sources
sudo apt-get update
sudo apt-get build-dep memcached --yes
cd && git clone https://github.com/shaygalon/memcache-perf.git
cd memcache-perf
git checkout 0afbe9b
make
```

On the client-agent VM:
```bash
./mcperf -T 16 -A
```


```bash
./mcperf -s 100.96.2.2 --loadonly
./mcperf -s 100.96.2.2 -a 10.0.16.3 --noload -T 16 -C 4 -D 4 -Q 1000 -c 4 -t 5 -w 2 --scan 5000:55000:5000
```

```bash
kubectl create -f interference/ibench-cpu.yaml
```