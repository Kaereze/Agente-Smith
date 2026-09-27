@echo off
:: Conferente em janela (normalmente roda escondido pela tarefa SolicitacoesNF_Conferente)
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
echo ============================================================
echo  CONFERENTE DE NF - olha os Itens Enviados a cada minuto
echo  e atualiza os e-mails consolidados. Feche esta janela pra parar.
echo ============================================================
".venv\Scripts\python.exe" src\conferente.py
pause
