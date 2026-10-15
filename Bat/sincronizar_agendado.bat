@echo off
:: Agendador: cópia dos hotéis + envio (a cada 10 min)
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
if not exist "logs" mkdir "logs"
".venv\Scripts\python.exe" src\sincronizar.py --agendado --enviar >> "logs\saida_console_sincronizar.txt" 2>&1
exit /b %ERRORLEVEL%
