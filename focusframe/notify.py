from plyer import notification

def show_notification(title: str, message: str, timeout: int = 5):
    try:
        notification.notify(title=title, message=message, timeout=timeout)
    except Exception:
        # Fallback: print if system toast fails
        print(f"[NOTIFY] {title}: {message}")
