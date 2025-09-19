import sqlite3
import time
from typing import Optional, Tuple

SCHEMA = """
CREATE TABLE IF NOT EXISTS events(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    kind TEXT NOT NULL,     -- emotion | app | decision | notification
    detail TEXT             -- JSON-ish or simple text
);
"""

class Store:
    def __init__(self, path: str = "focusframe.db"):
        self.path = path
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.execute(SCHEMA)
        self._conn.commit()

    def log(self, kind: str, detail: str):
        self._conn.execute("INSERT INTO events(ts, kind, detail) VALUES (?, ?, ?)",
                           (time.time(), kind, detail))
        self._conn.commit()

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass
