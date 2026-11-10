import argparse
import json
import logging
import platform
import sys
import time
from pathlib import Path

import cv2
import numpy as np

from thirdeyes.capture.demo import DemoCapture
from thirdeyes.capture.kinect import KinectCapture, KinectError, load_runtime, sensor_count
from thirdeyes.coordinator_audio import BeepPlayer, CoordinatorAudio
from thirdeyes.config import load_config
from thirdeyes.contracts import SoundEvent, FrameBundle
from thirdeyes.depth_processing import DepthProcessor
from thirdeyes.obstacle_detection import ObstacleDetector
from thirdeyes.ocr import TextReader
from thirdeyes.ocr_view import OCRView
from thirdeyes.speech import OfflineSpeech
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
    parser.add_argument("--ocr-image", type=Path, help="Read an image offline and print JSON; no camera or speech")
    parser.add_argument("--ocr-python", type=Path, help="Override isolated OCR Python executable")
    parser.add_argument("--ocr-models", type=Path, help="Override local OCR models folder")
    parser.add_argument("--read-once", action="store_true", help="Request OCR on the first fresh RGB frame")
    parser.add_argument("--no-speech", action="store_true", help="Disable offline text-to-speech; keep beeps")
    args = parser.parse_args(argv)
    if args.max_frames < 0 or args.timeout <= 0:
        parser.error("--max-frames must be >= 0; --timeout must be > 0")
    configure_logging()
    if args.ocr_image:
        reader = TextReader(python_path=args.ocr_python, models=args.ocr_models)
        try:
            image = cv2.imdecode(np.fromfile(args.ocr_image, np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError("Cannot read input image")
            now = time.monotonic()
            if not reader.request(FrameBundle(rgb=cv2.cvtColor(image, cv2.COLOR_BGR2RGB), color_received_at=now), now):
                logging.error("OCR unavailable: %s", reader.message)
                return 1
            while True:
                result = reader.poll()
                if result is not None:
                    if hasattr(sys.stdout, "reconfigure"):
                        sys.stdout.reconfigure(encoding="utf-8")
                    print(json.dumps(result, ensure_ascii=False, indent=2))
                    return 0 if result["status"] == "ok" else 1
                time.sleep(.025)
        except (OSError, ValueError) as exc:
            logging.error("OCR image: %s", exc)
            return 1
        finally:
            reader.close()
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
    modules = [ObjectFinder()]
    reader = None
    ocr_view = OCRView()
    read_requested = False
    logging.info("Source: %s; obstacle warnings active; placeholders: %s", "DEMO (synthetic)" if args.demo else "Kinect 1517",
                 ", ".join(type(module).__name__ for module in modules))
    last_status = None
    try:
        source.open()
        reader = TextReader(python_path=args.ocr_python, models=args.ocr_models)
        if not args.no_speech:
            audio.speech = OfflineSpeech(Path(__file__).resolve().parent.parent, args.ocr_python)
        started = time.monotonic()
        if not args.headless:
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW, 1152, 702)
        count = 0
        while True:
            frames = source.read()
            now = time.monotonic()
            observation = depth_processor.process(frames, now)
            report = detector.process(observation)
            audio.process(report, now)
            if args.read_once and not read_requested and frames.rgb is not None:
                read_requested = reader.request(frames, now)
            result = reader.poll()
            if result is not None:
                if not args.headless:
                    ocr_view.show(result, reader.snapshot_rgb)
                audio.read_text(result.get("speak", ""), now)
            status = (report.status, tuple((z.zone, z.level, z.known) for z in report.zones))
            if status != last_status:
                logging.info("OBSTACLES status=%s zones=%s", report.status,
                             [(z.zone, z.level, z.distance_m, z.reason) for z in report.zones])
                last_status = status
            for name, received in (("RGB", frames.color_received_at), ("depth", frames.depth_received_at)):
                if now - (received if received is not None else started) > args.timeout:
                    raise KinectError(f"Khong nhan duoc {name} trong {args.timeout:g}s. Kiem tra ket noi Kinect.")
            display = render(frames, args.demo, now, report, audio, reader)
            if not args.headless:
                cv2.imshow(WINDOW, display)
                key = cv2.waitKey(1) & 0xFF
                if key in (27, ord("q"), ord("Q")) or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    break
                if key in (ord("m"), ord("M")):
                    audio.toggle_mute()
                if key in (ord("t"), ord("T")) and not audio.muted:
                    audio.stop_speech()
                    audio.player.submit(SoundEvent("test", "manual_test"))
                if key in (ord("o"), ord("O")):
                    audio.stop_speech()
                    reader.request(frames, now)
                if key in (ord("r"), ord("R")):
                    audio.read_text(reader.last_text, now)
                if key in (ord("x"), ord("X")):
                    reader.cancel()
                    audio.stop_speech()
                ocr_view.pump()
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
            if reader is not None:
                reader.close()
            audio.close()
            ocr_view.close()
            if not args.headless:
                cv2.destroyAllWindows()
