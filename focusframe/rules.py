from typing import Tuple

FOCUS_EMOTIONS = {"angry", "fear", "disgust", "sad"}
RELAXED_EMOTIONS = {"neutral", "happy", "surprise"}

def map_app_category(proc_name: str, focus_list, casual_list) -> str:
    name = (proc_name or "").lower()
    if any(name == f.lower() for f in focus_list):
        return "focus"
    if any(name == c.lower() for c in casual_list):
        return "casual"
    # heuristic: IDE/process names
    if any(k in name for k in ["code", "idea", "studio", "vim", "emacs", "pycharm", "devenv"]):
        return "focus"
    if any(k in name for k in ["chrome", "edge", "firefox", "whatsapp", "telegram", "discord", "youtube", "spotify"]):
        return "casual"
    return "unknown"

def decide_action(
    emotion: str,
    app_category: str,
    focus_deferral_minutes: int,
    sad_deferral_minutes: int,
    batching_enabled: bool
) -> Tuple[str, str, int]:
    """
    Returns: (action, reason, minutes)
    action ∈ {"deliver", "defer", "batch"}
    minutes is only meaningful for defer/batch.
    """
    emo = (emotion or "").lower()

    # High-friction + focus app => defer
    if emo in {"angry", "fear", "disgust"} and app_category == "focus":
        return "defer", "negative_emotion_in_focus_app", focus_deferral_minutes

    # Sad + focus app => shorter defer
    if emo == "sad" and app_category == "focus":
        return "defer", "sad_in_focus_app", sad_deferral_minutes

    # Neutral/happy in focus app => batch if enabled
    if emo in RELAXED_EMOTIONS and app_category == "focus" and batching_enabled:
        return "batch", "batch_during_deep_work", 0

    # Casual app => deliver unless clearly negative
    if app_category == "casual" and emo not in {"angry", "fear", "disgust"}:
        return "deliver", "casual_context", 0

    # Unknowns default: deliver
    return "deliver", "default", 0
