# Libera no firewall do Windows a conversa entre os Painéis dos 4 PCs (porta 8766, só a rede local).
# Precisa de administrador UMA vez por PC: o Windows pergunta. Sem isso, a busca no Outlook dos outros PCs e o texto
# ao vivo não chegam (o resto do Painel funciona normal, pela planilha).
# 13/10/2026: também tira os BLOQUEIOS do Python que o Windows cria quando alguém clica "Cancelar" no aviso do firewall
# (no Windows, bloqueio vence permissão: com o pythonw.exe bloqueado, a regra da porta sozinha não adianta).
# Decisão do João: vale em qualquer perfil de rede (os Wi-Fi do escritório estão como "Público"), mas SÓ para a rede local.
$nome = "Painel Fiscal - rede entre os PCs"
$porta = 8766

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole(
    [Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin) {
    Write-Host "       Liberando a rede entre os PCs (o Windows vai pedir a senha de administrador uma vez)..."
    try {
        Start-Process powershell -Verb RunAs -Wait -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    } catch {
        Write-Host "       [AVISO] Permissao negada: a busca nos outros PCs fica desligada neste. Rode de novo quando puder."
        exit 1
    }
    if (Get-NetFirewallRule -DisplayName $nome -ErrorAction SilentlyContinue) { Write-Host "       Rede entre os PCs liberada."; exit 0 }
    exit 1
}

# 1. bloqueios de entrada do Python (python.exe / pythonw.exe), e só deles
$bloqueios = Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue |
    Where-Object { $_.Program -match '\\pythonw?\.exe$' } |
    Get-NetFirewallRule | Where-Object { $_.Action -eq 'Block' -and $_.Direction -eq 'Inbound' }
foreach ($r in $bloqueios) {
    Write-Host "       Tirando bloqueio do firewall: $($r.DisplayName) ($($r.Profile))"
    Remove-NetFirewallRule -Name $r.Name
}

# 2. a regra da porta 8766, só para a rede local
if (-not (Get-NetFirewallRule -DisplayName $nome -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -DisplayName $nome -Direction Inbound -Action Allow -Protocol TCP -LocalPort $porta `
        -RemoteAddress LocalSubnet -Profile Any | Out-Null
}

# 3. conferência
$regra = Get-NetFirewallRule -DisplayName $nome -ErrorAction SilentlyContinue
$restam = Get-NetFirewallApplicationFilter -ErrorAction SilentlyContinue | Where-Object { $_.Program -match '\\pythonw?\.exe$' } |
    Get-NetFirewallRule | Where-Object { $_.Action -eq 'Block' -and $_.Direction -eq 'Inbound' }
if ($regra -and -not $restam) {
    Write-Host "       OK: rede entre os PCs liberada (porta $porta, so a rede local) e nenhum bloqueio do Python."
    exit 0
}
Write-Host "       [AVISO] Algo ficou faltando: regra=$([bool]$regra), bloqueios restantes=$(@($restam).Count)."
exit 1
