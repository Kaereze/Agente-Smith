# SOLICITACOES NF - reinicia conferente e Painel com o codigo que ja esta na pasta (chamado pelo
# src\atualizador.py depois do git pull). Roda solto do Painel: ele mesmo e um dos processos reiniciados.
$pasta = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$log = Join-Path $pasta "logs\atualizacao.log"
function Registrar($texto) { Add-Content -Path $log -Value ("{0:dd/MM/yyyy HH:mm:ss} {1}" -f (Get-Date), $texto) -Encoding UTF8 }

Start-Sleep -Seconds 3   # deixa o Painel responder o comando antes de cair
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -like "*$pasta*" -and ($_.CommandLine -match 'conferente|app_servidor') } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
foreach ($t in @("SolicitacoesNF_Conferente", "SolicitacoesNF_Painel")) {
    if (Get-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue) { Start-ScheduledTask -TaskName $t }
}
Registrar "reiniciado na versao $(git -C $pasta log -1 --format=%h)"
