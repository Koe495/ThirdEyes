from dataclasses import dataclass

import numpy as np


@dataclass
class FrameBundle:
    """Latest independent frames, NOT an aligned or synchronized RGB-D pair.

    rgb: uint8 HxWx3, RGB order. depth_mm: uint16 HxW, millimetres.
    Sensor timestamps are milliseconds from the Kinect runtime.
    Received times use time.monotonic(), for stream freshness checks.
    Kinect capture normalizes horizontal orientation before publishing frames.
    """

    rgb: np.ndarray | None = None
    depth_mm: np.ndarray | None = None
    color_timestamp_ms: int | None = None
    depth_timestamp_ms: int | None = None
    color_received_at: float | None = None
    depth_received_at: float | None = None


@dataclass(frozen=True)
class PlaceholderResult:
    module: str
    status: str = "not_implemented"
    message: str = "Chua trien khai trong ban nguyen mau nay."


@dataclass(frozen=True)
class DepthCell:
    index: int
    zone: str
    bounds: tuple[int, int, int, int]
    distance_m: float | None
    valid_fraction: float


@dataclass(frozen=True)
class DepthObservation:
    status: str
    fresh: bool
    sensor_time_s: float | None
    cells: tuple[DepthCell, ...]
    roi: tuple[int, int, int, int] | None


@dataclass(frozen=True)
class ZoneRisk:
    zone: str
    level: int
    known: bool
    distance_m: float | None
    closing_mps: float
    ttc_s: float | None
    reason: str
    approaching: bool = False
    suppress_audio: bool = False  # only an emerging/receding patch; not "clear"


@dataclass(frozen=True)
class ObstacleReport:
    status: str
    zones: tuple[ZoneRisk, ...]
    roi: tuple[int, int, int, int] | None
    tracks: tuple = ()  # geometric patches only; IDs do not affect warning policy


@dataclass(frozen=True)
class SoundEvent:
    kind: str
    reason: str
    zones: tuple[str, ...] = ()
    pan: float | None = None  # -1 left, +1 right; continuous object tracking cue
