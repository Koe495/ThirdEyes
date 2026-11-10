import io
import unittest
import wave
from types import SimpleNamespace
from unittest.mock import Mock
import numpy as np
from thirdeyes.object_tracking import ObjectTracking
from thirdeyes.coordinator_audio import CoordinatorAudio
from thirdeyes.stereo_audio import render_cue


def region(x, distance=1.):
    return dict(box=[[x,20],[x+20,20],[x+20,60],[x,60]], confidence=.9, clock_hour=9,
                depth=dict(status='ok', distance_m=distance))


def result(t, *regions):
    return dict(target_label='Chai nước', status='ok' if regions else 'not_found',
                frame_received_at=t, frame_size=[100,100], regions=list(regions))


class TrackingTests(unittest.TestCase):
    def setUp(self):
        self.t = ObjectTracking()
        self.t.start('Chai nước', 0)
        self.audio = CoordinatorAudio(Mock(submit=Mock(return_value=True)))

    def acquire(self, x=5):
        self.assertIsNone(self.t.update(result(0,region(x)),.05))
        return self.t.update(result(.1,region(x)),.2)

    def test_initial_description_then_one_beep_each_second(self):
        r = self.acquire()
        self.assertIn('1 mét', r['speak'])
        self.t.audio_tick(self.audio, .2)  # no speech configured, release notice
        self.t.update(result(1., region(6)), 1.)
        self.t.audio_tick(self.audio, 1.19)
        self.audio.player.submit.assert_not_called()
        self.t.audio_tick(self.audio, 1.21)
        self.assertLess(self.audio.player.submit.call_args.args[0].pan, 0)
        self.t.audio_tick(self.audio, 1.8)
        self.assertEqual(self.audio.player.submit.call_count, 1)
        self.t.update(result(2., region(7)), 2.)
        self.t.audio_tick(self.audio, 2.22)
        self.assertEqual(self.audio.player.submit.call_count, 2)

    def test_lock_does_not_jump_to_other_nearer_instance(self):
        self.acquire()
        found = self.t.update(result(.3, region(70,.8), region(7,2.)), .4)
        self.assertEqual(found['regions'][0]['box'][0][0], 7)

    def test_ambiguity_and_loss_stop_direction(self):
        self.acquire(20)
        self.assertIsNone(self.t.update(result(.4, region(19), region(21)), .5))
        self.t.audio_tick(self.audio, 1.3)
        self.audio.player.submit.assert_not_called()
        self.assertFalse(self.t.fresh(1.3))

    def test_stale_and_other_target_are_not_used(self):
        self.assertIsNone(self.t.update(result(0, region(5)), 3))
        wrong = dict(result(3,region(5)), target_label='Ghế')
        self.assertIsNone(self.t.update(wrong, 3))
        self.assertIsNone(self.t.region)

    def test_reacquisition_is_silent_after_initial_description(self):
        self.acquire()
        self.t.audio_tick(self.audio,.2)
        self.assertIsNone(self.t.update(result(6,region(70)),6.1))
        self.assertIsNotNone(self.t.update(result(6.2,region(70)),6.3))
        self.assertIsNone(self.t.notice)
        self.t.stop()
        self.t.audio_tick(self.audio, 5.2)
        self.audio.player.submit.assert_not_called()

    def test_speech_mic_and_obstacle_have_priority(self):
        self.acquire()
        self.t.notice=None
        self.t.update(result(1,region(5)),1)
        self.t.audio_tick(self.audio,1.21,listening=True)
        self.audio.tracking_blocked=True
        self.t.audio_tick(self.audio,1.21)
        self.audio.tracking_blocked=False
        self.audio.speech=SimpleNamespace(state='speaking')
        self.t.audio_tick(self.audio,1.21)
        self.audio.player.submit.assert_not_called()

    def test_new_frames_only_no_backlog(self):
        frame=SimpleNamespace(rgb=np.zeros((2,2,3)),color_timestamp_ms=1,color_received_at=.1)
        self.assertTrue(self.t.should_request(frame,.2))
        self.t.submitted(frame,.2)
        self.assertFalse(self.t.should_request(frame,1.))
        frame.color_timestamp_ms=2; frame.color_received_at=1
        self.assertTrue(self.t.should_request(frame,1.1))

    def test_backend_failure_stops_even_without_frame_time(self):
        self.t.update(dict(target_label='Chai nước',status='error'),2.)
        self.assertFalse(self.t.active)
        self.assertIn('Đã dừng',self.t.notice)

    def test_first_description_retried_after_brief_miss(self):
        self.acquire()
        self.t.update(result(.3),.4)
        self.assertIsNone(self.t.update(result(.5,region(6)),.6))
        self.t.update(result(.6,region(6)),.65)
        self.assertIn('Tìm thấy',self.t.notice)
        self.audio.speech=Mock(state='ready',speak=Mock(return_value=True))
        self.t.audio_tick(self.audio,.66)
        self.assertFalse(self.t.description_pending)
        self.t.update(result(.7,region(7)),.8)
        self.assertIsNone(self.t.notice)

    def test_flicker_never_repeats_speech_and_loss_notice_once(self):
        self.audio.speech=Mock(state='ready',speak=Mock(return_value=True))
        self.acquire()
        self.t.audio_tick(self.audio,.2)
        for t in (1.,2.,3.,4.):
            self.t.update(result(t),t)
            self.t.audio_tick(self.audio,t)
        self.assertEqual(self.audio.speech.speak.call_count,1)
        self.t.audio_tick(self.audio,5.2)
        self.assertEqual(self.audio.speech.speak.call_count,2)
        for t in (6.,6.2,6.4):
            self.t.update(result(t,region(70)),t+.05)
            self.t.audio_tick(self.audio,t+.05)
        self.t.update(result(7),7)
        for t in (12.,20.,30.):
            self.t.audio_tick(self.audio,t)
        self.assertEqual(self.audio.speech.speak.call_count,2)

    def test_isolated_detections_do_not_start_audio(self):
        for t in (0.,1.,2.,3.):
            self.assertIsNone(self.t.update(result(t,region(5)),t+.1))
            self.t.audio_tick(self.audio,t+.1)
            self.t.update(result(t+.2),t+.3)
        self.audio.player.submit.assert_not_called()
        self.assertFalse(self.t.ever_seen)

    def test_stereo_volume_and_swap(self):
        def energy(pan, swap=False):
            with wave.open(io.BytesIO(render_cue('track', pan=pan, swap_channels=swap)), 'rb') as wav:
                self.assertEqual(wav.getnframes(), 3528)
                samples=np.frombuffer(wav.readframes(wav.getnframes()),'<i2').reshape(-1,2).astype(float)
                return (samples**2).sum(axis=0)
        self.assertGreater(energy(-.5)[0],energy(-.5)[1])
        self.assertGreater(energy(.5)[1],energy(.5)[0])
        np.testing.assert_allclose(energy(0)[0],energy(0)[1])
        np.testing.assert_allclose(energy(.5,True),energy(.5)[::-1])


if __name__=='__main__':
    unittest.main()
