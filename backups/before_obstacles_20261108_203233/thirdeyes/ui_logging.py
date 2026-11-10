"""Module 7: RGB/depth display and local activity log."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import cv2
import numpy as np

from thirdeyes.contracts import FrameBundle

WINDOW = "ThirdEyes | RGB + Depth"
ROOT = Path(__file__).resolve().parent.parent


def configure_logging():
    (ROOT / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[logging.StreamHandler(), RotatingFileHandler(
                            ROOT / "logs/thirdeyes.log", maxBytes=1_000_000,
                            backupCount=2, encoding="utf-8")], force=True)


def colorize_depth(depth_mm):
    """Display only; no mapping, obstacle analysis or distance estimation.

    Fixed normal-mode display range: 800..4000 mm. Out-of-range and
    SDK invalid codes (0, 4095, 8191) are black. Raw depth stays unchanged.
    """
    valid = (depth_mm >= 800) & (depth_mm <= 4000)
    scaled = (255 * (4000 - np.clip(depth_mm.astype(np.float32), 800, 4000)) / 3200).astype(np.uint8)
    colored = cv2.applyColorMap(scaled, cv2.COLORMAP_TURBO)
    colored[~valid] = 0
    return colored


def render(frames: FrameBundle, demo: bool, now: float):
    canvas = np.full((590, 1280, 3), (24, 24, 24), dtype=np.uint8)
    for column, data, received, label in (
        (0, frames.rgb, frames.color_received_at, "RGB / COLOR"),
        (640, frames.depth_mm, frames.depth_received_at, "DEPTH / 0.8 - 4.0 m"),
    ):
        if data is not None:
            panel = cv2.cvtColor(data, cv2.COLOR_RGB2BGR) if column == 0 else colorize_depth(data)
            canvas[45:525, column:column + 640] = panel
        state = "WAITING" if received is None else ("STALE" if now - received > 2 else "LIVE")
        if demo and received is not None:
            state = "SIMULATED"
        cv2.putText(canvas, f"{label}  |  {state}", (column + 16, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, .65, (230, 230, 230), 1, cv2.LINE_AA)
    footer = "DEMO - SYNTHETIC DATA" if demo else "KINECT v1 / model 1517"
    cv2.putText(canvas, f"{footer} | Q / ESC: quit | AI + audio: placeholders",
                (16, 550), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 210, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, "Depth: warm=near, cool=far, black=invalid/out of range | RGB/depth are NOT aligned",
                (16, 578), cv2.FONT_HERSHEY_SIMPLEX, .55, (190, 190, 190), 1, cv2.LINE_AA)
    return canvas
