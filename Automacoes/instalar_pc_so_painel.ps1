# PAINEL FISCAL - INSTALADOR DO PC "SO PAINEL" (sem Outlook, sem caixas de hotel)
# Para um PC novo que so olha o Painel, emite e PEDE o envio: quem envia o e-mail e o PC dono da caixa.
# Nao agenda conferente nem copia de planilhas (isso e dos PCs com Outlook).
# Uso: INSTALAR_PC_SO_PAINEL.bat -Operador Ingrid     (-SoConferir = so verifica e testa, nao liga nada)
# Nenhuma senha, chave ou segredo mora neste arquivo: ele so confere se os arquivos estao no lugar.
param([string]$Operador = "", [switch]$SoConferir)

$PY_VERSAO = "3.14.6"
$PY_URL = "https://www.python.org/ftp/python/$PY_VERSAO/python-$PY_VERSAO-amd64.exe"
$pasta = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$env:PYTHONIOENCODING = "utf-8"
$TOTAL = 10

function Passo($n, $texto) { Write-Host ""; Write-Host "[$n/$TOTAL] $texto" -ForegroundColor Cyan }
function Ok($texto) { Write-Host "   OK  $texto" -ForegroundColor Green }
function Aviso($texto) { Write-Host "   --  $texto" -ForegroundColor Yellow }
function Falha($texto) { Write-Host "   !!  $texto" -ForegroundColor Red; Read-Host "Aperte Enter pra fechar"; exit 1 }
function Recarregar-Path {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
}
function Tem-Winget { [bool](Get-Command winget -ErrorAction SilentlyContinue) }
function Achar-Python {
    Recarregar-Path
    $candidatos = @()
    if (Get-Command py -ErrorAction SilentlyContinue) { $candidatos += (& py -3.14 -c "import sys;print(sys.executable)" 2>$null) }
    $candidatos += @("$env:LOCALAPPDATA\Python\pythoncore-3.14-64\python.exe", "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe",
                     "$env:ProgramFiles\Python314\python.exe")
    if (Get-Command python -ErrorAction SilentlyContinue) { $candidatos += (Get-Command python).Source }
    foreach ($c in $candidatos) {
        if ($c -and (Test-Path $c) -and ($c -notlike "*WindowsApps*")) {
            $v = & $c -c "import sys;print(sys.version_info[:2] >= (3,12))" 2>$null
            if ($v -eq "True") { return $c }
        }
    }
    return $null
}

Write-Host "============ PAINEL FISCAL - INSTALAR PC SO PAINEL ============" -ForegroundColor Cyan
if (-not (Test-Path (Join-Path $pasta "src\app_servidor.py"))) {
    Falha "Rode este instalador de dentro da pasta do projeto (Solicitacoes NF). Veja o guia: 'Instalar um PC novo (so Painel)'."
}
if (-not $Operador) { $Operador = (Read-Host "   Nome do operador deste PC (como aparece no Painel, ex.: Ingrid)").Trim() }
if (-not $Operador) { Falha "Preciso do nome do operador." }

# 1. Python
Passo 1 "Python $PY_VERSAO"
$python = Achar-Python
if (-not $python) {
    if (Tem-Winget) {
        Aviso "Python nao encontrado - instalando pelo winget..."
        winget install -e --id Python.Python.3.14 --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Null
        $python = Achar-Python
    }
    if (-not $python) {
        Aviso "Baixando o instalador do python.org..."
        $exe = Join-Path $env:TEMP "python-$PY_VERSAO-amd64.exe"
        Invoke-WebRequest $PY_URL -OutFile $exe -UseBasicParsing
        Start-Process $exe -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0" -Wait
        $python = Achar-Python
    }
    if (-not $python) { Falha "Nao consegui instalar o Python. Instale em python.org (marque 'Add to PATH') e rode de novo." }
}
Ok $python

# 2. Git
Passo 2 "Git"
Recarregar-Path
if (-not (Get-Command git -ErrorAction SilentlyContinue) -and (Tem-Winget)) {
    Aviso "Git nao encontrado - instalando pelo winget..."
    winget install -e --id Git.Git --silent --accept-package-agreements --accept-source-agreements | Out-Null
    Recarregar-Path
}
$temGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
if ($temGit) { Ok (git --version) } else { Falha "Sem Git nao ha como receber as atualizacoes do Painel. Instale o Git (git-scm.com) e rode de novo." }

# 3. Projeto: versao mais nova do GitHub
Passo 3 "Projeto (versao mais nova do GitHub)"
Set-Location $pasta
if (-not (Test-Path (Join-Path $pasta ".git"))) { Falha "Esta pasta nao veio do GitHub (nao achei .git). Baixe o projeto com 'git clone' como diz o guia." }
git pull --ff-only
if ($LASTEXITCODE -ne 0) { Aviso "Nao consegui atualizar agora (sem acesso ao GitHub? conta sem convite?). Sigo com a versao desta pasta." }
Ok (git log -1 --format="Versao: %h - %s")

