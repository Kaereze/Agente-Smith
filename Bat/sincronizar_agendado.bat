@echo off
:: Agendador: cópia dos hotéis + envio (a cada 10 min)
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
if not exist "logs" mkdir "logs"
:: A saída da tela gira em 5 MB, como o log do robô (LGPD, 20/10/2026): fica a atual + 2 antigas.
set "SAIDA=logs\saida_console_sincronizar.txt"
if exist "%SAIDA%" for %%F in ("%SAIDA%") do if %%~zF GTR 5000000 (
    if exist "%SAIDA%.2" del /q "%SAIDA%.2" 2>nul
    if exist "%SAIDA%.1" ren "%SAIDA%.1" "saida_console_sincronizar.txt.2" 2>nul
    ren "%SAIDA%" "saida_console_sincronizar.txt.1" 2>nul
)
".venv\Scripts\python.exe" src\sincronizar.py --agendado --enviar >> "%SAIDA%" 2>&1
exit /b %ERRORLEVEL%
