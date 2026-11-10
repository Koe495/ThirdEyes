"""Persistent OCR subprocess. Private job files are removed by the controller."""
import argparse
import json
import os
from pathlib import Path
import sys

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")
os.environ.setdefault("HF_HUB_OFFLINE", "1")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    args = parser.parse_args()
    settings = json.loads(args.config.read_text(encoding="utf-8-sig"))
    engine = None
    for line in sys.stdin:
        request = json.loads(line)
        output = Path(request["output"])
        try:
            if engine is None:
                from text_reader import VietnameseOCR
                engine = VietnameseOCR(args.models, settings)
            import cv2
            import numpy as np
            image = cv2.imdecode(np.fromfile(request["image"], dtype=np.uint8), cv2.IMREAD_COLOR)
            result = engine.read(image, request["timestamp"])
        except Exception as exc:
            result = {"status": "error", "text": "", "speak": "Không khởi động được bộ đọc văn bản.",
                      "error": f"{type(exc).__name__}: {exc}", "regions": []}
        result["request_id"] = request["id"]
        temp = output.with_suffix(".pending")
        temp.write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding="utf-8")
        temp.replace(output)


if __name__ == "__main__":
    main()
