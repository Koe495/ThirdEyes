from types import SimpleNamespace
import unittest
from unittest.mock import patch
import numpy as np
from thirdeyes.control_panel import stream_status, zone_status
from thirdeyes.ui_theme import WARNING, DANGER, result_snapshot
from thirdeyes.app import main


class DashboardTests(unittest.TestCase):
    def test_stale_and_demo_frames_are_never_labelled_live(self):
        self.assertEqual(stream_status(None, 10)[1], WARNING)
        self.assertEqual(stream_status(1, 10)[1], DANGER)
        self.assertEqual(stream_status(9, 10, True)[0], 'MÔ PHỎNG')

    def test_unknown_distance_is_not_displayed_as_clear(self):
        zone = SimpleNamespace(known=False, distance_m=None, level=0, suppress_audio=False)
        self.assertEqual(zone_status(zone), ('Chưa đo được', '—', WARNING))

    def test_snapshot_annotations_do_not_change_capture_input(self):
        rgb = np.zeros((100, 100, 3), np.uint8)
        result = {'regions': [{'box': [[10,10], [80,10], [80,80], [10,80]], 'accepted': True}]}
        annotated = result_snapshot(rgb, result)
        self.assertGreater(annotated.sum(), 0)
        self.assertEqual(rgb.sum(), 0)

    def test_default_app_routes_results_to_dashboard_without_opencv_windows(self):
        with patch('thirdeyes.app.configure_logging'), patch('thirdeyes.app.ControlPanel') as panel, \
             patch('thirdeyes.app.BeepPlayer'), patch('thirdeyes.app.VoiceCommands') as voice, \
             patch('thirdeyes.app.ObjectFinder') as finder, patch('thirdeyes.app.TextReader') as reader, \
             patch('thirdeyes.app.time.sleep'), patch('thirdeyes.app.cv2.namedWindow') as window, \
             patch('thirdeyes.app.cv2.imshow') as image:
            found = {'status': 'not_found', 'speak': 'Chưa thấy chai nước.', 'target_label': 'Chai nước'}
            finder.return_value.poll.side_effect = [found, None]
            reader.return_value.poll.return_value = None
            finder.return_value.busy = reader.return_value.busy = False
            voice.return_value.poll.return_value = None
            voice.return_value.state = 'idle'
            voice.return_value.listening = False
            panel.return_value.poll.return_value = None
            self.assertEqual(main(['--demo', '--max-frames', '2', '--mute', '--no-speech']), 0)
            panel.return_value.show_result.assert_called_once_with(found, finder.return_value.snapshot_rgb)
            self.assertEqual(panel.return_value.present.call_count, 2)
            window.assert_not_called()
            image.assert_not_called()
            panel.return_value.close.assert_called_once()
