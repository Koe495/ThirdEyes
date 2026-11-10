"""Offline Paddle text detection + VietOCR recognition, adapted for ThirdEyes.

All models/configuration must already exist locally. No camera, speech,
LLM correction, runtime downloads or logging of recognized content.
"""
import json
from pathlib import Path
import time

import cv2
import numpy as np

MESSAGES = {
    "blurry": "Ảnh chưa rõ. Hãy giữ camera ổn định và đưa chữ vào vùng nhìn.",
    "no_text": "Chưa tìm thấy chữ trong ảnh.",
    "low_confidence": "Đã thấy chữ nhưng chưa đọc đủ rõ.",
    "error": "Không đọc được văn bản. Hãy kiểm tra trạng thái trên màn hình.",
}


def ordered_rows(boxes):
    """Group by relative line height, avoiding a fixed 15-pixel rounding bin."""
    rows = []
    for box in sorted(boxes, key=lambda b: float(b[:, 1].mean())):
        y = float(box[:, 1].mean())
        height = max(1., float(np.ptp(box[:, 1])))
        match = next((row for row in rows if abs(y - row[0]) <= .45 * max(height, row[1])), None)
        if match is None:
            rows.append([y, height, [box]])
        else:
            match[2].append(box)
            match[0] = float(np.mean([b[:, 1].mean() for b in match[2]]))
    return [box for row in sorted(rows, key=lambda r: r[0])
            for box in sorted(row[2], key=lambda b: float(b[:, 0].mean()))]


def rectify(image, box):
    """Perspective crop in detector order: top-left, top-right, bottom-right, bottom-left."""
    p = np.asarray(box, np.float32)
    width = max(np.linalg.norm(p[0] - p[1]), np.linalg.norm(p[2] - p[3]))
    height = max(np.linalg.norm(p[0] - p[3]), np.linalg.norm(p[1] - p[2]))
    w, h = max(2, int(round(width))), max(2, int(round(height)))
    target = np.float32([[0, 0], [w - 1, 0], [w - 1, h - 1], [0, h - 1]])
    crop = cv2.warpPerspective(image, cv2.getPerspectiveTransform(p, target), (w, h),
                               flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    return cv2.copyMakeBorder(crop, 3, 3, 3, 3, cv2.BORDER_REPLICATE)


class VietnameseOCR:
    def __init__(self, model_dir, settings, detector=None, recognizer=None):
        self.settings = settings
        if detector is not None and recognizer is not None:
            self.detector, self.recognizer = detector, recognizer
            return
        root = Path(model_dir)
        for required in (root / "det/inference.pdmodel", root / "det/inference.pdiparams",
                         root / "vgg_transformer.pth", root / "vietocr_config.json"):
            if not required.is_file():
                raise FileNotFoundError(f"Missing offline model: {required.name}; run setup_ocr.bat")
        import torch  # must be imported before Paddle on this pinned Windows stack
        torch.set_num_threads(settings["cpu_threads"])
        import paddle
        paddle.set_device("cpu")
        from paddleocr.paddleocr import parse_args
        from paddleocr.tools.infer.predict_det import TextDetector
        from vietocr.tool.predictor import Predictor

        args = parse_args(mMain=False)
        args.det_model_dir = str(root / "det")
        args.use_gpu = False
        args.enable_mkldnn = False
        args.cpu_threads = settings["cpu_threads"]
        args.det_limit_side_len = 1280
        self.detector = TextDetector(args)
        cfg = json.loads((root / "vietocr_config.json").read_text(encoding="utf-8"))
        cfg["weights"] = str(root / "vgg_transformer.pth")
        cfg["device"] = "cpu"
        cfg["cnn"]["pretrained"] = False
        cfg["predictor"]["beamsearch"] = False
        self.recognizer = Predictor(cfg)

    def read(self, frame_bgr, timestamp=None):
        start = time.perf_counter()
        result = {"status": "error", "text": "", "text_raw": "", "lines": [], "regions": [],
                  "speak": MESSAGES["error"], "timestamp": timestamp, "sharpness": None,
                  "process_ms": 0, "truncated": False, "rejected_regions": 0}
        try:
            if not isinstance(frame_bgr, np.ndarray) or frame_bgr.dtype != np.uint8 or frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3 or not frame_bgr.size:
                raise ValueError("Expected nonempty uint8 BGR HxWx3 image")
            gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
            result["sharpness"] = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            if result["sharpness"] < self.settings["blur_threshold"]:
                result.update(status="blurry", speak=MESSAGES["blurry"])
                return result
            scale = min(self.settings["upscale"], 1280 / max(frame_bgr.shape[:2]))
            image = cv2.resize(frame_bgr, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
            boxes, _ = self.detector(image)
            if boxes is None or len(boxes) == 0:
                result.update(status="no_text", speak=MESSAGES["no_text"])
                return result
            boxes = ordered_rows([np.asarray(b, np.float32) for b in boxes
                                  if np.asarray(b).shape == (4, 2) and np.isfinite(b).all()])
            for box in boxes:
                box[:, 0] = np.clip(box[:, 0], 0, image.shape[1] - 1)
                box[:, 1] = np.clip(box[:, 1], 0, image.shape[0] - 1)
            result["truncated"] = len(boxes) > self.settings["max_regions"]
            from PIL import Image
            raw, accepted = [], []
            for box in boxes[:self.settings["max_regions"]]:
                crop = rectify(image, box)
                text, probability = self.recognizer.predict(Image.fromarray(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)), return_prob=True)
                text = str(text).strip()
                confidence = float(probability) if probability is not None else 0.
                if not text:
                    continue
                raw.append(text)
                trusted = np.isfinite(confidence) and confidence >= self.settings["min_confidence"]
                result["regions"].append({"text": text, "confidence": confidence if np.isfinite(confidence) else 0.,
                                          "accepted": bool(trusted), "box": (box / scale).tolist()})
                if trusted:
                    accepted.append(text)
                else:
                    result["rejected_regions"] += 1
            result["text_raw"] = "\n".join(raw)
            if accepted:
                text = "\n".join(accepted)
                limit = self.settings["max_characters"]
                result["truncated"] |= len(text) > limit
                result.update(status="ok", text=text[:limit], lines=accepted, speak=text[:limit])
            else:
                status = "low_confidence" if raw else "no_text"
                result.update(status=status, speak=MESSAGES[status])
        except Exception as exc:
            result.update(status="error", error=f"{type(exc).__name__}: {exc}", speak=MESSAGES["error"])
        finally:
            result["process_ms"] = round((time.perf_counter() - start) * 1000)
        return result
