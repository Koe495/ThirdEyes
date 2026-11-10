import ctypes as ct
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import numpy as np

from thirdeyes.contracts import FrameBundle, DepthCell, ObstacleReport
from thirdeyes.rgbd import FrameSynchronizer, RGBDPair, measure_polygon, KinectRegionMapper
from thirdeyes.obstacle_tracking import PatchTracker
from thirdeyes.evaluation import metrics, SessionRecorder
from thirdeyes.voice_commands import parse_command, VoiceCommands
from thirdeyes.speech import OfflineSpeech
from repair_environment import repair


def bundle(color, depth, now=1):
    return FrameBundle(np.zeros((4, 4, 3), np.uint8), np.full((4, 4), 1000, np.uint16), color, depth, now, now)


class PairingTests(unittest.TestCase):
    def test_pairs_within_tolerance_and_expires(self):
        sync = FrameSynchronizer()
        sync.update(bundle(100, 112))
        self.assertEqual(sync.latest(1.1).skew_ms, 12)
        self.assertIsNone(sync.latest(1.4))

    def test_large_skew_is_not_pair(self):
        sync = FrameSynchronizer()
        sync.update(bundle(100, 125))
        self.assertIsNone(sync.latest(1))

    def test_matches_buffered_frame_not_latest_unrelated_rgb(self):
        sync = FrameSynchronizer()
        first = bundle(100, 0)
        sync.update(first)
        sync.update(bundle(150, 110, 1.05))
        self.assertEqual(sync.latest(1.05).color_ms, 100)
        self.assertIs(sync.latest(1.05).rgb, first.rgb)

    def test_duplicate_sensor_timestamp_does_not_refresh_age(self):
        sync = FrameSynchronizer()
        sync.update(bundle(100, 101))
        sync.update(bundle(100, 101, 2))
        self.assertIsNone(sync.latest(2))

    def test_timestamp_reset_drops_old_pair(self):
        sync = FrameSynchronizer()
        sync.update(bundle(100, 101))
        sync.update(bundle(5, 70, 1.1))
        self.assertIsNone(sync.latest(1.1))

    def test_buffers_are_bounded(self):
        sync = FrameSynchronizer()
        for i in range(100):
            sync.update(bundle(i * 33, i * 33 + 5, i * .033))
        self.assertLessEqual(len(sync.colors), 6)
        self.assertLessEqual(len(sync.depths), 6)


class MappingTests(unittest.TestCase):
    box = [[0, 0], [20, 0], [20, 20], [0, 20]]

    def test_region_uses_valid_samples_inside_polygon(self):
        points = [(x, 4, 1200) for x in range(15)] + [(100, 4, 800), (3, 3, 0)]
        result = measure_polygon(points, self.box)
        self.assertEqual(result, {'status': 'ok', 'distance_m': 1.2, 'samples': 15})

    def test_mixed_foreground_background_is_not_a_precise_measurement(self):
        points = [(x, 4, 1000 if x < 8 else 2500) for x in range(15)]
        self.assertEqual(measure_polygon(points, self.box)['status'], 'mixed_depth')

    def test_sparse_or_invalid_polygon_is_unknown(self):
        self.assertIsNone(measure_polygon([(1, 1, 1100)], self.box)['distance_m'])
        self.assertEqual(measure_polygon([], [[float('nan'), 0]] * 4)['status'], 'invalid_region')

    def test_sdk_native_coordinates_and_packed_depth_then_reflip(self):
        capture = Mock(flip_horizontal=True)
        seen = []
        def project(cr, dr, view, x, y, depth, cx, cy):
            seen.append((x, y, depth))
            ct.cast(cx, ct.POINTER(ct.c_int32))[0] = x - 10
            ct.cast(cy, ct.POINTER(ct.c_int32))[0] = y
            return 0
        capture.dll.NuiImageGetColorPixelCoordinatesFromDepthPixelAtResolution = project
        depth = np.zeros((480, 640), np.uint16)
        depth[4, 8] = 1200
        pair = RGBDPair(np.zeros((480, 640, 3), np.uint8), depth, 100, 105, 1)
        points = KinectRegionMapper(capture).points(pair, threading.Event())
        self.assertEqual(seen, [(631, 4, 1200 << 3)])
        self.assertEqual(points, [(18, 4, 1200)])

    def test_mapping_rejects_unsynchronized_pair(self):
        pair = RGBDPair(None, None, 10, 40, 1)
        with self.assertRaises(ValueError):
            KinectRegionMapper(Mock()).points(pair, threading.Event())


