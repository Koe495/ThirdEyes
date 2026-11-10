"""Snapshot object search using a separate inference process."""
from pathlib import Path
import logging
import math
from thirdeyes.ocr import TextReader

# Shared by the control panel and CLI; values must match model.names.
TARGETS = {
    'Chai nước': 'bottle',
    'Điện thoại': 'cell phone',
    'Ghế': 'chair',
    'Cốc': 'cup',
    'Sách': 'book',
    'Laptop': 'laptop',
    'Chuột máy tính': 'mouse',
    'Bàn phím': 'keyboard',
    'Điều khiển': 'remote',
    'Ba lô': 'backpack',
    'Túi xách': 'handbag',
    'Kéo': 'scissors',
    'Ly rượu có chân': 'wine glass',
    'Bát / tô': 'bowl',
    'Thìa / muỗng': 'spoon',
    'Nĩa': 'fork',
    'Dao': 'knife',
    'Tivi': 'tv',
    'Đồng hồ': 'clock',
    'Vali': 'suitcase',
    'Ô / dù': 'umbrella',
    'Ghế sofa': 'couch',
    'Ghế băng': 'bench',
    'Bàn ăn': 'dining table',
    'Giường': 'bed',
    'Chậu cây': 'potted plant',
    'Bình hoa': 'vase',
    'Tủ lạnh': 'refrigerator',
    'Lò vi sóng': 'microwave',
    'Bàn chải đánh răng': 'toothbrush',
    'Bút': 'pen',
}

def describe_found(result):
    if result['status'] != 'ok':
        return result.get('speak', 'Chưa có kết quả tìm vật.')
    directions = {'LEFT': 'bên trái', 'CENTER': 'phía trước', 'RIGHT': 'bên phải'}
    sentences = ['Trong ảnh vừa chụp:']
    for region in result.get('regions', []):
        if 'clock_hour' in region:
            hour = region['clock_hour']
            direction = 'chính giữa khung nhìn' if hour is None else f'hướng {hour} giờ'
        else:
            direction = directions.get(region.get('direction'), 'hướng chưa xác định')
        message = f"Tìm thấy {result['target_label'].lower()} ở {direction}"
        depth = region.get('depth', {})
        distance = depth.get('distance_m')
        if depth.get('status') == 'ok' and isinstance(distance, (int, float)) and math.isfinite(distance) and .8 <= distance <= 4:
            meters = f'{distance:.1f}'.rstrip('0').rstrip('.')
            message += f', khoảng cách ước tính {meters} mét'
        else:
            reasons = {'unpaired': 'ảnh màu và depth chưa đồng bộ',
                       'mapping_error': 'lỗi ánh xạ depth',
                       'unavailable': 'chưa có dữ liệu đo depth',
                       'insufficient_depth': 'thiếu dữ liệu depth trên vật',
                       'mixed_depth': 'depth trên vật chưa ổn định'}
            message += ', chưa đo được khoảng cách'
            reason = reasons.get(depth.get('status'))
            if reason:
                message += f' do {reason}'
        sentences.append(message + '.')
    if result.get('truncated'):
        sentences.append('Còn các vật cùng loại khác trong ảnh.')
    return ' '.join(sentences)

class ObjectFinder(TextReader):
    def annotate_regions(self, mapper, pair, regions, cancelled):
        mapper.annotate_objects(pair, regions, cancelled)

    def __init__(self, root=None, model=None):
        root = Path(root) if root else Path(__file__).resolve().parent.parent
        super().__init__(root=root, python_path=root / '.object-venv/Scripts/python.exe',
                         models=Path(model).resolve() if model else root / 'models/objects/yolo11s.pt')
        self.worker_script = 'object_worker.py'
        self.worker_config = root / 'config/objects.json'
        self.log_name = 'object_worker.log'
        self.message = 'F: tìm vật đã chọn'

    def find(self, frames, target='Chai nước', now=None, pair=None, mapper=None):
        if target not in TARGETS or self.busy:
            return False
        self.request_payload = {'target': TARGETS[target], 'target_label': target}
        accepted = self.request(frames, now, pair=pair, mapper=mapper)
        if accepted:
            self.message = f'Đang tìm {target.lower()} trong ảnh chụp'
        return accepted

    def poll(self):
        result = super().poll()
        if result is not None:
            for region in result.get('regions', []):
                status = result.get('rgbd_status', 'unpaired')
                region.setdefault('depth', {'status': status if status in {'unpaired', 'mapping_error'} else 'unavailable',
                                            'distance_m': None, 'samples': 0})
                logging.info('FIND measurement hour=%s status=%s distance_m=%s samples=%s rgbd=%s skew_ms=%s',
                             region.get('clock_hour'), region['depth'].get('status'), region['depth'].get('distance_m'),
                             region['depth'].get('samples'), status, result.get('rgbd_skew_ms'))
            result['speak'] = describe_found(result)
            result['text'] = result['speak']
            self.message = result['speak']
            self.last_text = result['speak']
        return result
