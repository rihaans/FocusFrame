import time
from typing import Optional, Tuple
import cv2
from fer import FER

class EmotionDetector:
    def __init__(self, camera_index: int = 0):
        self.camera_index = camera_index
        self.cap = None
        self.detector = FER(mtcnn=True)

    def open(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)  # CAP_DSHOW helps on Windows
            if not self.cap.isOpened():
                raise RuntimeError(f"Cannot open webcam index {self.camera_index}")

    def close(self):
        if self.cap:
            try:
                self.cap.release()
            finally:
                self.cap = None

    def read_emotion(self) -> Optional[Tuple[str, float]]:
        if self.cap is None:
            self.open()
        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None
        # FER returns list of detections; pick max dominant or None
        try:
            res = self.detector.detect_emotions(frame)
            if not res:
                return None
            # choose face with highest sum of emotions, then dominant
            best = max(res, key=lambda r: max(r["emotions"].values()))
            emotions = best["emotions"]
            dominant = max(emotions, key=emotions.get)
            score = emotions[dominant]
            return dominant, float(score)
        except Exception:
            return None
