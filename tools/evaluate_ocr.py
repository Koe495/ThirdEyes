"""Run with .ocr-venv Python. JSON manifest contains image, expected, source."""
import argparse
import json
from pathlib import Path
import sys
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'ocr_runtime'))
from thirdeyes.evaluation import metrics
from thirdeyes.ocr import read_settings
from text_reader.ocr_reader import VietnameseOCR


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--models', type=Path, default=ROOT / 'models/ocr')
    args = parser.parse_args()
    engine = VietnameseOCR(args.models, read_settings(ROOT / 'config/ocr.json'))
    rows = []
    for item in json.loads(args.manifest.read_text(encoding='utf-8')):
        path = args.manifest.parent / item['image']
        image = cv2.imdecode(np.fromfile(path, np.uint8), cv2.IMREAD_COLOR)
        if image is None:
            raise ValueError(f'Cannot read {path}')
        result = engine.read(image)
        rows.append({'image': item['image'], 'source': item.get('source', 'unspecified'),
                     'status': result['status'], 'text': result['text'], 'process_ms': result['process_ms'],
                     **metrics(item['expected'], result['text'])})
    chars = sum(r['reference_chars'] for r in rows)
    words = sum(r['reference_words'] for r in rows)
    output = {'samples': rows, 'cer': sum(r['char_errors'] for r in rows) / chars if chars else None,
              'wer': sum(r['word_errors'] for r in rows) / words if words else None}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'samples': len(rows), 'cer': output['cer'], 'wer': output['wer']}))


if __name__ == '__main__':
    main()
