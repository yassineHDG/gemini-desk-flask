@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Lancez d'abord setup_windows.bat.
  pause
  exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m compileall app run.py
call npm run build:css
docker compose config >nul
if errorlevel 1 goto :error
echo Verification terminee avec succes.
pause
exit /b 0

:error
echo La verification a echoue.
pause
exit /b 1
