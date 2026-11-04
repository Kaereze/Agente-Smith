@echo off
:: Abre o ajustes.json no Bloco de Notas (cria na primeira vez) e confere o que foi digitado quando voce fecha.
:: So no PC do administrador. Nao sobe ao GitHub. Depois de salvar, feche e abra o Painel de novo.
chcp 65001 >nul
cd /d "%~dp0.."
".venv\Scripts\python.exe" "Automacoes\gerar_ajustes_exemplo.py" --meu
notepad "ajustes.json"
echo.
echo Conferindo o que foi digitado...
".venv\Scripts\python.exe" "src\ajustes.py"
echo.
echo Para os novos valores valerem: menu do operador, "Fechar o Painel", e abra de novo.
pause
