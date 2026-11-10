"""Timestamp pairing and calibrated sparse RGB-region depth measurements."""
from collections import deque
from dataclasses import dataclass

import cv2
import numpy as np


@dataclass(frozen=True)
class RGBDPair:
    rgb: np.ndarray
    depth_mm: np.ndarray
    color_ms: int
    depth_ms: int
    received_at: float

    @property
    def skew_ms(self):
        return abs(self.color_ms - self.depth_ms)


class FrameSynchronizer:
    """Pair nearest frames within 20 ms, preserving independent obstacle depth."""
    def __init__(self, tolerance_ms=20, max_age_s=.3):
        self.tolerance_ms, self.max_age_s = tolerance_ms, max_age_s
        self.colors, self.depths = deque(maxlen=6), deque(maxlen=6)
        self.last = [None, None]
        self.pair = None

    def update(self, frames):
        for index, (image, ts, received, buffer) in enumerate((
            (frames.rgb, frames.color_timestamp_ms, frames.color_received_at, self.colors),
            (frames.depth_mm, frames.depth_timestamp_ms, frames.depth_received_at, self.depths),
        )):
            if image is None or ts is None or received is None or ts == self.last[index]:
                continue
            if self.last[index] is not None and ts < self.last[index]:
                self.colors.clear(); self.depths.clear(); self.pair = None
                self.last = [None, None]
            self.last[index] = ts
            buffer.append((ts, received, image))
        matches = [(c, d) for c in self.colors for d in self.depths
                   if abs(c[0] - d[0]) <= self.tolerance_ms]
        if matches:
            c, d = max(matches, key=lambda pair: (min(pair[0][0], pair[1][0]), -abs(pair[0][0] - pair[1][0])))
            self.pair = RGBDPair(c[2], d[2], c[0], d[0], min(c[1], d[1]))

    def latest(self, now):
        return self.pair if self.pair and 0 <= now - self.pair.received_at <= self.max_age_s else None


def measure_polygon(points, box, min_samples=12):
    """points: calibrated color x,y,z(mm); no hole filling or RGB scaling."""
    contour = np.asarray(box, np.float32)
    if contour.shape != (4, 2) or not np.isfinite(contour).all():
        return {'status': 'invalid_region', 'distance_m': None, 'samples': 0}
    selected = [z for x, y, z in points if 800 <= z <= 4000 and
                cv2.pointPolygonTest(contour, (float(x), float(y)), False) >= 0]
    if len(selected) < min_samples:
        return {'status': 'insufficient_depth', 'distance_m': None, 'samples': len(selected)}
    values = np.asarray(selected)
    q10, q90 = np.percentile(values, [10, 90])
    if q90 - q10 > 250:
        return {'status': 'mixed_depth', 'distance_m': None, 'samples': len(selected)}
    return {'status': 'ok', 'distance_m': round(float(np.median(values)) / 1000, 3), 'samples': len(selected)}


def measure_object(points, box, min_samples=6):
    """Estimate axial depth on the central half of a detection box.

    Bounding boxes include background. Use a tighter ROI without filling holes
    or guessing from the whole box when the object's center has no good depth.
    OCR keeps its original whole-polygon measurement.
    """
    contour = np.asarray(box, np.float32)
    if contour.shape != (4, 2) or not np.isfinite(contour).all():
        return {'status': 'invalid_region', 'distance_m': None, 'samples': 0}
    if cv2.contourArea(contour) <= 0:
        return {'status': 'invalid_region', 'distance_m': None, 'samples': 0}
    center = contour.mean(axis=0)
    roi = center + (contour - center) * .5
    result = measure_polygon(points, roi, min_samples=min_samples)
    result.update(method='object_center', roi=roi.tolist())
    return result


class KinectRegionMapper:
    """Use official SDK point projection on demand in the OCR worker thread."""
    def __init__(self, capture, stride=4):
        self.capture, self.stride = capture, stride

    def points(self, pair, cancelled, stride=None):
        import ctypes as ct
        from thirdeyes.capture.kinect import check
        if pair.skew_ms > 20:
            raise ValueError('RGB-depth pair is not synchronized')
        depth = pair.depth_mm
        h, w = depth.shape
        if (h, w) != (480, 640) or pair.rgb.shape[:2] != (480, 640):
            raise ValueError('SDK mapping requires 640x480 frames')
        project = self.capture.dll.NuiImageGetColorPixelCoordinatesFromDepthPixelAtResolution
        x_out, y_out = ct.c_int32(), ct.c_int32()
        pixels = {}
        stride = self.stride if stride is None else stride
        for y in range(0, h, stride):
            if cancelled.is_set():
                return []
            for x in range(0, w, stride):
                z = int(depth[y, x])
                if not 800 <= z <= 4000:
                    continue
                native_x = w - 1 - x if self.capture.flip_horizontal else x
                check(project(2, 2, None, native_x, y, z << 3, ct.byref(x_out), ct.byref(y_out)), 'RGB-depth mapping')
                color_x = w - 1 - x_out.value if self.capture.flip_horizontal else x_out.value
                color_y = y_out.value
                if 0 <= color_x < w and 0 <= color_y < h:
                    key = (color_x, color_y)
                    pixels[key] = min(z, pixels.get(key, z))
        return [(x, y, z) for (x, y), z in pixels.items()]

    def annotate(self, pair, regions, cancelled):
        points = self.points(pair, cancelled)
        for region in regions:
            region['depth'] = measure_polygon(points, region['box'])

    def annotate_objects(self, pair, regions, cancelled):
        points = self.points(pair, cancelled, stride=2)
        for region in regions:
            if cancelled.is_set():
                return
            region['depth'] = measure_object(points, region['box'])
