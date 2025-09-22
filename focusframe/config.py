from dataclasses import dataclass
from typing import Dict, Any
import copy
import os
import yaml

DEFAULT_CONFIG: Dict[str, Any] = {
    "emotion_backend": "fer",
    "sampling": {
        "emotion_interval_seconds": 1,
        "decision_interval_seconds": 2,
        "demo_notification_period_seconds": 30,
    },
    "deferral": {
        "focus_deferral_minutes": 15,
        "sad_deferral_minutes": 10,
    },
    "batching": {
        "enabled": True,
        "release_interval_minutes": 25,
    },
    "accuracy": {
        "conf_threshold": 0.5,
        "min_face_size_px": 60,
        "unknown_label": "unknown",
        "smoothing": {
            "ema_alpha": 0.5,
            "window": 3,
        },
    },
    "onnx": {
        "model_path": "models/emotion-ferplus-8.onnx",
        "labels": "ferplus8",
        "input_size": [64, 64],
    },
    "apps": {
        "focus": [],
        "casual": [],
    },
    "notifications": {
        "title_prefix": "[FocusFrame]",
        "demo_payloads": ["Demo notification"],
    },
}


@dataclass
class Config:
    raw: Dict[str, Any]

    @property
    def sampling(self) -> Dict[str, Any]:
        return self.raw["sampling"]

    @property
    def deferral(self) -> Dict[str, Any]:
        return self.raw["deferral"]

    @property
    def batching(self) -> Dict[str, Any]:
        return self.raw["batching"]

    @property
    def accuracy(self) -> Dict[str, Any]:
        return self.raw.get("accuracy", {})

    @property
    def apps(self) -> Dict[str, Any]:
        return self.raw["apps"]

    @property
    def notifications(self) -> Dict[str, Any]:
        return self.raw["notifications"]

    @property
    def onnx(self) -> Dict[str, Any]:
        return self.raw.get("onnx", {})


def load_config(path: str = "config.yaml") -> Config:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as handle:
            user = yaml.safe_load(handle) or {}
    else:
        user = {}

    merged: Dict[str, Any] = copy.deepcopy(DEFAULT_CONFIG)

    for key, value in user.items():
        if isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
            merged[key].update(value)
        else:
            merged[key] = value

    return Config(merged)
