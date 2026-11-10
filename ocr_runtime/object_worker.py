"""Persistent YOLO inference with explicitly local weights."""
import argparse
import json
import math
import os
from pathlib import Path
import sys
os.environ.update(YOLO_OFFLINE='true', YOLO_VERBOSE='false', OMP_NUM_THREADS='2', MKL_NUM_THREADS='2')
os.environ['YOLO_CONFIG_DIR'] = str(Path(__file__).resolve().parent.parent / 'runtime/yolo')

def clock_direction(box, width, height):
    """Clock on the normalized image plane: up=12, right=3, down=6.

    This is not a world azimuth. A central dead zone avoids unstable hours
    for objects near the camera's viewing axis.
    """
    x0, y0, x1, y1 = box
    dx = (x0 + x1) / width - 1
    dy = (y0 + y1) / height - 1
    if math.hypot(dx, dy) <= .20:
        return None
    angle = math.degrees(math.atan2(dx, -dy)) % 360
    hour = int(math.floor((angle + 15) / 30)) % 12
    return hour or 12


def detect(model, image, target, label, settings):
    classes = [int(k) for k, v in model.names.items() if v == target]
    base = {'target_label': label, 'regions': [], 'text': '', 'truncated': False}
    if not classes:
        return {**base, 'status': 'unsupported', 'speak': f'Model hiện tại chưa hỗ trợ {label.lower()}. Cần model huấn luyện bổ sung.'}
    prediction = model.predict(image, classes=classes, conf=settings['confidence'], iou=settings['iou'],
                               imgsz=settings['image_size'], device='cpu', verbose=False, max_det=30)[0]
    rows = sorted(prediction.boxes.data.cpu().tolist(), key=lambda row: -row[4])
    h, w = image.shape[:2]
    for x0, y0, x1, y1, confidence, category in rows[:settings['max_results']]:
        x0, x1 = max(0., min(w - 1., x0)), max(0., min(w - 1., x1))
        y0, y1 = max(0., min(h - 1., y0)), max(0., min(h - 1., y1))
        if x1 <= x0 or y1 <= y0:
            continue
        center = (x0 + x1) / (2 * w)
        direction = 'LEFT' if center < 1/3 else 'RIGHT' if center > 2/3 else 'CENTER'
        base['regions'].append({'text': label, 'accepted': True, 'confidence': confidence,
            'clock_hour': clock_direction((x0, y0, x1, y1), w, h),
            'direction': direction, 'box': [[x0,y0],[x1,y0],[x1,y1],[x0,y1]]})
    return {**base, 'status': 'ok' if base['regions'] else 'not_found',
            'truncated': len(rows) > settings['max_results'],
            'speak': f'Chưa thấy {label.lower()} trong ảnh. Hãy đổi góc camera và thử lại.'}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--models', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    args = parser.parse_args()
    settings = json.loads(args.config.read_text(encoding='utf-8-sig'))
    model = None
    for line in sys.stdin:
        request = json.loads(line)
        try:
            if not args.models.is_file():
                raise FileNotFoundError('Missing local weights. Run setup_objects.bat')
            if model is None:
                import torch
                torch.set_num_threads(settings['cpu_threads'])
                from ultralytics import YOLO, settings as yolo_settings
                yolo_settings.update({'sync': False})
                model = YOLO(str(args.models), task='detect')
            import cv2
            import numpy as np
            image = cv2.imdecode(np.fromfile(request['image'], np.uint8), cv2.IMREAD_COLOR)
            if image is None:
                raise ValueError('Invalid image')
            result = detect(model, image, request['target'], request['target_label'], settings)
        except Exception as exc:
            result = {'status': 'error', 'regions': [], 'text': '', 'speak': 'Không chạy được bộ tìm vật. Hãy kiểm tra cài đặt.', 'error': str(exc)}
        result['request_id'] = request['id']
        output = Path(request['output'])
        temporary = output.with_suffix('.pending')
        temporary.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding='utf-8')
        temporary.replace(output)

if __name__ == '__main__':
    main()
