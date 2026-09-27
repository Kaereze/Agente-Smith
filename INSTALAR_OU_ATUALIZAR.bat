@echo off
:: CORACAO: instala ou atualiza tudo neste PC (Python, Git, .venv, chave, conferente)
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "Automacoes\coracao.ps1" %*
