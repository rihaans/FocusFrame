import email
import imaplib
import json
import random
import re
import shutil
import time
import uuid
from dataclasses import asdict, dataclass, field
from email import policy
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

POSITIVE_WORDS = {
    "great",
    "good",
    "awesome",
    "excellent",
    "happy",
    "success",
    "thanks",
    "congrats",
    "progress",
    "complete",
}
NEGATIVE_WORDS = {
    "urgent",
    "fail",
    "issue",
    "problem",
    "delay",
    "blocked",
    "critical",
    "error",
    "broken",
    "sad",
}
TAG_KEYWORDS = {
    "urgent": ["urgent", "asap", "immediately", "critical"],
    "meeting": ["meeting", "standup", "sync", "catch-up", "call"],
    "reminder": ["reminder", "remember", "don't forget"],
    "deployment": ["deploy", "release", "build"],
    "social": ["party", "dinner", "game", "hangout"],
    "task": ["task", "todo", "action", "follow-up"],
}
TOKEN_RE = re.compile(r"[a-zA-Z']+")


@dataclass
class NotificationMessage:
    id: str
    source: str
    title: str
    message: str
    created_ts: float
    category: str = "general"
    metadata: Dict[str, Any] = field(default_factory=dict)
    sentiment: float = 0.0
    tags: List[str] = field(default_factory=list)

    @property
    def body(self) -> str:
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        payload["body"] = self.message
        return payload


def _analyze_sentiment(text: str) -> float:
    tokens = [token.lower() for token in TOKEN_RE.findall(text)]
    pos = sum(1 for token in tokens if token in POSITIVE_WORDS)
    neg = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    total = pos + neg
    if total == 0:
        return 0.0
    return (pos - neg) / total


def _extract_tags(text: str, category: str, metadata: Dict[str, Any]) -> List[str]:
    tags = set()
    lower = text.lower()
    for tag, keywords in TAG_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            tags.add(tag)
    if category:
        tags.add(category.lower())
    meta_tags = metadata.get("tags")
    if isinstance(meta_tags, list):
        tags.update(str(tag).lower() for tag in meta_tags)
    return sorted(tags)


def enrich_message(note: NotificationMessage) -> NotificationMessage:
    text = f"{note.title} {note.message}"
    note.sentiment = _analyze_sentiment(text)
    note.tags = _extract_tags(text, note.category, note.metadata)
    return note


class NotificationSource:
    def __init__(self, *, source_id: str, enabled: bool = True) -> None:
        self.source_id = source_id
        self.enabled = enabled

    def poll(self, now: Optional[float] = None) -> List[NotificationMessage]:
        raise NotImplementedError

    def enrich(self, note: NotificationMessage) -> NotificationMessage:
        return enrich_message(note)


class DemoNotificationSource(NotificationSource):
    def __init__(
        self,
        *,
        source_id: str,
        payloads: Iterable[str],
        interval_seconds: int,
        title_prefix: str = "[FocusFrame]",
        enabled: bool = True,
    ) -> None:
        super().__init__(source_id=source_id, enabled=enabled)
        self.payloads = list(payloads)
        self.interval = max(1, int(interval_seconds))
        self.title_prefix = title_prefix
        self._next_emit = time.time() + self.interval

    def poll(self, now: Optional[float] = None) -> List[NotificationMessage]:
        if not self.enabled or not self.payloads:
            return []

        now = now or time.time()
        produced: List[NotificationMessage] = []
        while now >= self._next_emit:
            message = random.choice(self.payloads)
            note = NotificationMessage(
                id=str(uuid.uuid4()),
                source=self.source_id,
                title=f"{self.title_prefix} Demo",
                message=message,
                created_ts=now,
                category="demo",
                metadata={"generated": True},
            )
            produced.append(self.enrich(note))
            self._next_emit += self.interval
        return produced


