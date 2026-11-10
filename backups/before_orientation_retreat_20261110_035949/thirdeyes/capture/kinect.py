"""Kinect v1 / model 1517, native Kinect for Windows SDK 1.8.

ctypes declarations follow NuiApi.h, NuiImageCamera.h, NuiSensor.h.
Uses the flat API: GetNextFrame takes POINTER(POINTER(ImageFrame)),
unlike the INuiSensor method. No PyKinect / Python 2 dependency.
"""
import ctypes as ct
import os
from pathlib import Path
import time

import numpy as np

from thirdeyes.contracts import FrameBundle

HRESULT = ct.c_int32
DWORD = ct.c_uint32
HANDLE = ct.c_void_p
WIDTH, HEIGHT = 640, 480
NO_FRAME = 0x83010001


class KinectError(RuntimeError):
    pass


class ViewArea(ct.Structure):
    _fields_ = [("zoom", ct.c_int32), ("x", ct.c_int32), ("y", ct.c_int32)]


class ImageFrame(ct.Structure):
    _fields_ = [
        ("timestamp", ct.c_int64), ("number", DWORD),
        ("image_type", ct.c_int32), ("resolution", ct.c_int32),
        ("texture", ct.c_void_p), ("flags", DWORD), ("view", ViewArea),
    ]


class LockedRect(ct.Structure):
    _fields_ = [("pitch", ct.c_int32), ("size", ct.c_int32), ("bits", ct.c_void_p)]


def check(hr: int, operation: str) -> None:
    if hr & 0x80000000:
        raise KinectError(f"{operation} failed (HRESULT 0x{hr & 0xFFFFFFFF:08X}). "
                          "Kiem tra nguon Kinect, USB, driver SDK 1.8 va dong ung dung dang dung Kinect.")


def load_runtime():
    if os.name != "nt":
        raise KinectError("Kinect SDK 1.8 can Windows. Dung --demo de thu giao dien.")
    # Load only the installed system runtime, not a DLL in the working directory.
    dll_path = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32/Kinect10.dll"
    try:
        dll = ct.WinDLL(str(dll_path))
    except OSError as exc:
        raise KinectError("Khong nap duoc Kinect10.dll. Can Kinect for Windows SDK/Runtime 1.8.") from exc
    signatures = {
        "NuiGetSensorCount": ([ct.POINTER(ct.c_int32)], HRESULT),
        "NuiInitialize": ([DWORD], HRESULT),
        "NuiShutdown": ([], None),
        "NuiImageStreamOpen": ([ct.c_int32, ct.c_int32, DWORD, DWORD, HANDLE, ct.POINTER(HANDLE)], HRESULT),
        "NuiImageStreamGetNextFrame": ([HANDLE, DWORD, ct.POINTER(ct.POINTER(ImageFrame))], HRESULT),
        "NuiImageStreamReleaseFrame": ([HANDLE, ct.POINTER(ImageFrame)], HRESULT),
    }
    for name, (arguments, result) in signatures.items():
        func = getattr(dll, name)
        func.argtypes, func.restype = arguments, result
    return dll


def sensor_count(dll) -> int:
    count = ct.c_int32()
    check(dll.NuiGetSensorCount(ct.byref(count)), "NuiGetSensorCount")
    return count.value


def texture_method(texture, slot, *argtypes):
    table = ct.cast(texture, ct.POINTER(ct.POINTER(ct.c_void_p))).contents
    return ct.WINFUNCTYPE(HRESULT, ct.c_void_p, *argtypes)(table[slot])


def copy_pixels(rect: LockedRect, channels: int) -> np.ndarray:
    """Copy pitched native memory BEFORE unlocking/releasing the SDK frame."""
    row_bytes = WIDTH * channels
    required = (HEIGHT - 1) * rect.pitch + row_bytes
    if not rect.bits or rect.pitch < row_bytes or rect.size < required:
        raise KinectError("Kinect tra ve bo dem anh khong hop le.")
    raw = ct.string_at(rect.bits, required)
    rows = np.ndarray((HEIGHT, row_bytes), dtype=np.uint8, buffer=raw,
                      strides=(rect.pitch, 1)).copy()
    if channels == 4:
        # Kinect RGB32 is stored B,G,R,X; the public contract is RGB.
        return rows.reshape(HEIGHT, WIDTH, 4)[:, :, [2, 1, 0]].copy()
    # SDK 1.x legacy texture packs depth in the upper 13 bits, even in
    # DEPTH-only mode. Lower 3 bits are the player index (zero here).
    return (rows.view(np.dtype("<u2")).reshape(HEIGHT, WIDTH) >> 3).copy()


class KinectCapture:
    def __init__(self):
        self.dll = None
        self.initialized = False
        self.color_stream = HANDLE()
        self.depth_stream = HANDLE()
        self.latest = FrameBundle()

    def open(self):
        self.dll = load_runtime()
        if sensor_count(self.dll) == 0:
            raise KinectError("Khong tim thay Kinect. Cam nguon va USB cua model 1517, sau do chay lai.")
        try:
            check(self.dll.NuiInitialize(0x02 | 0x20), "NuiInitialize")
            self.initialized = True
            # Color and depth: 640x480, buffer 2, polling without events.
            for image_type, stream in ((1, self.color_stream), (4, self.depth_stream)):
                check(self.dll.NuiImageStreamOpen(image_type, 2, 0x00010000, 2, None,
                                                 ct.byref(stream)), "NuiImageStreamOpen")
        except Exception:
            self.close()
            raise

    def _read_stream(self, stream, channels):
        frame = ct.POINTER(ImageFrame)()
        hr = self.dll.NuiImageStreamGetNextFrame(stream, 0, ct.byref(frame))
        if hr == 1 or (hr & 0xFFFFFFFF) == NO_FRAME:
            return None
        check(hr, "NuiImageStreamGetNextFrame")
        if not frame:
            raise KinectError("SDK tra ve frame rong.")
        try:
            texture = frame.contents.texture
            if not texture:
                raise KinectError("SDK tra ve texture rong.")
            rect = LockedRect()
            lock = texture_method(texture, 5, DWORD, ct.POINTER(LockedRect), ct.c_void_p, DWORD)
            unlock = texture_method(texture, 7, DWORD)
            check(lock(texture, 0, ct.byref(rect), None, 0), "LockRect")
            try:
                pixels = copy_pixels(rect, channels)
                timestamp = frame.contents.timestamp
            finally:
                check(unlock(texture, 0), "UnlockRect")
            return pixels, timestamp
        finally:
            check(self.dll.NuiImageStreamReleaseFrame(stream, frame), "NuiImageStreamReleaseFrame")

    def read(self) -> FrameBundle:
        for stream, channels, image_name, ts_name, received_name in (
            (self.color_stream, 4, "rgb", "color_timestamp_ms", "color_received_at"),
            (self.depth_stream, 2, "depth_mm", "depth_timestamp_ms", "depth_received_at"),
        ):
            result = self._read_stream(stream, channels)
            if result is not None:
                pixels, timestamp = result
                setattr(self.latest, image_name, pixels)
                setattr(self.latest, ts_name, timestamp)
                setattr(self.latest, received_name, time.monotonic())
        return self.latest

    def close(self):
        if self.initialized:
            self.dll.NuiShutdown()
            self.initialized = False
