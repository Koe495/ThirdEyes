import argparse
import json
import logging
import platform
import sys
import time
from dataclasses import replace
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
from thirdeyes.object_finding import ObjectFinder, TARGETS
from thirdeyes.ui_logging import WINDOW, configure_logging, render
from thirdeyes.rgbd import FrameSynchronizer, KinectRegionMapper
from thirdeyes.control_panel import ControlPanel, KEYS, describe_status
from thirdeyes.voice_commands import VoiceCommands
from thirdeyes.evaluation import SessionRecorder


def main(argv=None):
    parser = argparse.ArgumentParser(description="ThirdEyes - Kinect 1517 RGB/depth viewer")
    parser.add_argument("--demo", action="store_true", help="Use clearly labelled synthetic frames")
    parser.add_argument("--diagnose", action="store_true", help="Check runtime and sensor count; no GUI")
    parser.add_argument("--headless", action="store_true", help="Run without a display, for smoke checks")
    parser.add_argument("--max-frames", type=int, default=0, help="Stop after N display cycles (0: unlimited)")
    parser.add_argument("--timeout", type=float, default=10, help="Seconds without either stream before failure")
    parser.add_argument("--config", type=Path, default=Path(__file__).resolve().parent.parent / "config/obstacles.json")
    parser.add_argument("--mute", action="store_true", help="Keep visual warnings, disable beeps")
    parser.add_argument("--test-sound", action="store_true", help="Test stereo LEFT, CENTER, RIGHT, then exit")
    parser.add_argument("--audio-volume", type=float, default=.25, help="Cue amplitude in (0, 1], default .25")
    parser.add_argument("--swap-audio-channels", action="store_true", help="Swap stereo output for reversed headphones")
    parser.add_argument("--scenario", choices=["cycle", "stationary", "approach", "invalid", "retreat"], default="cycle",
                        help="Synthetic obstacle scenario, used with --demo")
    parser.add_argument("--ocr-image", type=Path, help="Read an image offline and print JSON; no camera or speech")
    parser.add_argument("--ocr-python", type=Path, help="Override isolated OCR Python executable")
    parser.add_argument("--ocr-models", type=Path, help="Override local OCR models folder")
    parser.add_argument("--read-once", action="store_true", help="Request OCR on the first fresh RGB frame")
    parser.add_argument("--no-speech", action="store_true", help="Disable offline text-to-speech; keep beeps")
    parser.add_argument("--no-flip", action="store_true", help="Keep Kinect SDK native horizontal orientation (diagnostics)")
    parser.add_argument('--no-controls', action='store_true', help='Disable the large-button control window')
    parser.add_argument('--find-target', choices=list(TARGETS), default='Chai nước')
    parser.add_argument('--find-once', action='store_true', help='Search once when a fresh frame arrives')
    parser.add_argument('--object-model', type=Path, help='Local YOLO weights; custom model must use English class names')
    parser.add_argument('--record-dir', type=Path, help='Opt in: save local RGB/depth samples for evaluation in a NEW directory')
    args = parser.parse_args(argv)
    if args.max_frames < 0 or args.timeout <= 0:
        parser.error("--max-frames must be >= 0; --timeout must be > 0")
    if not 0 < args.audio_volume <= 1:
        parser.error("--audio-volume must be in (0, 1]")
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
        player = BeepPlayer(volume=args.audio_volume, swap_channels=args.swap_audio_channels)
        try:
            logging.info("Stereo test: LEFT -> CENTER -> RIGHT; swapped=%s", args.swap_audio_channels)
            player.submit(SoundEvent("test", "manual_test"))
            finished = player.wait_idle(timeout=3)
            if not finished:
                logging.error("Stereo test timed out")
            return 0 if finished and not player.error else 1
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

    source = DemoCapture(args.scenario) if args.demo else KinectCapture(flip_horizontal=not args.no_flip)
    if not args.demo:
        logging.info("Kinect horizontal flip: %s (shared by RGB display, depth analysis and OCR)", not args.no_flip)
    depth_processor, detector = DepthProcessor(config), ObstacleDetector(config)
    audio = CoordinatorAudio(BeepPlayer(volume=args.audio_volume, swap_channels=args.swap_audio_channels),
                             config, muted=args.mute)
    logging.info("Stereo cues enabled; volume=%.2f swapped=%s", args.audio_volume, args.swap_audio_channels)
    finder = ObjectFinder(model=args.object_model)
    find_requested = False
    pending_found = None
    last_result_text = ''
    found_view = OCRView('ThirdEyes - Tìm vật (ảnh chụp)', 'ThirdEyes | Object search snapshot')
    reader = None
    panel = None
    voice = VoiceCommands(Path(__file__).resolve().parent.parent)
    synchronizer = FrameSynchronizer()
    mapper = None if args.demo else KinectRegionMapper(source)
    greeted = False
    voice_state = 'idle'
    recorder = None
    ocr_view = OCRView()
    read_requested = False
    logging.info("Source: %s; obstacle warnings and object search active", "DEMO (synthetic)" if args.demo else "Kinect 1517")
    last_status = None
    try:
        source.open()
        if args.record_dir:
            recorder = SessionRecorder(args.record_dir)
        reader = TextReader(python_path=args.ocr_python, models=args.ocr_models)
        if not args.no_speech:
            audio.speech = OfflineSpeech(Path(__file__).resolve().parent.parent, args.ocr_python)
        started = time.monotonic()
        if not args.headless:
            cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(WINDOW, 1152, 702)
            if not args.no_controls:
                panel = ControlPanel(demo=args.demo)
                panel.target.set(args.find_target)
        count = 0
        while True:
            frames = source.read()
            now = time.monotonic()
            synchronizer.update(frames)
            pair = synchronizer.latest(now)

            def request_read():
                if finder.busy:
                    return False
                audio.stop_speech()
                # OCR and measurement must use the same captured RGB image.
                snapshot = frames if pair is None else replace(frames, rgb=pair.rgb, depth_mm=pair.depth_mm,
                    color_timestamp_ms=pair.color_ms, depth_timestamp_ms=pair.depth_ms, color_received_at=pair.received_at)
                return reader.request(snapshot, now, pair=pair, mapper=mapper)
            def request_find(target=None):
                if reader.busy or finder.busy:
                    return False
                audio.stop_speech()
                snapshot = frames if pair is None else replace(frames, rgb=pair.rgb, depth_mm=pair.depth_mm,
                    color_received_at=pair.received_at, color_timestamp_ms=pair.color_ms, depth_timestamp_ms=pair.depth_ms)
                target = target or (panel.target.get() if panel else args.find_target)
                return finder.find(snapshot, target, now, pair, mapper)
            observation = depth_processor.process(frames, now)
            report = detector.process(observation)
            audio.process(report, now)
            if recorder:
                recorder.record(frames, report, now)
            if not greeted and not voice.listening and audio.speech is not None and audio.speech.state == 'ready':
                greeted = audio.read_text('ThirdEyes sẵn sàng. Bấm V, chờ tín hiệu rồi nói tìm chai nước, tìm điện thoại hoặc đọc văn bản.', now)
            if args.read_once and not read_requested and frames.rgb is not None:
                read_requested = request_read()
            result = reader.poll()
            if args.find_once and not find_requested and now - started > 1:
                find_requested = request_find()
            found = finder.poll()
            if found is not None:
                last_result_text = found['speak']
                pending_found = (found['speak'], now)
                if not args.headless:
                    found_view.show(found, finder.snapshot_rgb)
                logging.info('FIND status=%s target=%s count=%d ms=%s', found['status'], found.get('target_label'), len(found.get('regions', [])), found.get('total_ms'))
            if result is not None:
                last_result_text = result.get('speak', '')
                pending_found = (last_result_text, now)
                if not args.headless:
                    ocr_view.show(result, reader.snapshot_rgb)
            if pending_found and not voice.listening:
                if now - pending_found[1] > 10 or audio.read_text(pending_found[0], now):
                    pending_found = None
            status = (report.status, tuple((z.zone, z.level, z.known, z.reason, z.suppress_audio) for z in report.zones))
            if status != last_status:
                logging.info("OBSTACLES status=%s zones=%s", report.status,
                             [(z.zone, z.level, z.distance_m, z.reason) for z in report.zones])
                last_status = status
            for name, received in (("RGB", frames.color_received_at), ("depth", frames.depth_received_at)):
                if now - (received if received is not None else started) > args.timeout:
                    raise KinectError(f"Khong nhan duoc {name} trong {args.timeout:g}s. Kiem tra ket noi Kinect.")
            display = render(frames, args.demo, now, report, audio, reader)
            actions = []
            command = voice.poll()
            if command:
                actions.append(command)
            if voice.state != voice_state:
                voice_state = voice.state
                if voice_state == 'listening' and not audio.muted and now - audio.last_sound > .5:
                    audio.player.submit(SoundEvent('listen', 'microphone_ready'))
                elif voice_state in {'result', 'error'} and not command:
                    audio.read_text('Chưa nhận được lệnh rõ ràng. Bấm V để thử lại.', now)
                if voice_state == 'error':
                    logging.warning('Voice command input: %s', voice.message)
            if not args.headless:
                cv2.imshow(WINDOW, display)
                key = cv2.waitKey(1) & 0xFF
                if key == 27 or cv2.getWindowProperty(WINDOW, cv2.WND_PROP_VISIBLE) < 1:
                    actions.append('quit')
                elif key != 255 and chr(key).lower() in KEYS:
                    actions.append(KEYS[chr(key).lower()])
                if panel:
                    paired = f'RGB–depth lệch {pair.skew_ms} ms' if pair else 'Chưa có cặp RGB–depth phù hợp'
                    panel.update(f'{paired}\nOCR: {reader.status} | Giọng: {audio.speech.state if audio.speech else "tắt"}\n'
                                 f'Tìm vật: {finder.message[:110]}\nMicro: {voice.message}\n{describe_status(report, reader, audio)}')
                    action = panel.poll()
                    if action:
                        actions.append(action)
                ocr_view.pump()
                found_view.pump()
            if 'quit' in actions:
                break
            for action in actions:
                if isinstance(action, tuple) and action[0] == 'say':
                    if not voice.listening:
                        audio.read_text(action[1], now)
                elif isinstance(action, tuple) and action[0] == 'find':
                    target = action[1]
                    if target not in TARGETS:
                        continue
                    pending_found = None
                    args.find_target = target
                    if panel:
                        panel.target.set(target)
                    if request_find(target):
                        pending_found = (f'Đang tìm {target.lower()}.', now)
                    else:
                        pending_found = ('Chưa thể tìm vật lúc này. Hệ thống đang xử lý hoặc chưa có ảnh mới. Hãy thử lại.', now)
                elif action == 'read':
                    pending_found = None
                    request_read()
                elif action == 'find':
                    pending_found = None
                    request_find()
                elif action == 'repeat':
                    pending_found = (last_result_text or 'Chưa có kết quả để đọc lại.', now)
                elif action == 'cancel':
                    finder.cancel(); pending_found = None
                    reader.cancel(); audio.stop_speech()
                elif action == 'mute':
                    audio.toggle_mute()
                elif action == 'test' and not audio.muted:
                    audio.stop_speech(); audio.player.submit(SoundEvent('test', 'manual_test'))
                elif action == 'listen':
                    audio.stop_speech(); voice.listen()
                elif action == 'status':
                    audio.read_text(describe_status(report, reader, audio), now)
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
            voice.close()
            if recorder:
                recorder.close()
            # Mapping runs in the OCR thread: join it before releasing the SDK.
            if reader is not None:
                reader.close()
            finder.close()
            source.close()
        finally:
            audio.close()
            ocr_view.close()
            found_view.close()
            if panel is not None:
                panel.close()
            if not args.headless:
                cv2.destroyAllWindows()
