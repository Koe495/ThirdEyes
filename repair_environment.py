"""Repair project-local environments after a directory move; no downloads."""
from pathlib import Path
import subprocess
import sys


def repair(root):
    base = root / '.runtimes/cpython-3.10.22-windows-x86_64-none/python.exe'
    for name in ('.ocr-venv', '.audio-venv', '.object-venv'):
        cfg = root / name / 'pyvenv.cfg'
        if not cfg.exists():
            continue
        home = next((line.split('=', 1)[1].strip() for line in cfg.read_text().splitlines()
                     if line.startswith('home =')), '')
        if Path(home).resolve() == base.parent.resolve():
            continue
        if not base.is_file():
            raise RuntimeError('Missing bundled Python 3.10; run setup_ocr.bat')
        backup = cfg.with_suffix('.cfg.before_repair')
        if not backup.exists():
            backup.write_bytes(cfg.read_bytes())
        subprocess.run([str(base), '-m', 'venv', '--without-pip', str(root / name)], check=True)
        print('Repaired', name)


if __name__ == '__main__':
    repair(Path(__file__).resolve().parent)
