@echo off
setlocal
cd /d "%~dp0"
echo Installing TrainingHub...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0windows\install_traininghub.ps1"
if errorlevel 1 (
  echo.
  echo Installation failed. Review the message above.
  pause
)
