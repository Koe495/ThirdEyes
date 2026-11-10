"""Validated prototype thresholds (metres and seconds)."""
from dataclasses import asdict, dataclass, fields
import json
import math
from pathlib import Path


@dataclass(frozen=True)
class ObstacleConfig:
    roi_left: float = 0.20
    roi_right: float = 0.80
    roi_top: float = 0.18
    roi_bottom: float = 0.78
    near_m: float = 1.50
    critical_m: float = 1.00
    release_margin_m: float = 0.25
    approach_mps: float = 0.80
    approach_max_m: float = 3.00
    ttc_s: float = 2.00
    ttc_min_speed_mps: float = 0.30
    confirm_s: float = 0.18
    urgent_confirm_s: float = 0.10
    clear_s: float = 1.00
    history_s: float = 0.55
    speed_min_span_s: float = 0.25
    stale_s: float = 0.60
    min_valid_fraction: float = 0.30
    min_blob_fraction: float = 0.08
    cooldown_s: float = 0.80
    progress_m: float = 0.25
    fault_delay_s: float = 1.00
    fault_recover_s: float = 2.00
    emergence_entry_m: float = 0.95
    emergence_observe_s: float = 0.40
    recession_min_mps: float = 0.05
    recession_stop_s: float = 0.60
    recession_reverse_m: float = 0.04

    def __post_init__(self):
        for name, value in asdict(self).items():
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
            if value < 0 or (value == 0 and name not in {"roi_left", "roi_top"}):
                raise ValueError(f"{name} must be positive")
        if not (0 <= self.roi_left < self.roi_right <= 1 and 0 <= self.roi_top < self.roi_bottom <= 1):
            raise ValueError("ROI must be normalized bounds in 0..1")
        if self.roi_right - self.roi_left < .15 or self.roi_bottom - self.roi_top < .15:
            raise ValueError("ROI is too small for the 6x3 grid")
        if not .8 <= self.critical_m < self.near_m < self.approach_max_m <= 4:
            raise ValueError("Require 0.8 <= critical_m < near_m < approach_max_m <= 4")
        if self.near_m + self.release_margin_m > 4:
            raise ValueError("Near release threshold exceeds sensor range")
        if not .1 <= self.min_valid_fraction <= 1 or not .01 <= self.min_blob_fraction <= 1:
            raise ValueError("Invalid pixel/blob fractions")
        if not .15 <= self.speed_min_span_s < self.history_s <= 2:
            raise ValueError("Require 0.15 <= speed_min_span_s < history_s <= 2")
        if self.urgent_confirm_s > self.confirm_s or self.confirm_s >= self.clear_s:
            raise ValueError("Require urgent_confirm_s <= confirm_s < clear_s")
        if self.cooldown_s < .25 or self.progress_m < .10 or self.stale_s > 2:
            raise ValueError("Require cooldown >= .25s, progress >= .10m, stale <= 2s")
        if not .8 <= self.emergence_entry_m <= self.near_m:
            raise ValueError("Emergence band must start within the valid near range")
        if not .2 <= self.emergence_observe_s <= .8 or not .3 <= self.recession_stop_s <= 1.5:
            raise ValueError("Invalid emergence/stop observation time")
        if not .02 <= self.recession_min_mps <= .5 or not .02 <= self.recession_reverse_m <= .15:
            raise ValueError("Invalid recession/reversal threshold")


def load_config(path: Path) -> ObstacleConfig:
    values = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(values, dict):
        raise ValueError("Obstacle configuration must be a JSON object")
    unknown = set(values) - {item.name for item in fields(ObstacleConfig)}
    if unknown:
        raise ValueError(f"Unknown configuration keys: {sorted(unknown)}")
    return ObstacleConfig(**values)
