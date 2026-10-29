@echo off
:: Compara a Caixa de Entrada do Outlook DESTE PC com o que o Painel mostra, caixa por caixa. So le; nao muda nada.
:: Abra o Outlook antes. Duplo clique e pronto.
chcp 65001 >nul
cd /d "%~dp0.."
".venv\Scripts\python.exe" "Automacoes\conferir_contagem_outlook.py"
echo.
pause
