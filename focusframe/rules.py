from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .storage import Store

NEGATIVE_EMOTIONS = {"angry", "fear", "disgust"}
RELAXED_EMOTIONS = {"neutral", "happy", "happiness", "surprise"}


DEFAULT_RULES: List[Dict[str, Any]] = [
    {
        "id": "negative_focus_defer",
        "name": "Defer negative emotion in focus apps",
        "priority": 100,
        "condition": {
            "emotion_in": list(NEGATIVE_EMOTIONS),
            "app_category_in": ["focus"],
        },
        "action": "defer",
        "parameters": {
            "reason": "negative_emotion_in_focus_app",
            "minutes_key": "focus_deferral_minutes",
        },
    },
    {
        "id": "sad_focus_defer",
        "name": "Short defer for sadness",
        "priority": 90,
        "condition": {
            "emotion_in": ["sad"],
            "app_category_in": ["focus"],
        },
        "action": "defer",
        "parameters": {
            "reason": "sad_in_focus_app",
            "minutes_key": "sad_deferral_minutes",
        },
    },
    {
        "id": "batch_relaxed_focus",
        "name": "Batch relaxed focus context",
        "priority": 80,
        "condition": {
            "emotion_in": list(RELAXED_EMOTIONS),
            "app_category_in": ["focus"],
            "batching_enabled": True,
        },
        "action": "batch",
        "parameters": {
            "reason": "batch_during_deep_work",
        },
    },
    {
        "id": "casual_deliver",
        "name": "Deliver in casual apps",
        "priority": 70,
        "condition": {
            "app_category_in": ["casual"],
            "emotion_not_in": list(NEGATIVE_EMOTIONS),
        },
        "action": "deliver",
        "parameters": {
            "reason": "casual_context",
        },
    },
    {
        "id": "default_deliver",
        "name": "Default deliver",
        "priority": 10,
        "condition": {},
        "action": "deliver",
        "parameters": {
            "reason": "default",
        },
    },
]


@dataclass
class DecisionResult:
    action: str
    reason: str
    minutes: int = 0
    rule_id: Optional[str] = None


@dataclass
class Rule:
    id: str
    name: str
    priority: int
    condition: Dict[str, Any]
    action: str
    parameters: Dict[str, Any]
    updated_at: float

    def matches(
        self,
        *,
        emotion: str,
        context: Any,
        notification: Any,
        batching_enabled: bool,
    ) -> bool:
        cond = self.condition or {}
        emo = (emotion or "").lower()
        app_category = getattr(context, "app_category", None)
        notif_category = getattr(notification, "category", None)
        calendar_state = getattr(context, "calendar_state", None)
        day_segment = getattr(context, "day_segment", None)

        if "emotion_in" in cond and emo not in {e.lower() for e in cond["emotion_in"]}:
            return False
        if "emotion_not_in" in cond and emo in {e.lower() for e in cond["emotion_not_in"]}:
            return False
        if "emotion_is" in cond and emo != cond["emotion_is"].lower():
            return False
        if "app_category_in" in cond and app_category not in cond["app_category_in"]:
            return False
        if "notification_category_in" in cond and notif_category not in cond["notification_category_in"]:
            return False
        if cond.get("requires_work_hours") is True and not getattr(context, "is_work_hours", False):
            return False
        if cond.get("calendar_state_in") and calendar_state not in cond["calendar_state_in"]:
            return False
        if cond.get("day_segment_in") and day_segment not in cond["day_segment_in"]:
            return False
        if cond.get("batching_enabled") and not batching_enabled:
            return False
        return True

    def apply(self, *, config: "Config", emotion: str) -> DecisionResult:
        reason = self.parameters.get("reason", self.id)
        action = self.action
        minutes = int(self.parameters.get("minutes", 0))

        minutes_key = self.parameters.get("minutes_key")
        if minutes_key and hasattr(config, "deferral"):
            minutes = int(config.deferral.get(minutes_key, minutes or 0))

        return DecisionResult(action=action, reason=reason, minutes=minutes, rule_id=self.id)


class RuleEngine:
    def __init__(self, store: Store, config: "Config"):
        # Config is provided at runtime from focusframe.config
        self.store = store
        self.config = config
        self._rules: List[Rule] = []
        self._last_refresh = 0.0
        self.refresh(force=True)

    def refresh(self, force: bool = False) -> None:
        latest = self.store.rules_last_updated()
        if not force and latest <= self._last_refresh:
            return

        self.store.ensure_rules(DEFAULT_RULES)
        rows = self.store.fetch_rules()
        self._rules = [
            Rule(
                id=row["id"],
                name=row["name"],
                priority=int(row["priority"]),
                condition=row["condition"],
                action=row["action"],
                parameters=row["parameters"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]
        self._last_refresh = latest

    def decide(
        self,
        *,
        emotion: str,
        context: Any,
        notification: Any,
    ) -> DecisionResult:
        self.refresh()
        batching_enabled = bool(self.config.batching.get("enabled", True))
        emo = (emotion or "").lower() or "neutral"
        for rule in sorted(self._rules, key=lambda r: r.priority, reverse=True):
            if rule.matches(
                emotion=emo,
                context=context,
                notification=notification,
                batching_enabled=batching_enabled,
            ):
                return rule.apply(config=self.config, emotion=emo)
        return DecisionResult(action="deliver", reason="fallback", minutes=0, rule_id=None)
