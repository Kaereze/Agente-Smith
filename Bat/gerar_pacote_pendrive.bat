@echo off
:: Copia limpa do projeto pro pen drive (pra instalar nos outros PCs)
cd /d "%~dp0.."
powershell -NoProfile -ExecutionPolicy Bypass -File "Automacoes\gerar_pacote.ps1" %*
