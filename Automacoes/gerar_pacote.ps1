# SOLICITACOES NF - copia LIMPA do projeto pro pen drive (sem estado/, logs/, .venv/ deste PC)
# Uso: Bat\gerar_pacote_pendrive.bat   (ou: -Destino "E:\" pra escolher a unidade)
param([string]$Destino, [switch]$ComChave)

$pasta = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $pasta

if (-not $Destino) {
    # pen drive / HD externo: unidade que nao e a do Windows (prefere a que ja tem a pasta KARUZO)
    $unidades = Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Root -ne "$env:SystemDrive\" -and (Test-Path $_.Root) }
    $pen = ($unidades | Where-Object { Test-Path (Join-Path $_.Root "KARUZO") } | Select-Object -First 1)
    if (-not $pen) { $pen = $unidades | Select-Object -First 1 }
    if (-not $pen) { Write-Host "Nenhum pen drive/HD externo encontrado. Conecte e rode de novo." -ForegroundColor Red; Read-Host "Enter"; exit 1 }
    $Destino = Join-Path $pen.Root "KARUZO"
    New-Item -ItemType Directory -Force $Destino | Out-Null
}
$alvo = Join-Path $Destino "Solicitacoes NF"

if (git status --porcelain) {
    Write-Host "Ha mudancas nao salvas no git neste PC - elas NAO vao pro pacote. Salve (commit) antes." -ForegroundColor Yellow
}
if (Test-Path $alvo) {
    Write-Host "Ja existe $alvo - atualizando pra versao deste PC..." -ForegroundColor Cyan
    git -C $alvo pull --ff-only $pasta main
} else {
    Write-Host "Criando $alvo ..." -ForegroundColor Cyan
    git clone --no-hardlinks --quiet $pasta $alvo
}
if ($LASTEXITCODE -ne 0) { Write-Host "Falhou." -ForegroundColor Red; Read-Host "Enter"; exit 1 }

if (-not $ComChave) {
    $ComChave = (Read-Host "Levar a chave do Google junto (pra instalar sem pedir)? s/n") -match "^s"
}
if ($ComChave) {
    Copy-Item (Join-Path $env:APPDATA "SolicitacoesNF\chave-api.json") (Join-Path $Destino "chave-api.json") -Force
    Write-Host "Chave copiada pra $Destino - ela da acesso as planilhas: guarde bem o pen drive." -ForegroundColor Yellow
}

$proibidos = @("estado", "logs", ".venv", "config.local.json") | Where-Object { Test-Path (Join-Path $alvo $_) }
if ($proibidos) { Write-Host "ATENCAO: o pacote tem $proibidos - apague antes de levar." -ForegroundColor Red }

Write-Host ""
Write-Host "PRONTO: $alvo" -ForegroundColor Green
git -C $alvo log -1 --format="Versao: %h - %s"
Write-Host "No outro PC: conecte o pen drive e de duplo clique em $alvo\INSTALAR_OU_ATUALIZAR.bat"
Read-Host "Aperte Enter pra fechar"
