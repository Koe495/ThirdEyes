import io
import unittest
import wave
from unittest.mock import patch

import numpy as np

from thirdeyes.app import main
from thirdeyes.contracts import ObstacleReport, SoundEvent, ZoneRisk
from thirdeyes.coordinator_audio import BeepPlayer, CoordinatorAudio
from thirdeyes.stereo_audio import render_cue, SAMPLE_RATE
from test_obstacles import FakePlayer


def decode(data):
    with wave.open(io.BytesIO(data), "rb") as wav:
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (2, 2, SAMPLE_RATE)
        return np.frombuffer(wav.readframes(wav.getnframes()), dtype="<i2").reshape(-1, 2)


def risk(zone, level, distance):
    return ZoneRisk(zone, level, True, distance, 0., None, "near")


class StereoTests(unittest.TestCase):
    def test_left_only_in_left_channel(self):
        pcm = decode(render_cue("near", ("LEFT",)))
        self.assertTrue(np.any(pcm[:, 0]))
        self.assertFalse(np.any(pcm[:, 1]))

    def test_right_only_in_right_channel(self):
        pcm = decode(render_cue("near", ("RIGHT",)))
        self.assertFalse(np.any(pcm[:, 0]))
        self.assertTrue(np.any(pcm[:, 1]))

    def test_center_equal_channels_and_equal_total_energy(self):
        center = decode(render_cue("near", ("CENTER",))).astype(float)
        left = decode(render_cue("near", ("LEFT",))).astype(float)
        np.testing.assert_array_equal(center[:, 0], center[:, 1])
        self.assertAlmostEqual(np.sum(center ** 2) / np.sum(left ** 2), 1., places=3)

    def test_opposite_obstacles_are_separate_not_false_center(self):
        pcm = decode(render_cue("urgent", ("LEFT", "RIGHT")))
        tone, gap = round(.15 * SAMPLE_RATE), round(.06 * SAMPLE_RATE)
        self.assertEqual(len(pcm), 2 * tone + gap)
        self.assertFalse(np.any(pcm[:tone, 1]))
        self.assertFalse(np.any(pcm[tone:tone + gap]))
        self.assertFalse(np.any(pcm[tone + gap:, 0]))
        self.assertTrue(np.any(pcm[tone + gap:, 1]))

    def test_test_sequence_left_center_right(self):
        pcm = decode(render_cue("test"))
        tone, step = round(.1 * SAMPLE_RATE), round(.22 * SAMPLE_RATE)
        self.assertFalse(np.any(pcm[:tone, 1]))
        np.testing.assert_array_equal(pcm[step:step + tone, 0], pcm[step:step + tone, 1])
        self.assertFalse(np.any(pcm[2 * step:, 0]))
        self.assertTrue(np.any(pcm[2 * step:, 1]))

    def test_swapped_output_is_exact_channel_reverse(self):
        normal = decode(render_cue("test"))
        swapped = decode(render_cue("test", swap_channels=True))
        np.testing.assert_array_equal(normal[:, ::-1], swapped)

    def test_fault_has_no_direction_and_lower_pitch(self):
        pcm = decode(render_cue("depth_unavailable", ("LEFT",)))
        np.testing.assert_array_equal(pcm[:, 0], pcm[:, 1])
        spectrum = abs(np.fft.rfft(pcm[:, 0]))
        frequency = np.fft.rfftfreq(len(pcm), 1 / SAMPLE_RATE)[spectrum.argmax()]
        self.assertAlmostEqual(frequency, 500)

    def test_ramps_no_clipping_and_volume_scaling(self):
        for kind in ("near", "urgent", "depth_unavailable", "test"):
            pcm = decode(render_cue(kind, ("LEFT",), volume=1))
            self.assertFalse(np.any(pcm[[0, -1]]))
            self.assertLessEqual(abs(pcm.astype(int)).max(), 32767)
        loud = decode(render_cue("near", ("LEFT",), volume=.5)).astype(float)
        soft = decode(render_cue("near", ("LEFT",), volume=.25)).astype(float)
        self.assertAlmostEqual(np.linalg.norm(loud) / np.linalg.norm(soft), 2, places=3)

    def test_invalid_volume_rejected_before_thread_start(self):
        for volume in (-1, 0, 2, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                BeepPlayer(volume=volume)

    def test_highest_severity_first_then_remaining_direction(self):
        player = FakePlayer()
        audio = CoordinatorAudio(player)
        report = ObstacleReport("ok", (risk("LEFT", 1, 1.2), risk("RIGHT", 2, .9)), None)
        self.assertEqual(audio.process(report, 0).zones, ("RIGHT",))
        self.assertEqual(audio.announced["LEFT"].level, 0)
        self.assertIsNone(audio.process(report, .1))
        self.assertEqual(audio.process(report, 1).zones, ("LEFT",))
        self.assertIsNone(audio.process(report, 2))

    def test_same_severity_nearest_first_and_center_breaks_tie(self):
        player = FakePlayer()
        audio = CoordinatorAudio(player)
        report = ObstacleReport("ok", (risk("LEFT", 1, 1.4), risk("RIGHT", 1, 1.2),
                                         risk("CENTER", 1, 1.2)), None)
        self.assertEqual(audio.process(report, 0).zones, ("CENTER", "RIGHT", "LEFT"))
        self.assertIsNone(audio.process(report, 5))

    def test_failed_submit_does_not_mark_other_directions_announced(self):
        player = FakePlayer()
        player.accept = False
        audio = CoordinatorAudio(player)
        report = ObstacleReport("ok", (risk("LEFT", 2, .9),), None)
        self.assertIsNone(audio.process(report, 0))
        player.accept = True
        self.assertEqual(audio.process(report, .1).zones, ("LEFT",))

    def test_close_drains_accepted_cue_and_rejects_later_submissions(self):
        with patch("winsound.PlaySound") as play:
            player = BeepPlayer(swap_channels=True)
            self.assertTrue(player.submit(SoundEvent("near", "test", ("LEFT",))))
            player.close()
            self.assertTrue(player.wait_idle(.1))
            play.assert_called_once()
            pcm = decode(play.call_args.args[0])
            self.assertFalse(np.any(pcm[:, 0]))
            self.assertFalse(player.submit(SoundEvent("test", "closed")))

    def test_cli_test_waits_without_opening_camera(self):
        with patch("thirdeyes.app.configure_logging"), patch("thirdeyes.app.KinectCapture") as camera, \
                patch("winsound.PlaySound") as play:
            self.assertEqual(main(["--test-sound", "--swap-audio-channels"]), 0)
            play.assert_called_once()
            camera.assert_not_called()


if __name__ == "__main__":
    unittest.main()
