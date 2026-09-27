# SOLICITACOES NF - copia LIMPA do projeto pro pen drive (sem estado/, logs/, .venv/ deste PC)
# Uso: Bat\gerar_pacote_pendrive.bat   (ou: -Destino "E:\" pra escolher a unidade)
param([string]$Destino)

$pasta = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $pasta

if (-not $Destino) {
    $pen = Get-Volume | Where-Object { $_.DriveType -eq 'Removable' -and $_.DriveLetter } | Select-Object -First 1
    if (-not $pen) { Write-Host "Nenhum pen drive encontrado. Conecte e rode de novo." -ForegroundColor Red; Read-Host "Enter"; exit 1 }
    $Destino = "$($pen.DriveLetter):\"
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

$proibidos = @("estado", "logs", ".venv", "config.local.json") | Where-Object { Test-Path (Join-Path $alvo $_) }
if ($proibidos) { Write-Host "ATENCAO: o pacote tem $proibidos - apague antes de levar." -ForegroundColor Red }

Write-Host ""
Write-Host "PRONTO: $alvo" -ForegroundColor Green
git -C $alvo log -1 --format="Versao: %h - %s"
Write-Host "No outro PC: copie a pasta 'Solicitacoes NF' pra Area de Trabalho e rode Bat\configurar_este_pc.bat"
Read-Host "Aperte Enter pra fechar"
