@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Lancez d'abord setup_windows.bat.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"
python -m unittest discover -s tests -v
pause
