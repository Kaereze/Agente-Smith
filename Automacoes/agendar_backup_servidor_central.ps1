# BACKUP DO SERVIDOR CENTRAL - cria a tarefa agendada ServidorCentral_Backup neste PC (o "Servidor RA"), sem Docker.
# Roda todo dia as 03:00 (se o PC estava desligado nessa hora, roda assim que der). Nao pede administrador nem senha.
# Copia C:\ServidorCentral\central.sqlite para C:\ServidorCentral\copias\central-AAAA-MM-DD.sqlite, confere a copia e guarda 14 dias.
# Resultado de cada rodada: C:\ServidorCentral\copias\backup.log. Para tirar:  Unregister-ScheduledTask -TaskName ServidorCentral_Backup -Confirm:$false

$pastaProjeto = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonw = Join-Path $pastaProjeto ".venv\Scripts\pythonw.exe"
$script = Join-Path $pastaProjeto "ferramentas\backup_servidor_central.py"
$nomeTarefa = "ServidorCentral_Backup"

foreach ($arquivo in @($pythonw, $script)) {
    if (-not (Test-Path $arquivo)) {
        Write-Host "ERRO: nao encontrei $arquivo (rode INSTALAR_OU_ATUALIZAR.bat antes)" -ForegroundColor Red
        exit 1
    }
}

if (Get-ScheduledTask -TaskName $nomeTarefa -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $nomeTarefa -Confirm:$false
}

$usuario = "$env:USERDOMAIN\$env:USERNAME"
$acao = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $pastaProjeto
$gatilho = New-ScheduledTaskTrigger -Daily -At 3:00AM
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
Register-ScheduledTask -TaskName $nomeTarefa -Action $acao -Trigger $gatilho -Principal $principal -Settings $config `
    -Description "Copia de seguranca diaria do banco do servidor central (C:\ServidorCentral), 14 dias, com conferencia da copia." | Out-Null
Write-Host "Tarefa $nomeTarefa criada (todo dia as 03:00; se o PC estava desligado, roda quando ligar)." -ForegroundColor Green
Write-Host "Teste agora:  Start-ScheduledTask -TaskName $nomeTarefa   e olhe  C:\ServidorCentral\copias\backup.log" -ForegroundColor Green
