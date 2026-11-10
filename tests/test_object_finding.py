import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'ocr_runtime'))
from object_worker import detect
from thirdeyes.object_finding import describe_found, ObjectFinder
from thirdeyes.contracts import FrameBundle

CFG = {'confidence': .45, 'iou': .45, 'image_size': 640, 'max_results': 3}

def model(rows):
    m = Mock()
    m.names = {39: 'bottle', 56: 'chair', 67: 'cell phone'}
    prediction = Mock()
    prediction.boxes.data.cpu.return_value.tolist.return_value = rows
    m.predict.return_value = [prediction]
    return m

class ObjectTests(unittest.TestCase):
    def test_pen_is_unsupported_not_not_found(self):
        m = model([])
        self.assertEqual(detect(m, np.zeros((100, 300, 3)), 'pen', 'Bút', CFG)['status'], 'unsupported')
        m.predict.assert_not_called()

    def test_target_filter_and_directions(self):
        m = model([[0,0,50,80,.9,39],[120,0,170,80,.8,39],[250,0,299,80,.7,39]])
        result = detect(m, np.zeros((100,300,3)), 'bottle', 'Chai nước', CFG)
        self.assertEqual([r['direction'] for r in result['regions']], ['LEFT','CENTER','RIGHT'])
        self.assertEqual(m.predict.call_args.kwargs['classes'], [39])

    def test_not_found_does_not_claim_absence(self):
        result = detect(model([]), np.zeros((100,300,3)), 'chair', 'Ghế', CFG)
        self.assertEqual(result['status'], 'not_found')
        self.assertIn('Chưa thấy', result['speak'])

    def test_limit_results_and_clip_boxes(self):
        result = detect(model([[-10,-10,400,200,.8,39]] * 4), np.zeros((100,300,3)), 'bottle', 'Chai nước', CFG)
        self.assertTrue(result['truncated'])
        # Keep every candidate for depth ranking; cap only in the parent.
        self.assertEqual(len(result['regions']), 4)
        self.assertEqual(result['regions'][0]['box'][2], [299,99])

    def test_speech_only_uses_valid_depth(self):
        result = {'status':'ok','target_label':'Ghế','regions':[{'direction':'LEFT','depth':{'status':'mixed_depth','distance_m':1.}}]}
        self.assertIn('chưa đo được', describe_found(result))
        result['regions'][0]['depth'] = {'status':'ok','distance_m':1.2}
        self.assertIn('1.2 mét', describe_found(result))
        self.assertIn('ảnh vừa chụp', describe_found(result))

    def test_missing_frame_and_unknown_target_do_not_start_worker(self):
        finder = ObjectFinder()
        try:
            self.assertFalse(finder.find(FrameBundle(), 'Ghế'))
            self.assertFalse(finder.find(FrameBundle(), 'unknown'))
            self.assertIsNone(finder._process)
        finally:
            finder.close()

if __name__ == '__main__':
    unittest.main()
