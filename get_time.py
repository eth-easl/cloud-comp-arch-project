import json
import sys
from datetime import datetime


time_format = '%Y-%m-%dT%H:%M:%SZ'
file = open(sys.argv[1], 'r')
json_file = json.load(file)

start_times = []
completion_times = []
for item in json_file['items']:
    name = item['status']['containerStatuses'][0]['name']
    print("Job: ", str(name))
    if str(name) != "memcached":
        try:
            start_time = datetime.strptime(
                    item['status']['containerStatuses'][0]['state']['terminated']['startedAt'],
                    time_format)
            completion_time = datetime.strptime(
                    item['status']['containerStatuses'][0]['state']['terminated']['finishedAt'],
                    time_format)
            print("Job time: ", completion_time - start_time)
            start_times.append(start_time)
            completion_times.append(completion_time)
        except KeyError:
            print("Job {0} has not completed....".format(name))
            sys.exit(0)

if len(start_times) != 7 and len(completion_times) != 7:
    print("You haven't run all the PARSEC jobs. Exiting...")
    sys.exit(0)

print("Total time: {0}".format(max(completion_times) - min(start_times)))
file.close()
