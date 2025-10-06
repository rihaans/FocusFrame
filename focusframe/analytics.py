import json
import sqlite3
from collections import Counter
from dataclasses import dataclass
from typing import Dict, List, Tuple


@dataclass
class EmotionStat:
    label: str
    count: int
    average_confidence: float


@dataclass
class DecisionStat:
    action: str
    count: int


@dataclass
class FeedbackStat:
    outcome: str
    count: int
    average_latency: float


@dataclass
class RuleInsight:
    rule_id: str
    action: str
    decision_count: int
    feedback_overrides: int
    message: str


class Analytics:
    def __init__(self, db_path: str = "focusframe.db") -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def emotion_overview(self, limit: int = 100) -> List[EmotionStat]:
        query = """
            SELECT detail FROM events
            WHERE kind = 'emotion'
            ORDER BY ts DESC
            LIMIT ?
        """
        rows: List[str] = []
        with self._connect() as conn:
            for row in conn.execute(query, (limit,)):
                rows.append(row["detail"])

        counter: Counter[str] = Counter()
        scores: Dict[str, List[float]] = {}
        for detail in rows:
            if not detail or ":" not in detail:
                continue
            label, score_str = detail.split(":", 1)
            try:
                score = float(score_str)
            except ValueError:
                continue
            label = label.strip()
            counter[label] += 1
            scores.setdefault(label, []).append(score)

        stats: List[EmotionStat] = []
        for label, count in counter.most_common():
            values = scores[label]
            avg = sum(values) / len(values) if values else 0.0
            stats.append(EmotionStat(label=label, count=count, average_confidence=avg))
        return stats

    def decision_mix(self, limit: int = 200) -> List[DecisionStat]:
        query = """
            SELECT detail FROM events
            WHERE kind = 'decision'
            ORDER BY ts DESC
            LIMIT ?
        """
        counts: Counter[str] = Counter()
        with self._connect() as conn:
            for row in conn.execute(query, (limit,)):
                detail = row["detail"]
                if not detail:
                    continue
                try:
                    payload = json.loads(detail)
                except Exception:
                    continue
                action = payload.get("action", "unknown")
                counts[action] += 1
        return [DecisionStat(action=a, count=c) for a, c in counts.most_common()]

    def feedback_outcomes(self, limit: int = 200) -> List[FeedbackStat]:
        query = """
            SELECT detail FROM events
            WHERE kind = 'feedback'
            ORDER BY ts DESC
            LIMIT ?
        """
        counts: Counter[str] = Counter()
        aggregates: Dict[str, List[float]] = {}
        with self._connect() as conn:
            for row in conn.execute(query, (limit,)):
                detail = row["detail"]
                if not detail:
                    continue
                try:
                    payload = json.loads(detail)
                except Exception:
                    continue
                metadata = payload.get("metadata", {})
                outcome = metadata.get("response") or payload.get("action", "unknown")
                latency = float(metadata.get("latency_seconds", 0.0))
                counts[outcome] += 1
                aggregates.setdefault(outcome, []).append(latency)
        stats: List[FeedbackStat] = []
        for outcome, count in counts.most_common():
            values = aggregates.get(outcome, [])
            avg = (sum(values) / len(values)) if values else 0.0
            stats.append(FeedbackStat(outcome=outcome, count=count, average_latency=avg))
        return stats

    def rule_insights(self, limit: int = 200) -> List[RuleInsight]:
        decision_query = """
            SELECT detail FROM events
            WHERE kind = 'decision'
            ORDER BY ts DESC
            LIMIT ?
        """
        decisions: List[Tuple[str, str]] = []
        with self._connect() as conn:
            for row in conn.execute(decision_query, (limit,)):
                detail = row["detail"]
                if not detail:
                    continue
                try:
                    payload = json.loads(detail)
                except Exception:
                    continue
                rule_id = payload.get("rule_id")
                action = payload.get("action", "unknown")
                if rule_id:
                    decisions.append((rule_id, action))

        decision_counts: Counter[str] = Counter(rule_id for rule_id, _ in decisions)
        decision_map: Dict[str, str] = {}
        for rule_id, action in decisions:
            decision_map[rule_id] = action

        feedback_query = """
            SELECT detail FROM events
            WHERE kind = 'feedback'
            ORDER BY ts DESC
            LIMIT ?
        """
        overrides: Counter[str] = Counter()
        with self._connect() as conn:
            for row in conn.execute(feedback_query, (limit,)):
                detail = row["detail"]
                if not detail:
                    continue
                try:
                    payload = json.loads(detail)
                except Exception:
                    continue
                metadata = payload.get("metadata", {})
                rule_id = metadata.get("rule_id")
                action = payload.get("action") or metadata.get("response")
                if not rule_id or not action:
                    continue
                if action in {"user_snoozed", "user_dismissed", "user_opened"}:
                    overrides[rule_id] += 1

        insights: List[RuleInsight] = []
        for rule_id, count in decision_counts.most_common():
            override_count = overrides.get(rule_id, 0)
            action = decision_map.get(rule_id, "unknown")
            ratio = override_count / count if count else 0.0
            if override_count == 0:
                message = "Stable"
            elif ratio >= 0.5:
                message = "High overrides; consider revising"
            elif ratio >= 0.2:
                message = "Moderate overrides"
            else:
                message = "Some overrides observed"
            insights.append(
                RuleInsight(
                    rule_id=rule_id,
                    action=action,
                    decision_count=count,
                    feedback_overrides=override_count,
                    message=message,
                )
            )
        return insights
