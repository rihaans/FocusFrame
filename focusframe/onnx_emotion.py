import cv2
import numpy as np
from typing import Optional, Tuple
import onnxruntime as ort

# Supports FER+ (8 emotions) or FER2013 (7 emotions)
FERPLUS_8 = [
    "neutral",
    "happiness",
    "surprise",
    "sadness",
    "anger",
    "disgust",
    "fear",
    "contempt",
]
FER7 = [
    "angry",
    "disgust",
    "fear",
    "happy",
    "sad",
    "surprise",
    "neutral",
]


def softmax(x: np.ndarray) -> np.ndarray:
    x = x.astype(np.float32)
    x -= np.max(x)
    e = np.exp(x)
    return e / np.sum(e)


class ONNXEmotionDetector:
    """Webcam -> face crop (whole frame fallback) -> ONNX -> (label, score).

    NOTE: for production use, replace naive face handling with a face detector.
    """

    def __init__(
        self,
        model_path: str,
        labels: str = "ferplus8",
        input_size: Tuple[int, int] = (64, 64),
        conf_threshold: float = 0.55,
        min_face_size_px: int = 80,
    ) -> None:
        self.labels_name = labels.lower()
        self.labels = FERPLUS_8 if self.labels_name == "ferplus8" else FER7
        self.n_classes = len(self.labels)
        self.conf_threshold = float(conf_threshold)
        self.min_face = int(min_face_size_px)
        self.input_size = tuple(input_size)
        self.cap = None

        sess_opts = ort.SessionOptions()
        self.session = ort.InferenceSession(
            model_path,
            sess_options=sess_opts,
            providers=["CPUExecutionProvider"],
        )
        self.input_name = self.session.get_inputs()[0].name

    def open(self, camera_index: int = 0) -> None:
        if self.cap is None:
            self.cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
            if not self.cap.isOpened():
                raise RuntimeError(f"Cannot open webcam {camera_index}")

    def close(self) -> None:
        if self.cap:
            self.cap.release()
            self.cap = None

    def _prep(self, frame: np.ndarray) -> Optional[np.ndarray]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape[:2]
        size = min(h, w)
        y0 = (h - size) // 2
        x0 = (w - size) // 2
        face = gray[y0 : y0 + size, x0 : x0 + size]

        if min(face.shape[:2]) < self.min_face:
            return None

        resized = cv2.resize(face, self.input_size, interpolation=cv2.INTER_AREA)
        x = resized.astype(np.float32) / 255.0
        x = (x - 0.5) / 0.5
        x = np.expand_dims(x, 0)
        x = np.expand_dims(x, 0)
        return x

    def read_emotion(self, camera_index: int = 0) -> Optional[Tuple[str, float]]:
        if self.cap is None:
            self.open(camera_index)

        ok, frame = self.cap.read()
        if not ok or frame is None:
            return None

        x = self._prep(frame)
        if x is None:
            return None

        out = self.session.run(None, {self.input_name: x})
        logits = out[0].squeeze()
        if logits.ndim != 1:
            return None

        probs = softmax(logits)
        if probs.shape[0] != self.n_classes:
            if probs.ndim == 2 and probs.shape[-1] == self.n_classes:
                probs = probs[-1]
            else:
                return None

        idx = int(np.argmax(probs))
        score = float(probs[idx])
        label = self.labels[idx]
        if score < self.conf_threshold:
            return ("unknown", score)
        return (label, score)
