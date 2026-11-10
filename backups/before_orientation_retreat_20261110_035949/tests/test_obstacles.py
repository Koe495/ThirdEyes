import dataclasses
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import numpy as np

from thirdeyes.config import ObstacleConfig, load_config
from thirdeyes.contracts import FrameBundle, SoundEvent
from thirdeyes.coordinator_audio import BeepPlayer, CoordinatorAudio
from thirdeyes.depth_processing import DepthProcessor
from thirdeyes.obstacle_detection import ObstacleDetector


class FakePlayer:
    error = None

    def __init__(self):
        self.events = []
        self.accept = True

    def submit(self, event):
        if self.accept:
            self.events.append(event)
        return self.accept

    def close(self):
        pass


def frame(distance=3.5, timestamp=0., invalid=False):
    depth = np.full((120, 160), int(distance * 1000), np.uint16)
    if invalid:
        depth[:] = 0
    return FrameBundle(depth_mm=depth, depth_timestamp_ms=round(timestamp * 1000), depth_received_at=timestamp)


class Pipeline:
    def __init__(self):
        self.processor = DepthProcessor()
        self.detector = ObstacleDetector()
        self.player = FakePlayer()
        self.audio = CoordinatorAudio(self.player)
        self.t = 0.
        self.report = None

    def feed(self, distance=3.5, duration=.5, invalid=False):
        for _ in range(round(duration / .05)):
            self.push(frame(distance, self.t, invalid))
            self.t += .05
        return self.report

    def push(self, f, now=None):
        self.report = self.detector.process(self.processor.process(f, self.t if now is None else now))
        self.audio.process(self.report, self.t if now is None else now)
        return self.report


