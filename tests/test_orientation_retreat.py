import unittest
from unittest.mock import patch

import numpy as np

from thirdeyes.capture.kinect import KinectCapture
from thirdeyes.config import ObstacleConfig
from thirdeyes.contracts import DepthCell, DepthObservation
from thirdeyes.obstacle_detection import ObstacleDetector
from thirdeyes.coordinator_audio import CoordinatorAudio
from test_obstacles import Pipeline, frame, FakePlayer


class OrientationTests(unittest.TestCase):
    def test_both_streams_flip_before_consumers_and_cached_frames_do_not_flip_again(self):
        native_rgb = np.arange(24, dtype=np.uint8).reshape(2, 4, 3)
        native_depth = np.arange(8, dtype=np.uint16).reshape(2, 4)
        capture = KinectCapture()
        with patch.object(capture, "_read_stream", side_effect=[(native_rgb, 10), (native_depth, 11), None, None]):
            result = capture.read()
            np.testing.assert_array_equal(result.rgb, native_rgb[:, ::-1])
            np.testing.assert_array_equal(result.depth_mm, native_depth[:, ::-1])
            self.assertEqual(result.color_timestamp_ms, 10)
            before = result.rgb.copy()
            capture.read()
            np.testing.assert_array_equal(result.rgb, before)
            self.assertTrue(result.rgb.flags.c_contiguous)
        np.testing.assert_array_equal(native_rgb, np.arange(24, dtype=np.uint8).reshape(2, 4, 3))

    def test_native_orientation_can_be_requested_for_diagnostics(self):
        rgb = np.zeros((2, 4, 3), np.uint8)
        rgb[:, 0] = 255
        capture = KinectCapture(flip_horizontal=False)
        with patch.object(capture, "_read_stream", side_effect=[(rgb, 1), None]):
            np.testing.assert_array_equal(capture.read().rgb, rgb)

    def test_mirrored_text_input_returns_original_pixels_for_ocr(self):
        # An asymmetric glyph pattern stands for text; OCR gets exactly the
        # original pixels, not a second display-only flip or a channel swap.
        correct = np.zeros((40, 80, 3), np.uint8)
        correct[3:35, 8:12] = [255, 80, 10]
        correct[3:8, 8:30] = [255, 80, 10]
        native = correct[:, ::-1].copy()
        capture = KinectCapture()
        with patch.object(capture, "_read_stream", side_effect=[(native, 1), None]):
            np.testing.assert_array_equal(capture.read().rgb, correct)

    def test_depth_obstacle_direction_is_flipped_for_detector(self):
        p = Pipeline()
        native = np.full((120, 160), 3500, np.uint16)
        native[25:90, 35:55] = 1200  # SDK LEFT becomes normalized RIGHT
        capture = KinectCapture()
        for _ in range(20):
            with patch.object(capture, "_read_stream", side_effect=[None, (native, round(p.t * 1000))]):
                frames = capture.read()
                frames.depth_received_at = p.t
                p.push(frames)
            p.t += .05
        self.assertEqual(p.player.events[0].zones, ("RIGHT",))


