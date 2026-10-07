@echo off
setlocal EnableExtensions
:: ATUALIZAR_PAINEL.bat - deixa este PC igual ao GitHub (branch main) e reinicia o Painel Fiscal.
:: Pode ser rodado de dentro da pasta do projeto ou copiado pra qualquer lugar (acha a pasta sozinho).
:: Nunca apaga o que foi alterado a mao neste PC: se der conflito, para e avisa.
:: Uso: duplo clique  |  sem janela parada no fim: ATUALIZAR_PAINEL.bat --sem-pausa

:: O git pull pode trocar este proprio arquivo: roda uma copia dele no TEMP.
if /i "%~1"=="--copia" goto :principal
set "COPIA=%TEMP%\atualizar_painel_nf.bat"
:: tudo numa linha so: o cmd ja leu a linha inteira antes do git trocar o arquivo original
copy /y "%~f0" "%COPIA%" >nul & call "%COPIA%" --copia "%~dp0" %1 & exit /b

:principal
set "ORIGEM=%~2"
set "PAUSA=1"
if /i "%~3"=="--sem-pausa" set "PAUSA="
title Atualizar Painel Notas Fiscais
echo ============================================================
echo   ATUALIZAR PAINEL NOTAS FISCAIS
echo ============================================================
echo.

:: ---------- 1. pasta do projeto ----------
set "PASTA="
call :testar_pasta "%ORIGEM%"
call :testar_pasta "%USERPROFILE%\Desktop\Solicitacoes NF"
call :testar_pasta "%USERPROFILE%\OneDrive\Desktop\Solicitacoes NF"
call :testar_pasta "%USERPROFILE%\Desktop\NOTAS\Solicitacoes NF"
call :testar_pasta "C:\Solicitacoes NF"
if not defined PASTA (
  echo [ERRO] Nao achei a pasta "Solicitacoes NF" com o projeto.
  echo        Coloque este .bat dentro da pasta do projeto e rode de novo.
  goto :erro
)
cd /d "%PASTA%"
if not exist "logs" mkdir "logs"
set "LOG=%PASTA%\logs\atualizacao.log"
echo [1/6] Pasta: %PASTA%

:: ---------- 2. git ----------
set "GIT=git"
where git >nul 2>nul && goto :tem_git
set "GIT=%ProgramFiles%\Git\cmd\git.exe"
if exist "%GIT%" goto :tem_git
set "GIT=%LOCALAPPDATA%\Programs\Git\cmd\git.exe"
if exist "%GIT%" goto :tem_git
echo [ERRO] Git nao encontrado neste PC. Rode o INSTALAR_OU_ATUALIZAR.bat uma vez.
goto :erro
:tem_git
set "ANTES="
set "RAMO="
for /f "usebackq delims=" %%v in (`"%GIT%" rev-parse --short HEAD`) do set "ANTES=%%v"
for /f "usebackq delims=" %%v in (`"%GIT%" rev-parse --abbrev-ref HEAD`) do set "RAMO=%%v"
echo [2/6] Versao atual: %ANTES% (branch %RAMO%)
echo %date% %time% ATUALIZAR_PAINEL.bat inicio: %ANTES% branch %RAMO%>>"%LOG%"

:: ---------- 3. baixar do GitHub ----------
echo [3/6] Baixando a versao nova do GitHub...
"%GIT%" fetch origin --prune
if errorlevel 1 (
  echo [ERRO] Nao consegui falar com o GitHub. Confira a internet e rode de novo.
  goto :erro
)
set "NOVA="
for /f "usebackq delims=" %%v in (`"%GIT%" rev-parse --short origin/main`) do set "NOVA=%%v"
echo        GitHub (main): %NOVA%

:: ---------- 4. aplicar ----------
echo [4/6] Aplicando neste PC...
"%GIT%" merge-base --is-ancestor HEAD origin/main
if errorlevel 1 goto :tem_commits_proprios
:: so pra frente: o caso normal
"%GIT%" merge --ff-only origin/main
if errorlevel 1 goto :conflito
goto :aplicado

:tem_commits_proprios
echo        Este PC tem commits que o GitHub nao tem: juntando com a main...
"%GIT%" merge --no-edit origin/main
if errorlevel 1 (
  "%GIT%" merge --abort >nul 2>nul
  goto :conflito
)
goto :aplicado

:conflito
echo.
echo [ERRO] Nao deu pra atualizar sem mexer no que foi alterado neste PC.
echo        Nada foi apagado. Arquivos alterados aqui:
"%GIT%" status --short --untracked-files=no
echo        Peca ajuda (Remote Control / Claude) pra juntar essas mudancas.
echo %date% %time% conflito, nada aplicado>>"%LOG%"
goto :erro

:aplicado
set "DEPOIS="
for /f "usebackq delims=" %%v in (`"%GIT%" rev-parse --short HEAD`) do set "DEPOIS=%%v"
if "%DEPOIS%"=="%ANTES%" (echo        Ja estava na versao do GitHub.) else (echo        Atualizado de %ANTES% para %DEPOIS%.)

:: ---------- 5. bibliotecas ----------
echo [5/6] Conferindo as bibliotecas do Python...
if not exist ".venv\Scripts\python.exe" (
  echo [ERRO] Ambiente .venv nao existe neste PC. Rode o INSTALAR_OU_ATUALIZAR.bat uma vez.
  goto :erro
)
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 echo        [AVISO] pip falhou - sigo com as bibliotecas que ja estao instaladas.

:: ---------- 6. reiniciar conferente e Painel ----------
echo [6/6] Reiniciando o conferente e o Painel...
schtasks /query /tn "SolicitacoesNF_Painel" >nul 2>nul
if errorlevel 1 (
  echo [ERRO] A tarefa SolicitacoesNF_Painel nao existe neste PC. Rode o INSTALAR_OU_ATUALIZAR.bat uma vez.
  goto :erro
)
powershell -NoProfile -ExecutionPolicy Bypass -File "Automacoes\reiniciar_servicos.ps1"
echo        Esperando o Painel responder...
powershell -NoProfile -Command "for($i=0;$i -lt 30;$i++){try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8765/ -TimeoutSec 3 | Out-Null; exit 0}catch{Start-Sleep 2}}; exit 1"
if errorlevel 1 (
  echo        [AVISO] O Painel ainda nao respondeu. Ele volta sozinho em ate 10 min pela tarefa agendada.
) else (
  echo        Painel no ar.
)

echo.
echo ============================================================
echo   PRONTO. Versao neste PC: %DEPOIS%  (GitHub: %NOVA%)
echo ============================================================
echo %date% %time% ATUALIZAR_PAINEL.bat pronto: %DEPOIS%>>"%LOG%"
if defined PAUSA pause
exit /b 0

:erro
echo.
echo   Nada mais foi feito. Detalhes em logs\atualizacao.log
if defined PAUSA pause
exit /b 1

:testar_pasta
if defined PASTA exit /b 0
set "T=%~1"
if not defined T exit /b 0
if "%T:~-1%"=="\" set "T=%T:~0,-1%"
if exist "%T%\.git" if exist "%T%\src\app_servidor.py" set "PASTA=%T%"
exit /b 0
