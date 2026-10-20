@echo off
setlocal EnableExtensions
:: PAINEL_DEMO_EM_CASA.bat - abre o Painel Fiscal no PC de casa.
:: Com a chave do Google de casa: dados reais, so visualizacao (nao grava nada). Sem a chave: dados ficticios.
:: Nao precisa de Outlook nem Dropbox.
:: 1a vez: baixa o projeto do GitHub, instala o Python se faltar e cria o ambiente. Depois: atualiza e abre.
title Painel Fiscal - modo demonstracao
set "REPO=https://github.com/Kaereze/Notas-Fiscais.git"
set "LOGDEMO=%TEMP%\painel_demo_instalacao.log"
echo %date% %time% inicio>"%LOGDEMO%"

:: ---------- 1. pasta do projeto ----------
set "PASTA=%~dp0"
if exist "%PASTA%src\app_servidor.py" goto :tem_pasta
set "PASTA=%USERPROFILE%\Desktop\Painel Fiscal (demo)\"
if exist "%PASTA%src\app_servidor.py" goto :tem_pasta
set "PASTA=%USERPROFILE%\Desktop\PainelFiscal-demo\"
if exist "%PASTA%src\app_servidor.py" goto :tem_pasta
echo [1/4] Baixando o projeto do GitHub para "%PASTA%"...
where git >nul 2>nul
if errorlevel 1 goto :sem_git
git clone "%REPO%" "%USERPROFILE%\Desktop\PainelFiscal-demo"
if errorlevel 1 goto :erro_clone

:tem_pasta
cd /d "%PASTA%"
echo [1/4] Pasta do projeto: %CD%
echo [2/4] Atualizando com o GitHub...
git pull --ff-only origin main >>"%LOGDEMO%" 2>&1
if errorlevel 1 echo        [AVISO] Nao atualizei agora - sigo com a versao que ja esta aqui.

:: ---------- 3. Python de verdade (o "python" da Microsoft Store e so um atalho que nao funciona) ----------
echo [3/4] Conferindo o Python...
if exist ".venv\Scripts\python.exe" ".venv\Scripts\python.exe" -c "import sys" >nul 2>nul
if exist ".venv\Scripts\python.exe" if not errorlevel 1 goto :tem_venv
if exist ".venv" (
  echo        Ambiente .venv quebrado de uma tentativa anterior: apagando pra criar de novo...
  rmdir /s /q ".venv"
)
call :achar_python
if defined PY goto :criar_venv
echo        Python nao encontrado. Instalando o Python 3.13 (so pra este usuario, sem pedir administrador)...
where winget >nul 2>nul
if errorlevel 1 goto :sem_python
winget install -e --id Python.Python.3.13 --scope user --silent --accept-package-agreements --accept-source-agreements
call :achar_python
if not defined PY goto :sem_python

:criar_venv
echo        Usando: %PY%
%PY% -m venv .venv >>"%LOGDEMO%" 2>&1
if errorlevel 1 goto :erro_venv
if not exist ".venv\Scripts\python.exe" goto :erro_venv

:tem_venv
echo        Instalando as bibliotecas (1a vez demora alguns minutos)...
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt >>"%LOGDEMO%" 2>&1
if errorlevel 1 echo        [AVISO] Alguma biblioteca nao instalou - tento abrir mesmo assim. Detalhes: %LOGDEMO%

:: Com a chave do Google de casa (so leitura) em %APPDATA%\SolicitacoesNF\chave-api.json: dados REAIS, so visualizacao.
:: Sem a chave: dados ficticios (modo demonstracao), como antes.
set "MODO=--demo"
if exist "%APPDATA%\SolicitacoesNF\chave-api.json" set "MODO=--visualizar"
if "%MODO%"=="--visualizar" (
  echo [4/4] Abrindo o Painel com os DADOS REAIS, so visualizacao ^(modo casa^)...
  echo        Responder, enviar NF e marcar lido continuam so nos PCs do trabalho.
) else (
  echo [4/4] Abrindo o Painel em modo demonstracao ^(dados ficticios^)...
  echo        Para ver os dados reais, coloque a chave do Google de casa em:
  echo        %APPDATA%\SolicitacoesNF\chave-api.json
)
echo        Para fechar: feche a janela do Painel e esta janela preta.
".venv\Scripts\python.exe" src\app_servidor.py %MODO%
if errorlevel 1 goto :erro_painel
exit /b 0

:: ---------- acha um Python que FUNCIONA (testa de verdade, ignora o atalho da Store) ----------
:achar_python
set "PY="
for %%v in (3.14 3.13 3.12 3.11) do (
  if not defined PY py -%%v -c "import venv" >nul 2>nul && set "PY=py -%%v"
)
if not defined PY py -3 -c "import venv" >nul 2>nul && set "PY=py -3"
for %%d in (Python314 Python313 Python312 Python311) do (
  if not defined PY if exist "%LOCALAPPDATA%\Programs\Python\%%d\python.exe" set "PY="%LOCALAPPDATA%\Programs\Python\%%d\python.exe""
)
if not defined PY python -c "import sys, venv; assert 'WindowsApps' not in sys.executable" >nul 2>nul && set "PY=python"
exit /b 0

:sem_git
echo [ERRO] O Git nao esta instalado. Instale com:  winget install --id Git.Git -e
echo        ou baixe em https://git-scm.com/download/win  e rode este arquivo de novo.
goto :fim_erro
:erro_clone
echo [ERRO] Nao consegui baixar do GitHub. Confira a internet e o login do GitHub (conta Kaereze).
goto :fim_erro
:sem_python
echo [ERRO] Nao achei nem consegui instalar o Python.
echo        Instale o Python 3.13 em https://www.python.org/downloads/
echo        IMPORTANTE: na 1a tela do instalador marque "Add python.exe to PATH". Depois rode este arquivo de novo.
goto :fim_erro
:erro_venv
echo [ERRO] O Python (%PY%) nao conseguiu criar o ambiente .venv. O que ele disse:
type "%LOGDEMO%"
echo.
echo        Mande uma foto desta tela pro Claude.
goto :fim_erro
:erro_painel
echo [ERRO] O Painel nao abriu. Veja logs\painel.log na pasta do projeto.
goto :fim_erro
:fim_erro
echo        Registro completo: %LOGDEMO%
pause
exit /b 1
