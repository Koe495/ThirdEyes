@echo off
setlocal
cd /d "%~dp0"
if not exist ".runtimes\cpython-3.10.22-windows-x86_64-none\python.exe" (
    echo Run setup_ocr.bat first to install the bundled Python.
    exit /b 1
)
".venv\Scripts\python.exe" repair_environment.py
if errorlevel 1 exit /b 1
if not exist ".audio-venv\Scripts\python.exe" (
    ".runtimes\cpython-3.10.22-windows-x86_64-none\python.exe" -m venv .audio-venv
    if errorlevel 1 exit /b 1
)
".audio-venv\Scripts\python.exe" -m pip install -r requirements-audio.lock.txt
if errorlevel 1 exit /b 1
".audio-venv\Scripts\python.exe" setup_audio_models.py
if errorlevel 1 exit /b 1
echo Offline Vietnamese voice and commands installed.
