# FocusFrame - Notification Management System (MVP -> Review-2 70%)

## Overview
Local, privacy-first desktop app that manages notifications based on **real-time emotion** and **active app context**. It delivers, defers, or batches notifications using a **rule engine**, logs to **SQLite**, shows a **Tkinter dashboard** (live emotion + timeline), and supports **two emotion backends**:
- `fer` (TensorFlow/Keras via `fer` package + MTCNN, 7 emotions)
- `onnx` (ONNX Runtime, FER+ 8 emotions or FER7)

## Deliverables (Review-2 >=70%)
- [x] Real-time emotion (7/8 classes) with smoothing & confidence gating
- [x] App tracker (foreground process)
- [x] Rule engine (deliver/defer/batch) + scheduler
- [x] Tkinter dashboard (current emotion + 10-bar timeline)
- [x] Desktop toasts (Plyer)
- [x] SQLite logs (emotion/app/notifications/decisions)
- [x] Config-driven (`config.yaml`) + switchable emotion backend
- [x] Pluggable structure: `backends`, `plugins/`, `profiles/`, `reports/` (stubs OK)

## Architecture
- `focusframe/main.py` - Orchestrator loop (runs in thread), Tkinter UI in main thread
- `focusframe/emotion.py` - FER backend with smoothing + confidence gating
- `focusframe/onnx_emotion.py` - ONNX backend (FER+/FER7) via onnxruntime
- `focusframe/apptracker.py` - Foreground process (Windows first)
- `focusframe/rules.py` - Rule engine (deliver/defer/batch)
- `focusframe/scheduler.py` - Deferral & batch window release
- `focusframe/notify.py` - Plyer wrapper
- `focusframe/storage.py` - SQLite events
- `focusframe/dashboard.py` - Live UI (current emotion + mini timeline)
- `config.yaml` - Sampling, deferral, batching, backend selection, thresholds

## Emotion Backends
### ONNX (preferred for demo)
- Model: FER+ 8 emotions (`emotion-ferplus-8.onnx`)
- Labels: `["neutral","happiness","surprise","sadness","anger","disgust","fear","contempt"]`
- Input: grayscale 64x64, NCHW (1x1x64x64), normalized
- Runtime: onnxruntime (CPU)
- Config:
```yaml
emotion_backend: "onnx"
onnx:
  model_path: "models/emotion-ferplus-8.onnx"
  labels: "ferplus8"
  input_size: [64, 64]
```

### FER (TensorFlow/MTCNN)
- 7 emotions, Keras model via `fer` package
- Temporal smoothing + confidence gating
- Config:
```yaml
emotion_backend: "fer"

accuracy:
  conf_threshold: 0.5
  min_face_size_px: 60
  smoothing:
    ema_alpha: 0.5
    window: 3
  unknown_label: "unknown"
```
- EMA smoothing reduces jitter; `unknown` when below threshold.

## Profiles (make project bigger)
`profiles/exam.yaml`, `profiles/focus.yaml`, `profiles/evening.yaml` - swap rules/thresholds quickly.

## Plugins (extensible story)
`plugins/` can contain `on_decision(note, state)` callbacks (stubbed for now).

## Reports
`reports/weekly.py` (stub): read SQLite and print counts per emotion, deferrals vs deliveries.

## How to run
```bash
python -m focusframe.main --demo
# switch backend in config.yaml
```

## Notes for Codex
- Always read `.codex/focusframe.md` before writing code.
- Respect `config.yaml` keys; default sensibly when missing.
- If adding UI elements, avoid blocking Tk mainloop; use queue/event pattern.
- Keep both backends working; never break FER when updating ONNX paths.

---

## Update - 2025-09-21
- Switched default backend to ONNX (FER+ 8 emotions)
- Kept FER backend as fallback with smoothing + confidence gating
- Added ONNX runtime dependency and config knobs
- Created structure for `models/`, `plugins/`, `profiles/`, `reports/`
- Next: flesh out profile loading, plugin hooks, weekly report CLI, export CSV button

## Update - 2025-09-22
- Switched runtime back to FER backend for validation (set emotion_backend: "fer")
- ONNX pipeline still available via config toggle
- Tuned sampling + smoothing for faster FER updates and added history fallback
- Refreshed dashboard UI with confidence bar, timeline bars, and stats panel

