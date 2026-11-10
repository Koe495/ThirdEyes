"""Replay a local recording, without hardware or sound. Optional labelled intervals."""
import argparse
import json
from pathlib import Path
import sys
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from thirdeyes.contracts import FrameBundle
from thirdeyes.depth_processing import DepthProcessor
from thirdeyes.obstacle_detection import ObstacleDetector
from thirdeyes.coordinator_audio import CoordinatorAudio


class Collector:
    def submit(self, event):
        return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('recording', type=Path)
    parser.add_argument('--labels', type=Path, help='JSON intervals: start_s,end_s,zone,expect_alert')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    processor, detector = DepthProcessor(), ObstacleDetector()
    coordinator = CoordinatorAudio(Collector())
    events, start = [], None
    for line in (args.recording / 'frames.jsonl').read_text(encoding='utf-8').splitlines():
        row = json.loads(line)
        if start is None:
            start = row['time']
        with np.load(args.recording / row['file'], allow_pickle=False) as data:
            frames = FrameBundle(data['rgb'], data['depth_mm'], row['color_ms'], row['depth_ms'],
                                 row['color_received_at'], row['depth_received_at'])
        event = coordinator.process(detector.process(processor.process(frames, row['time'])), row['time'])
        if event:
            events.append({'time_s': row['time'] - start, 'kind': event.kind, 'zones': event.zones})
    results = []
    if args.labels:
        for label in json.loads(args.labels.read_text(encoding='utf-8')):
            count = sum(label['start_s'] <= e['time_s'] <= label['end_s'] and label['zone'] in e['zones']
                        and e['kind'] in {'near', 'urgent'} for e in events)
            results.append({**label, 'alerts': count, 'passed': bool(count) == label['expect_alert']})
    args.output.write_text(json.dumps({'events': events, 'label_results': results}, indent=2), encoding='utf-8')
    print(f'{len(events)} sound events; {len(results)} labelled intervals')


if __name__ == '__main__':
    main()
