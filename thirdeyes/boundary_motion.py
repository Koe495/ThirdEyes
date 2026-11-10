"""Guard newly visible near patches while establishing their direction.

Invalid depth does not prove an object was below 0.8 m. This is a bounded
temporal heuristic per fixed depth cell, not object identity tracking.
"""
from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass
class _Emergence:
    started: float
    last_seen: float
    last_progress: float
    peak: float
    progress_anchor: float
    receding: bool = False
    samples: deque = field(default_factory=deque)


class BoundaryMotionGuard:
    def __init__(self, config):
        self.config = config
        self.previous = {}
        self.tracks = {}

    def reset(self):
        self.previous.clear()
        self.tracks.clear()

    def update(self, cells, timestamp):
        return {cell.index: reason for cell in cells
                if (reason := self._update(cell.index, cell.distance_m, timestamp)) is not None}

    def _update(self, index, distance, now):
        cfg = self.config
        previous = self.previous.get(index)
        self.previous[index] = distance
        track = self.tracks.get(index)
        if track is not None and now - track.last_seen > .2:
            self.tracks.pop(index, None)
            track = None
        if distance is None:
            return None
        # An unmeasurable foreground may leave visible background in this tile.
        # Also guard a sudden first near-floor return against that far background.
        appeared = ((previous is None and distance <= cfg.near_m) or
                    (previous is not None and distance <= cfg.emergence_entry_m and previous - distance >= .35))
        if track is None and appeared:
            track = _Emergence(now, now, now, distance, distance)
            self.tracks[index] = track
        if track is None:
            return None
        if distance > cfg.near_m + cfg.release_margin_m or track.peak - distance >= cfg.recession_reverse_m:
            self.tracks.pop(index, None)
            return None
        track.last_seen = now
        track.peak = max(track.peak, distance)
        if distance - track.progress_anchor >= .01:
            track.last_progress = now
            track.progress_anchor = distance
        track.samples.append((now, distance))
        while track.samples and now - track.samples[0][0] > cfg.history_s:
            track.samples.popleft()
        if not track.receding and len(track.samples) >= 3:
            times, distances = np.asarray(track.samples).T
            differences = np.diff(distances)
            span = times[-1] - times[0]
            positive = np.maximum(differences, 0).sum()
            negative = np.maximum(-differences, 0).sum()
            if span >= .15 and distances[-1] - distances[0] >= .02 and np.count_nonzero(differences > .001) >= 2 and negative <= .4 * positive:
                centered = times - times.mean()
                speed = float(np.dot(centered, distances - distances.mean()) / np.dot(centered, centered))
                track.receding = speed >= cfg.recession_min_mps
        if track.receding:
            if now - track.last_progress < cfg.recession_stop_s:
                return "receding"
        elif now - track.started < cfg.emergence_observe_s:
            return "emerging"
        self.tracks.pop(index, None)
        return None
