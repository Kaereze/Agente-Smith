# SERVIDOR CENTRAL - faz o servidor da API central subir SOZINHO neste PC (o "Servidor RA"), sem Docker e sem ninguem entrar no Windows.
# Pede administrador UMA vez e cria:
#   (1) a tarefa ServidorCentral: roda como SISTEMA, sobe logo que o Windows liga (30 s depois) e religa a cada 10 min se cair;
#   (2) a regra de firewall da porta 8770, so para a rede local;
#   (3) a tarefa ServidorCentral_Backup (copia de seguranca as 03:00): chama agendar_backup_servidor_central.ps1.
# Nao guarda senha nenhuma: a conta SISTEMA nao tem senha. A chave do Google (de onde sai o token) fica na pasta do usuario que
# rodou este script (%APPDATA%\SolicitacoesNF\chave-api.json); a tarefa recebe essa pasta em --appdata.
# Resultado desta instalacao: C:\ServidorCentral\agendar.log.
# Para tirar:  Unregister-ScheduledTask -TaskName ServidorCentral,ServidorCentral_Backup -Confirm:$false  e apague a regra "Painel Fiscal - servidor central".
param([switch]$Elevado, [string]$AppData = $env:APPDATA)

$pastaDados = "C:\ServidorCentral"
$log = Join-Path $pastaDados "agendar.log"
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)

if (-not $admin) {
    Write-Host "Este passo cria tarefas que rodam sem ninguem entrar no Windows: o Windows vai pedir a senha de administrador uma vez..."
    New-Item -ItemType Directory -Force $pastaDados | Out-Null
    try {
        Start-Process powershell -Verb RunAs -Wait -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`" -Elevado -AppData `"$AppData`""
    } catch {
        Write-Host "[ERRO] Permissao negada ou cancelada: nada foi alterado." -ForegroundColor Red
        exit 1
    }
    if (Test-Path $log) { Get-Content $log }
    exit 0
}

New-Item -ItemType Directory -Force $pastaDados | Out-Null
$meuLog = $false
try { Start-Transcript -Path $log -Force -ErrorAction Stop | Out-Null; $meuLog = $true } catch { }

$pastaProjeto = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$pythonw = Join-Path $pastaProjeto ".venv\Scripts\pythonw.exe"
$script = Join-Path $pastaProjeto "ferramentas\rodar_servidor_central.py"
$chave = Join-Path $AppData "SolicitacoesNF\chave-api.json"
$nomeTarefa = "ServidorCentral"
$nomeRegra = "Painel Fiscal - servidor central"
$porta = 8770

foreach ($arquivo in @($pythonw, $script, $chave)) {
    if (-not (Test-Path $arquivo)) {
        Write-Host "ERRO: nao encontrei $arquivo (rode INSTALAR_OU_ATUALIZAR.bat antes; a chave do Google tem que estar na pasta do usuario)" -ForegroundColor Red
        if ($meuLog) { Stop-Transcript | Out-Null }
        exit 1
    }
}

# 1. tira a tarefa antiga (do usuario) e o servidor que ela deixou rodando, para a porta ficar livre
if (Get-ScheduledTask -TaskName $nomeTarefa -ErrorAction SilentlyContinue) {
    Stop-ScheduledTask -TaskName $nomeTarefa -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $nomeTarefa -Confirm:$false
}
Get-CimInstance Win32_Process | Where-Object { $_.Name -match '^pythonw?\.exe$' -and $_.CommandLine -match 'rodar_servidor_central' } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Seconds 2

# 2. tarefa como SISTEMA: sobe ao ligar o Windows, mesmo sem ninguem entrar
$acao = New-ScheduledTaskAction -Execute $pythonw -Argument "`"$script`" --appdata `"$AppData`"" -WorkingDirectory $pastaProjeto
$gatilho = New-ScheduledTaskTrigger -AtStartup
$gatilho.Delay = "PT30S"
$gatilho.Repetition = (New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 10)).Repetition
$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest
$config = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopOnIdleEnd -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $nomeTarefa -Action $acao -Trigger $gatilho -Principal $principal -Settings $config `
    -Description "Servidor central da API do Painel Fiscal (porta $porta). Roda como SISTEMA ao ligar o Windows. Se a porta ja esta em uso, a nova instancia sai na hora." | Out-Null
Write-Host "Tarefa $nomeTarefa criada (SISTEMA, ao ligar o Windows, religa a cada 10 min se cair)." -ForegroundColor Green

# 3. firewall: so a rede local, so a porta do servidor
if (-not (Get-NetFirewallRule -DisplayName $nomeRegra -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $nomeRegra -Direction Inbound -Action Allow -Protocol TCP -LocalPort $porta `
        -RemoteAddress LocalSubnet -Profile Any | Out-Null
    Write-Host "Porta $porta liberada so para a rede local." -ForegroundColor Green
} else {
    Write-Host "Regra de firewall ja existe."
}

# 4. liga agora e confere (o servidor responde? roda como SISTEMA?)
Start-ScheduledTask -TaskName $nomeTarefa
$ok = $false
for ($i = 0; $i -lt 15; $i++) {
    Start-Sleep -Seconds 3
    try { $r = Invoke-RestMethod -Uri "http://127.0.0.1:$porta/v1/saude" -TimeoutSec 3; if ($r.ok) { $ok = $true; break } } catch { }
}
if ($ok) {
    Write-Host "Servidor central no ar em http://127.0.0.1:$porta (abas: $($r.abas))." -ForegroundColor Green
    $dono = Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'rodar_servidor_central' } | Select-Object -First 1
    if ($dono) { $q = Invoke-CimMethod -InputObject $dono -MethodName GetOwner; Write-Host "Processo do servidor roda como: $($q.Domain)\$($q.User)" }
} else {
    Write-Host "[ATENCAO] O servidor nao respondeu em 45 s. Veja a pasta logs do projeto e o Agendador de Tarefas." -ForegroundColor Yellow
}

# 5. backup diario (mesma sessao de administrador, sem pedir de novo)
& (Join-Path $PSScriptRoot "agendar_backup_servidor_central.ps1") -Elevado
if ($meuLog) { Stop-Transcript | Out-Null }
