@echo off
setlocal
cd /d "%~dp0"

where docker >nul 2>nul || (
  echo Docker est introuvable. Installez et demarrez Docker Desktop.
  pause
  exit /b 1
)

docker compose up -d
if errorlevel 1 (
  echo Impossible de demarrer MySQL et phpMyAdmin.
  pause
  exit /b 1
)

echo MySQL demarre sur 127.0.0.1:3306
echo phpMyAdmin sera disponible sur http://127.0.0.1:8080
pause
