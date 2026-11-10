"""Native boundary checks without a physical Kinect."""
import ctypes as ct
import unittest
from unittest.mock import patch

import numpy as np

from thirdeyes.capture.kinect import (
    HEIGHT, WIDTH, ImageFrame, KinectCapture, KinectError, LockedRect, check, copy_pixels,
)
from thirdeyes.ui_logging import colorize_depth


class BufferTests(unittest.TestCase):
    def test_sdk_struct_layout(self):
        if ct.sizeof(ct.c_void_p) == 8:
            self.assertEqual(ct.sizeof(ImageFrame), 48)
            self.assertEqual(ImageFrame.texture.offset, 24)
            self.assertEqual(ct.sizeof(LockedRect), 16)

    def test_rgb_order_padding_and_detached_buffer(self):
        pitch = WIDTH * 4 + 16
        memory = (ct.c_ubyte * (pitch * HEIGHT))()
        memory[0:4] = (11, 22, 33, 0)
        memory[pitch:pitch + 4] = (44, 55, 66, 0)
        rect = LockedRect(pitch, len(memory), ct.addressof(memory))
        image = copy_pixels(rect, 4)
        self.assertEqual(image[0, 0].tolist(), [33, 22, 11])
        self.assertEqual(image[1, 0].tolist(), [66, 55, 44])
        memory[0] = 99
        self.assertEqual(int(image[0, 0, 2]), 11)

    def test_depth_unpack_and_invalid_display(self):
        packed = np.zeros((HEIGHT, WIDTH), dtype=np.uint16)
        packed[0, :5] = [1200 << 3, 4000 << 3, 0, 4095 << 3, 8191 << 3]
        rect = LockedRect(WIDTH * 2, packed.nbytes, packed.ctypes.data)
        depth = copy_pixels(rect, 2)
        self.assertEqual(depth[0, :5].tolist(), [1200, 4000, 0, 4095, 8191])
        rendered = colorize_depth(depth)
        self.assertTrue(np.all(rendered[0, 2:5] == 0))
        self.assertTrue(np.any(rendered[0, 0] != 0))
        self.assertEqual(int(depth[0, 4]), 8191)

    def test_reject_short_buffer(self):
        with self.assertRaises(KinectError):
            copy_pixels(LockedRect(WIDTH * 4, 5, 1), 4)

    def test_hresult_signed_and_unsigned(self):
        check(0, "OK")
        for value in (0x83010014, ct.c_int32(0x83010014).value):
            with self.assertRaises(KinectError):
                check(value, "disconnected")

    def test_release_and_unlock_after_copy_failure(self):
        frame = ImageFrame()
        frame.texture = 123
        calls = []

        class FakeSDK:
            def NuiImageStreamGetNextFrame(self, stream, timeout, output):
                ct.cast(output, ct.POINTER(ct.POINTER(ImageFrame)))[0] = ct.pointer(frame)
                return 0

            def NuiImageStreamReleaseFrame(self, stream, ptr):
                calls.append("release")
                return 0

        def method(texture, slot, *args):
            def callback(*args):
                calls.append("lock" if slot == 5 else "unlock")
                return 0
            return callback

        source = KinectCapture()
        source.dll = FakeSDK()
        with patch("thirdeyes.capture.kinect.texture_method", side_effect=method):
            with self.assertRaises(KinectError):
                source._read_stream(None, 4)
        self.assertEqual(calls, ["lock", "unlock", "release"])

    def test_no_frame_is_not_fatal(self):
        class FakeSDK:
            def NuiImageStreamGetNextFrame(self, *args):
                return ct.c_int32(0x83010001).value
        source = KinectCapture()
        source.dll = FakeSDK()
        self.assertIsNone(source._read_stream(None, 4))


if __name__ == "__main__":
    unittest.main()
