import tkinter as tk
import queue


class Dashboard:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("FocusFrame – Live Emotions")
        self.root.geometry("500x300")
        self.root.configure(bg="black")

        # Queue for inter-thread communication
        self.queue = queue.Queue()

        # Label for current emotion
        self.label = tk.Label(
            self.root,
            text="Waiting...",
            font=("Arial", 36, "bold"),
            fg="white",
            bg="black"
        )
        self.label.pack(expand=True, pady=20)

        # Canvas for timeline
        self.timeline_canvas = tk.Canvas(self.root, width=480, height=60, bg="black", highlightthickness=0)
        self.timeline_canvas.pack(pady=10)

        # Emotion history
        self.history = []  # [(emotion, score), ...]

        # Periodic UI update
        self.update_ui()

    def update_ui(self):
        try:
            while True:
                emotion, score = self.queue.get_nowait()
                self.history.append((emotion, score))
                if len(self.history) > 10:  # keep last 10
                    self.history.pop(0)

                # Update main label
                color = self.get_color(emotion)
                self.label.config(
                    text=f"{emotion.capitalize()} ({score:.2f})",
                    fg=color
                )

                # Update timeline
                self.draw_timeline()

        except queue.Empty:
            pass
        self.root.after(200, self.update_ui)

    def draw_timeline(self):
        self.timeline_canvas.delete("all")
        bar_width = 480 // max(1, len(self.history))
        for i, (emotion, score) in enumerate(self.history):
            color = self.get_color(emotion)
            x0 = i * bar_width
            x1 = x0 + bar_width - 2
            self.timeline_canvas.create_rectangle(x0, 0, x1, 60, fill=color, outline="")
            self.timeline_canvas.create_text(
                (x0 + x1) // 2, 30,
                text=emotion[0].upper(),  # just the first letter
                fill="black",
                font=("Arial", 14, "bold")
            )

    def get_color(self, emotion: str) -> str:
        e = (emotion or "").lower()
        if e in {"angry", "fear", "disgust"}:
            return "red"
        elif e == "sad":
            return "magenta"
        elif e == "happy":
            return "green"
        elif e == "neutral":
            return "yellow"
        elif e == "surprise":
            return "cyan"
        return "white"

    def push_emotion(self, emotion: str, score: float):
        self.queue.put((emotion, score))

    def run(self):
        """Start Tkinter mainloop (must be called in main thread)."""
        self.root.mainloop()
