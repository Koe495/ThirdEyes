"""Snapshot object search using a separate inference process."""
from pathlib import Path
import logging
import math
from thirdeyes.ocr import TextReader

from thirdeyes.object_catalog import TARGETS


def valid_distance(region):
    depth = region.get('depth', {})
    distance = depth.get('distance_m')
    if (depth.get('status') == 'ok' and not isinstance(distance, bool)
            and isinstance(distance, (int, float)) and math.isfinite(distance) and .8 <= distance <= 4):
        return distance
    return None


def prioritize_regions(result):
    """Sort all measured candidates before imposing the display limit."""
    regions = result.get('regions', [])
    if result.get('status') != 'ok' or not regions:
        return
    def key(region):
        distance = valid_distance(region)
        return (distance is None, distance if distance is not None else float('inf'),
                -region.get('confidence', 0))
    regions = sorted(regions, key=key)
    unknown = sum(valid_distance(r) is None for r in regions)
    result['detected_count'] = len(regions)
    result['unmeasured_count'] = unknown
    result['selection'] = 'nearest_measured' if unknown < len(regions) else 'confidence_only'
    for i, region in enumerate(regions):
        region['preferred'] = i == 0
    limit = max(1, min(30, int(result.get('max_results', 3))))
    result['regions'] = regions[:limit]
    result['truncated'] = bool(result.get('truncated')) or len(regions) > limit


def describe_found(result):
    if result['status'] != 'ok':
        return result.get('speak', 'Chưa có kết quả tìm vật.')
    directions = {'LEFT': 'bên trái', 'CENTER': 'phía trước', 'RIGHT': 'bên phải'}
    sentences = ['Trong ảnh vừa chụp:']
    selected = result.get('selection')
    if selected == 'nearest_measured' and result.get('detected_count', 0) > 1:
        sentences.append('Ưu tiên vật gần nhất trong các vật đo được khoảng cách.')
    elif selected == 'confidence_only':
        sentences.append('Chưa xác định được vật gần nhất. Báo vật nhận diện rõ nhất.')
    # Speak one preferred result; retain other candidates for the result window.
    regions = result.get('regions', [])[:1] if selected else result.get('regions', [])
    for region in regions:
        if 'clock_hour' in region:
            hour = region['clock_hour']
            direction = 'chính giữa khung nhìn' if hour is None else f'hướng {hour} giờ'
        else:
            direction = directions.get(region.get('direction'), 'hướng chưa xác định')
        message = f"Tìm thấy {result['target_label'].lower()} ở {direction}"
        depth = region.get('depth', {})
        distance = valid_distance(region)
        if distance is not None:
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
    if selected == 'nearest_measured' and result.get('unmeasured_count'):
        sentences.append('Có vật khác chưa đo được khoảng cách nên chưa thể so sánh đầy đủ.')
    if result.get('candidate_limit_reached'):
        sentences.append('Ảnh có nhiều vật; kết quả chỉ xét các ứng viên đã nhận diện.')
    elif result.get('truncated') and not selected:
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
        self.tracking_active = False
        self.frame_received_at = None

    def find(self, frames, target='Chai nước', now=None, pair=None, mapper=None):
        if target not in TARGETS or self.busy:
            return False
        self.request_payload = {'target': TARGETS[target], 'target_label': target}
        accepted = self.request(frames, now, pair=pair, mapper=mapper)
        if accepted:
            self.frame_received_at = frames.color_received_at
            self.message = f'Đang tìm {target.lower()} trong ảnh chụp'
        return accepted

    def poll(self):
        result = super().poll()
        if result is not None:
            result.setdefault('target_label', self.request_payload.get('target_label'))
            result['frame_received_at'] = self.frame_received_at
            if self.snapshot_rgb is not None:
                result['frame_size'] = [self.snapshot_rgb.shape[1], self.snapshot_rgb.shape[0]]
            for region in result.get('regions', []):
                status = result.get('rgbd_status', 'unpaired')
                region.setdefault('depth', {'status': status if status in {'unpaired', 'mapping_error'} else 'unavailable',
                                            'distance_m': None, 'samples': 0})
                logging.info('FIND measurement hour=%s status=%s distance_m=%s samples=%s rgbd=%s skew_ms=%s',
                             region.get('clock_hour'), region['depth'].get('status'), region['depth'].get('distance_m'),
                             region['depth'].get('samples'), status, result.get('rgbd_skew_ms'))
            if self.tracking_active:
                result['max_results'] = 30  # association must see every retained candidate
            prioritize_regions(result)
            result['speak'] = describe_found(result)
            result['text'] = result['speak']
            self.message = result['speak']
            self.last_text = result['speak']
        return result
