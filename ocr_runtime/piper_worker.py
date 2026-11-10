"""Local Vietnamese TTS, interruptible without stopping the camera process."""
import argparse
import json
from pathlib import Path
import queue
import re
import sys
import threading


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--model', type=Path, required=True)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stdin.reconfigure(encoding='utf-8')
    output_lock = threading.Lock()

    def emit(state, **fields):
        with output_lock:
            print(json.dumps({'state': state, **fields}, ensure_ascii=False), flush=True)

    try:
        if not args.model.is_file() or not Path(str(args.model) + '.json').is_file():
            raise FileNotFoundError('Missing local Piper model; run setup_audio.bat')
        import sounddevice as sd
        import onnxruntime as ort
        from piper import PiperVoice
        # Limit CPU usage independently of OCR and the depth loop.
        voice = PiperVoice.load(args.model)
        voice.use_tashkeel = False  # Never fetch optional Arabic resources for OCR text.
        options = ort.SessionOptions()
        options.intra_op_num_threads = 2
        options.inter_op_num_threads = 1
        voice.session = ort.InferenceSession(str(args.model), sess_options=options, providers=['CPUExecutionProvider'])
        pending = queue.Queue(maxsize=1)
        generation = [0]
        closing = threading.Event()

        def synthesize():
            while not closing.is_set():
                try:
                    token, text = pending.get(timeout=.1)
                except queue.Empty:
                    continue
                try:
                    if token != generation[0]:
                        continue
                    emit('speaking')
                    # Short text chunks bound cancellation latency during inference.
                    for segment in re.findall(r'.{1,160}(?:\s|$)', text[:3000]):
                        if token != generation[0] or closing.is_set():
                            break
                        for chunk in voice.synthesize(segment):
                            if token != generation[0] or closing.is_set():
                                break
                            # Raw stream uses 50 ms blocks so stop never waits for a paragraph.
                            data = chunk.audio_int16_bytes
                            with sd.RawOutputStream(samplerate=chunk.sample_rate, channels=1, dtype='int16') as stream:
                                size = max(2, int(chunk.sample_rate * .05) * 2)
                                for start in range(0, len(data), size):
                                    if token != generation[0] or closing.is_set():
                                        stream.abort()
                                        break
                                    stream.write(data[start:start + size])
                    if token == generation[0]:
                        emit('ready')
                except Exception as exc:
                    emit('error', message=str(exc))
                finally:
                    pending.task_done()

        thread = threading.Thread(target=synthesize, daemon=True)
        thread.start()
        emit('ready', voice='Piper tiếng Việt VAIS1000 (offline)')
        for line in sys.stdin:
            command = json.loads(line)
            generation[0] += 1
            while not pending.empty():
                try:
                    pending.get_nowait(); pending.task_done()
                except queue.Empty:
                    break
            if command['action'] == 'quit':
                break
            if command['action'] == 'speak':
                pending.put((generation[0], command.get('text', '')))
            else:
                emit('ready')
        closing.set()
        thread.join(timeout=1)
    except Exception as exc:
        emit('error', message=str(exc))


if __name__ == '__main__':
    main()
