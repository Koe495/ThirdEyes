"""Explicit synthetic input. Never silently substituted for a real camera."""
import time

import numpy as np

from thirdeyes.contracts import FrameBundle


class DemoCapture:
    def __init__(self, scenario="cycle"):
        self.scenario = scenario

    def open(self):
        self.started = time.monotonic()

    def read(self):
        now = time.monotonic()
        elapsed = now - self.started
        phase = int(elapsed * 50)
        y, x = np.indices((480, 640))
        rgb = np.stack(((x + phase) % 256, y % 256, (x // 3 + y // 3) % 256), axis=-1).astype(np.uint8)
        depth = np.full((480, 640), 3500, dtype=np.uint16)
        t = elapsed % 18
        distance = None
        if self.scenario == "stationary":
            distance = 1250
        elif self.scenario == "approach":
            distance = max(850, 3000 - elapsed * 1000)
        elif self.scenario == "invalid":
            depth[:] = 0
        elif 2 <= t < 7:
            distance = 1250
        elif 9 <= t < 11:
            distance = max(850, 3000 - (t - 9) * 1100)
        elif 11 <= t < 14:
            distance = 900
        elif 14 <= t < 16:
            depth[:] = 0
        if distance is not None:
            depth[120:360, 270:370] = int(distance)
            rgb[120:360, 270:370] = (240, 170, 45)
        timestamp = int((now - self.started) * 1000)
        return FrameBundle(rgb, depth, timestamp, timestamp, now, now)

    def close(self):
        pass
