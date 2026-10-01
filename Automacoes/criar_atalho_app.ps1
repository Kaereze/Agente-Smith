# SOLICITACOES NF - atalho "Painel Notas Fiscais" na Area de Trabalho para abrir o app
$projeto = Split-Path -Parent $PSScriptRoot
$desktop = [Environment]::GetFolderPath("Desktop")
Remove-Item (Join-Path $desktop "Solicitacoes NF.lnk") -ErrorAction SilentlyContinue   # nome da versao de teste
$shell = New-Object -ComObject WScript.Shell
$atalho = $shell.CreateShortcut((Join-Path $desktop "Painel Notas Fiscais.lnk"))
$atalho.TargetPath = Join-Path $projeto ".venv\Scripts\pythonw.exe"
$atalho.Arguments = '"' + (Join-Path $projeto "src\app_servidor.py") + '"'
$atalho.WorkingDirectory = $projeto
$atalho.IconLocation = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe,0"
$atalho.Description = "Painel Notas Fiscais - fila de solicitacoes sincronizada pela Planilha Central"
$atalho.Save()
Write-Host "Atalho criado na Area de Trabalho: Painel Notas Fiscais"
