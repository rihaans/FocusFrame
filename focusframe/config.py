from dataclasses import dataclass, field
from typing import List, Dict, Any
import yaml
import os

DEFAULT_CONFIG = {
    "sampling": {
        "emotion_interval_seconds": 5,
        "decision_interval_seconds": 5,
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
    "apps": {"focus": [], "casual": []},
    "notifications": {
        "title_prefix": "[FocusFrame]",
        "demo_payloads": ["Demo notification"],
    },
}

@dataclass
class Config:
    raw: Dict[str, Any]

    @property
    def sampling(self): return self.raw["sampling"]
    @property
    def deferral(self): return self.raw["deferral"]
    @property
    def batching(self): return self.raw["batching"]
    @property
    def apps(self): return self.raw["apps"]
    @property
    def notifications(self): return self.raw["notifications"]

def load_config(path: str = "config.yaml") -> Config:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            user = yaml.safe_load(f) or {}
    else:
        user = {}
    merged = DEFAULT_CONFIG.copy()
    # shallow merge for brevity
    for k, v in user.items():
        if isinstance(v, dict) and k in merged:
            merged[k].update(v)
        else:
            merged[k] = v
    return Config(merged)
