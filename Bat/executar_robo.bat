@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0.."
echo ============================================================
echo  ROBO SOLICITACOES NF - execucao manual
echo  (o modo SIMULACAO / TESTE / PRODUCAO vem do config.json)
echo ============================================================
".venv\Scripts\python.exe" robo.py
echo.
echo Terminou. Detalhes em logs\solicitacoes_nf.log
pause
