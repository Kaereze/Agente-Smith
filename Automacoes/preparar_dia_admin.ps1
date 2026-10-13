# Dia do administrador (usuário, 13/10/2026): abre uma janela do PowerShell com o comando do firewall JÁ DIGITADO,
# sem executar. Quem tem a senha só aperta Enter e confirma a senha de administrador quando o Windows pedir.
# Roda como usuário comum (não pede senha); o liberar_rede.ps1 é que pede a elevação.
# caminho curto e sem acento: a janela abre na pasta do projeto (caminho longo com "Usuário" quebrava o desenho da linha)
$projeto = Split-Path $PSScriptRoot -Parent
$cmd = "powershell -NoProfile -ExecutionPolicy Bypass -File .\Automacoes\liberar_rede.ps1"
$cmdEsc = $cmd.Replace("'", "''")
$boot = @"
`$host.UI.RawUI.WindowTitle = 'Dia do administrador - aperte Enter'
Write-Host ''
Write-Host '  Dia do administrador - Painel Fiscal' -ForegroundColor Cyan
Write-Host '  O comando abaixo libera a rede entre os PCs (porta 8766, so a rede local) e tira os bloqueios do Python.'
Write-Host '  Aperte ENTER e confirme a senha de administrador quando o Windows pedir.' -ForegroundColor Yellow
Write-Host ''
`$null = Register-EngineEvent -SourceIdentifier PowerShell.OnIdle -MaxTriggerCount 1 -Action {
    [Microsoft.PowerShell.PSConsoleReadLine]::RevertLine()
    [Microsoft.PowerShell.PSConsoleReadLine]::Insert('$cmdEsc')
    [Microsoft.PowerShell.PSConsoleReadLine]::InvokePrompt()
}
"@
$b64 = [Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($boot))
Start-Process powershell -WorkingDirectory $projeto -ArgumentList "-NoExit -NoProfile -ExecutionPolicy Bypass -EncodedCommand $b64"
Write-Host "Janela do Dia do administrador aberta com o comando pronto (nao executado)."
