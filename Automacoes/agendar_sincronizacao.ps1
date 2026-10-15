# SOLICITACOES NF - agenda a COPIA das planilhas dos hoteis pra Planilha Central
param([int]$Minutos = 10)   # 10 min: pedido do usuario, 15/10/2026 (era 30)

$pastaProjeto = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$batPath = Join-Path $pastaProjeto "Bat\sincronizar_agendado.bat"
$vbsPath = Join-Path $pastaProjeto "Bat\_rodar_oculto.vbs"
$nomeTarefa = "SolicitacoesNF_CopiaHoteis"

foreach ($arquivo in @($batPath, $vbsPath)) {
    if (-not (Test-Path $arquivo)) { Write-Host "ERRO: nao encontrei $arquivo" -ForegroundColor Red; exit 1 }
}

if (Get-ScheduledTask -TaskName $nomeTarefa -ErrorAction SilentlyContinue) {
    Unregister-ScheduledTask -TaskName $nomeTarefa -Confirm:$false
}

$usuario = "$env:USERDOMAIN\$env:USERNAME"
$acao = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "//B `"$vbsPath`" `"$batPath`"" -WorkingDirectory $pastaProjeto

$gatilho = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$gatilho.Delay = "PT3M"
$gatilho.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes $Minutos)).Repetition
# Logon so repete a partir do PROXIMO logon; este gatilho repete ja
$gatilhoAgora = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $Minutos)

$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited

# IgnoreNew: se a anterior ainda estiver rodando, nao comeca outra.
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 25) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $nomeTarefa -Action $acao -Trigger @($gatilho, $gatilhoAgora) -Principal $principal -Settings $config `
    -Description "Solicitacoes NF: copia as respostas novas das planilhas dos hoteis pra Planilha Central a cada $Minutos minuto(s)." | Out-Null

Write-Host "Tarefa '$nomeTarefa' criada: roda ao entrar no Windows e a cada $Minutos minuto(s)." -ForegroundColor Green
Write-Host "Pra rodar agora e testar:  Start-ScheduledTask -TaskName $nomeTarefa"