class ObstacleTests(unittest.TestCase):
    def test_stationary_near_only_one_beep_over_30_seconds(self):
        p = Pipeline()
        report = p.feed(1.25, 30)
        self.assertEqual([e.kind for e in p.player.events], ["near"])
        self.assertTrue(all(z.level == 1 for z in report.zones))

    def test_stationary_critical_only_one_urgent(self):
        p = Pipeline()
        p.feed(.90, 4)
        self.assertEqual([e.kind for e in p.player.events], ["urgent"])

    def test_far_no_beep(self):
        p = Pipeline()
        p.feed(3.5, 3)
        self.assertFalse(p.player.events)

    def test_fast_approach_warns_before_near_threshold(self):
        p = Pipeline()
        for i in range(16):
            p.push(frame(2.8 - i * .05, p.t))
            p.t += .05
        self.assertEqual(p.player.events[0].kind, "urgent")
        self.assertTrue(all(z.distance_m > 1.5 for z in p.report.zones))
        self.assertGreater(p.report.zones[0].closing_mps, .8)

    def test_retreat_does_not_count_as_approach(self):
        p = Pipeline()
        for i in range(20):
            p.push(frame(2 + i * .05, p.t))
            p.t += .05
        self.assertFalse(p.player.events)

    def test_fast_motion_restarts_after_stationary_pause(self):
        p = Pipeline()
        p.feed(.85, 1)  # remember an earlier, very close risk
        p.feed(1.6, 2)  # still inside near-release range; does not rearm episode
        previous = len(p.player.events)
        for i in range(10):
            p.push(frame(1.6 - i * .05, p.t))
            p.t += .05
        self.assertGreater(len(p.player.events), previous)
        self.assertEqual(p.player.events[-1].kind, "urgent")

    def test_missing_patch_must_not_clear_latched_zone(self):
        p = Pipeline()
        p.feed(1.2, .5)
        for _ in range(40):
            f = frame(3.5, p.t)
            # Remove one complete center grid tile while other tiles are far.
            f.depth_mm[21:45, 64:80] = 0
            p.push(f)
            p.t += .05
        center = next(z for z in p.report.zones if z.zone == "CENTER")
        self.assertFalse(center.known)
        self.assertEqual(center.level, 1)

    def test_failed_audio_is_visible_and_does_not_crash(self):
        with patch("winsound.Beep", side_effect=RuntimeError("speaker unavailable")):
            player = BeepPlayer()
            try:
                with self.assertLogs(level="ERROR"):
                    player.submit(SoundEvent("near", "test"))
                    player._queue.join()
                self.assertIn("speaker unavailable", player.error)
                self.assertFalse(player.submit(SoundEvent("near", "test")))
            finally:
                player.close()

    def test_single_depth_step_is_not_fast_motion(self):
        p = Pipeline()
        p.feed(3.5, 1)
        p.feed(2.0, 1)
        self.assertFalse(p.player.events)

    def test_one_frame_near_glitch_does_not_beep(self):
        p = Pipeline()
        p.feed(3, .5)
        p.feed(.9, .05)
        p.feed(3, 1)
        self.assertFalse(p.player.events)

    def test_near_threshold_jitter_does_not_chatter(self):
        p = Pipeline()
        p.feed(1.45, .5)
        for i in range(80):
            p.feed(1.48 if i % 2 else 1.53, .05)
        self.assertEqual(len(p.player.events), 1)

    def test_clear_then_new_obstacle_rearms(self):
        p = Pipeline()
        p.feed(1.25, 1)
        p.feed(3.5, 2)
        p.feed(1.25, 1)
        self.assertEqual([e.kind for e in p.player.events], ["near", "near"])

    def test_short_clearance_does_not_rearm(self):
        p = Pipeline()
        p.feed(1.25, 1)
        p.feed(3.5, .3)
        p.feed(1.25, 1)
        self.assertEqual(len(p.player.events), 1)

    def test_closer_by_25cm_triggers_again(self):
        p = Pipeline()
        p.feed(1.48, 1)
        p.feed(1.18, 1)
        self.assertEqual(len(p.player.events), 2)

    def test_escalation_to_critical(self):
        p = Pipeline()
        p.feed(1.15, 1)
        p.feed(.95, .5)
        self.assertEqual([e.kind for e in p.player.events], ["near", "urgent"])

    def test_invalid_is_unknown_not_clear_and_not_periodic(self):
        p = Pipeline()
        p.feed(1.25, 1)
        p.feed(invalid=True, duration=4)
        self.assertEqual(p.report.status, "invalid")
        self.assertTrue(all(z.level == 1 and not z.known for z in p.report.zones))
        p.feed(1.25, 3)
        self.assertEqual([e.kind for e in p.player.events], ["near", "depth_unavailable"])

    def test_invalid_flicker_does_not_beep(self):
        p = Pipeline()
        for _ in range(12):
            p.feed(invalid=True, duration=.1)
            p.feed(3.5, .2)
        self.assertFalse(p.player.events)

    def test_fault_rearms_after_sustained_recovery(self):
        p = Pipeline()
        p.feed(invalid=True, duration=2)
        p.feed(3.5, 2.5)
        p.feed(invalid=True, duration=2)
        self.assertEqual([e.kind for e in p.player.events], ["depth_unavailable"] * 2)

    def test_repeated_frame_not_counted_as_multiple_confirmations(self):
        p = Pipeline()
        f = frame(1.2, 0)
        for i in range(10):
            p.push(f, now=i * .05)
        self.assertFalse(p.player.events)

    def test_frozen_stream_becomes_stale_and_beeps_once(self):
        p = Pipeline()
        f = frame(3.0, 0)
        for i in range(100):
            p.push(f, now=i * .05)
        self.assertEqual(p.report.status, "stale")
        self.assertEqual([e.kind for e in p.player.events], ["depth_unavailable"])

    def test_frozen_sensor_timestamp_even_if_receipt_time_changes(self):
        p = Pipeline()
        for i in range(60):
            f = frame(3.0, 0)
            f.depth_received_at = i * .05
            p.push(f, now=i * .05)
        self.assertEqual(p.report.status, "stale")
        self.assertEqual([e.kind for e in p.player.events], ["depth_unavailable"])

    def test_timestamp_reset_does_not_create_velocity(self):
        p = Pipeline()
        p.feed(3.5, 1)
        p.t = 0
        p.feed(2.1, .5)
        self.assertFalse(p.player.events)

    def test_invalid_sentinels_excluded(self):
        for value in (0, 4095, 8191, 600):
            f = frame()
            f.depth_mm[:] = value
            result = DepthProcessor().process(f, 0)
            self.assertEqual(result.status, "invalid")
            self.assertTrue(all(c.distance_m is None for c in result.cells))

    def test_isolated_close_pixel_does_not_trigger(self):
        p = Pipeline()
        for _ in range(15):
            f = frame(3.5, p.t)
            f.depth_mm[50, 80] = 850
            p.push(f)
            p.t += .05
        self.assertFalse(p.player.events)

    def test_center_patch_detected_with_far_background(self):
        p = Pipeline()
        for _ in range(12):
            f = frame(3.5, p.t)
            f.depth_mm[40:80, 70:90] = 1200
            p.push(f)
            p.t += .05
        self.assertEqual(p.player.events[0].zones, ("CENTER",))

    def test_outside_roi_is_not_obstacle(self):
        p = Pipeline()
        for _ in range(12):
            f = frame(3.5, p.t)
            f.depth_mm[100:, :] = 850
            p.push(f)
            p.t += .05
        self.assertFalse(p.player.events)

    def test_mute_then_unmute_warns_current_hazard(self):
        p = Pipeline()
        p.audio.toggle_mute()
        p.feed(1.2, 2)
        self.assertFalse(p.player.events)
        p.audio.toggle_mute()
        p.feed(1.2, .5)
        self.assertEqual(len(p.player.events), 1)

    def test_busy_audio_retries_current_risk_without_dropping(self):
        p = Pipeline()
        p.player.accept = False
        p.feed(1.2, 1)
        self.assertFalse(p.player.events)
        p.player.accept = True
        p.feed(1.2, .5)
        self.assertEqual(len(p.player.events), 1)

    def test_audio_does_not_block_capture_or_queue_many_beeps(self):
        entered, release = threading.Event(), threading.Event()

        def beep(*args):
            entered.set()
            release.wait(1)

        with patch("winsound.Beep", side_effect=beep):
            player = BeepPlayer()
            try:
                start = time.monotonic()
                self.assertTrue(player.submit(SoundEvent("near", "test")))
                self.assertLess(time.monotonic() - start, .1)
                self.assertTrue(entered.wait(.5))
                self.assertFalse(player.submit(SoundEvent("urgent", "test")))
            finally:
                release.set()
                player.close()

    def test_config_rejects_invalid_thresholds(self):
        for values in ({"near_m": .7}, {"critical_m": float("nan")}, {"cooldown_s": 0},
                       {"roi_left": .9}, {"progress_m": .01}, {"near_m": "1.5"}):
            with self.assertRaises(ValueError):
                ObstacleConfig(**values)

    def test_config_load_and_unknown_key(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(dataclasses.asdict(ObstacleConfig())))
            self.assertEqual(load_config(path), ObstacleConfig())
            path.write_text('{"near_typo": 1.5}')
            with self.assertRaises(ValueError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
