@echo off
:: Abre o Painel Notas Fiscais (janela propria). O servidor local fecha sozinho 3 min depois da janela.
cd /d "%~dp0.."
start "" ".venv\Scripts\pythonw.exe" src\app_servidor.py
