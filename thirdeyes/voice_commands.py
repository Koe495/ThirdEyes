"""Push-to-listen Vietnamese commands; microphone opens only on explicit request."""
import json
import os
from pathlib import Path
import queue
import subprocess
import threading
from thirdeyes.voice_grammar import COMMANDS, parse_command


class VoiceCommands:
    def __init__(self, root):
        self.root = Path(root)
        self.state = 'idle'
        self.message = 'V: nghe 6 giây'
        self.events = queue.Queue(maxsize=4)
        self.process = None
        self.thread = None
        self.closed = False
        self.lock = threading.Lock()

    def listen(self):
        if self.closed or (self.thread is not None and self.thread.is_alive()):
            return False
        self.state = 'starting'
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return True

    @property
    def listening(self):
        return self.state in {'starting', 'listening'}

    def _run(self):
        try:
            python = self.root / '.audio-venv/Scripts/python.exe'
            with self.lock:
                if self.closed:
                    return
                self.process = subprocess.Popen([str(python), str(self.root / 'ocr_runtime/voice_worker.py')],
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding='utf-8',
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            for line in self.process.stdout:
                result = json.loads(line)
                self.state = result['state']
                self.message = result.get('message', self.state)
                action = parse_command(result) if self.state == 'result' else None
                if action:
                    self.events.put_nowait(action)
                elif self.state == 'result':
                    self.message = 'Chưa nhận được lệnh rõ ràng. Bấm V để thử lại.'
            self.process.wait(timeout=2)
            if self.state in {'starting', 'listening'}:
                self.state, self.message = 'error', 'Tiến trình nhận lệnh đã dừng.'
        except Exception as exc:
            self.state, self.message = 'error', str(exc)
        finally:
            if self.process is not None and self.process.stdout is not None:
                self.process.stdout.close()

    def poll(self):
        try:
            return self.events.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        with self.lock:
            self.closed = True
            if self.process is not None and self.process.poll() is None:
                self.process.terminate()
        if self.thread:
            self.thread.join(timeout=3)
