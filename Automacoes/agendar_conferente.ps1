# SOLICITACOES NF - liga o CONFERENTE DE NF sozinho, escondido

$pastaProjeto = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonw = Join-Path $pastaProjeto ".venv\Scripts\pythonw.exe"
$script = Join-Path $pastaProjeto "src\conferente.py"
$nomeTarefa = "SolicitacoesNF_Conferente"

foreach ($arquivo in @($pythonw, $script)) {
    if (-not (Test-Path $arquivo)) {
        Write-Host "ERRO: nao encontrei $arquivo (rode Bat\instalar.bat antes)" -ForegroundColor Red
        exit 1
    }
}

if (Get-ScheduledTask -TaskName $nomeTarefa -ErrorAction SilentlyContinue) {
    Write-Host "Removendo a tarefa antiga '$nomeTarefa'..."
    Unregister-ScheduledTask -TaskName $nomeTarefa -Confirm:$false
}

$usuario = "$env:USERDOMAIN\$env:USERNAME"

# pythonw = Python sem janela nenhuma.
$acao = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`"" -WorkingDirectory $pastaProjeto

$gatilho = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$gatilho.Delay = "PT3M"
$gatilho.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10)).Repetition
# Logon so repete a partir do PROXIMO logon; este gatilho repete ja
$gatilhoAgora = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10)

# Interactive: o Outlook so funciona com alguem logado.
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited

# Sem limite de tempo (fica ligado o dia todo). IgnoreNew: se ja esta rodando, nao abre outro.
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $nomeTarefa -Action $acao -Trigger @($gatilho, $gatilhoAgora) -Principal $principal -Settings $config `
    -Description "Conferente de NF: poe o check nos e-mails consolidados quando a NF e enviada ao hospede." | Out-Null

Start-ScheduledTask -TaskName $nomeTarefa
Write-Host ""
Write-Host "Conferente ligado agora e configurado pra ligar sozinho ao entrar no Windows." -ForegroundColor Green
Write-Host "O que ele faz fica em logs\solicitacoes_nf.log (linhas [conferente])."
Write-Host "Pra desligar:  Stop-ScheduledTask -TaskName $nomeTarefa ; Disable-ScheduledTask -TaskName $nomeTarefa"
