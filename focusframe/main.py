import argparse
import random
import threading
import time
from typing import Callable, Optional

from colorama import Fore, Style, init as colorama_init

from .apptracker import get_foreground_process_name
from .config import load_config
from .dashboard import Dashboard
from .notify import show_notification
from .rules import decide_action, map_app_category
from .scheduler import Notification, Scheduler
from .storage import Store  

colorama_init(autoreset=True)


def colorize_emotion(emotion: str, score: float) -> str:
    emo = (emotion or "").lower()
    text = f"{emotion} ({score:.2f})"

    if emo in {"angry", "fear", "disgust"}:
        return Fore.RED + text + Style.RESET_ALL
    if emo == "sad":
        return Fore.MAGENTA + text + Style.RESET_ALL
    if emo == "happy" or emo == "happiness":
        return Fore.GREEN + text + Style.RESET_ALL
    if emo == "neutral":
        return Fore.YELLOW + text + Style.RESET_ALL
    if emo == "surprise":
        return Fore.CYAN + text + Style.RESET_ALL
    if emo == "contempt":
        return Fore.BLUE + text + Style.RESET_ALL
    if emo == "unknown":
        return Fore.WHITE + text + Style.RESET_ALL
    return text


def build_detector(args, cfg) -> tuple[object, Callable[[], Optional[tuple[str, float]]], str]:
    accuracy = cfg.accuracy
    smoothing = accuracy.get("smoothing", {})
    backend = str(cfg.raw.get("emotion_backend", "fer")).lower()

    if backend == "onnx":
        from .onnx_emotion import ONNXEmotionDetector as EDetector

        onnx_cfg = cfg.onnx
        model_path = onnx_cfg.get("model_path", "models/emotion-ferplus-8.onnx")
        labels = onnx_cfg.get("labels", "ferplus8")
        input_size = tuple(onnx_cfg.get("input_size", [64, 64]))

        detector = EDetector(
            model_path=model_path,
            labels=labels,
            input_size=input_size,
            conf_threshold=float(accuracy.get("conf_threshold", 0.55)),
            min_face_size_px=int(accuracy.get("min_face_size_px", 80)),
        )

        def reader() -> Optional[tuple[str, float]]:
            return detector.read_emotion(camera_index=args.camera)

        backend_name = "onnx"
    else:
        from .emotion import EmotionDetector as EDetector

        detector = EDetector(
            camera_index=args.camera,
            ema_alpha=float(smoothing.get("ema_alpha", 0.6)),
            window=int(smoothing.get("window", 7)),
            conf_threshold=float(accuracy.get("conf_threshold", 0.55)),
            min_face_size_px=int(accuracy.get("min_face_size_px", 80)),
            unknown_label=str(accuracy.get("unknown_label", "unknown")),
        )

        def reader() -> Optional[tuple[str, float]]:
            return detector.read_emotion()

        backend_name = "fer"

    return detector, reader, backend_name


def main() -> None:
    ap = argparse.ArgumentParser(description="FocusFrame Local MVP")
    ap.add_argument("--camera", type=int, default=0)
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--config", type=str, default="config.yaml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    detector, emotion_reader, backend_name = build_detector(args, cfg)
    store = Store()
    scheduler = Scheduler(batch_release_minutes=cfg.batching["release_interval_minutes"])
    dashboard = Dashboard()
    stop_event = threading.Event()

    print("[FocusFrame] Starting local MVP")
    print(f"- Emotion backend: {backend_name}")
    print(f"- Emotion interval: {cfg.sampling['emotion_interval_seconds']}s")
    print(f"- Decision interval: {cfg.sampling['decision_interval_seconds']}s")
    if args.demo:
        print(f"- Demo notifications every {cfg.sampling['demo_notification_period_seconds']}s")

    def focusframe_loop() -> None:
        nonlocal detector, store, scheduler, dashboard
        next_emotion_ts = 0.0
        next_decision_ts = 0.0
        next_demo_ts = time.time() + cfg.sampling["demo_notification_period_seconds"]

        last_emotion: Optional[str] = None
        last_emotion_score: float = 0.0
        pending_inbox: list[Notification] = []

        while not stop_event.is_set():
            now = time.time()

            if now >= next_emotion_ts:
                emo = emotion_reader()
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

            last_app = get_foreground_process_name()
            store.log("app", last_app)

            if args.demo and now >= next_demo_ts:
                msg = random.choice(cfg.notifications["demo_payloads"])
                pending_inbox.append(
                    Notification(title=f"{cfg.notifications['title_prefix']} Demo", message=msg)
                )
                store.log("notification", f"demo_enqueued:{msg}")
                next_demo_ts = now + cfg.sampling["demo_notification_period_seconds"]

            if now >= next_decision_ts and pending_inbox:
                app_cat = map_app_category(last_app, cfg.apps["focus"], cfg.apps["casual"])
                carry: list[Notification] = []
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
                        print(Fore.GREEN + f"[Deliver] {note.message} ({reason})" + Style.RESET_ALL)
                        show_notification(note.title, f"{note.message} ({reason})")
                    elif action == "defer":
                        print(
                            Fore.YELLOW
                            + f"[Defer] {note.message} for {minutes}m ({reason})"
                            + Style.RESET_ALL
                        )
                        scheduler.defer(note, minutes)
                    elif action == "batch":
                        print(
                            Fore.CYAN
                            + f"[Batch] {note.message} (will release later) ({reason})"
                            + Style.RESET_ALL
                        )
                        scheduler.batch(note)
                    else:
                        carry.append(note)
                pending_inbox = carry
                next_decision_ts = now + cfg.sampling["decision_interval_seconds"]

            due = scheduler.release_due()
            for released in due:
                print(Fore.MAGENTA + f"[Release] {released.message}" + Style.RESET_ALL)
                show_notification(
                    f"{cfg.notifications['title_prefix']} Release",
                    f"{released.message} (released)",
                )

            if stop_event.wait(0.2):
                break

    worker = threading.Thread(target=focusframe_loop, name="focusframe-loop", daemon=False)
    worker.start()

    try:
        dashboard.run()
    except KeyboardInterrupt:
        print("\n[FocusFrame] Interrupted by user")
    finally:
        stop_event.set()
        try:
            dashboard.stop()
        except AttributeError:
            pass
        worker.join(timeout=3.0)
        if worker.is_alive():
            print("[FocusFrame] Waiting for background loop to finish...")
        detector.close()
        store.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[FocusFrame] Interrupted during startup")
