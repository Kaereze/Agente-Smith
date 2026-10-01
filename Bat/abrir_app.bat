@echo off
:: Abre o Painel Notas Fiscais (janela propria). O servidor fica rodando em segundo plano.
cd /d "%~dp0.."
start "" ".venv\Scripts\pythonw.exe" src\app_janela.py
