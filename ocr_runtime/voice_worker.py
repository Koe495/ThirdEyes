"""One bounded microphone session; local model, no recording saved."""
import json
import argparse
import math
from pathlib import Path
import queue
import sys
import time

# Only dependency-free catalog/grammar is imported into the audio environment.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from thirdeyes.voice_grammar import PHRASES


def select_input_device(sd, selector):
    if not selector:
        index = sd.default.device[0]
        return index, sd.query_devices(index, 'input')
    name = selector.casefold()
    devices = [
        (index, device) for index, device in enumerate(sd.query_devices())
        if device['max_input_channels'] > 0
        and (name in device['name'].casefold() or device['name'].casefold() in name)
        and not any(excluded in device['name'].casefold()
                    for excluded in ('stereo mix', 'pc speaker'))
    ]
    if not devices:
        raise ValueError(f'Không tìm thấy micro khớp với: {selector}')
    api_priority = {2: 0, 1: 1, 0: 2, 3: 3}
    return min(devices, key=lambda item: (api_priority.get(item[1]['hostapi'], 4), item[0]))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser()
    parser.add_argument('--device', help='Microphone name or device identifier')
    args = parser.parse_args()

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
        device_index, device_info = select_input_device(sd, args.device)
        rate = int(device_info['default_samplerate'])
        recognizer = KaldiRecognizer(model, rate, json.dumps(PHRASES, ensure_ascii=False))
        recognizer.SetWords(True)
        audio = queue.Queue(maxsize=40)
        overflow = []
        signal = {'sum_squares': 0, 'samples': 0, 'peak': 0, 'last_emit': time.monotonic()}

        def callback(data, frames, timing, status):
            if status:
                overflow.append(str(status))
            try:
                block = bytes(data)
                audio.put_nowait(block)
            except queue.Full:
                overflow.append('Audio processing too slow')

        with sd.RawInputStream(device=device_index, samplerate=rate, channels=1, dtype='int16',
                               blocksize=int(rate * .1), callback=callback):
            emit('listening', device=device_info['name'], samplerate=rate,
                 message='Đang nghe: tìm chai nước, tìm điện thoại, đọc văn bản, đọc lại, dừng lại, trạng thái.')
            deadline = time.monotonic() + 6
            while time.monotonic() < deadline:
                if overflow:
                    raise RuntimeError(overflow[0])
                try:
                    data = audio.get(timeout=.2)
                except queue.Empty:
                    continue
                samples = memoryview(data).cast('h')
                signal['sum_squares'] += sum(sample * sample for sample in samples)
                signal['samples'] += len(samples)
                signal['peak'] = max(signal['peak'], max((abs(sample) for sample in samples), default=0))
                now = time.monotonic()
                if now - signal['last_emit'] >= 1:
                    rms = math.sqrt(signal['sum_squares'] / signal['samples']) if signal['samples'] else 0
                    emit('audio_level', device=device_info['name'], rms=round(rms), peak=signal['peak'])
                    signal.update(sum_squares=0, samples=0, peak=0, last_emit=now)
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
