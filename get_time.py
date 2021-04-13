import json
import sys
from datetime import datetime


time_format = '%Y-%m-%dT%H:%M:%SZ'
file = open(sys.argv[1], 'r')
json_file = json.load(file)

start_times = []
completion_times = []
for item in json_file['items']:
    name = item['metadata']['name']
    print("Job: ", str(name))
    start_time = datetime.strptime(item['status']['startTime'],
                                   time_format)
    completion_time = datetime.strptime(item['status']['completionTime'],
                                        time_format)
    print("Job time: ", completion_time - start_time)
    start_times.append(start_time)
    completion_times.append(completion_time)
    if not item['status']['succeeded']:
        print("Job {0} has not terminated!".format(name))

if len(start_times) != 6 and len(completion_times) != 6:
    print("You haven't run all the PARSEC jobs. Exiting...")
    sys.exit(0)

print("Total time: {0}".format(max(completion_times) - min(start_times)))
file.close()
