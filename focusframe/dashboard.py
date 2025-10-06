import json
import queue
import threading
import tkinter as tk
from collections import Counter
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple

from .analytics import Analytics
from .reports import summary_text, export_events
from .rules import DEFAULT_RULES
from .storage import Store


class LiveFeedTab:
    MAX_HISTORY = 40

    def __init__(self, parent: ttk.Notebook, style: ttk.Style) -> None:
        self.frame = ttk.Frame(parent, padding=(24, 18), style="Card.TFrame")
        parent.add(self.frame, text="Live Feed")

        self.queue: "queue.Queue[Tuple[str, float]]" = queue.Queue()
        self.history: List[Tuple[str, float]] = []
        self.latest_context: Optional[Dict[str, object]] = None

        header = ttk.Label(
            self.frame,
            text="FocusFrame - Live Emotion Console",
            style="Title.TLabel",
        )
        header.grid(row=0, column=0, columnspan=2, sticky="w")

        current_card = ttk.Frame(self.frame, style="Card.TFrame", padding=(18, 12))
        current_card.grid(row=1, column=0, sticky="nsew", padx=(0, 16), pady=(16, 0))

        self.emotion_label = ttk.Label(current_card, text="Waiting...", style="Emotion.TLabel")
        self.emotion_label.grid(row=0, column=0, sticky="w")

        self.confidence_label = ttk.Label(current_card, text="Confidence: --", style="Card.TLabel")
        self.confidence_label.grid(row=1, column=0, sticky="w", pady=(6, 0))

        self.confidence_bar = ttk.Progressbar(
            current_card,
            orient="horizontal",
            length=260,
            mode="determinate",
        )
        self.confidence_bar.grid(row=2, column=0, sticky="we", pady=(4, 12))

        self.context_text = tk.Text(
            current_card,
            height=8,
            width=48,
            bg="#10131a",
            fg="#d8e2ff",
            bd=0,
            highlightthickness=0,
            font=("Consolas", 11),
            state="disabled",
        )
        self.context_text.grid(row=3, column=0, sticky="nsew")
        current_card.rowconfigure(3, weight=1)

        history_card = ttk.Frame(self.frame, style="Card.TFrame", padding=(18, 12))
        history_card.grid(row=1, column=1, sticky="nsew", pady=(16, 0))

        history_header = ttk.Label(history_card, text="Recent Snapshots", style="Card.TLabel")
        history_header.pack(anchor="w")

        self.history_panel = tk.Text(
            history_card,
            height=12,
            width=44,
            bg="#0d111a",
            fg="#d8e2ff",
            bd=0,
            highlightthickness=0,
            font=("Consolas", 11),
            state="disabled",
        )
        self.history_panel.pack(fill="both", expand=True, pady=(8, 12))

        self.meta_label = ttk.Label(history_card, text="Awaiting signal...", style="Meta.TLabel", justify="left")
        self.meta_label.pack(anchor="w")

        timeline_card = ttk.Frame(self.frame, style="Card.TFrame", padding=(16, 12))
        timeline_card.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(18, 0))
        ttk.Label(
            timeline_card,
            text="Emotion Timeline",
            style="Card.TLabel",
        ).pack(anchor="w")

        self.timeline_canvas = tk.Canvas(
            timeline_card,
            height=140,
            bg="#0d111a",
            highlightthickness=0,
            bd=0,
        )
        self.timeline_canvas.pack(fill="both", expand=True, pady=(12, 0))

        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        self.frame.rowconfigure(2, weight=1)

    def schedule(self, root: tk.Tk) -> None:
        self._drain_queue()
        root.after(120, lambda: self.schedule(root))

    def _drain_queue(self) -> None:
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
        if self.latest_context is not None:
            self._render_context(self.latest_context)

    def push_emotion(self, emotion: str, score: float) -> None:
        self.queue.put((emotion, score))

    def update_context(self, context: Dict[str, object]) -> None:
        self.latest_context = context

    def _push_history(self, emotion: str, score: float) -> None:
        self.history.append((emotion, score))
        if len(self.history) > self.MAX_HISTORY:
            self.history.pop(0)

    def _render_current(self, emotion: str, score: float) -> None:
        display = emotion.replace("_", " ").title()
        self.emotion_label.config(text=display)
        self.confidence_label.config(text=f"Confidence: {score:.0%}")
        self.confidence_bar.config(value=max(0, min(100, int(score * 100))))

    def _render_history(self) -> None:
        rows = [f"{name[:12].ljust(12)} | {score:0.2f}" for name, score in reversed(self.history[-12:])]
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
        height = self.timeline_canvas.winfo_height() or 140
        bar_width = width / max(1, len(self.history))

        for idx, (emotion, score) in enumerate(self.history):
            color = self.get_color(emotion)
            x0 = idx * bar_width
            x1 = x0 + bar_width - 4
            bar_height = max(12, score * height)
            y0 = height - bar_height
            self.timeline_canvas.create_rectangle(x0, y0, x1, height, fill=color, outline="")
            if bar_width >= 26:
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

    def _render_context(self, context: Dict[str, object]) -> None:
        summary_keys = [
            ("active_app", "App"),
            ("app_category", "Category"),
            ("day_segment", "Segment"),
            ("calendar_state", "Calendar"),
            ("calendar_event", "Event"),
            ("cpu_percent", "CPU%"),
            ("memory_percent", "Memory%"),
            ("net_bytes_sent", "Net Sent"),
            ("net_bytes_recv", "Net Recv"),
            ("top_process", "Top Proc"),
        ]
        rows = []
        for key, label in summary_keys:
            value = context.get(key)
            if value is None:
                continue
            if isinstance(value, float):
                if "percent" in key:
                    value = f"{value:.1f}"
                elif "net_bytes" in key:
                    value = f"{value/1024/1024:.1f} MB"
            rows.append(f"{label:>10}: {value}")
        buffer = "\n".join(rows) if rows else "Context unavailable"
        self.context_text.configure(state="normal")
        self.context_text.delete("1.0", tk.END)
        self.context_text.insert(tk.END, buffer)
        self.context_text.configure(state="disabled")

    @staticmethod
    def get_color(emotion: str) -> str:
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


