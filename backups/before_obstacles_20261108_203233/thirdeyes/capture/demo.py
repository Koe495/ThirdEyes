"""Explicit synthetic input. Never silently substituted for a real camera."""
import time

import numpy as np

from thirdeyes.contracts import FrameBundle


class DemoCapture:
    def open(self):
        self.started = time.monotonic()

    def read(self):
        now = time.monotonic()
        phase = int((now - self.started) * 50)
        y, x = np.indices((480, 640))
        rgb = np.stack(((x + phase) % 256, y % 256, (x // 3 + y // 3) % 256), axis=-1).astype(np.uint8)
        depth = (800 + x * 3200 // 639).astype(np.uint16)
        depth[190:290, (phase % 480):(phase % 480) + 100] = 1200
        depth[:30, :80] = 0
        timestamp = int((now - self.started) * 1000)
        return FrameBundle(rgb, depth, timestamp, timestamp, now, now)

    def close(self):
        pass
