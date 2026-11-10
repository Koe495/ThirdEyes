"""One bounded microphone session; local model, no recording saved."""
import json
from pathlib import Path
import queue
import sys
import time

# Only dependency-free catalog/grammar is imported into the audio environment.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from thirdeyes.voice_grammar import PHRASES


def main():
    sys.stdout.reconfigure(encoding='utf-8')

    def emit(state, **data):
        print(json.dumps({'state': state, **data}, ensure_ascii=False), flush=True)

    try:
        import sounddevice as sd
        from vosk import Model, KaldiRecognizer, SetLogLevel
        SetLogLevel(-1)
        path = Path(__file__).resolve().parent.parent / 'models/voice/vosk-model-small-vn-0.4'
        if not (path / 'am/final.mdl').is_file():
            raise FileNotFoundError('Chưa có model Vosk. Chạy setup_audio.bat.')
        model = Model(str(path))
        rate = int(sd.query_devices(kind='input')['default_samplerate'])
        recognizer = KaldiRecognizer(model, rate, json.dumps(PHRASES, ensure_ascii=False))
        recognizer.SetWords(True)
        audio = queue.Queue(maxsize=40)
        overflow = []

        def callback(data, frames, timing, status):
            if status:
                overflow.append(str(status))
            try:
                audio.put_nowait(bytes(data))
            except queue.Full:
                overflow.append('Audio processing too slow')

        with sd.RawInputStream(samplerate=rate, channels=1, dtype='int16',
                               blocksize=int(rate * .1), callback=callback):
            emit('listening', message='Đang nghe: tìm chai nước, tìm điện thoại, đọc văn bản, đọc lại, dừng lại, trạng thái.')
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                if overflow:
                    raise RuntimeError(overflow[0])
                try:
                    data = audio.get(timeout=.2)
                except queue.Empty:
                    continue
                if recognizer.AcceptWaveform(data):
                    result = json.loads(recognizer.Result())
                    if result.get('text'):
                        emit('result', **result)
                        return
            emit('result', **json.loads(recognizer.FinalResult()))
    except Exception as exc:
        emit('error', message=str(exc))


if __name__ == '__main__':
    main()
