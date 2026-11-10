import math
import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ocr_runtime'))
from object_worker import clock_direction
from thirdeyes.rgbd import measure_object, measure_polygon, KinectRegionMapper
from thirdeyes.object_finding import ObjectFinder, describe_found


class ObjectDepthTests(unittest.TestCase):
    box = [[0, 0], [100, 0], [100, 100], [0, 100]]

    def test_center_measures_object_without_background_at_box_edges(self):
        points = [(x, y, 1200 if 25 <= x <= 75 and 25 <= y <= 75 else 2800)
                  for x in range(0, 101, 4) for y in range(0, 101, 4)]
        self.assertEqual(measure_polygon(points, self.box)['status'], 'mixed_depth')
        measured = measure_object(points, self.box)
        self.assertEqual(measured['status'], 'ok')
        self.assertEqual(measured['distance_m'], 1.2)
        self.assertEqual(measured['method'], 'object_center')

    def test_no_center_depth_does_not_borrow_background(self):
        points = [(x, y, 2200) for x in range(20) for y in range(100)]
        self.assertEqual(measure_object(points, self.box)['status'], 'insufficient_depth')

    def test_mixed_center_still_rejected(self):
        points = [(x, 50, 1000 if x < 50 else 2500) for x in range(25, 76)]
        self.assertEqual(measure_object(points, self.box)['status'], 'mixed_depth')

    def test_invalid_out_of_range_and_sparse_samples(self):
        for distance in (0, 799, 4001):
            measured = measure_object([(x, 50, distance) for x in range(25, 76)], self.box)
            self.assertEqual(measured['status'], 'insufficient_depth')
        self.assertEqual(measure_object([(50, 50, 1200)] * 5, self.box)['status'], 'insufficient_depth')
        for box in ([[0, 0]] * 4, [[float('nan'), 0]] * 4, []):
            self.assertEqual(measure_object([], box)['status'], 'invalid_region')

    def test_object_mapping_uses_denser_grid_and_cancellation(self):
        mapper = KinectRegionMapper(Mock())
        mapper.points = Mock(return_value=[(x, 50, 1500) for x in range(30, 70)])
        region = {'box': self.box}
        event = threading.Event()
        pair = object()
        mapper.annotate_objects(pair, [region], event)
        mapper.points.assert_called_once_with(pair, event, stride=2)
        self.assertEqual(region['depth']['distance_m'], 1.5)
        event.set()
        untouched = {'box': self.box}
        mapper.annotate_objects(pair, [untouched], event)
        self.assertNotIn('depth', untouched)

    def test_finder_routes_to_object_measurement_not_ocr(self):
        mapper = Mock()
        ObjectFinder.annotate_regions(None, mapper, 'pair', ['region'], 'cancel')
        mapper.annotate_objects.assert_called_once_with('pair', ['region'], 'cancel')
        mapper.annotate.assert_not_called()


class ClockDirectionTests(unittest.TestCase):
    def test_all_hours_on_image_plane(self):
        for hour in range(1, 13):
            radians = math.radians(hour * 30)
            x, y = 320 + 200 * math.sin(radians), 240 - 150 * math.cos(radians)
            self.assertEqual(clock_direction((x-5, y-5, x+5, y+5), 640, 480), hour)

    def test_center_dead_zone_and_resolution_independence(self):
        for box in ((310, 230, 330, 250), (280, 210, 300, 230)):
            self.assertIsNone(clock_direction(box, 640, 480))
        self.assertEqual(clock_direction((550, 200, 610, 280), 640, 480), 3)
        self.assertEqual(clock_direction((1100, 400, 1220, 560), 1280, 960), 3)
        self.assertEqual(clock_direction((30, 200, 90, 280), 640, 480), 9)

    def test_spoken_clock_depth_and_missing_depth(self):
        region = {'clock_hour': 3, 'depth': {'status': 'ok', 'distance_m': 2.0}}
        result = {'status': 'ok', 'target_label': 'Chai nước', 'regions': [region]}
        speech = describe_found(result)
        self.assertIn('hướng 3 giờ', speech)
        self.assertIn('ước tính 2 mét', speech)
        self.assertIn('ảnh vừa chụp', speech)
        region['clock_hour'] = None
        self.assertIn('chính giữa', describe_found(result))
        for distance in (None, float('nan'), float('inf'), 0, .7, 4.1):
            region['depth']['distance_m'] = distance
            self.assertIn('chưa đo được', describe_found(result))
        region['depth'] = {'status': 'mixed_depth', 'distance_m': None}
        self.assertIn('chưa ổn định', describe_found(result))

    def test_missing_pair_gets_explicit_diagnostic(self):
        finder = ObjectFinder()
        try:
            finder._results.put({'status': 'ok', 'text': '', 'target_label': 'Chai nước',
                                 'rgbd_status': 'unpaired', 'regions': [{'clock_hour': 9}]})
            result = finder.poll()
            self.assertEqual(result['regions'][0]['depth']['status'], 'unpaired')
            self.assertIn('chưa đồng bộ', result['speak'])
        finally:
            finder.close()


if __name__ == '__main__':
    unittest.main()