class FileNotificationSource(NotificationSource):
    def __init__(
        self,
        *,
        source_id: str,
        path: str,
        category: str = "general",
        enabled: bool = True,
    ) -> None:
        super().__init__(source_id=source_id, enabled=enabled)
        self.path = Path(path)
        self.category = category
        self._seen_ids: set[str] = set()
        self._last_mtime: float = 0.0

    def poll(self, now: Optional[float] = None) -> List[NotificationMessage]:
        if not self.enabled or not self.path.exists():
            return []

        try:
            stat = self.path.stat()
        except OSError:
            return []

        if stat.st_mtime <= self._last_mtime and self._seen_ids:
            return []

        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw_lines = [line.strip() for line in handle if line.strip()]
        except OSError:
            return []

        messages: List[NotificationMessage] = []
        for line in raw_lines:
            try:
                payload = json.loads(line)
            except json.JSONDecodeError:
                continue

            note_id = payload.get("id") or str(uuid.uuid4())
            if note_id in self._seen_ids:
                continue

            note = NotificationMessage(
                id=note_id,
                source=self.source_id,
                title=payload.get("title") or payload.get("subject") or "Notification",
                message=payload.get("message") or payload.get("body") or "",
                created_ts=float(payload.get("created_ts") or payload.get("timestamp") or time.time()),
                category=payload.get("category") or self.category,
                metadata=payload.get("metadata") or {},
            )
            messages.append(self.enrich(note))
            self._seen_ids.add(note_id)

        self._last_mtime = stat.st_mtime
        return messages


