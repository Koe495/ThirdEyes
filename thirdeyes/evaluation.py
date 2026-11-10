"""Reproducible OCR error metrics and opt-in local RGB/depth recordings."""
from dataclasses import asdict
import json
from pathlib import Path
import unicodedata

import numpy as np


def edit_distance(expected, actual):
    previous = list(range(len(actual) + 1))
    for i, left in enumerate(expected, 1):
        row = [i]
        for j, right in enumerate(actual, 1):
            row.append(min(row[-1] + 1, previous[j] + 1, previous[j - 1] + (left != right)))
        previous = row
    return previous[-1]


def metrics(expected, actual):
    expected, actual = (' '.join(unicodedata.normalize('NFC', t).split()) for t in (expected, actual))
    chars, words = edit_distance(expected, actual), edit_distance(expected.split(), actual.split())
    return {'char_errors': chars, 'reference_chars': len(expected),
            'word_errors': words, 'reference_words': len(expected.split()),
            'cer': chars / len(expected) if expected else None,
            'wer': words / len(expected.split()) if expected else None,
            'unexpected_text': bool(actual) if not expected else False}


class SessionRecorder:
    def __init__(self, directory, interval=.1):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=False)
        self.interval, self.last, self.count = interval, -float('inf'), 0
        self.index = (self.directory / 'frames.jsonl').open('w', encoding='utf-8')

    def record(self, frames, report, now):
        if now - self.last < self.interval or frames.rgb is None or frames.depth_mm is None:
            return
        name = f'{self.count:05d}.npz'
        np.savez_compressed(self.directory / name, rgb=frames.rgb, depth_mm=frames.depth_mm)
        self.index.write(json.dumps({'file': name, 'time': now, 'color_ms': frames.color_timestamp_ms,
            'depth_ms': frames.depth_timestamp_ms, 'color_received_at': frames.color_received_at,
            'depth_received_at': frames.depth_received_at, 'report': asdict(report)}, ensure_ascii=False) + '\n')
        self.index.flush()
        self.last, self.count = now, self.count + 1

    def close(self):
        self.index.close()
