"""Online tracking by repeated detection, with bounded result age and audio cadence.

Association is geometric, not identity recognition. After a long loss we explicitly
announce a new acquisition; similar objects crossing can remain ambiguous.
"""
import math
import logging
from thirdeyes.object_finding import describe_found


def bounds(region, width, height):
    points = region.get('box', [])
    if len(points) != 4 or width <= 0 or height <= 0:
        return None
    xs, ys = [p[0] / width for p in points], [p[1] / height for p in points]
    box = (min(xs), min(ys), max(xs), max(ys))
    return box if all(math.isfinite(x) for x in box) and box[2] > box[0] and box[3] > box[1] else None


def similarity(a, b):
    area_a, area_b = (a[2]-a[0])*(a[3]-a[1]), (b[2]-b[0])*(b[3]-b[1])
    if not .4 <= area_b / area_a <= 2.5:
        return None
    inter = max(0, min(a[2], b[2])-max(a[0], b[0])) * max(0, min(a[3], b[3])-max(a[1], b[1]))
    iou = inter / (area_a + area_b - inter)
    movement = math.hypot((a[0]+a[2]-b[0]-b[2])/2, (a[1]+a[3]-b[1]-b[3])/2)
    return iou + max(0, .18-movement) if iou >= .1 or movement <= .18 else None


class ObjectTracking:
    freshness_s = 1.2
    lost_s = 5.0
    interval_s = 1.0

    def __init__(self):
        self.stop()

    def stop(self):
        self.active = False
        self.target = None
        self.box = None
        self.region = None
        self.seen_at = -math.inf
        self.last_beep = -math.inf
        self.last_request = -math.inf
        self.frame_key = None
        self.notice = None
        self.lost_reported = False
        self.ever_seen = False
        self.description_pending = False
        self.first_spoken = False
        self.hits = 0
        self.last_hit = -math.inf
        self.message = 'F: bắt đầu theo dõi vật | X: dừng'

    def start(self, target, now):
        self.stop()
        self.active, self.target, self.started = True, target, now
        self.message = f'Đang tìm {target.lower()} để theo dõi'

    def should_request(self, frames, now):
        key = (frames.color_timestamp_ms, frames.color_received_at)
        if (not self.active or frames.rgb is None or frames.color_received_at is None
                or now - frames.color_received_at > self.freshness_s
                or key == self.frame_key or now - self.last_request < .1):
            return False
        return True

    def submitted(self, frames, now):
        self.frame_key = (frames.color_timestamp_ms, frames.color_received_at)
        self.last_request = now

    def fresh(self, now):
        return self.region is not None and 0 <= now - self.seen_at <= self.freshness_s

    def update(self, result, now):
        if not self.active or result.get('target_label') != self.target:
            return None
        if result.get('status') in {'error', 'timeout', 'unsupported', 'unavailable'}:
            self.active = False
            self.region = None
            self.notice = 'Đã dừng theo dõi vì không chạy được bộ tìm vật. Hãy kiểm tra model và thử lại.'
            self.message = self.notice
            return None
        stamp = result.get('frame_received_at')
        if stamp is None or not 0 <= now - stamp <= self.freshness_s:
            self.region = None
            self.hits = 0
            self.notice = None
            self.message = 'Kết quả nhận diện đã cũ; chờ khung hình mới'
            return None
        width, height = result.get('frame_size', (0, 0))
        if stamp <= self.last_hit:
            return None
        candidates = [(r, bounds(r, width, height)) for r in result.get('regions', [])]
        candidates = [(r, b) for r, b in candidates if b is not None]
        reacquire = self.box is not None and now - self.last_hit > self.lost_s
        chosen = None
        if candidates and (self.box is None or reacquire):
            chosen = candidates[0]  # Finder already sorts by valid nearest depth.
        elif candidates:
            scores = [(similarity(self.box, b), r, b) for r, b in candidates]
            scores = sorted((s for s in scores if s[0] is not None), key=lambda s: -s[0])
            # Do not guess when two candidates are similarly plausible.
            if scores and (len(scores) == 1 or scores[0][0] - scores[1][0] >= .1):
                chosen = scores[0][1:]
        if chosen is None:
            self.region = None
            self.hits = 0
            if not self.lost_reported:
                self.notice = None
            self.message = 'Chưa xác định được vật đang theo dõi; tạm dừng bíp'
            return None
        region, self.box = chosen
        self.hits = self.hits + 1 if not reacquire and stamp - self.last_hit <= self.freshness_s else 1
        self.last_hit = stamp
        if self.hits < 2:
            self.region = None
            self.notice = None
            self.message = 'Đang xác nhận vật qua hai lượt nhận diện; chưa phát bíp'
            return None
        self.region = region
        self.ever_seen, self.seen_at = True, stamp
        selected = dict(result, regions=[dict(self.region, preferred=True)], selection='tracked',
                        detected_count=1, unmeasured_count=0, truncated=False, candidate_limit_reached=False)
        text = describe_found(selected).replace('Trong ảnh vừa chụp: ', '')
        selected['speak'] = selected['text'] = text
        selected['tracking'] = True
        self.description_pending = not self.first_spoken
        if self.description_pending:
            self.notice = text
            self.last_beep = now
        else:
            self.notice = None
        self.message = f'Đang theo dõi {self.target.lower()} | X: dừng'
        return selected

    def audio_tick(self, audio, now, listening=False):
        if self.active and not self.fresh(now):
            delay = self.lost_s if self.ever_seen else 10.0
            if now - max(self.seen_at, self.started) >= delay and not self.lost_reported:
                self.notice = ('Tạm mất dấu vật.' if self.ever_seen else 'Chưa thấy vật cần tìm.') + ' Hãy giữ vật rõ trong khung hình.'
                self.lost_reported = True
            elif not self.lost_reported:
                self.notice = None
        if listening or audio.muted:
            return
        speech = audio.speech
        speaking = speech is not None and speech.state in {'starting', 'speaking'}
        if self.notice:
            if speech is None or speech.state in {'error', 'no_vi_voice'}:
                self.notice = None
                if self.fresh(now):
                    self.description_pending = False
                    self.first_spoken = True
            elif not speaking and audio.read_text(self.notice, now):
                logging.info('TRACK SPEECH description=%s at=%.3f', self.fresh(now), now)
                self.notice = None
                if self.fresh(now):
                    self.description_pending = False
                    self.first_spoken = True
                self.last_beep = now
            return
        if not self.active or not self.fresh(now) or speaking or now - self.last_beep < self.interval_s:
            return
        pan = max(-1., min(1., self.box[0] + self.box[2] - 1))
        if audio.tracking_beep(round(pan * 20) / 20, now):
            self.last_beep = now