class RulesTab:
    COLUMNS = ("rule_id", "priority", "action", "reason", "minutes", "condition")

    def __init__(self, parent: ttk.Notebook, store: Store, style: ttk.Style) -> None:
        self.store = store
        self.frame = ttk.Frame(parent, padding=(18, 16), style="Card.TFrame")
        parent.add(self.frame, text="Rules Studio")

        header = ttk.Label(self.frame, text="Rule Catalogue", style="Title.TLabel")
        header.grid(row=0, column=0, sticky="w")

        instructions = ttk.Label(
            self.frame,
            text="Double-click a cell to edit. Press Enter or click away to commit.",
            style="Meta.TLabel",
        )
        instructions.grid(row=1, column=0, columnspan=3, sticky="w", pady=(4, 12))

        self.tree = ttk.Treeview(
            self.frame,
            columns=self.COLUMNS,
            show="headings",
            selectmode="browse",
            height=12,
        )
        headings = {
            "rule_id": "Rule ID",
            "priority": "Priority",
            "action": "Action",
            "reason": "Reason",
            "minutes": "Minutes",
            "condition": "Condition (JSON)",
        }
        widths = {
            "rule_id": 160,
            "priority": 80,
            "action": 120,
            "reason": 200,
            "minutes": 90,
            "condition": 320,
        }
        for column in self.COLUMNS:
            self.tree.heading(column, text=headings[column])
            anchor = "w" if column in {"rule_id", "reason", "condition"} else "center"
            self.tree.column(column, width=widths[column], anchor=anchor)
        self.tree.grid(row=2, column=0, columnspan=3, sticky="nsew")

        self.tree.bind("<Double-1>", self._on_double_click)

        button_frame = ttk.Frame(self.frame, style="Card.TFrame")
        button_frame.grid(row=3, column=0, columnspan=3, sticky="we", pady=(12, 0))
        ttk.Button(button_frame, text="Refresh", command=self.refresh).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(button_frame, text="Apply Changes", command=self.apply_changes).pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(button_frame, text="Reset Selected", command=self.reset_selected).pack(side=tk.LEFT)

        self.status_var = tk.StringVar(value="Double-click to edit a rule")
        ttk.Label(self.frame, textvariable=self.status_var, style="Meta.TLabel").grid(
            row=4, column=0, columnspan=3, sticky="we", pady=(12, 0)
        )

        self.frame.columnconfigure(0, weight=1)
        self.frame.columnconfigure(1, weight=1)
        self.frame.columnconfigure(2, weight=1)
        self.frame.rowconfigure(2, weight=1)

        self.current_rules: Dict[str, Dict[str, object]] = {}
        self.modified: Dict[str, Dict[str, str]] = {}
        self._editor: Optional[tk.Entry] = None
        self._editing: Optional[Tuple[str, str]] = None

        self.refresh()

    def refresh(self) -> None:
        try:
            rows = self.store.fetch_rules()
        except Exception as exc:
            self.status_var.set(f"Failed to load rules: {exc}")
            return
        self.current_rules = {row["id"]: row for row in rows}
        self.modified.clear()
        self.tree.delete(*self.tree.get_children())
        for row in rows:
            params = row.get("parameters") or {}
            minutes = params.get("minutes")
            condition = json.dumps(row.get("condition", {}), ensure_ascii=False)
            values = (
                row["id"],
                str(row.get("priority", "")),
                str(row.get("action", "")),
                str(params.get("reason", "")),
                str(minutes) if minutes is not None else "",
                condition,
            )
            self.tree.insert("", tk.END, iid=row["id"], values=values)
        self.status_var.set(f"Loaded {len(rows)} rules")

    def _on_double_click(self, event: tk.Event) -> None:
        item = self.tree.identify_row(event.y)
        column = self.tree.identify_column(event.x)
        if not item or not column:
            return
        self._start_edit(item, column)

    def _start_edit(self, item: str, column: str) -> None:
        col_index = int(column.replace('#', '')) - 1
        if col_index < 0 or col_index >= len(self.COLUMNS):
            return
        column_key = self.COLUMNS[col_index]
        if column_key == "rule_id":
            return

        bbox = self.tree.bbox(item, column)
        if not bbox:
            return
        x, y, width, height = bbox
        value = self.tree.set(item, column_key)

        if self._editor:
            self._editor.destroy()

        self._editor = tk.Entry(self.tree)
        self._editor.insert(0, value)
        self._editor.select_range(0, tk.END)
        self._editor.focus()
        self._editor.place(x=x, y=y, width=width, height=height)
        self._editing = (item, column_key)

        self._editor.bind("<Return>", lambda e: self._commit_edit())
        self._editor.bind("<Escape>", lambda e: self._cancel_edit())
        self._editor.bind("<FocusOut>", lambda e: self._commit_edit())

    def _commit_edit(self) -> None:
        if not self._editing or not self._editor:
            return
        item, column_key = self._editing
        new_value = self._editor.get().strip()
        self.tree.set(item, column_key, new_value)
        self.modified.setdefault(item, {})[column_key] = new_value
        self._editor.destroy()
        self._editor = None
        self._editing = None
        self.status_var.set(f"Edited {column_key} for {item} (pending apply)")

    def _cancel_edit(self) -> None:
        if self._editor:
            self._editor.destroy()
        self._editor = None
        self._editing = None

    def apply_changes(self) -> None:
        if not self.modified:
            self.status_var.set("No edits to apply")
            return
        applied = 0
        for rule_id in list(self.modified.keys()):
            original = self.current_rules.get(rule_id)
            if not original:
                continue
            values = self.tree.item(rule_id, "values")
            value_map = dict(zip(self.COLUMNS, values))
            try:
                priority = int(value_map["priority"])
            except ValueError:
                self.status_var.set(f"Priority must be integer for {rule_id}")
                return
            action = value_map["action"].strip() or original.get("action", "")
            reason = value_map["reason"].strip()
            minutes_raw = value_map["minutes"].strip()
            try:
                minutes = int(minutes_raw) if minutes_raw else None
            except ValueError:
                self.status_var.set(f"Minutes must be integer for {rule_id}")
                return
            condition_raw = value_map["condition"].strip() or "{}"
            try:
                condition = json.loads(condition_raw)
            except json.JSONDecodeError as exc:
                self.status_var.set(f"Condition JSON invalid for {rule_id}: {exc}")
                return

            params = dict(original.get("parameters", {}))
            params["reason"] = reason
            if minutes is not None:
                params["minutes"] = minutes
            else:
                params.pop("minutes", None)

            updated = {
                "id": rule_id,
                "name": original.get("name", rule_id),
                "priority": priority,
                "condition": condition,
                "action": action,
                "parameters": params,
            }
            try:
                self.store.upsert_rule(updated)
            except Exception as exc:
                self.status_var.set(f"Failed to update {rule_id}: {exc}")
                return
            applied += 1
        self.status_var.set(f"Applied {applied} rule update(s)")
        self.refresh()

    def reset_selected(self) -> None:
        selection = self.tree.selection()
        if not selection:
            self.status_var.set("Select a rule to reset")
            return
        rule_id = selection[0]
        default_lookup = {rule["id"]: rule for rule in DEFAULT_RULES}
        default = default_lookup.get(rule_id)
        if not default:
            self.status_var.set("No default definition available")
            return
        try:
            self.store.upsert_rule(default)
        except Exception as exc:
            self.status_var.set(f"Failed to reset {rule_id}: {exc}")
            return
        self.status_var.set(f"Reset {rule_id} to default")
        self.refresh()


