@echo off
setlocal
cd /d "%~dp0"
docker compose down
echo Services arretes. Les donnees MySQL sont conservees dans le volume Docker.
pause
