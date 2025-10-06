import csv
import json
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence


@dataclass
class EventRecord:
    timestamp: float
    kind: str
    detail: str


class ReportGenerator:
    def __init__(self, db_path: str = "focusframe.db") -> None:
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def fetch_events(self, kinds: Sequence[str], limit: int = 1000) -> List[EventRecord]:
        placeholders = ",".join("?" for _ in kinds)
        query = f"""
            SELECT ts, kind, detail
            FROM events
            WHERE kind IN ({placeholders})
            ORDER BY ts DESC
            LIMIT ?
        """
        rows: List[EventRecord] = []
        with self._connect() as conn:
            for row in conn.execute(query, (*kinds, limit)):
                rows.append(EventRecord(timestamp=row["ts"], kind=row["kind"], detail=row["detail"] or ""))
        return rows

    def export_events_csv(self, destination: Path, kinds: Sequence[str]) -> Path:
        events = self.fetch_events(kinds, limit=5000)
        destination = destination.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["timestamp", "iso_time", "kind", "detail"])
            for event in events:
                iso_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(event.timestamp))
                writer.writerow([f"{event.timestamp:.3f}", iso_time, event.kind, event.detail])
        return destination

    def build_summary_text(self, limit: int = 500) -> str:
        events = self.fetch_events(["emotion", "decision", "feedback"], limit=limit)
        summary = {
            "emotion": 0,
            "decision": 0,
            "feedback": 0,
            "emotion_labels": {},
            "decisions": {},
            "feedback_actions": {},
        }
        for event in events:
            summary[event.kind] = summary.get(event.kind, 0) + 1
            if event.kind == "emotion" and ":" in event.detail:
                label, _ = event.detail.split(":", 1)
                summary["emotion_labels"][label] = summary["emotion_labels"].get(label, 0) + 1
            elif event.kind == "decision":
                try:
                    payload = json.loads(event.detail)
                except Exception:
                    payload = {}
                action = payload.get("action", "unknown")
                summary["decisions"][action] = summary["decisions"].get(action, 0) + 1
            elif event.kind == "feedback":
                try:
                    payload = json.loads(event.detail)
                except Exception:
                    payload = {}
                meta = payload.get("metadata", {})
                response = meta.get("response") or payload.get("action", "unknown")
                summary["feedback_actions"][response] = summary["feedback_actions"].get(response, 0) + 1

        lines: List[str] = ["FocusFrame Summary", "==================", ""]
        lines.append(f"Emotion events: {summary['emotion']}")
        for label, count in sorted(summary["emotion_labels"].items(), key=lambda t: t[1], reverse=True):
            lines.append(f"  - {label}: {count}")
        lines.append("")
        lines.append(f"Decisions: {summary['decision']}")
        for action, count in sorted(summary["decisions"].items(), key=lambda t: t[1], reverse=True):
            lines.append(f"  - {action}: {count}")
        lines.append("")
        lines.append(f"Feedback responses: {summary['feedback']}")
        for action, count in sorted(summary["feedback_actions"].items(), key=lambda t: t[1], reverse=True):
            lines.append(f"  - {action}: {count}")
        return "\n".join(lines)


def export_events(db_path: str, destination: Path, kinds: Iterable[str]) -> Path:
    generator = ReportGenerator(db_path)
    return generator.export_events_csv(destination, list(kinds))


def summary_text(db_path: str, limit: int = 500) -> str:
    generator = ReportGenerator(db_path)
    return generator.build_summary_text(limit)
