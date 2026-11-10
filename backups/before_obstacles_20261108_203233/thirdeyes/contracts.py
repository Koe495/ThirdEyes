from dataclasses import dataclass

import numpy as np


@dataclass
class FrameBundle:
    """Latest independent frames, NOT an aligned or synchronized RGB-D pair.

    rgb: uint8 HxWx3, RGB order. depth_mm: uint16 HxW, millimetres.
    Sensor timestamps are milliseconds from the Kinect runtime.
    Received times use time.monotonic(), for stream freshness checks.
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
