# SOLICITACOES NF - configura este PC (instala, confere chave/Outlook, identifica e agenda)
# Uso: Bat\configurar_este_pc.bat   (ou: -SoConferir pra so verificar, sem agendar nada)
param([switch]$SoConferir)

$ErrorActionPreference = "Stop"
$pasta = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $pasta
$py = Join-Path $pasta ".venv\Scripts\python.exe"
$env:PYTHONIOENCODING = "utf-8"

function Passo($n, $texto) { Write-Host ""; Write-Host "[$n/6] $texto" -ForegroundColor Cyan }
function Ok($texto) { Write-Host "   OK  $texto" -ForegroundColor Green }
function Falha($texto) { Write-Host "   !!  $texto" -ForegroundColor Red; Read-Host "Aperte Enter pra fechar"; exit 1 }

# 1. Python
Passo 1 "Python"
$lancador = Get-Command py -ErrorAction SilentlyContinue
if (-not (Test-Path $py) -and -not $lancador) { Falha "Python nao instalado. Instale em https://www.python.org/downloads/ (marque 'Add to PATH') e rode de novo." }
Ok "Python encontrado"

# 2. Ambiente + bibliotecas
Passo 2 "Bibliotecas do robo"
if (-not (Test-Path $py)) { & py -3 -m venv .venv; if (-not (Test-Path $py)) { Falha "Nao consegui criar o ambiente .venv" } }
& $py -m pip install -q --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { Falha "pip install falhou (sem internet?)" }
Ok "Bibliotecas instaladas"

# 3. Chave do Google
Passo 3 "Chave do Google"
$chaveDir = Join-Path $env:APPDATA "SolicitacoesNF"
$chave = Join-Path $chaveDir "chave-api.json"
if (-not (Test-Path $chave)) {
    New-Item -ItemType Directory -Force $chaveDir | Out-Null
    Write-Host "   Falta a chave. Abrindo a pasta: cole nela o arquivo chave-api.json (o mesmo do PC principal)." -ForegroundColor Yellow
    Start-Process explorer.exe $chaveDir
    Read-Host "   Depois de colar, aperte Enter"
    if (-not (Test-Path $chave)) { Falha "Ainda nao achei $chave" }
}
Ok "Chave em $chave"

# 4. Outlook + identidade do PC
Passo 4 "Outlook e identidade deste PC"
& $py src\identidade.py
if ($LASTEXITCODE -ne 0) { Falha "Nao consegui identificar o PC (Outlook aberto? contas notafiscal@ configuradas?)" }
$papel = (& $py -c "import sys; sys.path.insert(0,'src'); from config import carregar_config; print(carregar_config()['papel'])").Trim()
Ok "Papel deste PC: $papel"

if ($SoConferir) { Write-Host ""; Write-Host "So conferencia (-SoConferir): nada foi agendado." -ForegroundColor Yellow; exit 0 }

# 5. Conferente (todo PC)
Passo 5 "Conferente ligando sozinho com o Windows"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pasta "Automacoes\agendar_conferente.ps1")
Ok "Tarefa SolicitacoesNF_Conferente"

# 6. Copia + envio (so no principal)
Passo 6 "Copia das planilhas + envio"
if ($papel -eq "principal") {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pasta "Automacoes\agendar_sincronizacao.ps1") -Minutos 30
    Ok "Tarefa SolicitacoesNF_CopiaHoteis (a cada 30 min)"
} else {
    Write-Host "   --  Pulado: este PC e conferente. Copia e envio rodam so no PC principal." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "PRONTO. Este PC esta configurado como: $papel" -ForegroundColor Green
Read-Host "Aperte Enter pra fechar"
