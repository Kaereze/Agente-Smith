@echo off
:: Instala o Painel num PC SEM Outlook (so olha, emite e pede o envio). Uso: INSTALAR_PC_SO_PAINEL.bat -Operador Ingrid
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "Automacoes\instalar_pc_so_painel.ps1" %*
