import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from thirdeyes.app import main
from thirdeyes.capture.kinect import KinectError
from thirdeyes.contracts import FrameBundle


class AppTests(unittest.TestCase):
    def test_camera_failure_closes_resources_and_requests_fault_sound(self):
        with patch("thirdeyes.app.configure_logging"), patch("thirdeyes.app.KinectCapture") as camera, \
                patch("thirdeyes.app.BeepPlayer") as player, patch("thirdeyes.app.time.sleep"):
            camera.return_value.open.side_effect = KinectError("disconnected")
            with self.assertLogs(level="ERROR"):
                self.assertEqual(main(["--headless"]), 1)
            camera.return_value.close.assert_called_once()
            player.return_value.close.assert_called_once()
            self.assertEqual(player.return_value.submit.call_args.args[0].kind, "depth_unavailable")

    def test_missing_config_returns_error_without_camera_open(self):
        with tempfile.TemporaryDirectory() as folder, patch("thirdeyes.app.configure_logging"), \
                patch("thirdeyes.app.KinectCapture") as camera, self.assertLogs(level="ERROR"):
            result = main(["--config", str(Path(folder) / "absent.json"), "--headless"])
            self.assertEqual(result, 1)
            camera.assert_not_called()

    def test_real_camera_smoke_requires_both_streams(self):
        with patch("thirdeyes.app.configure_logging"), patch("thirdeyes.app.KinectCapture") as camera, \
                patch("thirdeyes.app.BeepPlayer"), self.assertLogs(level="ERROR"):
            camera.return_value.read.return_value = FrameBundle()
            self.assertEqual(main(["--headless", "--max-frames", "1", "--mute"]), 1)
            camera.return_value.close.assert_called_once()
