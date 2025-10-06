import argparse
import threading
import time
from collections import deque
from typing import Callable, Deque, Optional

from colorama import Fore, Style, init as colorama_init

from .config import Config, load_config
from .context import ContextManager
from .dashboard import Dashboard
from .feedback import FeedbackManager
from .notifications import NotificationManager, NotificationMessage, build_sources
from .notify import show_notification
from .rules import DecisionResult, RuleEngine
from .scheduler import Scheduler
from .storage import Store

colorama_init(autoreset=True)


def colorize_emotion(emotion: str, score: float) -> str:
    emo = (emotion or "").lower()
    text = f"{emotion} ({score:.2f})"

    if emo in {"angry", "fear", "disgust"}:
        return Fore.RED + text + Style.RESET_ALL
    if emo == "sad":
        return Fore.MAGENTA + text + Style.RESET_ALL
    if emo in {"happy", "happiness"}:
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


def build_detector(args: argparse.Namespace, cfg: Config) -> tuple[object, Callable[[], Optional[tuple[str, float]]], str]:
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


def log_decision(
    store: Store,
    note: NotificationMessage,
    decision: DecisionResult,
    context_data: dict,
    emotion_label: Optional[str],
    emotion_score: float,
) -> None:
    payload = {
        "notification_id": note.id,
        "rule_id": decision.rule_id,
        "action": decision.action,
        "reason": decision.reason,
        "minutes": decision.minutes,
        "emotion": emotion_label,
        "emotion_score": emotion_score,
        "context": context_data,
    }
    store.log_json("decision", payload)


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
    dashboard = Dashboard(store=store)
    rule_engine = RuleEngine(store, cfg)
    context_manager = ContextManager(cfg.context, cfg.calendar, cfg.apps)
    notification_sources = build_sources(cfg.notifications, demo_mode=args.demo)
    notification_manager = NotificationManager(notification_sources)

    feedback_cfg = cfg.feedback
    feedback_manager = FeedbackManager(
        store,
        enabled=bool(feedback_cfg.get("enabled", True)),
        prompt=bool(feedback_cfg.get("prompt", True)),
    )
    feedback_manager.start()

    poll_interval = int(cfg.notifications.get("poll_interval_seconds", 5))
    context_log_interval = float(cfg.context.get("log_interval_seconds", cfg.sampling["decision_interval_seconds"]))
    next_notification_poll = time.time() + poll_interval
    next_context_log_ts = 0.0

    stop_event = threading.Event()

    print("[FocusFrame] Starting local MVP")
    print(f"- Emotion backend: {backend_name}")
    print(f"- Emotion interval: {cfg.sampling['emotion_interval_seconds']}s")
    print(f"- Decision interval: {cfg.sampling['decision_interval_seconds']}s")
    print(f"- Notification sources: {[src.source_id for src in notification_sources]}")

    pending_inbox: Deque[NotificationMessage] = deque()
    next_emotion_ts = 0.0
    next_decision_ts = 0.0

    last_emotion: Optional[str] = None
    last_emotion_score: float = 0.0

    def focusframe_loop() -> None:
        nonlocal pending_inbox, next_emotion_ts, next_decision_ts
        nonlocal next_notification_poll, next_context_log_ts
        nonlocal last_emotion, last_emotion_score

        while not stop_event.is_set():
            now = time.time()
            context_snapshot = context_manager.snapshot()
            context_data = context_snapshot.as_dict()
            dashboard.push_context(context_data)

            if now >= next_context_log_ts:
                store.log_context(context_data)
                next_context_log_ts = now + context_log_interval

            if now >= next_notification_poll:
                new_notes = notification_manager.poll()
                for note in new_notes:
                    pending_inbox.append(note)
                    store.log_json("notification", note.to_dict())
                next_notification_poll = now + poll_interval

            if now >= next_emotion_ts:
                emo = emotion_reader()
                if emo:
                    emotion_label, emotion_score = emo
                    store.log("emotion", f"{emotion_label}:{emotion_score:.3f}")
                    print("[Emotion]", colorize_emotion(emotion_label, emotion_score))
                    show_notification("Emotion Detected", f"{emotion_label} ({emotion_score:.2f})")
                    dashboard.push_emotion(emotion_label, emotion_score)
                    last_emotion, last_emotion_score = emotion_label, emotion_score
                else:
                    print("[Emotion] No face detected")
                    last_emotion = None
                next_emotion_ts = now + cfg.sampling["emotion_interval_seconds"]

            if pending_inbox and now >= next_decision_ts:
                decisions_to_process = len(pending_inbox)
                carry: Deque[NotificationMessage] = deque()
                for _ in range(decisions_to_process):
                    note = pending_inbox.popleft()
                    decision = rule_engine.decide(
                        emotion=last_emotion or "neutral",
                        context=context_snapshot,
                        notification=note,
                    )
                    log_decision(store, note, decision, context_data, last_emotion, last_emotion_score)

                    if decision.action == "deliver":
                        print(
                            Fore.GREEN
                            + f"[Deliver] {note.message} ({decision.reason})"
                            + Style.RESET_ALL
                        )
                        show_notification(note.title, f"{note.message} ({decision.reason})")
                        feedback_manager.enqueue_delivery(
                            note,
                            rule_id=decision.rule_id,
                            decision_reason=decision.reason,
                            context=context_data,
                            emotion=last_emotion,
                            emotion_score=last_emotion_score,
                        )
                    elif decision.action == "defer":
                        print(
                            Fore.YELLOW
                            + f"[Defer] {note.message} for {decision.minutes}m ({decision.reason})"
                            + Style.RESET_ALL
                        )
                        scheduler.defer(note, decision.minutes)
                        store.log_feedback(
                            note.id,
                            "deferred",
                            {
                                "rule_id": decision.rule_id,
                                "reason": decision.reason,
                                "minutes": decision.minutes,
                                "emotion": last_emotion,
                                "context": context_data,
                            },
                        )
                    elif decision.action == "batch":
                        print(
                            Fore.CYAN
                            + f"[Batch] {note.message} (will release later) ({decision.reason})"
                            + Style.RESET_ALL
                        )
                        scheduler.batch(note)
                        store.log_feedback(
                            note.id,
                            "batched",
                            {
                                "rule_id": decision.rule_id,
                                "reason": decision.reason,
                                "emotion": last_emotion,
                                "context": context_data,
                            },
                        )
                    else:
                        carry.append(note)
                pending_inbox.extend(carry)
                next_decision_ts = now + cfg.sampling["decision_interval_seconds"]

            due = scheduler.release_due()
            for released in due:
                print(Fore.MAGENTA + f"[Release] {released.message}" + Style.RESET_ALL)
                show_notification(
                    f"{cfg.notifications['title_prefix']} Release",
                    f"{released.message} (released)",
                )
                store.log_feedback(
                    released.id,
                    "released",
                    {
                        "emotion": last_emotion,
                        "context": context_data,
                    },
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
        feedback_manager.stop()
        detector.close()
        store.close()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[FocusFrame] Interrupted during startup")
