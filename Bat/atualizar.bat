@echo off
:: Baixa a versao nova do GitHub e reinicia o conferente
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "Automacoes\atualizar.ps1"
