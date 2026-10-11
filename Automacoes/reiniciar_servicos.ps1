# SOLICITACOES NF - reinicia conferente e Painel com o codigo que ja esta na pasta (chamado pelo
# src\atualizador.py depois do git pull, pela tarefa SolicitacoesNF_Reiniciar do Agendador do Windows).
# 11/10/2026: deixa registro do comeco e do fim em logs\atualizacao.log e segue a ordem que funcionou nos PCs:
# para as tarefas, encerra o que sobrou, religa as tarefas e confere que os processos voltaram.
$pasta = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$log = Join-Path $pasta "logs\atualizacao.log"
function Registrar($texto) { Add-Content -Path $log -Value ("{0:dd/MM/yyyy HH:mm:ss} {1}" -f (Get-Date), $texto) -Encoding UTF8 }
function Versao {
    try {
        $cabeca = (Get-Content (Join-Path $pasta ".git\HEAD") -Raw).Trim()
        if ($cabeca -notlike "ref:*") { return $cabeca.Substring(0, 7) }
        $ref = Join-Path $pasta (".git\" + $cabeca.Substring(4).Trim())
        if (Test-Path $ref) { return (Get-Content $ref -Raw).Trim().Substring(0, 7) }
    } catch { }
    return "?"
}
function Processos {
    @(Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
        Where-Object { $_.CommandLine -like "*$pasta*" -and ($_.CommandLine -match 'conferente\.py|app_servidor\.py') })
}

Registrar "reinicio: comecou (versao na pasta $(Versao))"
try {
    Start-Sleep -Seconds 3   # deixa o Painel responder o comando antes de cair
    $tarefas = @("SolicitacoesNF_Conferente", "SolicitacoesNF_Painel") |
        Where-Object { Get-ScheduledTask -TaskName $_ -ErrorAction SilentlyContinue }
    foreach ($t in $tarefas) { Stop-ScheduledTask -TaskName $t -ErrorAction SilentlyContinue }
    Processos | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false -ErrorAction SilentlyContinue }
    Start-Sleep -Seconds 2
    if ($tarefas) {
        foreach ($t in $tarefas) { Start-ScheduledTask -TaskName $t }
    } else {   # PC sem as tarefas agendadas: sobe direto
        $pythonw = Join-Path $pasta ".venv\Scripts\pythonw.exe"
        Start-Process -FilePath $pythonw -ArgumentList "`"$pasta\src\conferente.py`"" -WorkingDirectory $pasta
        Start-Process -FilePath $pythonw -ArgumentList "`"$pasta\src\app_servidor.py`" --sem-janela" -WorkingDirectory $pasta
    }
    $vivos = @()
    for ($i = 0; $i -lt 15 -and $vivos.Count -lt 2; $i++) {
        Start-Sleep -Seconds 2
        $vivos = @(Processos | ForEach-Object { if ($_.CommandLine -match 'conferente\.py') { 'conferente' } else { 'painel' } } | Sort-Object -Unique)
    }
    if ($vivos.Count -ge 2) {
        Registrar "reiniciado na versao $(Versao) (conferente e Painel no ar)"
    } else {
        Registrar "reinicio INCOMPLETO na versao $(Versao): no ar so [$($vivos -join ', ')] - a repeticao de 10 min da tarefa tenta de novo"
    }
} catch {
    Registrar "reinicio FALHOU: $($_.Exception.Message)"
}
