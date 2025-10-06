import time
from dataclasses import dataclass, field
from typing import List, Optional

from .notifications import NotificationMessage


@dataclass
class ScheduledItem:
    notification: NotificationMessage
    created_ts: float = field(default_factory=lambda: time.time())
    unlock_ts: Optional[float] = None


class Scheduler:
    def __init__(self, batch_release_minutes: int = 25):
        self.defer_pool: List[ScheduledItem] = []
        self.batch_pool: List[ScheduledItem] = []
        self.last_batch_release = time.time()
        self.batch_release_seconds = max(1, batch_release_minutes) * 60

    def defer(self, note: NotificationMessage, minutes: int) -> None:
        unlock = time.time() + max(1, minutes) * 60
        self.defer_pool.append(ScheduledItem(notification=note, unlock_ts=unlock))

    def batch(self, note: NotificationMessage) -> None:
        self.batch_pool.append(ScheduledItem(notification=note))

    def ready_to_release_batch(self) -> bool:
        return (time.time() - self.last_batch_release) >= self.batch_release_seconds

    def release_due(self) -> List[NotificationMessage]:
        now = time.time()
        due: List[NotificationMessage] = []
        still_waiting: List[ScheduledItem] = []
        for item in self.defer_pool:
            if (item.unlock_ts or now + 1) <= now:
                due.append(item.notification)
            else:
                still_waiting.append(item)
        self.defer_pool = still_waiting

        if self.ready_to_release_batch() and self.batch_pool:
            due.extend(item.notification for item in self.batch_pool)
            self.batch_pool = []
            self.last_batch_release = now

        return due