class DirectoryNotificationSource(NotificationSource):
    def __init__(
        self,
        *,
        source_id: str,
        path: str,
        pattern: str = "*.json",
        archive_path: Optional[str] = None,
        category: str = "general",
        enabled: bool = True,
    ) -> None:
        super().__init__(source_id=source_id, enabled=enabled)
        self.directory = Path(path)
        self.pattern = pattern
        self.category = category
        self.archive_dir = Path(archive_path) if archive_path else None
        if self.archive_dir:
            self.archive_dir.mkdir(parents=True, exist_ok=True)

    def poll(self, now: Optional[float] = None) -> List[NotificationMessage]:
        if not self.enabled or not self.directory.exists():
            return []

        messages: List[NotificationMessage] = []
        for file_path in sorted(self.directory.glob(self.pattern)):
            if not file_path.is_file():
                continue
            try:
                payload = json.loads(file_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                try:
                    file_path.unlink()
                except FileNotFoundError:
                    pass
                continue
            except OSError:
                continue

            note = NotificationMessage(
                id=payload.get("id") or str(uuid.uuid4()),
                source=self.source_id,
                title=payload.get("title") or payload.get("subject") or "Notification",
                message=payload.get("message") or payload.get("body") or "",
                created_ts=float(payload.get("created_ts") or payload.get("timestamp") or time.time()),
                category=payload.get("category") or self.category,
                metadata=payload.get("metadata") or {},
            )
            messages.append(self.enrich(note))

            try:
                if self.archive_dir:
                    target = self.archive_dir / file_path.name
                    shutil.move(str(file_path), target)
                else:
                    file_path.unlink()
            except OSError:
                pass
        return messages


class IMAPNotificationSource(NotificationSource):
    def __init__(
        self,
        *,
        source_id: str,
        host: str,
        username: str,
        password: str,
        mailbox: str = "INBOX",
        use_ssl: bool = True,
        limit: int = 5,
        enabled: bool = True,
    ) -> None:
        super().__init__(source_id=source_id, enabled=enabled)
        self.host = host
        self.username = username
        self.password = password
        self.mailbox = mailbox
        self.use_ssl = use_ssl
        self.limit = max(1, int(limit))
        self._last_uids: set[str] = set()

    def poll(self, now: Optional[float] = None) -> List[NotificationMessage]:
        if not self.enabled or not self.host or not self.username or not self.password:
            return []

        try:
            client = imaplib.IMAP4_SSL(self.host) if self.use_ssl else imaplib.IMAP4(self.host)
            client.login(self.username, self.password)
            client.select(self.mailbox)
            status, data = client.search(None, "UNSEEN")
            if status != "OK":
                client.logout()
                return []
            uids = data[0].split()[-self.limit :]
            messages: List[NotificationMessage] = []
            for uid in uids:
                uid_str = uid.decode("utf-8", errors="ignore")
                if uid_str in self._last_uids:
                    continue
                status, msg_data = client.fetch(uid, "(RFC822)")
                if status != "OK" or not msg_data:
                    continue
                raw = msg_data[0][1]
                message = email.message_from_bytes(raw, policy=policy.default)
                title = message.get("subject", "Email")
                payload = message.get_body(preferencelist=("plain", "html"))
                if payload:
                    body = payload.get_content()
                else:
                    body_raw = message.get_payload(decode=True)
                    if isinstance(body_raw, bytes):
                        body = body_raw.decode(message.get_content_charset() or "utf-8", errors="ignore")
                    else:
                        body = body_raw or ""
                note = NotificationMessage(
                    id=uid_str,
                    source=self.source_id,
                    title=title,
                    message=str(body).strip()[:500],
                    created_ts=time.time(),
                    category="email",
                    metadata={
                        "from": message.get("from"),
                        "to": message.get("to"),
                    },
                )
                messages.append(self.enrich(note))
                self._last_uids.add(uid_str)
            client.logout()
            return messages
        except Exception:
            return []


class NotificationManager:
    def __init__(self, sources: Iterable[NotificationSource]) -> None:
        self.sources = [src for src in sources if src.enabled]

    def poll(self) -> List[NotificationMessage]:
        now = time.time()
        batch: List[NotificationMessage] = []
        for source in self.sources:
            try:
                batch.extend(source.poll(now))
            except Exception:
                continue
        return batch


def build_sources(config: Dict[str, Any], demo_mode: bool = False) -> List[NotificationSource]:
    sources: List[NotificationSource] = []
    title_prefix = config.get("title_prefix", "[FocusFrame]")
    payloads = config.get("demo_payloads", [])

    for entry in config.get("sources", []):
        source_type = (entry.get("type") or "demo").lower()
        source_id = entry.get("id") or f"source_{len(sources)+1}"
        enabled = bool(entry.get("enabled", True))

        if source_type == "demo":
            interval = int(entry.get("interval_seconds", config.get("demo_interval_seconds", 30)))
            if demo_mode:
                enabled = True
            if not enabled:
                continue
            sources.append(
                DemoNotificationSource(
                    source_id=source_id,
                    payloads=payloads,
                    interval_seconds=interval,
                    title_prefix=title_prefix,
                    enabled=True,
                )
            )
        elif source_type == "file":
            if not enabled:
                continue
            sources.append(
                FileNotificationSource(
                    source_id=source_id,
                    path=entry.get("path", "notifications.jsonl"),
                    category=entry.get("category", "general"),
                    enabled=True,
                )
            )
        elif source_type == "directory":
            if not enabled:
                continue
            sources.append(
                DirectoryNotificationSource(
                    source_id=source_id,
                    path=entry.get("path", "profiles/inbox"),
                    pattern=entry.get("pattern", "*.json"),
                    archive_path=entry.get("archive_path"),
                    category=entry.get("category", "general"),
                    enabled=True,
                )
            )
        elif source_type == "imap":
            if not enabled:
                continue
            sources.append(
                IMAPNotificationSource(
                    source_id=source_id,
                    host=entry.get("host", ""),
                    username=entry.get("username", ""),
                    password=entry.get("password", ""),
                    mailbox=entry.get("mailbox", "INBOX"),
                    use_ssl=bool(entry.get("use_ssl", True)),
                    limit=int(entry.get("limit", 5)),
                    enabled=True,
                )
            )

    if demo_mode and not any(isinstance(src, DemoNotificationSource) for src in sources):
        sources.append(
            DemoNotificationSource(
                source_id="demo",
                payloads=payloads or ["Demo notification"],
                interval_seconds=int(config.get("demo_interval_seconds", 30)),
                title_prefix=title_prefix,
                enabled=True,
            )
        )
    return sources
