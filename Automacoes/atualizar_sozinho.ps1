# SOLICITACOES NF - atualiza este PC pelo GitHub sem ninguem clicar (chamado pelo Painel: src\atualizador.py)
# git pull so pra frente -> bibliotecas -> reinicia conferente e Painel com a versao nova.
# Nao pergunta nada (roda escondido). O resultado fica em logs\atualizacao.log.
$pasta = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $pasta
$log = Join-Path $pasta "logs\atualizacao.log"
New-Item -ItemType Directory -Force (Join-Path $pasta "logs") | Out-Null
function Registrar($texto) { Add-Content -Path $log -Value ("{0:dd/MM/yyyy HH:mm:ss} {1}" -f (Get-Date), $texto) -Encoding UTF8 }

Start-Sleep -Seconds 3   # deixa o Painel responder antes de ser reiniciado
Registrar "inicio (versao $(git log -1 --format=%h))"
$saida = git pull --ff-only 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) { Registrar "git pull falhou: $saida"; exit 1 }
Registrar "git pull: $($saida.Trim())"

$venvPy = Join-Path $pasta ".venv\Scripts\python.exe"
& $venvPy -m pip install -q --disable-pip-version-check -r requirements.txt 2>&1 | Out-Null
Registrar "bibliotecas conferidas"

Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -like "*$pasta*" -and ($_.CommandLine -match 'conferente|app_servidor') } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
foreach ($t in @("SolicitacoesNF_Conferente", "SolicitacoesNF_Painel")) {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) { Start-ScheduledTask -TaskName $t }
}
Registrar "reiniciado na versao $(git log -1 --format=%h)"
