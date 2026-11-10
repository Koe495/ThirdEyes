"""Module 4: nonblocking, cancellable bridge to an isolated Python 3.10 OCR worker."""
import json
import logging
import math
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import uuid

import cv2
import numpy as np

from thirdeyes.contracts import FrameBundle

ROOT = Path(__file__).resolve().parent.parent


def read_settings(path):
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    bounds = {"blur_threshold": (0, 1000), "upscale": (1, 3), "min_confidence": (0, 1),
              "max_regions": (1, 100), "max_characters": (100, 10000), "frame_max_age_s": (.1, 5),
              "timeout_s": (5, 180), "cpu_threads": (1, 4)}
    if set(data) != set(bounds):
        raise ValueError("Invalid keys in config/ocr.json")
    for key, (low, high) in bounds.items():
        value = data[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
            raise ValueError(f"Invalid OCR setting: {key}")
        if key in {"max_regions", "max_characters", "cpu_threads"} and not isinstance(value, int):
            raise ValueError(f"{key} must be an integer")
    return data


class TextReader:
    def __init__(self, root=ROOT, python_path=None, models=None):
        self.root = Path(root)
        self.python = Path(python_path) if python_path else self.root / ".ocr-venv/Scripts/python.exe"
        self.models = Path(models) if models else self.root / "models/ocr"
        try:
            self.settings = read_settings(self.root / "config/ocr.json")
            self.status = "idle"
            self.message = "O: doc chu | R: doc lai | X: dung"
        except (OSError, ValueError, TypeError) as exc:
            self.settings = None
            self.status, self.message = "unavailable", "Cau hinh OCR loi; xem log"
            logging.warning("OCR disabled: %s", exc)
        self.last_result = None
        self.last_text = ""
        self.snapshot_rgb = None
        self._thread = None
        self._cancel = threading.Event()
        self._closed = False
        self._process = None
        self._log = None
        self._process_lock = threading.Lock()
        self._results = queue.Queue(maxsize=1)

    @property
    def busy(self):
        return self._thread is not None and self._thread.is_alive()

    def request(self, frames: FrameBundle, now=None):
        now = time.monotonic() if now is None else now
        if self._closed or self.busy or self.settings is None:
            return False
        if frames.rgb is None or frames.color_received_at is None:
            self.status, self.message = "no_frame", "Chua co anh RGB"
            return False
        if now - frames.color_received_at > self.settings["frame_max_age_s"]:
            self.status, self.message = "stale", "Anh RGB da cu"
            return False
        rgb = frames.rgb
        if rgb.dtype != np.uint8 or rgb.ndim != 3 or rgb.shape[2] != 3:
            self.status, self.message = "error", "RGB khong hop le"
            return False
        if not self.python.is_file():
            self.status, self.message = "unavailable", "Chay setup_ocr.bat de cai OCR"
            return False
        self.snapshot_rgb = rgb.copy()  # detach from the live Kinect frame
        self._cancel = threading.Event()
        while not self._results.empty():
            self._results.get_nowait()
        self.status, self.message = "working", "Dang doc anh chup; canh bao vat can van hoat dong"
        captured_at = time.time() - max(0., now - frames.color_received_at)
        self._thread = threading.Thread(target=self._perform, args=(self.snapshot_rgb, captured_at, self._cancel),
                                        name="ThirdEyes-OCR", daemon=True)
        self._thread.start()
        return True

    def _start_process(self, cancelled):
        with self._process_lock:
            if cancelled.is_set():
                return None
            if self._process is None or self._process.poll() is not None:
                if self._log is not None:
                    self._log.close()
                log_dir = self.root / "logs"
                log_dir.mkdir(exist_ok=True)
                # A fresh process overwrites its diagnostic log; OCR contents are not logged.
                self._log = (log_dir / "ocr_worker.log").open("w", encoding="utf-8")
                env = os.environ.copy()
                env.update(PYTHONUTF8="1", OMP_NUM_THREADS="2", MKL_NUM_THREADS="2", HF_HUB_OFFLINE="1")
                flags = (subprocess.CREATE_NO_WINDOW | subprocess.BELOW_NORMAL_PRIORITY_CLASS) if os.name == "nt" else 0
                self._process = subprocess.Popen(
                    [str(self.python), str(self.root / "ocr_runtime/worker.py"), "--models", str(self.models),
                     "--config", str(self.root / "config/ocr.json")], stdin=subprocess.PIPE,
                    stdout=self._log, stderr=self._log, text=True, encoding="utf-8", env=env,
                    creationflags=flags, cwd=self.root)
            return self._process

    def _terminate(self):
        with self._process_lock:
            proc, self._process = self._process, None
            if proc is not None:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=1)
                if proc.stdin is not None:
                    proc.stdin.close()
            if self._log is not None:
                self._log.close()
                self._log = None

    def _perform(self, rgb, captured_at, cancelled):
        started = time.monotonic()
        result = None
        jobs = self.root / "runtime/ocr_jobs"
        try:
            jobs.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="request_", dir=jobs) as directory:
                image, output = Path(directory) / "frame.png", Path(directory) / "result.json"
                ok, encoded = cv2.imencode(".png", cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
                if not ok:
                    raise RuntimeError("Cannot encode RGB snapshot")
                encoded.tofile(image)
                proc = self._start_process(cancelled)
                if proc is None or cancelled.is_set():
                    return
                request_id = uuid.uuid4().hex
                request = {"id": request_id, "image": str(image), "output": str(output), "timestamp": captured_at}
                proc.stdin.write(json.dumps(request) + "\n")
                proc.stdin.flush()
                while not cancelled.wait(.025):
                    if output.is_file():
                        result = json.loads(output.read_text(encoding="utf-8"))
                        if result.get("request_id") != request_id:
                            raise RuntimeError("OCR response id mismatch")
                        break
                    if proc.poll() is not None:
                        raise RuntimeError("OCR worker stopped; see logs/ocr_worker.log")
                    if time.monotonic() - started > self.settings["timeout_s"]:
                        self._terminate()
                        result = {"status": "timeout", "text": "", "speak": "Đọc văn bản quá lâu. Hãy thử lại với ít chữ hơn."}
                        break
        except Exception as exc:
            result = {"status": "error", "text": "", "error": str(exc), "speak": "Không đọc được văn bản. Hãy thử lại."}
        if cancelled.is_set() or self._closed:
            return
        if result is not None:
            result["total_ms"] = round((time.monotonic() - started) * 1000)
            self._results.put_nowait(result)

    def poll(self):
        try:
            result = self._results.get_nowait()
        except queue.Empty:
            return None
        self.last_result = result
        self.status = result["status"]
        self.message = f"{self.status} | {result.get('total_ms', 0)} ms | R: doc lai | X: dung"
        if self.status == "ok":
            self.last_text = result["text"]
        logging.info("OCR status=%s ms=%s regions=%s truncated=%s", self.status, result.get("total_ms"),
                     len(result.get("regions", [])), result.get("truncated", False))
        if result.get("error"):
            logging.error("OCR backend: %s", result["error"])
        return result

    def cancel(self):
        self._cancel.set()
        self._terminate()
        while not self._results.empty():
            self._results.get_nowait()
        self.status, self.message = "cancelled", "Da dung doc chu"

    def close(self):
        self._closed = True
        self.cancel()
        if self._thread is not None:
            self._thread.join(timeout=3)