class RetreatTests(unittest.TestCase):
    def hazard_events(self, p):
        return [e for e in p.player.events if e.kind in {"near", "urgent"}]

    def move(self, p, start, end, speed):
        direction = 1 if end > start else -1
        n = round(abs(end - start) / speed / .05)
        for i in range(n + 1):
            distance = start + direction * i * speed * .05
            p.push(frame(distance, p.t))
            p.t += .05

    def test_invalid_to_08_and_away_is_silent_through_warning_range(self):
        p = Pipeline()
        p.feed(invalid=True, duration=.3)
        self.move(p, .8, 2.1, .4)
        self.assertFalse(self.hazard_events(p))

    def test_background_to_08_then_retreat_is_silent(self):
        p = Pipeline()
        p.feed(3.5, .5)
        self.move(p, .8, 2.0, .4)
        self.assertFalse(self.hazard_events(p))

    def test_first_measurement_above_boundary_can_still_recede(self):
        p = Pipeline()
        p.feed(invalid=True, duration=.3)
        self.move(p, 1.1, 2.0, .4)
        self.assertFalse(self.hazard_events(p))

    def test_slow_recession_is_not_announced(self):
        p = Pipeline()
        p.feed(invalid=True, duration=.3)
        self.move(p, .8, 1.2, .10)
        self.assertFalse(self.hazard_events(p))

    def test_stopping_near_reenables_warning(self):
        p = Pipeline()
        self.move(p, .8, 1.1, .3)
        self.assertFalse(self.hazard_events(p))
        p.feed(1.1, 1.5)
        self.assertEqual(len(self.hazard_events(p)), 1)

    def test_reversing_back_towards_camera_reenables_warning(self):
        p = Pipeline()
        self.move(p, .8, 1.2, .4)
        self.assertFalse(self.hazard_events(p))
        self.move(p, 1.2, .85, .5)
        self.assertTrue(self.hazard_events(p))

    def test_stationary_return_at_08_is_not_silenced_forever(self):
        p = Pipeline()
        p.feed(invalid=True, duration=.3)
        p.feed(.81, 1.5)
        self.assertEqual([e.kind for e in self.hazard_events(p)], ["urgent"])

    def test_boundary_jitter_does_not_fake_sustained_retreat(self):
        p = Pipeline()
        for i in range(40):
            p.push(frame(.82 + (.005 if i % 2 else -.005), p.t))
            p.t += .05
        self.assertEqual(len(self.hazard_events(p)), 1)

    def test_repeated_frames_cannot_establish_recession(self):
        p = Pipeline()
        f = frame(.8, 0)
        for i in range(6):
            p.push(f, now=i * .05)
        self.assertEqual(p.report.zones[0].reason, "emerging")
        self.assertFalse(self.hazard_events(p))

    def test_recession_does_not_mask_another_obstacle_in_same_zone(self):
        detector = ObstacleDetector()
        player = FakePlayer()
        audio = CoordinatorAudio(player)
        for i in range(45):
            t = i * .05
            # Cell 0 emerges/recedes; cell 1 is a distinct stationary hazard.
            distances = [.8 + t * .4, 1.2, 3.5, 3.5, 3.5, 3.5]
            cells = tuple(DepthCell(j, "CENTER", (0, 0, 1, 1), d, 1.) for j, d in enumerate(distances))
            report = detector.process(DepthObservation("ok", True, t, cells, (0, 0, 1, 1)))
            audio.process(report, t)
        self.assertTrue([e for e in player.events if e.kind in {"near", "urgent"}])

    def test_existing_latched_risk_does_not_beep_on_receding_reappearance(self):
        p = Pipeline()
        p.feed(.85, 1)
        p.feed(invalid=True, duration=.3)
        p.audio.announced.clear()  # e.g. mute/unmute while depth is unavailable
        before = len(self.hazard_events(p))
        self.move(p, .8, 2.1, .4)
        self.assertEqual(len(self.hazard_events(p)), before)

    def test_old_hysteresis_does_not_turn_background_into_new_hazard(self):
        detector, player = ObstacleDetector(), FakePlayer()
        audio = CoordinatorAudio(player)

        def feed(t, distances):
            cells = tuple(DepthCell(j, "CENTER", (0, 0, 1, 1), d, 1. if d is not None else 0.)
                          for j, d in enumerate(distances))
            report = detector.process(DepthObservation("ok" if None not in distances else "invalid", True, t, cells, (0, 0, 1, 1)))
            audio.process(report, t)

        for i in range(20):
            feed(i * .05, [.85] * 6)
        feed(1., [None] * 6)
        audio.announced.clear()
        before = len(player.events)
        for i in range(55):
            feed(1.05 + i * .05, [.8 + i * .02] + [1.6] * 5)
        self.assertEqual(len(player.events), before)

    def test_invalid_new_configuration_is_rejected(self):
        for values in ({"emergence_observe_s": 4}, {"recession_reverse_m": .001},
                       {"emergence_entry_m": .6}, {"recession_stop_s": 0}):
            with self.assertRaises(ValueError):
                ObstacleConfig(**values)


if __name__ == "__main__":
    unittest.main()
