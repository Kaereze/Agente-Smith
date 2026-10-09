@echo off
setlocal EnableExtensions
:: PAINEL_DEMO_EM_CASA.bat - abre o Painel Fiscal no PC de casa com DADOS FICTICIOS (modo demonstracao).
:: Nao precisa de Outlook, chave do Google nem Dropbox. Nada e enviado: so pra ver e testar a tela.
:: 1a vez: baixa o projeto do GitHub (git clone) e instala o Python do projeto. Depois: atualiza e abre.
title Painel Fiscal - modo demonstracao
set "REPO=https://github.com/Kaereze/Notas-Fiscais.git"
set "PASTA=%~dp0"
if exist "%PASTA%src\app_servidor.py" goto :tem_pasta
set "PASTA=%USERPROFILE%\Desktop\Painel Fiscal (demo)\"
if exist "%PASTA%src\app_servidor.py" goto :tem_pasta

echo [1/4] Baixando o projeto do GitHub para "%PASTA%"...
where git >nul 2>nul || (
  echo [ERRO] O Git nao esta instalado. Instale com:  winget install --id Git.Git -e
  echo        ou baixe em https://git-scm.com/download/win  e rode este arquivo de novo.
  pause & exit /b 1
)
git clone "%REPO%" "%PASTA:~0,-1%"
if errorlevel 1 ( echo [ERRO] Nao consegui clonar. Confira a internet e o login do GitHub. & pause & exit /b 1 )

:tem_pasta
cd /d "%PASTA%"
echo [2/4] Atualizando com o GitHub...
git pull --ff-only origin main >nul 2>nul && (echo        Atualizado.) || (echo        [AVISO] Nao atualizei agora - sigo com a versao que ja esta aqui.)

echo [3/4] Conferindo o Python do projeto...
if exist ".venv\Scripts\python.exe" goto :tem_venv
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo [ERRO] O Python nao esta instalado. Instale com:  winget install --id Python.Python.3.14 -e
  echo        ou baixe em https://www.python.org/downloads/  e rode este arquivo de novo.
  pause & exit /b 1
)
%PY% -m venv .venv
if errorlevel 1 ( echo [ERRO] Nao consegui criar o ambiente .venv & pause & exit /b 1 )
:tem_venv
".venv\Scripts\python.exe" -m pip install -q --disable-pip-version-check -r requirements.txt
if errorlevel 1 echo        [AVISO] pip falhou - sigo com as bibliotecas que ja estao instaladas.

echo [4/4] Abrindo o Painel em modo demonstracao (dados ficticios)...
echo        Para fechar: feche a janela do Painel e esta janela preta.
".venv\Scripts\python.exe" src\app_servidor.py --demo
if errorlevel 1 ( echo [ERRO] O Painel nao abriu. Veja logs\solicitacoes_nf.log & pause & exit /b 1 )
