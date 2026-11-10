"""Short, offline stereo PCM cues; directions are in normalized camera space."""
from functools import lru_cache
import io
import math
import wave

import numpy as np

SAMPLE_RATE = 44100
TONES = {"track": (850, .080), "near": (1000, .100), "urgent": (1600, .150), "listen": (700, .060),
         "depth_unavailable": (500, .100), "test": (1000, .100)}
GAINS = {"LEFT": (1., 0.), "CENTER": (2 ** -.5, 2 ** -.5), "RIGHT": (0., 1.)}


@lru_cache(maxsize=64)
def render_cue(kind: str, zones: tuple[str, ...] = (), volume: float = .25,
               swap_channels: bool = False, pan: float | None = None) -> bytes:
    """Return 16-bit stereo WAV. Multiple directions stay separate in time."""
    if not math.isfinite(volume) or not 0 < volume <= 1:
        raise ValueError("Audio volume must be in (0, 1]")
    frequency, duration = TONES[kind]
    if pan is not None and (not math.isfinite(pan) or not -1 <= pan <= 1):
        raise ValueError('Stereo pan must be in [-1, 1]')
    if kind == "test":
        directions = ("LEFT", "CENTER", "RIGHT")
    elif kind == "depth_unavailable":
        directions = ("CENTER",)
    else:
        directions = tuple(dict.fromkeys(zones)) or ("CENTER",)
    count = round(SAMPLE_RATE * duration)
    tone = np.sin(2 * np.pi * frequency * np.arange(count) / SAMPLE_RATE)
    # Five-millisecond ramps remove abrupt edges/clicks.
    ramp = round(SAMPLE_RATE * .005)
    tone[:ramp] *= np.linspace(0, 1, ramp)
    tone[-ramp:] *= np.linspace(1, 0, ramp)
    pause = np.zeros((round(SAMPLE_RATE * (.12 if kind == "test" else .06)), 2))
    parts = []
    for direction in directions:
        gains = GAINS[direction]
        if kind == 'track' and pan is not None:
            angle = (pan + 1) * math.pi / 4
            gains = (math.cos(angle), math.sin(angle))
        if swap_channels:
            gains = gains[::-1]
        if parts:
            parts.append(pause)
        parts.append(tone[:, None] * np.array(gains) * volume)
    pcm = np.rint(np.concatenate(parts) * 32767).astype("<i2")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm.tobytes())
    return output.getvalue()
