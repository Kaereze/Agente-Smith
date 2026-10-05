@echo off
:: Confere TODAS as NFs do ano pelos e-mails enviados das caixas deste PC e grava no Painel.
:: Rode uma vez em cada PC depois de atualizar (o conferente sozinho só olha os últimos 45 dias).
:: Não baixa nada do Dropbox; leva poucos minutos.
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
echo Conferindo as NFs de 2026 pelos e-mails enviados deste PC (Outlook precisa estar aberto)...
".venv\Scripts\python.exe" src\confirmar_nfs.py --desde=2026-01-01 --rever --sem-dropbox --sem-ocr --gravar
pause