class InsightsTab:
    REFRESH_INTERVAL_MS = 5000

    def __init__(self, parent: ttk.Notebook, analytics: Analytics, style: ttk.Style) -> None:
        self.analytics = analytics
        self.frame = ttk.Frame(parent, padding=(18, 16), style="Card.TFrame")
        parent.add(self.frame, text="Insights")

        header = ttk.Label(self.frame, text="Operational Insights", style="Title.TLabel")
        header.grid(row=0, column=0, columnspan=3, sticky="w")

        self.emotion_tree = self._build_tree(
            self.frame,
            columns=("count", "avg"),
            headings={"count": "Count", "avg": "Avg Confidence"},
            column_widths={"count": 80, "avg": 120},
        )
        self.emotion_tree.grid(row=1, column=0, sticky="nsew", pady=(12, 0))
        ttk.Label(self.frame, text="Emotion Trends", style="Card.TLabel").grid(row=2, column=0, sticky="w", pady=(4, 16))

        self.decision_tree = self._build_tree(
            self.frame,
            columns=("count",),
            headings={"count": "Count"},
            column_widths={"count": 80},
        )
        self.decision_tree.grid(row=1, column=1, sticky="nsew", padx=(16, 0), pady=(12, 0))
        ttk.Label(self.frame, text="Decision Mix", style="Card.TLabel").grid(row=2, column=1, sticky="w", pady=(4, 16))

        self.feedback_tree = self._build_tree(
            self.frame,
            columns=("count", "latency"),
            headings={"count": "Count", "latency": "Avg Latency (s)"},
            column_widths={"count": 80, "latency": 140},
        )
        self.feedback_tree.grid(row=1, column=2, sticky="nsew", padx=(16, 0), pady=(12, 0))
        ttk.Label(self.frame, text="Feedback Outcomes", style="Card.TLabel").grid(row=2, column=2, sticky="w", pady=(4, 16))

        self.rule_tree = self._build_tree(
            self.frame,
            columns=("action", "decisions", "overrides", "note"),
            headings={"action": "Action", "decisions": "Decisions", "overrides": "Overrides", "note": "Insight"},
            column_widths={"action": 120, "decisions": 90, "overrides": 100, "note": 220},
        )
        self.rule_tree.grid(row=3, column=0, columnspan=3, sticky="nsew", pady=(12, 0))
        ttk.Label(self.frame, text="Rule Insights", style="Card.TLabel").grid(row=4, column=0, sticky="w", pady=(4, 0))

        self.status_var = tk.StringVar(value="Refreshing analytics...")
        ttk.Label(self.frame, textvariable=self.status_var, style="Meta.TLabel").grid(row=5, column=0, columnspan=3, sticky="we", pady=(12, 0))

        for col in range(3):
            self.frame.columnconfigure(col, weight=1)
        self.frame.rowconfigure(1, weight=1)
        self.frame.rowconfigure(3, weight=1)

        self._lock = threading.Lock()

    def schedule(self, root: tk.Tk) -> None:
        threading.Thread(target=self._refresh_async, daemon=True).start()
        root.after(self.REFRESH_INTERVAL_MS, lambda: self.schedule(root))

    def _refresh_async(self) -> None:
        if self._lock.locked():
            return
        with self._lock:
            try:
                emotions = self.analytics.emotion_overview(limit=200)
                decisions = self.analytics.decision_mix(limit=200)
                feedback = self.analytics.feedback_outcomes(limit=200)
                insights = self.analytics.rule_insights(limit=200)
            except Exception as exc:
                self.status_var.set(f"Analytics error: {exc}")
                return

        def update_ui() -> None:
            self._populate_tree(
                self.emotion_tree,
                [(stat.label, stat.count, f"{stat.average_confidence:.2f}") for stat in emotions],
            )
            self._populate_tree(
                self.decision_tree,
                [(stat.action, stat.count) for stat in decisions],
            )
            self._populate_tree(
                self.feedback_tree,
                [
                    (
                        stat.outcome,
                        stat.count,
                        f"{stat.average_latency:.2f}",
                    )
                    for stat in feedback
                ],
            )
            self._populate_tree(
                self.rule_tree,
                [
                    (
                        insight.action,
                        insight.decision_count,
                        insight.feedback_overrides,
                        insight.message,
                    )
                    for insight in insights
                ],
            )
            self.status_var.set("Analytics updated")

        try:
            self.frame.after_idle(update_ui)
        except tk.TclError:
            pass

    def _build_tree(
        self,
        parent: ttk.Frame,
        *,
        columns: Tuple[str, ...],
        headings: Dict[str, str],
        column_widths: Dict[str, int],
    ) -> ttk.Treeview:
        tree = ttk.Treeview(parent, columns=columns, show="headings", height=10)
        for column in columns:
            tree.heading(column, text=headings.get(column, column.title()))
            tree.column(column, width=column_widths.get(column, 120), anchor="center")
        return tree

    def _populate_tree(self, tree: ttk.Treeview, rows: List[Tuple]) -> None:
        tree.delete(*tree.get_children())
        for row in rows:
            tree.insert("", tk.END, values=row)


