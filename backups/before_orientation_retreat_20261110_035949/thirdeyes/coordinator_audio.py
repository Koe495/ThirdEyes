"""Module 6: event-based beeps. Stationary obstacles do not beep periodically."""
from dataclasses import dataclass
import logging
import queue
import threading

from thirdeyes.config import ObstacleConfig
from thirdeyes.contracts import ObstacleReport, SoundEvent


class BeepPlayer:
    """One short sound at a time; no queue buildup or camera-thread blocking."""
    def __init__(self):
        self.error = None
        self._queue = queue.Queue(maxsize=1)
        self._lock = threading.Lock()
        self._busy = False
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="ThirdEyes-beep", daemon=True)
        self._thread.start()

    def submit(self, event: SoundEvent) -> bool:
        with self._lock:
            if self._busy or self.error or self._stop.is_set():
                return False
            self._busy = True
            self._queue.put_nowait(event)
        return True

    def _run(self):
        while not self._stop.is_set():
            try:
                event = self._queue.get(timeout=.1)
            except queue.Empty:
                continue
            try:
                import winsound
                frequency, duration = {"near": (1000, 100), "urgent": (1600, 150),
                                       "depth_unavailable": (500, 100), "test": (1000, 100)}[event.kind]
                winsound.Beep(frequency, duration)
            except Exception as exc:
                self.error = str(exc)
                logging.exception("Audio failed; visual warnings remain active")
            finally:
                with self._lock:
                    self._busy = False
                self._queue.task_done()

    def close(self):
        self._stop.set()
        self._thread.join(timeout=1)


@dataclass
class _Announced:
    level: int = 0
    distance: float | None = None
    moving: bool = False
    stopped_since: float | None = None


class CoordinatorAudio:
    default_mode = "obstacle_warning"

    def __init__(self, player, config: ObstacleConfig | None = None, muted=False, speech=None):
        self.player = player
        self.config = config or ObstacleConfig()
        self.muted = muted
        self.speech = speech
        self.announced = {}
        self.last_sound = -float("inf")
        self.last_level = 0
        self.fault_since = None
        self.recovery_since = None
        self.fault_announced = False
        self.last_event = None

    def toggle_mute(self):
        self.muted = not self.muted
        if self.muted:
            self.stop_speech()
        if not self.muted:
            self.announced.clear()
            self.fault_announced = False
        logging.info("Audio %s", "MUTED" if self.muted else "ON")

    def process(self, report: ObstacleReport, now: float) -> SoundEvent | None:
        cfg = self.config
        faulty = report.status != "ok"
        if faulty:
            self.recovery_since = None
            if self.fault_since is None:
                self.fault_since = now
        else:
            self.fault_since = None
            if self.recovery_since is None:
                self.recovery_since = now
            if now - self.recovery_since >= cfg.fault_recover_s:
                self.fault_announced = False
        candidates = []
        for zone in report.zones:
            memory = self.announced.setdefault(zone.zone, _Announced())
            if zone.level == 0 and zone.known:
                self.announced[zone.zone] = _Announced()
            if zone.approaching:
                memory.stopped_since = None
            elif zone.known:
                if memory.stopped_since is None:
                    memory.stopped_since = now
                if now - memory.stopped_since >= cfg.clear_s:
                    memory.moving = False
            if zone.level == 0 or zone.distance_m is None:
                continue
            progressed = memory.distance is not None and memory.distance - zone.distance_m >= cfg.progress_m
            new_motion = zone.level == 2 and zone.approaching and not memory.moving
            if memory.level < zone.level or progressed or new_motion:
                candidates.append(zone)
        level = max((z.level for z in candidates), default=0)
        event = None
        if candidates:
            reason = "risk_increased" if level > self.last_level else "new_or_closer_obstacle"
            event = SoundEvent("urgent" if level == 2 else "near", reason, tuple(z.zone for z in candidates))
        elif faulty and self.fault_since is not None and now - self.fault_since >= cfg.fault_delay_s and not self.fault_announced:
            event = SoundEvent("depth_unavailable", "depth_missing_or_low_confidence")
        minimum_gap = .25 if level > self.last_level else cfg.cooldown_s
        if event is None or self.muted or now - self.last_sound < minimum_gap:
            return None
        self.stop_speech()
        if not self.player.submit(event):
            return None  # Retry only while the current risk persists.
        self.last_sound, self.last_level, self.last_event = now, level, event
        if event.kind == "depth_unavailable":
            self.fault_announced = True
        else:
            # Simultaneous zones share one beep, with separate episode memories.
            for z in candidates:
                memory = self.announced[z.zone]
                memory.level = max(memory.level, z.level)
                memory.distance = z.distance_m if memory.distance is None else min(memory.distance, z.distance_m)
                if z.approaching:
                    memory.moving = True
                    memory.stopped_since = None
        logging.info("BEEP kind=%s reason=%s zones=%s details=%s", event.kind, event.reason, ",".join(event.zones),
                     [(z.zone, round(z.distance_m, 3), round(z.closing_mps, 3), z.reason) for z in candidates])
        return event

    def close(self):
        self.player.close()
        if self.speech is not None:
            self.speech.close()

    def stop_speech(self):
        if self.speech is not None:
            self.speech.stop()

    def read_text(self, text, now):
        if self.muted or self.speech is None or now - self.last_sound < .5:
            return False
        return self.speech.speak(text)

    def notify_shutdown_fault(self) -> bool:
        if self.muted or self.fault_announced:
            return False
        event = SoundEvent("depth_unavailable", "camera_or_processing_stopped")
        self.stop_speech()
        accepted = self.player.submit(event)
        if accepted:
            logging.info("BEEP kind=%s reason=%s", event.kind, event.reason)
        return accepted
