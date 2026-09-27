@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
echo Rodando os testes automaticos (nao usa Google nem Outlook de verdade)...
".venv\Scripts\python.exe" -m pytest testes -v
pause
