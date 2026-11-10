@echo off
setlocal
cd /d "%~dp0"
echo Setup downloads Python, libraries and model files once. OCR runtime is offline.
if not exist ".setup-tools\Scripts\python.exe" (
    python -m venv .setup-tools
    if errorlevel 1 goto failed
)
".setup-tools\Scripts\python.exe" -m pip install uv==0.13.7
if errorlevel 1 goto failed
".setup-tools\Scripts\uv.exe" python install 3.10.22 --install-dir .runtimes --no-bin --no-registry
if errorlevel 1 goto failed
if not exist ".ocr-venv\Scripts\python.exe" (
    ".runtimes\cpython-3.10.22-windows-x86_64-none\python.exe" -m venv .ocr-venv
    if errorlevel 1 goto failed
)
".ocr-venv\Scripts\python.exe" -m pip install pip==26.3
if errorlevel 1 goto failed
".ocr-venv\Scripts\python.exe" -m pip install --no-deps torch==2.2.2+cpu torchvision==0.17.2+cpu --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto failed
rem Full locked inference runtime. --no-deps deliberately excludes unused training,
rem document-export and cloud features, plus duplicate OpenCV distributions.
".ocr-venv\Scripts\python.exe" -m pip install --no-deps -r requirements-ocr.lock.txt
if errorlevel 1 goto failed
".ocr-venv\Scripts\python.exe" ocr_runtime\setup_models.py --models models\ocr
if errorlevel 1 goto failed
echo OCR setup complete. Run run.bat, then press O to read text.
echo Vietnamese speech requires a Vietnamese SAPI voice installed in Windows.
pause
exit /b 0
:failed
echo OCR setup failed. Camera and obstacle modules can still run.
pause
exit /b 1