# 4. .venv + bibliotecas (criado AQUI; nunca copiado de outro PC)
Passo 4 "Ambiente .venv e bibliotecas"
$venvPy = Join-Path $pasta ".venv\Scripts\python.exe"
if ((Test-Path $venvPy) -and -not (& $venvPy -c "print('ok')" 2>$null)) {
    Aviso ".venv quebrado - recriando"
    Remove-Item (Join-Path $pasta ".venv") -Recurse -Force -Confirm:$false
}
if (-not (Test-Path $venvPy)) { & $python -m venv (Join-Path $pasta ".venv") }
if (-not (Test-Path $venvPy)) { Falha "Nao consegui criar o .venv" }
& $venvPy -m pip install -q --disable-pip-version-check --upgrade pip | Out-Null
& $venvPy -m pip install -q --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { Falha "Instalacao das bibliotecas falhou (sem internet?)" }
Ok "Bibliotecas instaladas"

# 5. Chave do Google e segredo da rede (arquivos que VOCE coloca; este instalador nunca os mostra nem os guarda)
Passo 5 "Chave do Google e segredo da rede"
$chaveDir = Join-Path $env:APPDATA "SolicitacoesNF"
$chave = Join-Path $chaveDir "chave-api.json"
$segredo = Join-Path $chaveDir "segredo-rede.txt"
New-Item -ItemType Directory -Force $chaveDir | Out-Null
if (-not (Test-Path $chave) -or -not (Test-Path $segredo)) {
    Aviso "Faltam arquivos. Abrindo a pasta: cole nela o chave-api.json e o segredo-rede.txt (renomeie se precisar)."
    Start-Process explorer.exe $chaveDir
    Read-Host "   Depois de colar, aperte Enter"
}
if (-not (Test-Path $chave)) { Falha "Ainda nao achei $chave" }
Ok "chave-api.json no lugar"
if (Test-Path $segredo) { Ok "segredo-rede.txt no lugar" } else { Aviso "Sem segredo-rede.txt: o Painel abre, mas pesquisa e texto de e-mails dos outros PCs nao chegam." }

# 6. Configuracao deste PC: so Painel, sem Outlook
Passo 6 "Configuracao deste PC (so Painel, sem Outlook)"
& $venvPy (Join-Path $pasta "Automacoes\configurar_pc_so_painel.py") $Operador
if ($LASTEXITCODE -ne 0) { Falha "Nao consegui gravar a configuracao deste PC." }

# 7. WebView2 (motor da janela do Painel)
Passo 7 "WebView2 (janela do Painel)"
$wv = Get-ItemProperty "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" -ErrorAction SilentlyContinue
if (-not $wv) { $wv = Get-ItemProperty "HKCU:\Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" -ErrorAction SilentlyContinue }
if ($wv) { Ok "WebView2 instalado (versao $($wv.pv))" }
elseif (Tem-Winget) {
    Aviso "WebView2 nao encontrado - instalando pelo winget..."
    winget install -e --id Microsoft.EdgeWebView2Runtime --silent --accept-package-agreements --accept-source-agreements | Out-Null
    Ok "WebView2 instalado"
} else { Aviso "WebView2 nao encontrado. Baixe em developer.microsoft.com/microsoft-edge/webview2 (Evergreen Bootstrapper)." }

if ($SoConferir) {
    Passo 10 "Teste final (so conferencia: nada foi ligado)"
    & $venvPy (Join-Path $pasta "Automacoes\testar_pc_novo.py")
    Write-Host ""; Aviso "So conferencia (-SoConferir): firewall, tarefa e atalho nao foram mexidos."; exit 0
}

# 8. Firewall: porta 8766, so a rede local (o Windows pede permissao de administrador uma vez)
Passo 8 "Firewall (conversa entre os PCs, porta 8766, so rede local)"
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pasta "Automacoes\liberar_rede.ps1")
if ($LASTEXITCODE -ne 0) { Aviso "Nao liberou agora. Sem isso os OUTROS PCs nao falam com este. Peca a TI para liberar a porta 8766 (TCP) entre os PCs." }

# 9. Painel em segundo plano + atalho (sem conferente e sem copia de planilhas)
Passo 9 "Painel Notas Fiscais"
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -like "*$pasta*app_servidor*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pasta "Automacoes\agendar_painel.ps1") | Out-Null
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pasta "Automacoes\criar_atalho_app.ps1") | Out-Null
Ok "Painel em segundo plano (tarefa SolicitacoesNF_Painel) + atalho na Area de Trabalho"
Start-Sleep -Seconds 20

# 10. Teste final: chave, Planilha Central e os outros PCs
Passo 10 "Teste final (chave, Planilha Central e os outros PCs)"
& $venvPy (Join-Path $pasta "Automacoes\testar_pc_novo.py")

Write-Host ""
Write-Host "PRONTO. Pasta: $pasta  |  Papel: so_painel  |  Operador: $Operador" -ForegroundColor Green
Write-Host "Abra o atalho 'Painel Notas Fiscais' na Area de Trabalho."
Read-Host "Aperte Enter pra fechar"
