"""Run explicitly during installation; inference never downloads weights."""
from pathlib import Path
import hashlib
import urllib.request

root = Path(__file__).resolve().parent
target = root / 'models/objects/yolo11s.pt'
target.parent.mkdir(parents=True, exist_ok=True)
if not target.exists():
    temporary = target.with_suffix('.partial')
    urllib.request.urlretrieve('https://huggingface.co/Ultralytics/YOLO11/resolve/main/yolo11s.pt', temporary)
    temporary.replace(target)
(target.parent / 'sha256.txt').write_text(hashlib.sha256(target.read_bytes()).hexdigest() + '  yolo11s.pt\n')
print('Local model:', target)
