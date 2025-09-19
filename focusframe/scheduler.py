import time
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class Notification:
    title: str
    message: str
    created_ts: float = field(default_factory=lambda: time.time())

class Scheduler:
    def __init__(self, batch_release_minutes: int = 25):
        self.defer_pool: List[Notification] = []
        self.batch_pool: List[Notification] = []
        self.last_batch_release = time.time()
        self.batch_release_seconds = max(1, batch_release_minutes) * 60

    def defer(self, note: Notification, minutes: int):
        # store with unlock time
        unlock = time.time() + max(1, minutes) * 60
        setattr(note, "unlock_ts", unlock)
        self.defer_pool.append(note)

    def batch(self, note: Notification):
        self.batch_pool.append(note)

    def ready_to_release_batch(self) -> bool:
        return (time.time() - self.last_batch_release) >= self.batch_release_seconds

    def release_due(self) -> List[Notification]:
        now = time.time()
        due = []
        # release defers that matured
        still_waiting = []
        for n in self.defer_pool:
            if getattr(n, "unlock_ts", now+1) <= now:
                due.append(n)
            else:
                still_waiting.append(n)
        self.defer_pool = still_waiting

        # release batch if time
        if self.ready_to_release_batch() and self.batch_pool:
            due.extend(self.batch_pool)
            self.batch_pool = []
            self.last_batch_release = now

        return due
