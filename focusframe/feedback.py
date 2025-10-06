import queue
import threading
import time
from dataclasses import dataclass
from typing import Optional

from .notifications import NotificationMessage
from .storage import Store


@dataclass
class FeedbackItem:
    notification: NotificationMessage
    rule_id: Optional[str]
    decision_reason: str
    context: dict
    emotion: Optional[str]
    emotion_score: float
    delivered_ts: float


class FeedbackManager:
    """Optional CLI feedback capture for delivered notifications."""

    def __init__(self, store: Store, *, enabled: bool = True, prompt: bool = True) -> None:
        self.store = store
        self.enabled = enabled
        self.prompt = prompt and enabled
        self._queue: "queue.Queue[Optional[FeedbackItem]]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        if not self.prompt or self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="feedback-manager", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if not self.prompt:
            return
        self._stop.set()
        self._queue.put(None)
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None

    def enqueue_delivery(
        self,
        notification: NotificationMessage,
        *,
        rule_id: Optional[str],
        decision_reason: str,
        context: dict,
        emotion: Optional[str],
        emotion_score: float,
    ) -> None:
        if not self.enabled:
            return
        item = FeedbackItem(
            notification=notification,
            rule_id=rule_id,
            decision_reason=decision_reason,
            context=context,
            emotion=emotion,
            emotion_score=emotion_score,
            delivered_ts=time.time(),
        )
        self.store.log_feedback(
            notification.id,
            "delivered",
            {
                "rule_id": rule_id,
                "reason": decision_reason,
                "emotion": emotion,
                "emotion_score": emotion_score,
                "context": context,
            },
        )
        if self.prompt:
            self._queue.put(item)

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                item = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                break
            self._prompt_user(item)

    def _prompt_user(self, item: FeedbackItem) -> None:
        notification = item.notification
        print("\n[Feedback] Notification delivered")
        print(f"  ID: {notification.id}")
        print(f"  Title: {notification.title}")
        print(f"  Message: {notification.message}")
        print(f"  Rule: {item.rule_id or 'N/A'} ({item.decision_reason})")
        options = "[o]pen / [s]nooze / [d]ismiss / [enter] ignore"
        try:
            response = input(f"[Feedback] Enter outcome {options}: ").strip().lower()
        except EOFError:
            response = ""
        mapping = {
            "o": "user_opened",
            "s": "user_snoozed",
            "d": "user_dismissed",
        }
        action = mapping.get(response, "user_ignored")
        metadata = {
            "rule_id": item.rule_id,
            "reason": item.decision_reason,
            "emotion": item.emotion,
            "emotion_score": item.emotion_score,
            "context": item.context,
            "response": response,
            "latency_seconds": max(0.0, time.time() - item.delivered_ts),
        }
        self.store.log_feedback(notification.id, action, metadata)
