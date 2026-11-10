import argparse
import logging
import platform
import time
from pathlib import Path

import cv2

from thirdeyes.capture.demo import DemoCapture
from thirdeyes.capture.kinect import KinectCapture, KinectError, load_runtime, sensor_count
from thirdeyes.coordinator_audio import BeepPlayer, CoordinatorAudio
from thirdeyes.config import load_config
from thirdeyes.contracts import SoundEvent
from thirdeyes.depth_processing import DepthProcessor
from thirdeyes.obstacle_detection import ObstacleDetector
from thirdeyes.ocr import TextReader
from thirdeyes.object_finding import ObjectFinder
from thirdeyes.ui_logging import WINDOW, configure_logging, render


def main(argv=None):
    parser = argparse.ArgumentParser(description="ThirdEyes - Kinect 1517 RGB/depth viewer")
    parser.add_argument("--demo", action="store_true", help="Use clearly labelled synthetic frames")
    parser.add_argument("--diagnose", action="store_true", help="Check runtime and sensor count; no GUI")
    parser.add_argument("--headless", action="store_true", help="Run without a display, for smoke checks")
    parser.add_argument("--max-frames", type=int, default=0, help="Stop after N display cycles (0: unlimited)")
    parser.add_argument("--timeout", type=float, default=10, help="Seconds without either stream before failure")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent.parent / "config/obstacles.json")
    parser.add_argument("--mute", action="store_true", help="Keep visual warnings, disable beeps")
    parser.add_argument("--test-sound", action="store_true", help="Play one short test beep, then exit")
    parser.add_argument("--scenario", choices=["cycle", "stationary", "approach", "invalid"], default="cycle",
                        help="Synthetic obstacle scenario, used with --demo")
    args = parser.parse_args(argv)
    if args.max_frames < 0 or args.timeout <= 0:
        parser.error("--max-frames must be >= 0; --timeout must be > 0")
    configure_logging()
    try:
        config = load_config(args.config)
    except (OSError, ValueError, TypeError) as exc:
        logging.error("Invalid configuration: %s", exc)
        return 1
    if args.test_sound:
        player = BeepPlayer()
        try:
            player.submit(SoundEvent("test", "manual_test"))
            time.sleep(.3)
            return 1 if player.error else 0
        finally:
            player.close()
    if args.diagnose:
        logging.info("Python %s (%s)", platform.python_version(), platform.architecture()[0])
        try:
            count = sensor_count(load_runtime())
            logging.info("Kinect SDK 1.8 runtime loaded. Sensors detected: %d", count)
            if count == 0:
                logging.error("Chua co Kinect. Cam nguon/USB va chay lai; --demo de thu giao dien.")
            return 0 if count > 0 else 1
        except KinectError as exc:
            logging.error("%s", exc)
            return 1

    source = DemoCapture(args.scenario) if args.demo else KinectCapture()
    depth_processor, detector = DepthProcessor(config), ObstacleDetector(config)
    audio = CoordinatorAudio(BeepPlayer(), config, muted=args.mute)
    modules = [TextReader(), ObjectFinder()]
    logging.info("Source: %s; obstacle warnings active; placeholders: %s", "DEMO (synthetic)" if args.demo else "Kinect 1517",
                 ", ".join(type(module).__name__ for module in modules))
    last_status = None
    try:
        source.open()
        started = time.monotonic()
        if not args.headless:
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW, 1152, 639)
        count = 0
        while True:
            frames = source.read()
            now = time.monotonic()
            observation = depth_processor.process(frames, now)
            report = detector.process(observation)
            audio.process(report, now)
            status = (report.status, tuple((z.zone, z.level, z.known) for z in report.zones))
            if status != last_status:
                logging.info("OBSTACLES status=%s zones=%s", report.status,
                             [(z.zone, z.level, z.distance_m, z.reason) for z in report.zones])
                last_status = status
            for name, received in (("RGB", frames.color_received_at), ("depth", frames.depth_received_at)):
                if now - (received if received is not None else started) > args.timeout:
                    raise KinectError(f"Khong nhan duoc {name} trong {args.timeout:g}s. Kiem tra ket noi Kinect.")
            display = render(frames, args.demo, now, report, audio)
            if not args.headless:
                cv2.imshow(WINDOW, display)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q"), ord("Q")) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
                if key in (ord("m"), ord("M")):
                    audio.toggle_mute()
                if key in (ord("t"), ord("T")) and not audio.muted:
                    audio.player.submit(SoundEvent("test", "manual_test"))
            count += 1
            if args.max_frames and count >= args.max_frames:
                if frames.rgb is None or frames.depth_mm is None:
                    raise KinectError("Da het so vong kiem tra nhung chua nhan du RGB va depth.")
                break
            time.sleep(.02)
        logging.info("Viewer stopped normally after %d cycles. RGB: %s; depth: %s; timestamps (ms): %s / %s",
                     count, None if frames.rgb is None else frames.rgb.shape,
                     None if frames.depth_mm is None else frames.depth_mm.shape,
                     frames.color_timestamp_ms, frames.depth_timestamp_ms)
        return 0
    except KeyboardInterrupt:
        logging.info("Stopped by Ctrl+C.")
        return 0
    except (KinectError, OSError, ValueError, cv2.error) as exc:
        logging.error("%s", exc)
        if audio.notify_shutdown_fault():
            time.sleep(.15)
        return 1
    finally:
        try:
            source.close()
        finally:
            audio.close()
            if not args.headless:
                cv2.destroyAllWindows()
