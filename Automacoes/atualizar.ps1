# SOLICITACOES NF - baixa a versao nova (git pull), atualiza bibliotecas e reinicia o conferente
$pasta = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $pasta
$py = Join-Path $pasta ".venv\Scripts\python.exe"

Write-Host "Baixando a versao nova..." -ForegroundColor Cyan
git pull --ff-only
if ($LASTEXITCODE -ne 0) { Write-Host "git pull falhou (sem internet ou arquivo alterado a mao neste PC)." -ForegroundColor Red; Read-Host "Enter"; exit 1 }

& $py -m pip install -q --disable-pip-version-check -r requirements.txt

# Espera o robo terminar o que estiver fazendo (trava) antes de reiniciar
$i = 0; while ((Test-Path (Join-Path $pasta "estado\_execucao.lock")) -and $i -lt 60) { Start-Sleep 5; $i++ }
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -like "*$pasta*conferente*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
if (Get-ScheduledTask -TaskName SolicitacoesNF_Conferente -ErrorAction SilentlyContinue) {
    Start-ScheduledTask -TaskName SolicitacoesNF_Conferente
    Write-Host "Conferente reiniciado com a versao nova." -ForegroundColor Green
}
git log -1 --format="Versao atual: %h - %s"
Read-Host "Aperte Enter pra fechar"
