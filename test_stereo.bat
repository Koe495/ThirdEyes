@echo off
setlocal
cd /d "%~dp0"
echo Stereo test: LEFT - CENTER - RIGHT.
call run.bat --test-sound %*
