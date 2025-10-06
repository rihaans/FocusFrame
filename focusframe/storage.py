import json
import sqlite3
import time
from typing import Any, Dict, Iterable, List, Optional

SCHEMA = """
CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,
    detail TEXT
);
"""

RULES_SCHEMA = """
CREATE TABLE IF NOT EXISTS rules(
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    priority INTEGER NOT NULL,
    condition TEXT NOT NULL,
    action TEXT NOT NULL,
    parameters TEXT,
    updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_rules_priority ON rules(priority DESC, updated_at DESC);
"""


class Store:
    def __init__(self, path: str = "focusframe.db"):
        self.path = path
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._bootstrap()

    def _bootstrap(self) -> None:
        self._conn.executescript(SCHEMA)
        self._conn.executescript(RULES_SCHEMA)
        self._conn.commit()

    def log(self, kind: str, detail: str) -> None:
        self._conn.execute(
            "INSERT INTO events(ts, kind, detail) VALUES (?, ?, ?)",
            (time.time(), kind, detail),
        )
        self._conn.commit()

    def log_json(self, kind: str, payload: Dict[str, Any]) -> None:
        self.log(kind, json.dumps(payload, ensure_ascii=False))

    def log_context(self, snapshot: Dict[str, Any]) -> None:
        self.log_json("context", snapshot)

    def log_feedback(
        self,
        notification_id: str,
        action: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        payload = {
            "notification_id": notification_id,
            "action": action,
            "metadata": metadata or {},
        }
        self.log_json("feedback", payload)

    def ensure_rules(self, defaults: Iterable[Dict[str, Any]]) -> None:
        cur = self._conn.execute("SELECT COUNT(1) FROM rules")
        (count,) = cur.fetchone()
        if count:
            return

        now = time.time()
        rows = [
            (
                rule["id"],
                rule["name"],
                int(rule["priority"]),
                json.dumps(rule["condition"], ensure_ascii=False),
                rule["action"],
                json.dumps(rule.get("parameters", {}), ensure_ascii=False),
                now,
            )
            for rule in defaults
        ]
        self._conn.executemany(
            "INSERT INTO rules(id, name, priority, condition, action, parameters, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        self._conn.commit()

    def upsert_rule(self, rule: Dict[str, Any]) -> None:
        now = time.time()
        self._conn.execute(
            """
            INSERT INTO rules(id, name, priority, condition, action, parameters, updated_at)
            VALUES(:id, :name, :priority, :condition, :action, :parameters, :updated_at)
            ON CONFLICT(id) DO UPDATE SET
                name=excluded.name,
                priority=excluded.priority,
                condition=excluded.condition,
                action=excluded.action,
                parameters=excluded.parameters,
                updated_at=excluded.updated_at
            """,
            {
                "id": rule["id"],
                "name": rule["name"],
                "priority": int(rule["priority"]),
                "condition": json.dumps(rule["condition"], ensure_ascii=False),
                "action": rule["action"],
                "parameters": json.dumps(rule.get("parameters", {}), ensure_ascii=False),
                "updated_at": now,
            },
        )
        self._conn.commit()

    def fetch_rules(self) -> List[Dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT id, name, priority, condition, action, parameters, updated_at FROM rules"
            " ORDER BY priority DESC, updated_at DESC"
        )
        rows: List[Dict[str, Any]] = []
        for row in cur.fetchall():
            rows.append(
                {
                    "id": row["id"],
                    "name": row["name"],
                    "priority": int(row["priority"]),
                    "condition": json.loads(row["condition"]),
                    "action": row["action"],
                    "parameters": json.loads(row["parameters"]) if row["parameters"] else {},
                    "updated_at": float(row["updated_at"]),
                }
            )
        return rows

    def rules_last_updated(self) -> float:
        cur = self._conn.execute("SELECT COALESCE(MAX(updated_at), 0) FROM rules")
        (ts,) = cur.fetchone()
        return float(ts or 0.0)

    def close(self) -> None:
        try:
            self._conn.close()
        except Exception:
            pass
