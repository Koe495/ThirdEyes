import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock

import numpy as np

from thirdeyes.contracts import FrameBundle, ObstacleReport, ZoneRisk
from thirdeyes.coordinator_audio import CoordinatorAudio
from thirdeyes.ocr import TextReader, read_settings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ocr_runtime"))
from text_reader.ocr_reader import VietnameseOCR, ordered_rows, rectify

FAKE_WORKER = r'''
import sys, json, time
from pathlib import Path
import cv2
for line in sys.stdin:
    req = json.loads(line)
    time.sleep(DELAY)
    pixel = cv2.imread(req['image'])[0, 0].tolist()
    result = {'request_id': req['id'], 'status': 'ok', 'text': 'Xin chào', 'speak': 'Xin chào', 'pixel_bgr': pixel}
    out = Path(req['output'])
    tmp = out.with_suffix('.pending')
    tmp.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
    tmp.replace(out)
'''


class OCRBridgeTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        (self.root / "config").mkdir()
        (self.root / "ocr_runtime").mkdir()
        shutil.copyfile(ROOT / "config/ocr.json", self.root / "config/ocr.json")
        (self.root / "ocr_runtime/worker.py").write_text(FAKE_WORKER.replace("DELAY", ".25"), encoding="utf-8")
        self.reader = TextReader(self.root, python_path=sys.executable)

    def tearDown(self):
        self.reader.close()
        self.directory.cleanup()

    def frames(self):
        rgb = np.full((50, 60, 3), [200, 50, 10], dtype=np.uint8)
        return FrameBundle(rgb=rgb, color_received_at=time.monotonic())

    def wait_result(self):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            result = self.reader.poll()
            if result is not None:
                return result
            time.sleep(.01)
        self.fail("OCR test timed out")

    def test_request_is_nonblocking_and_rgb_conversion_is_correct(self):
        f = self.frames()
        start = time.monotonic()
        self.assertTrue(self.reader.request(f))
        self.assertLess(time.monotonic() - start, .15)
        f.rgb[:] = 0
        result = self.wait_result()
        self.assertEqual(result["pixel_bgr"], [10, 50, 200])
        self.assertEqual(self.reader.last_text, "Xin chào")
        self.assertFalse(list((self.root / "runtime/ocr_jobs").iterdir()))

    def test_busy_rejects_another_request(self):
        self.assertTrue(self.reader.request(self.frames()))
        self.assertFalse(self.reader.request(self.frames()))
        self.assertEqual(self.wait_result()["status"], "ok")

    def test_cancel_does_not_publish_late_result_and_can_restart(self):
        self.reader.request(self.frames())
        time.sleep(.05)
        self.reader.cancel()
        self.reader._thread.join(timeout=2)
        self.assertIsNone(self.reader.poll())
        self.assertFalse(list((self.root / "runtime/ocr_jobs").iterdir()))
        self.assertTrue(self.reader.request(self.frames()))
        self.assertEqual(self.wait_result()["status"], "ok")

    def test_timeout_terminates_worker_and_returns_state(self):
        self.reader.settings["timeout_s"] = .1
        self.reader.request(self.frames())
        self.assertEqual(self.wait_result()["status"], "timeout")
        self.assertIsNone(self.reader._process)

    def test_no_frame_stale_and_missing_environment(self):
        self.assertFalse(self.reader.request(FrameBundle()))
        self.assertEqual(self.reader.status, "no_frame")
        f = self.frames()
        f.color_received_at -= 3
        self.assertFalse(self.reader.request(f))
        self.assertEqual(self.reader.status, "stale")
        self.reader.python = self.root / "absent.exe"
        self.assertFalse(self.reader.request(self.frames()))
        self.assertEqual(self.reader.status, "unavailable")

    def test_worker_crash_is_reported(self):
        (self.root / "ocr_runtime/worker.py").write_text("raise RuntimeError('crash')")
        self.reader.request(self.frames())
        with self.assertLogs(level="ERROR"):
            self.assertEqual(self.wait_result()["status"], "error")

    def test_close_cannot_start_more_work(self):
        self.reader.close()
        self.assertFalse(self.reader.request(self.frames()))

    def test_invalid_config_detected(self):
        p = self.root / "config/ocr.json"
        settings = read_settings(p)
        settings["cpu_threads"] = .5
        p.write_text(json.dumps(settings))
        with self.assertRaises(ValueError):
            read_settings(p)
        with self.assertLogs(level="WARNING"):
            disabled = TextReader(self.root, python_path=sys.executable)
        try:
            self.assertFalse(disabled.request(self.frames()))
            self.assertEqual(disabled.status, "unavailable")
        finally:
            disabled.close()


class OCRGeometryTests(unittest.TestCase):
    def box(self, x, y, width=50, height=15):
        return np.float32([[x, y], [x + width, y], [x + width, y + height], [x, y + height]])

    def test_line_order_uses_height_not_rounding_bin(self):
        boxes = [self.box(80, 20), self.box(5, 22), self.box(5, 60)]
        ordered = ordered_rows(boxes)
        self.assertEqual([int(b[0, 0]) for b in ordered], [5, 80, 5])

    def test_perspective_crop_preserves_rotated_text_area(self):
        image = np.full((120, 200, 3), 255, np.uint8)
        box = np.float32([[20, 30], [150, 50], [148, 70], [18, 50]])
        crop = rectify(image, box)
        self.assertGreater(crop.shape[1], crop.shape[0] * 3)
        self.assertTrue(np.all(crop == 255))

    def test_empty_or_wrong_color_shape_is_error(self):
        settings = read_settings(ROOT / "config/ocr.json")
        engine = VietnameseOCR("unused", settings, detector=Mock(), recognizer=Mock())
        self.assertEqual(engine.read(None)["status"], "error")
        self.assertEqual(engine.read(np.zeros((10, 10), np.uint8))["status"], "error")

    def test_blur_does_not_invoke_model(self):
        settings = read_settings(ROOT / "config/ocr.json")
        detector = Mock()
        engine = VietnameseOCR("unused", settings, detector=detector, recognizer=Mock())
        self.assertEqual(engine.read(np.zeros((40, 40, 3), np.uint8))["status"], "blurry")
        detector.assert_not_called()

    def test_missing_models_fail_before_network_or_model_import(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                VietnameseOCR(directory, read_settings(ROOT / "config/ocr.json"))


class SpeechPriorityTests(unittest.TestCase):
    def test_beep_interrupts_speech_first(self):
        calls = []
        player, speech = Mock(), Mock()
        player.submit.side_effect = lambda event: calls.append("beep") or True
        speech.stop.side_effect = lambda: calls.append("stop_speech")
        coordinator = CoordinatorAudio(player, speech=speech)
        report = ObstacleReport("ok", (ZoneRisk("CENTER", 2, True, .9, 0, None, "critical"),), None)
        coordinator.process(report, 2)
        self.assertEqual(calls, ["stop_speech", "beep"])
        self.assertFalse(coordinator.read_text("hello", 2.1))
        speech.speak.assert_not_called()

    def test_muting_stops_speech_and_suppresses_new_text(self):
        speech = Mock()
        coordinator = CoordinatorAudio(Mock(), speech=speech)
        coordinator.toggle_mute()
        speech.stop.assert_called_once()
        self.assertFalse(coordinator.read_text("hello", 10))

    def test_repeat_requires_available_voice(self):
        coordinator = CoordinatorAudio(Mock())
        self.assertFalse(coordinator.read_text("hello", 10))


if __name__ == "__main__":
    unittest.main()
