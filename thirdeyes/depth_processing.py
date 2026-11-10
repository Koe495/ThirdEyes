"""Module 2: supported depth patches; RGB/depth registration remains deferred."""
import cv2
import numpy as np

from thirdeyes.config import ObstacleConfig
from thirdeyes.contracts import DepthCell, DepthObservation, FrameBundle

ZONES = ("LEFT", "CENTER", "RIGHT")
GRID_COLS, GRID_ROWS = 6, 3


class DepthProcessor:
    def __init__(self, config: ObstacleConfig | None = None):
        self.config = config or ObstacleConfig()
        self.last_timestamp = None
        self.last_advance_at = None
        self.cached = DepthObservation("waiting", False, None, (), None)

    def process(self, frames: FrameBundle, now: float) -> DepthObservation:
        cfg = self.config
        if frames.depth_mm is None or frames.depth_received_at is None or frames.depth_timestamp_ms is None:
            return DepthObservation("waiting", False, None, (), None)
        if now - frames.depth_received_at > cfg.stale_s:
            return DepthObservation("stale", False, None, (), self.cached.roi)
        timestamp = frames.depth_timestamp_ms
        if timestamp == self.last_timestamp:
            if self.last_advance_at is not None and now - self.last_advance_at > cfg.stale_s:
                return DepthObservation("stale", False, None, (), self.cached.roi)
            c = self.cached
            return DepthObservation(c.status, False, c.sensor_time_s, c.cells, c.roi)
        self.last_timestamp = timestamp
        self.last_advance_at = now
        depth = frames.depth_mm
        if depth.ndim != 2 or depth.dtype != np.uint16 or min(depth.shape) < 60:
            raise ValueError("Expected a uint16 depth image in millimetres, at least 60x60")
        h, w = depth.shape
        x0, x1 = int(w * cfg.roi_left), int(w * cfg.roi_right)
        y0, y1 = int(h * cfg.roi_top), int(h * cfg.roi_bottom)
        xs = np.linspace(x0, x1, GRID_COLS + 1, dtype=int)
        ys = np.linspace(y0, y1, GRID_ROWS + 1, dtype=int)
        cells = []
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                tile = depth[ys[row]:ys[row + 1], xs[col]:xs[col + 1]]
                valid = (tile >= 800) & (tile <= 4000)
                fraction = float(valid.mean())
                distance = None
                if fraction >= cfg.min_valid_fraction:
                    # Require a connected foreground patch, not a few hot pixels.
                    minimum_area = max(25, int(tile.size * cfg.min_blob_fraction))
                    candidates = []
                    # Try several quantiles so a narrow foreground patch is
                    # not swallowed into the background component.
                    for threshold in np.unique(np.percentile(tile[valid], [5, 20, 50]) + 80):
                        mask = (valid & (tile <= threshold)).astype(np.uint8)
                        n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
                        candidates.extend(float(np.median(tile[labels == i])) / 1000
                                          for i in range(1, n) if stats[i, cv2.CC_STAT_AREA] >= minimum_area)
                    if candidates:
                        distance = min(candidates)
                cells.append(DepthCell(row * GRID_COLS + col, ZONES[col // 2],
                                       (int(xs[col]), int(ys[row]), int(xs[col + 1]), int(ys[row + 1])),
                                       distance, fraction))
        usable = sum(cell.distance_m is not None for cell in cells)
        known = usable == len(cells)
        status = "ok" if known else ("partial" if usable else "invalid")
        self.cached = DepthObservation(status, True, timestamp / 1000, tuple(cells), (x0, y0, x1, y1))
        return self.cached
