@echo off
:: Configura este PC (rodar uma vez em cada PC novo)
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "Automacoes\configurar_pc.ps1"
