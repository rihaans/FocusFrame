import queue
import tkinter as tk
from collections import Counter
from tkinter import ttk
from typing import List, Tuple


class Dashboard:
    """Tkinter dashboard showing current emotion, confidence, and recent history."""

    MAX_HISTORY = 20

    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("FocusFrame - Live Emotion Console")
        self.root.geometry("760x460")
        self.root.configure(bg="#10131a")
        self.root.minsize(720, 420)

        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure("Card.TFrame", background="#151b29")
        self.style.configure("Card.TLabel", background="#151b29", foreground="#f5f5f5", font=("Segoe UI", 12))
        self.style.configure("Title.TLabel", background="#10131a", foreground="#8ab4ff", font=("Segoe UI", 16, "bold"))
        self.style.configure("Emotion.TLabel", background="#151b29", foreground="#ffffff", font=("Segoe UI", 40, "bold"))
        self.style.configure("Meta.TLabel", background="#151b29", foreground="#aeb9d6", font=("Segoe UI", 11))

        self.queue: "queue.Queue[Tuple[str, float]]" = queue.Queue()
        self.history: List[Tuple[str, float]] = []

        self._build_layout()
        self.update_ui()

    def _build_layout(self) -> None:
        header = ttk.Label(self.root, text="FocusFrame - Emotion Operations", style="Title.TLabel")
        header.pack(anchor="w", padx=24, pady=(20, 10))

        content = ttk.Frame(self.root, style="Card.TFrame", padding=(24, 18))
        content.pack(fill="both", expand=True, padx=24, pady=(0, 24))

        self.emotion_label = ttk.Label(content, text="Waiting...", style="Emotion.TLabel")
        self.emotion_label.grid(row=0, column=0, sticky="w", pady=(0, 12))

        self.confidence_label = ttk.Label(content, text="Confidence: --", style="Card.TLabel")
        self.confidence_label.grid(row=1, column=0, sticky="w")

        self.confidence_bar = ttk.Progressbar(content, orient="horizontal", length=260, mode="determinate")
        self.confidence_bar.grid(row=2, column=0, sticky="w", pady=(6, 18))

        right_card = ttk.Frame(content, style="Card.TFrame", padding=(16, 16))
        right_card.grid(row=0, column=1, rowspan=3, sticky="nsew", padx=(32, 0))
        content.columnconfigure(1, weight=1)
        content.rowconfigure(3, weight=1)

        title = ttk.Label(right_card, text="Recent Snapshots", style="Card.TLabel")
        title.pack(anchor="w")

        self.history_panel = tk.Text(
            right_card,
            height=8,
            width=32,
            bg="#0d111a",
            fg="#d8e2ff",
            bd=0,
            highlightthickness=0,
            font=("Consolas", 11),
            state="disabled",
        )
        self.history_panel.pack(fill="both", expand=True, pady=(10, 12))

        self.meta_label = ttk.Label(right_card, text="Awaiting signal...", style="Meta.TLabel", justify="left")
        self.meta_label.pack(anchor="w")

        timeline_card = ttk.Frame(content, style="Card.TFrame", padding=(0, 16))
        timeline_card.grid(row=3, column=0, columnspan=2, sticky="nsew", pady=(24, 0))
        timeline_card.columnconfigure(0, weight=1)
        content.rowconfigure(3, weight=1)

        ttk.Label(timeline_card, text=f"Last {self.MAX_HISTORY} Emotions", style="Card.TLabel").pack(anchor="w", padx=16)

        self.timeline_canvas = tk.Canvas(
            timeline_card,
            height=120,
            bg="#0d111a",
            highlightthickness=0,
            bd=0,
        )
        self.timeline_canvas.pack(fill="both", expand=True, padx=16, pady=(12, 0))

    def update_ui(self) -> None:
        updated = False
        try:
            while True:
                emotion, score = self.queue.get_nowait()
                self._push_history(emotion, score)
                self._render_current(emotion, score)
                updated = True
        except queue.Empty:
            pass

        if updated:
            self._render_history()
            self._render_timeline()
            self._render_meta()

        self.root.after(120, self.update_ui)

    def _push_history(self, emotion: str, score: float) -> None:
        self.history.append((emotion, score))
        if len(self.history) > self.MAX_HISTORY:
            self.history.pop(0)

    def _render_current(self, emotion: str, score: float) -> None:
        display = emotion.replace("_", " ").title()
        self.emotion_label.config(text=display)
        self.confidence_label.config(text=f"Confidence: {score:.0%}")
        self.confidence_bar.config(value=max(0, min(100, int(score * 100))))
        self.confidence_bar.update_idletasks()

    def _render_history(self) -> None:
        rows = [f"{name[:12].ljust(12)} | {score:0.2f}" for name, score in reversed(self.history[-8:])]
        buffer = "\n".join(rows) if rows else "Awaiting signal..."
        self.history_panel.configure(state="normal")
        self.history_panel.delete("1.0", tk.END)
        self.history_panel.insert(tk.END, buffer)
        self.history_panel.configure(state="disabled")

    def _render_timeline(self) -> None:
        self.timeline_canvas.delete("all")
        if not self.history:
            return

        width = self.timeline_canvas.winfo_width() or 640
        height = self.timeline_canvas.winfo_height() or 120
        bar_width = width / max(1, len(self.history))

        for idx, (emotion, score) in enumerate(self.history):
            color = self.get_color(emotion)
            x0 = idx * bar_width
            x1 = x0 + bar_width - 4
            bar_height = max(12, score * height)
            y0 = height - bar_height
            self.timeline_canvas.create_rectangle(x0, y0, x1, height, fill=color, outline="")
            self.timeline_canvas.create_text(
                x0 + bar_width / 2,
                y0 - 10,
                text=emotion[:3].upper(),
                fill="#8ab4ff",
                font=("Segoe UI", 9, "bold"),
            )

    def _render_meta(self) -> None:
        if not self.history:
            self.meta_label.config(text="Awaiting signal...")
            return

        counts = Counter(emotion for emotion, _ in self.history)
        top = counts.most_common(3)
        sparkline = "  ".join(f"{emo[:3].upper()} x{count}" for emo, count in top)
        avg_conf = sum(score for _, score in self.history) / len(self.history)
        text = (
            f"Top emotions: {sparkline}\n"
            f"Rolling confidence: {avg_conf:.0%}\n"
            f"Samples captured: {len(self.history)}"
        )
        self.meta_label.config(text=text)

    def get_color(self, emotion: str) -> str:
        lookup = {
            "angry": "#ff6b6b",
            "fear": "#ff922b",
            "disgust": "#a5f08b",
            "sad": "#748ffc",
            "happy": "#63e6be",
            "happiness": "#63e6be",
            "neutral": "#f5d376",
            "surprise": "#4dabf7",
            "contempt": "#faa2c1",
            "unknown": "#ced4da",
        }
        return lookup.get((emotion or "").lower(), "#dee2e6")

    def push_emotion(self, emotion: str, score: float) -> None:
        self.queue.put((emotion, score))

    def run(self) -> None:
        self.root.mainloop()