class Dashboard:
    def __init__(self, store: Store, db_path: Optional[str] = None) -> None:
        self.store = store
        self.db_path = db_path or store.path
        self.analytics = Analytics(self.db_path)

        self.root = tk.Tk()
        self.root.title("FocusFrame")
        self.root.geometry("960x640")
        self.root.configure(bg="#10131a")
        self.root.minsize(880, 560)
        self.root.protocol("WM_DELETE_WINDOW", self.stop)

        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except (tk.TclError, RuntimeError):
            pass
        self.style.configure("Card.TFrame", background="#151b29")
        self.style.configure("Card.TLabel", background="#151b29", foreground="#f5f5f5", font=("Segoe UI", 12))
        self.style.configure("Title.TLabel", background="#10131a", foreground="#8ab4ff", font=("Segoe UI", 16, "bold"))
        self.style.configure("Emotion.TLabel", background="#151b29", foreground="#ffffff", font=("Segoe UI", 42, "bold"))
        self.style.configure("Meta.TLabel", background="#151b29", foreground="#aeb9d6", font=("Segoe UI", 11))

        self._build_menu()

        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=12, pady=12)

        self.live_tab = LiveFeedTab(self.notebook, self.style)
        self.rules_tab = RulesTab(self.notebook, store, self.style)
        self.insights_tab = InsightsTab(self.notebook, self.analytics, self.style)

        self.live_tab.schedule(self.root)
        self.insights_tab.schedule(self.root)

    def _build_menu(self) -> None:
        menubar = tk.Menu(self.root)
        reports_menu = tk.Menu(menubar, tearoff=0)
        reports_menu.add_command(label="Copy Summary", command=self.copy_summary)
        reports_menu.add_command(label="Export Events to CSV", command=self.export_events_csv)
        menubar.add_cascade(label="Reports", menu=reports_menu)
        self.root.config(menu=menubar)

    def copy_summary(self) -> None:
        try:
            summary = summary_text(self.db_path, limit=500)
        except Exception as exc:
            messagebox.showerror("Reports", f"Failed to build summary: {exc}")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(summary)
        messagebox.showinfo("Reports", "Summary copied to clipboard")

    def export_events_csv(self) -> None:
        filename = filedialog.asksaveasfilename(
            title="Export FocusFrame Events",
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All Files", "*.*")],
            initialfile="focusframe-events.csv",
        )
        if not filename:
            return
        try:
            destination = export_events(self.db_path, Path(filename), ["emotion", "decision", "feedback"])
        except Exception as exc:
            messagebox.showerror("Reports", f"Failed to export: {exc}")
            return
        messagebox.showinfo("Reports", f"Exported events to {destination}")

    def push_emotion(self, emotion: str, score: float) -> None:
        self.live_tab.push_emotion(emotion, score)

    def push_context(self, context: Dict[str, object]) -> None:
        self.live_tab.update_context(context)

    def run(self) -> None:
        try:
            self.root.mainloop()
        finally:
            try:
                self.root.destroy()
            except (tk.TclError, RuntimeError):
                pass

    def stop(self) -> None:
        try:
            self.root.quit()
        except (tk.TclError, RuntimeError):
            pass
