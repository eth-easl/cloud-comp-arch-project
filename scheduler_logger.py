from datetime import datetime
from enum import Enum
import urllib.parse


LOG_STRING = "{timestamp} {event} {job_name} {args}"

class Job(Enum):
    SCHEDULER = "scheduler"
    MEMCACHED = "memcached"
    BLACKSCHOLES = "blackscholes"
    CANNEAL = "canneal"
    DEDUP = "dedup"
    FERRET = "ferret"
    FREQMINE = "freqmine"
    RADIX = "radix"
    VIPS = "vips"


class SchedulerLogger:
    def __init__(self):
        start_date = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.file = open(f"log{start_date}.txt", "w")
        self._log("start", Job.SCHEDULER)

    def _log(self, event: str, job_name: Job, args: str = "") -> None:
        self.file.write(
            LOG_STRING.format(timestamp=datetime.now().isoformat(), event=event, job_name=job_name.value,
                              args=args).strip() + "\n")

    def job_start(self, job: Job, initial_cores: list[str], initial_threads: int) -> None:
        assert job != Job.SCHEDULER, "You don't have to log SCHEDULER here"

        self._log("start", job, "["+(",".join(str(i) for i in initial_cores))+"] "+str(initial_threads))

    def job_end(self, job: Job) -> None:
        assert job != Job.SCHEDULER, "You don't have to log SCHEDULER here"

        self._log("end", job)

    def update_cores(self, job: Job, cores: list[str]) -> None:
        assert job != Job.SCHEDULER, "You don't have to log SCHEDULER here"

        self._log("update_cores", job, "["+(",".join(str(i) for i in cores))+"]")

    def job_pause(self, job: Job) -> None:
        assert job != Job.SCHEDULER, "You don't have to log SCHEDULER here"

        self._log("pause", job)

    def job_unpause(self, job: Job) -> None:
        assert job != Job.SCHEDULER, "You don't have to log SCHEDULER here"

        self._log("unpause", job)

    def custom_event(self, job:Job, comment: str):
        self._log("custom", job, urllib.parse.quote_plus(comment))

    def end(self) -> None:
        self._log("end", Job.SCHEDULER)
        self.file.flush()
        self.file.close()
