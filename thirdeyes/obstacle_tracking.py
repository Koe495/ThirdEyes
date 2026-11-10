"""Short-lived geometric patch IDs, not semantic object recognition."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class PatchTrack:
    track_id: int
    bounds: tuple
    distance_m: float
    age_s: float


class PatchTracker:
    def __init__(self):
        self.tracks = {}
        self.next_id = 1
        self.last_time = None

    def update(self, cells, now):
        if self.last_time is not None and (now <= self.last_time or now - self.last_time > .6):
            self.tracks.clear()
        self.last_time = now
        remaining = {c.index: c for c in cells if c.distance_m is not None and c.distance_m <= 3.0}
        clusters = []
        while remaining:
            first = remaining.pop(next(iter(remaining)))
            members, pending = [first], [first]
            while pending:
                c = pending.pop()
                adjacent = [n for n in remaining.values() if
                            abs(n.index // 6 - c.index // 6) + abs(n.index % 6 - c.index % 6) == 1
                            and abs(n.distance_m - c.distance_m) <= .25]
                for n in adjacent:
                    remaining.pop(n.index); members.append(n); pending.append(n)
            bounds = (min(c.bounds[0] for c in members), min(c.bounds[1] for c in members),
                      max(c.bounds[2] for c in members), max(c.bounds[3] for c in members))
            clusters.append((bounds, min(c.distance_m for c in members)))
        previous = {key: value for key, value in self.tracks.items() if now - value[2] <= .3}
        proposals = []
        for bounds, distance in clusters:
            x, y = (bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2
            costs = []
            for key, (track, started, seen) in previous.items():
                bx = (track.bounds[0] + track.bounds[2]) / 2
                by = (track.bounds[1] + track.bounds[3]) / 2
                shift = math.hypot(x - bx, y - by) / max(1, bounds[2] - bounds[0], track.bounds[2] - track.bounds[0])
                dz = abs(distance - track.distance_m)
                if shift <= 1.2 and dz <= .5:
                    costs.append((shift + dz, key))
            costs.sort()
            # Ambiguous overlap/merge: issue a new ID rather than claim identity.
            proposals.append(costs[0][1] if costs and (len(costs) == 1 or costs[1][0] - costs[0][0] > .15) else None)
        current = {}
        for (bounds, distance), candidate in zip(clusters, proposals):
            if candidate is None or proposals.count(candidate) > 1:
                key, started = self.next_id, now
                self.next_id += 1
            else:
                key, started = candidate, previous[candidate][1]
            track = PatchTrack(key, bounds, distance, now - started)
            current[key] = (track, started, now)
        # Retain missing tracks briefly for re-association, but never display them.
        self.tracks = {**previous, **current}
        return tuple(value[0] for value in current.values())
