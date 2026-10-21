@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo Lancez d'abord setup_windows.bat.
  pause
  exit /b 1
)

docker compose up -d
if errorlevel 1 (
  echo Impossible de demarrer Docker. Verifiez Docker Desktop.
  pause
  exit /b 1
)

echo Attente de MySQL...
timeout /t 12 /nobreak >nul
start "Tailwind Gemini Desk" cmd /k "cd /d ""%~dp0"" && npm run dev:css"
call ".venv\Scripts\activate.bat"
echo Application: http://127.0.0.1:5000
echo phpMyAdmin: http://127.0.0.1:8080
python run.py
pause
