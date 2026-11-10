@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    python -m venv .venv
    if errorlevel 1 goto failed
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Setup complete. Run run.bat for Kinect, or demo.bat for synthetic data.
pause
exit /b 0
:failed
echo Setup failed. Check Python 3.14 x64 and internet connection.
pause
exit /b 1
