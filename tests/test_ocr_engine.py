"""Run with .ocr-venv Python to test the recognition result contract."""
import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ocr_runtime"))
from text_reader.ocr_reader import VietnameseOCR
from thirdeyes.ocr import read_settings


@unittest.skipUnless(importlib.util.find_spec("PIL"), "Run these tests with .ocr-venv Python (Pillow)")
class RecognitionTests(unittest.TestCase):
    def engine(self, outputs, **changes):
        settings = read_settings(ROOT / "config/ocr.json")
        settings.update(blur_threshold=0, **changes)
        boxes = [np.float32([[10, y], [100, y], [100, y + 20], [10, y + 20]]) for y in range(10, 10 + len(outputs) * 30, 30)]
        detector = Mock(return_value=(np.asarray(boxes), 0))
        recognizer = Mock()
        recognizer.predict.side_effect = outputs
        return VietnameseOCR("unused", settings, detector, recognizer)

    def test_low_confidence_is_kept_raw_but_not_spoken_as_fact(self):
        result = self.engine([("sai", .2)]).read(np.full((100, 100, 3), 200, np.uint8))
        self.assertEqual(result["status"], "low_confidence")
        self.assertEqual(result["text_raw"], "sai")
        self.assertEqual(result["text"], "")
        self.assertNotEqual(result["speak"], "sai")

    def test_confident_regions_keep_original_coordinates_and_newlines(self):
        result = self.engine([("Xin chào", .9), ("Việt Nam", .95)]).read(np.full((100, 100, 3), 200, np.uint8))
        self.assertEqual(result["text"], "Xin chào\nViệt Nam")
        self.assertEqual(result["regions"][0]["box"][0], [5., 5.])

    def test_text_limit_is_explicit(self):
        result = self.engine([("x" * 150, .9)], max_characters=100).read(np.full((100, 100, 3), 200, np.uint8))
        self.assertTrue(result["truncated"])
        self.assertEqual(len(result["text"]), 100)

    def test_region_limit_is_explicit(self):
        result = self.engine([("a", .9), ("b", .9)], max_regions=1).read(np.full((100, 100, 3), 200, np.uint8))
        self.assertTrue(result["truncated"])
        self.assertEqual(result["text"], "a")

    def test_no_boxes_returns_no_text(self):
        result = self.engine([]).read(np.full((100, 100, 3), 200, np.uint8))
        self.assertEqual(result["status"], "no_text")


if __name__ == "__main__":
    unittest.main()
