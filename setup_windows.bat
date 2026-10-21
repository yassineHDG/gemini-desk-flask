@echo off
setlocal
cd /d "%~dp0"

echo [1/5] Verification de Python...
where python >nul 2>nul || (
  echo Python est introuvable. Installez Python 3.11 ou plus recent.
  pause
  exit /b 1
)

echo [2/5] Creation de l'environnement virtuel...
if not exist ".venv\Scripts\python.exe" python -m venv .venv

echo [3/5] Installation des dependances Python...
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if errorlevel 1 goto :error

echo [4/5] Installation de Tailwind CSS v4...
where npm >nul 2>nul || (
  echo Node.js et npm sont introuvables. Installez Node.js LTS.
  pause
  exit /b 1
)
call npm install
call npm run build:css
if errorlevel 1 goto :error

echo [5/5] Configuration locale...
if not exist ".env" copy ".env.example" ".env" >nul

echo.
echo Installation terminee.
echo 1. Ouvrez .env et ajoutez GEMINI_API_KEY.
echo 2. Lancez start_all_windows.bat.
pause
exit /b 0

:error
echo Une erreur est survenue pendant l'installation.
pause
exit /b 1
