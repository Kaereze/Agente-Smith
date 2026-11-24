# SERVIDOR CENTRAL - mantem o servidor da API central rodando neste PC (o "Servidor RA"), sem Docker.
# Faz duas coisas: (1) cria a tarefa agendada ServidorCentral (liga no logon e religa a cada 10 min se cair);
# (2) libera a porta 8770 no firewall, so para a rede local (pede administrador uma vez).
# Nao precisa de senha: o token sai da chave do Google deste PC (ferramentas\rodar_servidor_central.py).
# Para tirar:  Unregister-ScheduledTask -TaskName ServidorCentral -Confirm:$false  e apague a regra "Painel Fiscal - servidor central".

$pastaProjeto = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonw = Join-Path $pastaProjeto ".venv\Scripts\pythonw.exe"
$script = Join-Path $pastaProjeto "ferramentas\rodar_servidor_central.py"
$nomeTarefa = "ServidorCentral"
$nomeRegra = "Painel Fiscal - servidor central"
$porta = 8770

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
$gatilho = New-ScheduledTaskTrigger -AtLogOn -User $usuario
$gatilho.Delay = "PT30S"
$gatilho.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10)).Repetition
$principal = New-ScheduledTaskPrincipal -UserId $usuario -LogonType Interactive -RunLevel Limited
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $nomeTarefa -Action $acao -Trigger $gatilho -Principal $principal -Settings $config `
    -Description "Servidor central da API do Painel Fiscal (porta $porta). Se a porta ja esta em uso, a nova instancia sai na hora." | Out-Null
Write-Host "Tarefa $nomeTarefa criada (liga no logon e religa a cada 10 min se cair)." -ForegroundColor Green

# firewall: so a rede local, so a porta do servidor
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not (Get-NetFirewallRule -DisplayName $nomeRegra -ErrorAction SilentlyContinue)) {
    if ($admin) {
        New-NetFirewallRule -DisplayName $nomeRegra -Direction Inbound -Action Allow -Protocol TCP -LocalPort $porta `
            -RemoteAddress LocalSubnet -Profile Any | Out-Null
        Write-Host "Porta $porta liberada so para a rede local." -ForegroundColor Green
    } else {
        Write-Host "Liberando a porta $porta (o Windows vai pedir a senha de administrador uma vez)..."
        $comando = "New-NetFirewallRule -DisplayName '$nomeRegra' -Direction Inbound -Action Allow -Protocol TCP -LocalPort $porta -RemoteAddress LocalSubnet -Profile Any"
        try {
            Start-Process powershell -Verb RunAs -Wait -ArgumentList "-NoProfile -Command $comando"
        } catch {
            Write-Host "[AVISO] Permissao negada: os outros PCs nao vao alcancar o servidor ate a porta ser liberada." -ForegroundColor Yellow
        }
    }
}
Start-ScheduledTask -TaskName $nomeTarefa
Write-Host "Servidor central iniciado. Confira:  curl http://127.0.0.1:$porta/v1/saude" -ForegroundColor Green
