import datetime as dt
import platform
import time
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Tuple

import psutil

from .apptracker import get_foreground_process_name

try:
    from .gcal import GoogleCalendarManager, GCAL_AVAILABLE
except ImportError:
    GCAL_AVAILABLE = False
    GoogleCalendarManager = None


def _parse_time(value: str) -> dt.time:
    hour, minute = value.split(":", 1)
    return dt.time(int(hour), int(minute))


class CalendarPlanner:
    def __init__(self, blocks: List[Dict[str, Any]]):
        self.blocks: List[Tuple[str, List[str], dt.time, dt.time]] = []
        for block in blocks or []:
            try:
                name = block.get("name") or "busy"
                days = [d.lower() for d in block.get("days", [])]
                start = _parse_time(block["start"])
                end = _parse_time(block["end"])
            except (KeyError, ValueError):
                continue
            self.blocks.append((name, days, start, end))

    def current_state(self, now: Optional[dt.datetime] = None) -> Tuple[str, Optional[str]]:
        now = now or dt.datetime.now()
        day = now.strftime("%a").lower()[:3]
        current_time = now.time()
        for name, days, start, end in self.blocks:
            if days and day not in days:
                continue
            if start <= current_time <= end:
                return "busy", name
        return "free", None


def _system_idle_seconds() -> float:
    system = platform.system().lower()
    if "windows" in system:
        try:
            import ctypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_ulong)]

            last_input = LASTINPUTINFO()
            last_input.cbSize = ctypes.sizeof(LASTINPUTINFO)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(last_input)):
                millis = ctypes.windll.kernel32.GetTickCount() - last_input.dwTime
                return max(0.0, millis / 1000.0)
        except Exception:
            pass
    return 0.0


def _day_segment(now: dt.datetime) -> str:
    hour = now.hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


@dataclass
class ContextSnapshot:
    timestamp: float
    active_app: str
    app_category: str
    day_segment: str
    is_work_hours: bool
    idle_seconds: float
    calendar_state: str
    calendar_event: Optional[str]
    location: str
    cpu_percent: float
    memory_percent: float
    net_bytes_sent: float
    net_bytes_recv: float
    top_process: Optional[str]
    battery_percent: Optional[float]
    battery_plugged: Optional[bool]

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ContextManager:
    def __init__(self, cfg: Dict[str, Any], calendar_cfg: Dict[str, Any], apps_cfg: Dict[str, Any]):
        self.location = cfg.get("location", "unspecified")
        work_hours = cfg.get("work_hours", {})
        try:
            self.work_start = _parse_time(work_hours.get("start", "09:00"))
            self.work_end = _parse_time(work_hours.get("end", "17:00"))
        except ValueError:
            self.work_start = dt.time(9, 0)
            self.work_end = dt.time(17, 0)
        self.calendar = CalendarPlanner(calendar_cfg.get("busy_blocks", []))
        self.apps_cfg = apps_cfg

        # Initialize Google Calendar if enabled and available
        self.gcal_manager: Optional[GoogleCalendarManager] = None
        self.use_google_calendar = False
        if GCAL_AVAILABLE and calendar_cfg.get("use_google_calendar", False):
            try:
                credentials_path = calendar_cfg.get("google_credentials_path", "credentials.json")
                token_path = calendar_cfg.get("google_token_path", "token.pickle")
                self.gcal_manager = GoogleCalendarManager(credentials_path, token_path)
                # Try to authenticate (will use cached token if available)
                if self.gcal_manager.is_authenticated() or self.gcal_manager.authenticate():
                    self.use_google_calendar = True
                    print("[FocusFrame] Google Calendar integration enabled")
                else:
                    print("[FocusFrame] Google Calendar authentication failed, using static calendar")
            except Exception as e:
                print(f"[FocusFrame] Error initializing Google Calendar: {e}")
                print("[FocusFrame] Falling back to static calendar")

    def snapshot(self) -> ContextSnapshot:
        now = dt.datetime.now()

        active_app = get_foreground_process_name()
        app_category = self._categorize_app(active_app)
        idle_seconds = _system_idle_seconds()
        day_segment = _day_segment(now)

        # Get calendar state from Google Calendar or static planner
        if self.use_google_calendar and self.gcal_manager:
            try:
                calendar_state, calendar_event = self.gcal_manager.get_current_event_status()
            except Exception as e:
                print(f"[FocusFrame] Error fetching Google Calendar status: {e}")
                # Fall back to static calendar
                calendar_state, calendar_event = self.calendar.current_state(now)
        else:
            calendar_state, calendar_event = self.calendar.current_state(now)

        is_work_hours = self._within_work_hours(now.time())
        cpu_percent = psutil.cpu_percent(interval=0.0)
        memory_percent = psutil.virtual_memory().percent
        try:
            net = psutil.net_io_counters()
            net_bytes_sent = float(net.bytes_sent)
            net_bytes_recv = float(net.bytes_recv)
        except Exception:
            net_bytes_sent = 0.0
            net_bytes_recv = 0.0

        top_process = None
        try:
            processes = list(psutil.process_iter(["name", "cpu_percent"]))
            if processes:
                top = max(processes, key=lambda p: p.info.get("cpu_percent", 0.0))
                name = top.info.get("name") or str(top.pid)
                cpu = top.info.get("cpu_percent", 0.0)
                top_process = f"{name}:{cpu:.1f}"
        except Exception:
            top_process = None

        battery_percent = None
        battery_plugged = None
        try:
            battery = psutil.sensors_battery()
        except Exception:
            battery = None
        if battery:
            battery_percent = battery.percent
            battery_plugged = battery.power_plugged

        snapshot = ContextSnapshot(
            timestamp=time.time(),
            active_app=active_app,
            app_category=app_category,
            day_segment=day_segment,
            is_work_hours=is_work_hours,
            idle_seconds=idle_seconds,
            calendar_state=calendar_state,
            calendar_event=calendar_event,
            location=self.location,
            cpu_percent=cpu_percent,
            memory_percent=memory_percent,
            net_bytes_sent=net_bytes_sent,
            net_bytes_recv=net_bytes_recv,
            top_process=top_process,
            battery_percent=battery_percent,
            battery_plugged=battery_plugged,
        )
        return snapshot

    def _within_work_hours(self, current_time: dt.time) -> bool:
        start = self.work_start
        end = self.work_end
        if start <= end:
            return start <= current_time <= end
        return current_time >= start or current_time <= end

    def _categorize_app(self, process_name: str) -> str:
        name = (process_name or "").lower()
        focus_list = [n.lower() for n in self.apps_cfg.get("focus", [])]
        casual_list = [n.lower() for n in self.apps_cfg.get("casual", [])]
        if any(name == f for f in focus_list):
            return "focus"
        if any(name == c for c in casual_list):
            return "casual"
        focus_keywords = ["code", "idea", "studio", "vim", "emacs", "pycharm", "devenv"]
        casual_keywords = ["chrome", "edge", "firefox", "whatsapp", "telegram", "discord", "youtube", "spotify"]
        if any(k in name for k in focus_keywords):
            return "focus"
        if any(k in name for k in casual_keywords):
            return "casual"
        return "unknown"
