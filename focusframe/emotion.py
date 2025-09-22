from collections import Counter
from typing import Dict, List, Optional, Tuple

import cv2
from fer import FER


class EmotionDetector:
    def __init__(
        self,
        camera_index: int = 0,
        ema_alpha: float = 0.6,
        window: int = 7,
        conf_threshold: float = 0.55,
        min_face_size_px: int = 80,
        unknown_label: str = "unknown",
    ) -> None:
        self.camera_index = camera_index
        self.ema_alpha = float(ema_alpha)
        self.window = max(1, int(window))
        self.conf_threshold = float(conf_threshold)
        self.min_face_size_px = int(min_face_size_px)
        self.unknown_label = unknown_label
        self.cap = None
        self.detector = FER(mtcnn=True)
        self._label_history: List[str] = []
        self._ema_scores: Dict[str, float] = {}
        self._last_valid: Optional[Tuple[str, float]] = None

    def open(self) -> None:
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                raise RuntimeError(f"Cannot open webcam index {self.camera_index}")

    def close(self) -> None:
        if self.cap:
            try:
                self.cap.release()
            finally:
                self.cap = None

    def _update_smoothing(self, label: str, score: float) -> Tuple[str, float]:
        prev = self._ema_scores.get(label, score)
        self._ema_scores[label] = (self.ema_alpha * score) + ((1.0 - self.ema_alpha) * prev)

        self._label_history.append(label)
        if len(self._label_history) > self.window:
            self._label_history.pop(0)

        smoothed_label = Counter(self._label_history).most_common(1)[0][0]
        smoothed_score = self._ema_scores.get(smoothed_label, score)
        return smoothed_label, smoothed_score

    def read_emotion(self, camera_index: Optional[int] = None) -> Optional[Tuple[str, float]]:
        if camera_index is not None and camera_index != self.camera_index:
            self.camera_index = camera_index
            if self.cap:
                self.close()

        if self.cap is None:
            self.open()

        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None

        try:
            results = self.detector.detect_emotions(frame)
        except Exception:
            return None

        if not results:
            return None

        best = max(results, key=lambda item: max(item["emotions"].values()))
        box = best.get("box")
        if box and len(box) >= 4:
            width, height = box[2], box[3]
            if min(width, height) < self.min_face_size_px:
                return None

        emotions = best["emotions"]
        dominant = max(emotions, key=emotions.get)
        score = float(emotions[dominant])

        smoothed_label, smoothed_score = self._update_smoothing(dominant, score)

        if smoothed_score >= self.conf_threshold:
            self._last_valid = (smoothed_label, smoothed_score)
            return smoothed_label, smoothed_score

        if self._last_valid is not None:
            return self._last_valid

        return self.unknown_label, smoothed_score
