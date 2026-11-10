"""Nonblocking offline speech bridge. No network or English-voice fallback."""
import json
import os
from pathlib import Path
import subprocess
import threading


class OfflineSpeech:
    def __init__(self, root, python_path=None):
        self.root = Path(root)
        self.python = Path(python_path) if python_path else self.root / ".ocr-venv/Scripts/python.exe"
        self.command = [str(self.python), str(self.root / "ocr_runtime/speech_worker.py")]
        model = self.root / 'models/speech/vi_VN-vais1000-medium.onnx'
        audio_python = self.root / '.audio-venv/Scripts/python.exe'
        if model.is_file() and audio_python.is_file():
            self.command = [str(audio_python), str(self.root / 'ocr_runtime/piper_worker.py'), '--model', str(model)]
        self.state = "starting"
        self.message = "Dang kiem tra giong tieng Viet offline"
        self._process = None
        self._closed = False
        self._lock = threading.Lock()
        self._thread = threading.Thread(target=self._run, name="ThirdEyes-speech", daemon=True)
        self._thread.start()

    def _run(self):
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            with self._lock:
                if self._closed:
                    return
                self._process = subprocess.Popen(self.command,
                                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                                 text=True, encoding="utf-8", creationflags=flags,
                                                 env={**os.environ, "PYTHONUTF8": "1"})
            for line in self._process.stdout:
                result = json.loads(line)
                self.state = result["state"]
                self.message = result.get("message", result.get("voice", self.state))
            if not self._closed and self.state not in {"no_vi_voice", "error"}:
                self.state, self.message = "error", "Offline speech process stopped"
        except Exception as exc:
            self.state, self.message = "error", str(exc)

    def _send(self, command):
        with self._lock:
            if self._closed or self._process is None or self._process.poll() is not None:
                return False
            try:
                self._process.stdin.write(json.dumps(command, ensure_ascii=False) + "\n")
                self._process.stdin.flush()
                return True
            except (OSError, ValueError):
                self.state = "error"
                return False

    def speak(self, text):
        if self.state not in {"ready", "speaking"} or not text.strip():
            return False
        return self._send({"action": "speak", "text": text[:3000]})

    def stop(self):
        self._send({"action": "stop"})

    def close(self):
        self._send({"action": "quit"})
        with self._lock:
            self._closed = True
            if self._process is not None:
                try:
                    self._process.wait(timeout=.5)
                except subprocess.TimeoutExpired:
                    self._process.terminate()
                    self._process.wait(timeout=1)
                self._process.stdin.close()
        self._thread.join(timeout=1)
        if self._process is not None and self._process.stdout is not None and not self._thread.is_alive():
            self._process.stdout.close()
