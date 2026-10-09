# Libera no firewall do Windows a conversa entre os Painéis dos 4 PCs (porta 8766, só a rede local).
# Precisa de administrador UMA vez por PC: o Windows pergunta. Sem isso, a busca no Outlook dos outros PCs e o texto
# ao vivo não chegam (o resto do Painel funciona normal, pela planilha).
$nome = "Painel Fiscal - rede entre os PCs"
$porta = 8766
if (Get-NetFirewallRule -DisplayName $nome -ErrorAction SilentlyContinue) {
    Write-Host "       Rede entre os PCs: ja liberada."
    exit 0
}
$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Host "       Liberando a rede entre os PCs (o Windows vai pedir permissao uma vez)..."
    try {
        Start-Process powershell -Verb RunAs -Wait -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    } catch {
        Write-Host "       [AVISO] Permissao negada: a busca nos outros PCs fica desligada neste. Rode de novo quando puder."
        exit 1
    }
    if (Get-NetFirewallRule -DisplayName $nome -ErrorAction SilentlyContinue) { Write-Host "       Rede entre os PCs liberada."; exit 0 }
    exit 1
}
New-NetFirewallRule -DisplayName $nome -Direction Inbound -Action Allow -Protocol TCP -LocalPort $porta `
    -RemoteAddress LocalSubnet -Profile Any | Out-Null
Write-Host "       Rede entre os PCs liberada (porta $porta, so a rede local)."
