"""Explicit installation only. Runtime never downloads a model."""
import argparse
import hashlib
import json
from pathlib import Path
import urllib.request
import zipfile


def download(url, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        temporary = target.with_suffix(target.suffix + '.partial')
        with urllib.request.urlopen(url, timeout=60) as source, temporary.open('wb') as output:
            while block := source.read(1024 * 1024):
                output.write(block)
        temporary.replace(target)
    print(target.name, target.stat().st_size, flush=True)


def setup(root):
    speech = root / 'models/speech'
    origin = 'https://huggingface.co/rhasspy/piper-voices/resolve/main/vi/vi_VN/vais1000/medium/'
    for filename in ('vi_VN-vais1000-medium.onnx', 'vi_VN-vais1000-medium.onnx.json', 'MODEL_CARD'):
        download(origin + filename, speech / filename)
    archive = root / 'models/voice/vosk-model-small-vn-0.4.zip'
    download('https://alphacephei.com/vosk/models/vosk-model-small-vn-0.4.zip', archive)
    destination = archive.parent.resolve()
    with zipfile.ZipFile(archive) as zipped:
        for member in zipped.infolist():
            target = (destination / member.filename).resolve()
            if not target.is_relative_to(destination):
                raise ValueError('Unsafe archive path')
        zipped.extractall(destination)
    files = list(speech.glob('*')) + [archive]
    (root / 'models/audio_manifest.json').write_text(json.dumps(
        {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}, indent=2), encoding='utf-8')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parent)
    setup(parser.parse_args().root)
