import platform
import psutil

def get_foreground_process_name() -> str:
    """
    Returns the executable name of the current foreground app if possible.
    Falls back to an educated guess when OS APIs are unavailable.
    """
    system = platform.system().lower()
    if "windows" in system:
        try:
            import win32gui
            import win32process
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                _, pid = win32process.GetWindowThreadProcessId(hwnd)
                p = psutil.Process(pid)
                return p.name()
        except Exception:
            pass  # fall back below

    # Linux/macOS fallback: not perfectly accurate without extra tools
    try:
        # Pick the top CPU-consuming GUI-ish process (best-effort)
        procs = [(p, p.cpu_percent(interval=0)) for p in psutil.process_iter(["name"])]
        procs = sorted(procs, key=lambda t: t[1], reverse=True)
        for p, _ in procs[:10]:
            if p.info.get("name"):
                return p.info["name"]
    except Exception:
        pass

    return "unknown"