def cell(index, distance):
    x, y = index % 6 * 10, index // 6 * 10
    return DepthCell(index, 'CENTER', (x, y, x + 10, y + 10), distance, 1)


class TrackingTests(unittest.TestCase):
    def test_patch_keeps_id_when_moving_one_cell(self):
        tracker = PatchTracker()
        first = tracker.update([cell(1, 1.2)], 0)[0]
        moved = tracker.update([cell(2, 1.25)], .1)[0]
        self.assertEqual(first.track_id, moved.track_id)
        self.assertEqual(moved.age_s, .1)

    def test_separate_patches_and_missing_are_not_drawn_as_current(self):
        tracker = PatchTracker()
        tracks = tracker.update([cell(0, 1.0), cell(5, 2.)], 0)
        self.assertEqual(len(tracks), 2)
        self.assertEqual(tracker.update([], .1), ())
        self.assertEqual(tracker.update([cell(0, 1.0)], .2)[0].track_id, tracks[0].track_id)

    def test_long_gap_starts_new_id(self):
        tracker = PatchTracker()
        first = tracker.update([cell(1, 1.2)], 0)[0]
        last = tracker.update([cell(1, 1.2)], 1)[0]
        self.assertNotEqual(first.track_id, last.track_id)


class VoiceAndMetricsTests(unittest.TestCase):
    def test_voice_exact_whitelist_and_confidence(self):
        self.assertEqual(parse_command({'text': ' ĐỌC  VĂN BẢN ', 'result': [{'conf': .9}]}), 'read')
        for text in ('tắt cảnh báo', 'thoát', 'đọc văn bản ngay'):
            self.assertIsNone(parse_command({'text': text, 'result': [{'conf': .99}]}))
        self.assertIsNone(parse_command({'text': 'đọc lại', 'result': [{'conf': .5}]}))
        self.assertIsNone(parse_command({'text': 'đọc lại'}))

    def test_microphone_is_not_opened_on_initialization(self):
        with patch('thirdeyes.voice_commands.subprocess.Popen') as process:
            voice = VoiceCommands('unused')
            process.assert_not_called()
            voice.close()
            self.assertFalse(voice.listen())

    def test_metric_counts_substitution_deletion_and_insertions(self):
        result = metrics('xin chào bạn', 'xin chào')
        self.assertEqual(result['word_errors'], 1)
        self.assertAlmostEqual(result['wer'], 1 / 3)
        self.assertEqual(metrics('á', 'a\u0301')['cer'], 0)
        self.assertTrue(metrics('', 'noise')['unexpected_text'])
        self.assertIsNone(metrics('', '')['cer'])

    def test_recording_does_not_overwrite_an_existing_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(FileExistsError):
                SessionRecorder(folder)
            recorder = SessionRecorder(Path(folder) / 'new')
            try:
                recorder.record(bundle(1, 2), ObstacleReport('ok', (), None), 1)
                recorder.record(bundle(1, 2), ObstacleReport('ok', (), None), 1.05)
            finally:
                recorder.close()
            rows = (Path(folder) / 'new/frames.jsonl').read_text().splitlines()
            self.assertEqual(len(rows), 1)
            self.assertEqual(json.loads(rows[0])['depth_ms'], 2)

    def test_relocation_repairs_only_project_environments(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            base = root / '.runtimes/cpython-3.10.22-windows-x86_64-none/python.exe'
            base.parent.mkdir(parents=True); base.touch()
            cfg = root / '.ocr-venv/pyvenv.cfg'
            cfg.parent.mkdir(); cfg.write_text('home = Z:\\old\\python\n')
            with patch('repair_environment.subprocess.run') as run:
                repair(root)
            self.assertEqual(run.call_args.args[0][-1], str(root / '.ocr-venv'))
            self.assertTrue(cfg.with_suffix('.cfg.before_repair').is_file())


if __name__ == '__main__':
    unittest.main()
