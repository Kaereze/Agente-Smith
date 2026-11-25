# BACKUP DO SERVIDOR CENTRAL - cria a tarefa ServidorCentral_Backup neste PC (o "Servidor RA"), sem Docker.
# Roda como SISTEMA todo dia as 03:00, mesmo sem ninguem entrar no Windows (se o PC estava desligado nessa hora, roda assim que der).
# Pede administrador uma vez (e nao pede de novo quando chamado por agendar_servidor_central.ps1).
# Copia C:\ServidorCentral\central.sqlite para C:\ServidorCentral\copias\central-AAAA-MM-DD.sqlite, confere a copia e guarda 14 dias.
# Resultado de cada rodada: C:\ServidorCentral\copias\backup.log. Para tirar:  Unregister-ScheduledTask -TaskName ServidorCentral_Backup -Confirm:$false
param([switch]$Elevado)

$pastaDados = "C:\ServidorCentral"
$log = Join-Path $pastaDados "agendar.log"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $admin) {
    Write-Host "Este passo cria uma tarefa que roda sem ninguem entrar no Windows: o Windows vai pedir a senha de administrador uma vez..."
    New-Item -ItemType Directory -Force $pastaDados | Out-Null
    try {
        Start-Process powershell -Verb RunAs -Wait -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Elevado"
    } catch {
        Write-Host "[ERRO] Permissao negada ou cancelada: nada foi alterado." -ForegroundColor Red
        exit 1
    }
    if (Test-Path $log) { Get-Content $log }
    exit 0
}

$meuLog = $false
try { Start-Transcript -Path $log -Append -ErrorAction Stop | Out-Null; $meuLog = $true } catch { }   # se o instalador ja abriu o log, so escreve nele

$pastaProjeto = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonw = Join-Path $pastaProjeto ".venv\Scripts\pythonw.exe"
$script = Join-Path $pastaProjeto "ferramentas\backup_servidor_central.py"
$nomeTarefa = "ServidorCentral_Backup"

foreach ($arquivo in @($pythonw, $script)) {
    if (-not (Test-Path $arquivo)) {
        Write-Host "ERRO: nao encontrei $arquivo (rode INSTALAR_OU_ATUALIZAR.bat antes)" -ForegroundColor Red
        if ($meuLog) { Stop-Transcript | Out-Null }
        exit 1
    }
}

if (Get-ScheduledTask -TaskName $nomeTarefa -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $nomeTarefa -Confirm:$false
}

$acao = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $pastaProjeto
$gatilho = New-ScheduledTaskTrigger -Daily -At 3:00AM
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName $nomeTarefa -Action $acao -Trigger $gatilho -Principal $principal -Settings $config `
    -Description "Copia de seguranca diaria do banco do servidor central (C:\ServidorCentral), 14 dias, com conferencia da copia. Roda como SISTEMA." | Out-Null
Write-Host "Tarefa $nomeTarefa criada (SISTEMA, todo dia as 03:00; se o PC estava desligado, roda quando ligar)." -ForegroundColor Green
if ($meuLog) { Stop-Transcript | Out-Null }
