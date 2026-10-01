# SOLICITACOES NF - mantem o Painel Notas Fiscais rodando escondido (dados sempre atualizados)

$pastaProjeto = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonw = Join-Path $pastaProjeto ".venv\Scripts\pythonw.exe"
$script = Join-Path $pastaProjeto "src\app_servidor.py"
$nomeTarefa = "SolicitacoesNF_Painel"

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
$acao = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`" --sem-janela" -WorkingDirectory $pastaProjeto

# Liga 1 min depois do logon; a repeticao a cada 10 min religa se ele tiver caido
# (se ja estiver rodando, a porta ocupada faz a nova instancia sair na hora).
$gatilho = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$gatilho.Delay = "PT1M"
$gatilho.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10)).Repetition
$gatilhoAgora = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 10)

$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $nomeTarefa -Action $acao -Trigger @($gatilho, $gatilhoAgora) -Principal $principal -Settings $config `
    -Description "Painel Notas Fiscais em segundo plano: mantem os dados atualizados pra janela abrir ja carregada." | Out-Null

Start-ScheduledTask -TaskName $nomeTarefa
Write-Host "Painel ligado em segundo plano e configurado pra ligar sozinho ao entrar no Windows." -ForegroundColor Green
