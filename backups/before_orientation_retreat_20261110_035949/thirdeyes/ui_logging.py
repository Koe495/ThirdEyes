"""Module 7: RGB/depth display and local activity log."""
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import cv2
import numpy as np

from thirdeyes.contracts import FrameBundle, ObstacleReport

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


def render(frames: FrameBundle, demo: bool, now: float, report: ObstacleReport | None = None, audio=None, reader=None):
    canvas = np.full((780, 1280, 3), (24, 24, 24), dtype=np.uint8)
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
    cv2.putText(canvas, f"{footer} | Q/ESC: quit | M: mute | T: beep | O: OCR | R: repeat | X: stop OCR",
                (16, 550), cv2.FONT_HERSHEY_SIMPLEX, .6, (0, 210, 255), 1, cv2.LINE_AA)
    cv2.putText(canvas, "Depth: warm=near, cool=far, black=invalid/out of range | RGB/depth are NOT aligned",
                (16, 578), cv2.FONT_HERSHEY_SIMPLEX, .55, (190, 190, 190), 1, cv2.LINE_AA)
    if report is not None:
        audio_state = "OFF" if audio is None else ("MUTED" if audio.muted else "ON")
        if audio is not None and audio.player.error:
            audio_state = "ERROR - check log / speakers"
        color = (80, 200, 80) if report.status == "ok" else (0, 170, 255)
        cv2.putText(canvas, f"Depth: {report.status.upper()} | Audio: {audio_state} | Prototype thresholds - indoor demo",
                    (16, 606), cv2.FONT_HERSHEY_SIMPLEX, .6, color, 1, cv2.LINE_AA)
        for i, zone in enumerate(report.zones):
            color = ((80, 200, 80), (0, 210, 255), (60, 60, 255))[zone.level]
            distance = "?" if zone.distance_m is None else f"{zone.distance_m:.2f}m"
            state = ("MONITORING", "NEAR", "URGENT")[zone.level] if zone.known else "LOW CONFIDENCE"
            cv2.putText(canvas, f"{zone.zone}: {state} {distance}", (16 + i * 420, 638),
                        cv2.FONT_HERSHEY_SIMPLEX, .58, color, 1, cv2.LINE_AA)
            cv2.putText(canvas, f"Closing: {zone.closing_mps:.2f}m/s | {zone.reason}", (16 + i * 420, 664),
                        cv2.FONT_HERSHEY_SIMPLEX, .52, (210, 210, 210), 1, cv2.LINE_AA)
            if report.roi is not None:
                x0, y0, x1, y1 = report.roi
                left = 640 + x0 + (x1 - x0) * i // 3
                right = 640 + x0 + (x1 - x0) * (i + 1) // 3
                cv2.rectangle(canvas, (left, y0 + 45), (right, y1 + 45), color, 2)
        cv2.putText(canvas, "Stationary obstacle: one alert; repeated beep only for a new/worsening risk. Black depth is UNKNOWN.",
                    (16, 695), cv2.FONT_HERSHEY_SIMPLEX, .52, (190, 190, 190), 1, cv2.LINE_AA)
    if reader is not None:
        speech_state = "disabled"
        if audio is not None and audio.speech is not None:
            speech_state = audio.speech.state
        cv2.putText(canvas, f"OCR: {reader.status.upper()} | Offline Vietnamese voice: {speech_state}",
                    (16, 728), cv2.FONT_HERSHEY_SIMPLEX, .58, (240, 220, 140), 1, cv2.LINE_AA)
        cv2.putText(canvas, reader.message[:125], (16, 758), cv2.FONT_HERSHEY_SIMPLEX,
                    .52, (210, 210, 210), 1, cv2.LINE_AA)
    return canvas
