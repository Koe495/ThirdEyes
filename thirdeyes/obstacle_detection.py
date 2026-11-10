"""Module 3: relative closing speed and hysteretic hazard states.

No object identity or ego-motion compensation is inferred from depth alone.
Sensor timestamps drive tracking; repeated GUI frames are not new evidence.
"""
from collections import deque
from dataclasses import dataclass

import numpy as np

from thirdeyes.config import ObstacleConfig
from thirdeyes.boundary_motion import BoundaryMotionGuard
from thirdeyes.contracts import DepthObservation, ObstacleReport, ZoneRisk
from thirdeyes.depth_processing import ZONES


@dataclass
class _State:
    level: int = 0
    reason: str = "clear"
    pending: int | None = None
    since: float = 0
    samples: int = 0


class ObstacleDetector:
    def __init__(self, config: ObstacleConfig | None = None):
        self.config = config or ObstacleConfig()
        self.histories = {}
        self.boundary_guard = BoundaryMotionGuard(self.config)
        self.states = {z: _State() for z in ZONES}
        self.last_time = None
        self.cached = ObstacleReport("waiting", (), None)

    def _speed(self, index: int, timestamp: float, distance: float | None) -> float:
        if distance is None:
            self.histories.pop(index, None)
            return 0.0
        history = self.histories.setdefault(index, deque())
        history.append((timestamp, distance))
        while history and timestamp - history[0][0] > self.config.history_s:
            history.popleft()
        if len(history) < 4 or timestamp - history[0][0] < self.config.speed_min_span_s:
            return 0.0
        times, distances = np.array(history).T
        changes = -np.diff(distances)
        drops = changes[changes > .008]
        # Require sustained decreases and >=12 cm travel. A lone occlusion
        # step is insufficient evidence of velocity.
        if len(drops) < 3 or distances[0] - distances[-1] < .12:
            return 0.0
        if float(drops.max()) > .65 * float(drops.sum()):
            return 0.0
        if np.sum(np.maximum(-changes, 0)) > .4 * np.sum(np.maximum(changes, 0)):
            return 0.0
        times = times - times.mean()
        speed = -float(np.dot(times, distances - distances.mean()) / np.dot(times, times))
        return max(0.0, speed)

    def process(self, observation: DepthObservation) -> ObstacleReport:
        cfg = self.config
        if observation.status in {"stale", "waiting"}:
            self.histories.clear()
            self.boundary_guard.reset()
            self.last_time = None
            for state in self.states.values():
                state.pending = None
            # Missing data must never re-arm stationary-obstacle alarms.
            zones = tuple(ZoneRisk(z, self.states[z].level, False, None, 0, None, "unknown") for z in ZONES)
            self.cached = ObstacleReport(observation.status, zones, observation.roi)
            return self.cached
        if not observation.fresh:
            return self.cached
        timestamp = observation.sensor_time_s
        if timestamp is None:
            raise ValueError("Fresh depth observation requires a sensor timestamp")
        if self.last_time is not None and (timestamp <= self.last_time or timestamp - self.last_time > cfg.stale_s):
            self.histories.clear()
            self.boundary_guard.reset()
            for state in self.states.values():
                state.pending = None
        self.last_time = timestamp
        speeds = {c.index: self._speed(c.index, timestamp, c.distance_m) for c in observation.cells}
        guarded = self.boundary_guard.update(observation.cells, timestamp)
        zones = []
        for zone in ZONES:
            state = self.states[zone]
            cells = [c for c in observation.cells if c.zone == zone]
            valid = [c for c in cells if c.distance_m is not None]
            known = bool(cells) and len(valid) == len(cells)
            distance = min((c.distance_m for c in valid), default=None)
            eligible = [c for c in valid if c.index not in guarded]
            has_guarded = len(eligible) != len(valid)
            risk_distance = min((c.distance_m for c in eligible), default=None)
            speed = max((speeds[c.index] for c in eligible), default=0.0)
            ttc = min((c.distance_m / speeds[c.index] for c in eligible if speeds[c.index] > .05), default=None)
            approaching = any(c.distance_m <= cfg.approach_max_m and
                              (speeds[c.index] >= cfg.approach_mps or
                               (speeds[c.index] >= cfg.ttc_min_speed_mps and
                                c.distance_m / speeds[c.index] <= cfg.ttc_s)) for c in eligible)
            desired, reason = 0, "clear"
            if risk_distance is not None:
                # Do not transfer a guarded foreground's hysteresis latch to
                # unrelated, farther background patches in the same zone.
                near_limit = cfg.near_m + (cfg.release_margin_m if state.level >= 1 and not has_guarded else 0)
                critical_limit = cfg.critical_m + (cfg.release_margin_m / 2
                                                  if state.level == 2 and state.reason == "critical" and not has_guarded else 0)
                if risk_distance <= near_limit:
                    desired, reason = 1, "near"
                if risk_distance <= critical_limit:
                    desired, reason = 2, "critical"
                elif approaching:
                    desired, reason = 2, "approaching"
            # Low confidence can raise risk, but cannot assert clearance.
            if not known and desired < state.level:
                state.pending = None
            elif desired == state.level:
                state.pending = None
                state.reason = reason
            else:
                if state.pending != desired:
                    state.pending, state.since, state.samples = desired, timestamp, 1
                else:
                    state.samples += 1
                delay = (cfg.urgent_confirm_s if desired == 2 else cfg.confirm_s) if desired > state.level else cfg.clear_s
                if timestamp - state.since >= delay and state.samples >= 3:
                    state.level, state.reason, state.pending = desired, reason, None
            guard_reasons = [guarded[c.index] for c in valid if c.index in guarded]
            suppressed = bool(guard_reasons) and desired == 0
            display_reason = ("receding" if "receding" in guard_reasons else "emerging") if suppressed else state.reason
            # If another eligible hazard exists, its distance drives the alert.
            reported_distance = risk_distance if desired else distance
            zones.append(ZoneRisk(zone, state.level, known, reported_distance, speed, ttc,
                                  display_reason, approaching, suppressed))
        self.cached = ObstacleReport(observation.status, tuple(zones), observation.roi)
        return self.cached
