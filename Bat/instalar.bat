@echo off
chcp 65001 > nul
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
    echo Criando ambiente Python...
    py -3.14 -m venv .venv || py -m venv .venv
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
echo.
echo Pronto. Agora rode TESTAR_CONFIG.bat
pause
