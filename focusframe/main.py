import argparse
import random
import time
import threading
from typing import Optional

from .config import load_config
from .emotion import EmotionDetector
from .apptracker import get_foreground_process_name
from .rules import map_app_category, decide_action
from .scheduler import Scheduler, Notification
from .notify import show_notification
from .storage import Store
from .dashboard import Dashboard

# ✅ Console colors
from colorama import Fore, Style, init as colorama_init
colorama_init(autoreset=True)


def colorize_emotion(emotion: str, score: float) -> str:
    emo = (emotion or "").lower()
    text = f"{emotion} ({score:.2f})"

    if emo in {"angry", "fear", "disgust"}:
        return Fore.RED + text + Style.RESET_ALL
    elif emo == "sad":
        return Fore.MAGENTA + text + Style.RESET_ALL
    elif emo == "happy":
        return Fore.GREEN + text + Style.RESET_ALL
    elif emo == "neutral":
        return Fore.YELLOW + text + Style.RESET_ALL
    elif emo == "surprise":
        return Fore.CYAN + text + Style.RESET_ALL
    return text


def main():
    ap = argparse.ArgumentParser(description="FocusFrame Local MVP")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--config", type=str, default="config.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    store = Store()
    detector = EmotionDetector(camera_index=args.camera)
    scheduler = Scheduler(batch_release_minutes=cfg.batching["release_interval_minutes"])
    dashboard = Dashboard()  # ✅ Tkinter dashboard

    print("[FocusFrame] Starting local MVP…")
    print(f"- Emotion interval: {cfg.sampling['emotion_interval_seconds']}s")
    print(f"- Decision interval: {cfg.sampling['decision_interval_seconds']}s")
    if args.demo:
        print(f"- Demo notifications every {cfg.sampling['demo_notification_period_seconds']}s")

    def focusframe_loop():
        nonlocal detector, store, scheduler, dashboard
        next_emotion_ts = 0.0
        next_decision_ts = 0.0
        next_demo_ts = time.time() + cfg.sampling["demo_notification_period_seconds"]

        last_emotion: Optional[str] = None
        last_emotion_score: float = 0.0
        last_app: Optional[str] = None
        pending_inbox = []

        try:
            while True:
                now = time.time()

                # 1) Emotion sampling
                if now >= next_emotion_ts:
                    emo = detector.read_emotion()
                    if emo:
                        last_emotion, last_emotion_score = emo
                        print("[Emotion]", colorize_emotion(last_emotion, last_emotion_score))
                        store.log("emotion", f"{last_emotion}:{last_emotion_score:.3f}")
                        show_notification("Emotion Detected", f"{last_emotion} ({last_emotion_score:.2f})")
                        dashboard.push_emotion(last_emotion, last_emotion_score)
                    else:
                        print("[Emotion] No face detected")
                        last_emotion = None
                    next_emotion_ts = now + cfg.sampling["emotion_interval_seconds"]

                # 2) App sampling
                last_app = get_foreground_process_name()
                store.log("app", last_app)

                # 3) Demo notifications
                if args.demo and now >= next_demo_ts:
                    msg = random.choice(cfg.notifications["demo_payloads"])
                    pending_inbox.append(Notification(title=f"{cfg.notifications['title_prefix']} Demo", message=msg))
                    store.log("notification", f"demo_enqueued:{msg}")
                    next_demo_ts = now + cfg.sampling["demo_notification_period_seconds"]

                # 4) Decision making
                if now >= next_decision_ts and pending_inbox:
                    app_cat = map_app_category(last_app, cfg.apps["focus"], cfg.apps["casual"])
                    carry = []
                    for note in pending_inbox:
                        action, reason, minutes = decide_action(
                            emotion=(last_emotion or "neutral"),
                            app_category=app_cat,
                            focus_deferral_minutes=cfg.deferral["focus_deferral_minutes"],
                            sad_deferral_minutes=cfg.deferral["sad_deferral_minutes"],
                            batching_enabled=cfg.batching["enabled"],
                        )
                        store.log("decision", f"{action}:{reason}:{minutes}m for {note.message}")

                        if action == "deliver":
                            print(Fore.GREEN + f"[Deliver] {note.message} • ({reason})" + Style.RESET_ALL)
                            show_notification(note.title, f"{note.message}  • ({reason})")
                        elif action == "defer":
                            print(Fore.YELLOW + f"[Defer] {note.message} for {minutes}m • ({reason})" + Style.RESET_ALL)
                            scheduler.defer(note, minutes)
                        elif action == "batch":
                            print(Fore.CYAN + f"[Batch] {note.message} (will release later) • ({reason})" + Style.RESET_ALL)
                            scheduler.batch(note)
                        else:
                            carry.append(note)
                    pending_inbox = carry
                    next_decision_ts = now + cfg.sampling["decision_interval_seconds"]

                # 5) Release due notifications
                due = scheduler.release_due()
                for n in due:
                    print(Fore.MAGENTA + f"[Release] {n.message}" + Style.RESET_ALL)
                    show_notification(f"{cfg.notifications['title_prefix']} Release", n.message + "  • (released)")

                time.sleep(0.2)
        except KeyboardInterrupt:
            print("\n[FocusFrame] Stopping…")
        finally:
            detector.close()
            store.close()

    # Run focusframe loop in background thread
    t = threading.Thread(target=focusframe_loop, daemon=True)
    t.start()

    # Run dashboard in main thread
    dashboard.run()


if __name__ == "__main__":
    main()
