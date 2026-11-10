@echo off
setlocal
cd /d "%~dp0"
if not exist ".object-venv\Scripts\python.exe" (
  ".runtimes\cpython-3.10.22-windows-x86_64-none\python.exe" -m venv .object-venv
  if errorlevel 1 exit /b 1
)
".venv\Scripts\python.exe" repair_environment.py
if errorlevel 1 exit /b 1
".object-venv\Scripts\python.exe" -m pip install --no-deps torch==2.2.2+cpu torchvision==0.17.2+cpu --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 exit /b 1
".object-venv\Scripts\python.exe" -m pip install ultralytics==8.3.40 numpy==1.26.4 opencv-python==4.10.0.84
if errorlevel 1 exit /b 1
".object-venv\Scripts\python.exe" setup_object_model.py
