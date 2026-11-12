# SOLICITACOES NF - CORACAO: instala OU atualiza tudo neste PC (um arquivo so)
# Python 3.14 + Git (baixa se faltar) -> projeto na Area de Trabalho -> .venv + bibliotecas
# -> chave do Google -> identidade do PC -> conferente (todo PC) / copia+envio (so no principal)
# Uso: INSTALAR_OU_ATUALIZAR.bat   (-SoConferir = so verifica, nao agenda nem reinicia nada)
# REGRA (pedido do Joao, 05/11/2026): toda seguranca nova entra aqui E em Automacoes\testar_pc_novo.py na mesma entrega.
# O passo 7 instala/libera os requisitos de seguranca e o passo 11 reconhece e verifica o PC inteiro.
param([switch]$SoConferir)

$PY_VERSAO = "3.14.6"
$PY_URL = "https://www.python.org/ftp/python/$PY_VERSAO/python-$PY_VERSAO-amd64.exe"
$pasta = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$env:PYTHONIOENCODING = "utf-8"

function Passo($n, $texto) { Write-Host ""; Write-Host "[$n/11] $texto" -ForegroundColor Cyan }
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
# Pen drive / HD externo = qualquer unidade que nao seja a do Windows, com o projeto na raiz ou em KARUZO
function Pendrive-Com-Projeto {
    Get-PSDrive -PSProvider FileSystem | Where-Object { $_.Root -ne "$env:SystemDrive\" } | ForEach-Object {
        foreach ($p in @((Join-Path $_.Root "KARUZO\Solicitacoes NF"), (Join-Path $_.Root "Solicitacoes NF"))) {
            if (Test-Path (Join-Path $p ".git")) { $p }
        }
    } | Select-Object -First 1
}

Write-Host "==================== SOLICITACOES NF - INSTALAR / ATUALIZAR ====================" -ForegroundColor Cyan

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
    if (-not $python) { Falha "Nao consegui instalar o Python. Instale manualmente em python.org (marque 'Add to PATH') e rode de novo." }
}
Ok $python

# 2. Git
Passo 2 "Git"
Recarregar-Path
if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    if (Tem-Winget) {
        Aviso "Git nao encontrado - instalando pelo winget..."
        winget install -e --id Git.Git --silent --accept-package-agreements --accept-source-agreements | Out-Null
        Recarregar-Path
    }
}
$temGit = [bool](Get-Command git -ErrorAction SilentlyContinue)
if ($temGit) { Ok (git --version) } else { Aviso "Sem Git: a instalacao funciona, mas atualizar vai ser copiando a pasta de novo." }

# 3. Projeto no lugar certo (rodando do pen drive -> vai pra Area de Trabalho) + versao nova
Passo 3 "Projeto"
$noPendrive = [IO.Path]::GetPathRoot($pasta) -ne "$env:SystemDrive\"
if ($noPendrive) {
    $destino = Join-Path ([Environment]::GetFolderPath("Desktop")) "Solicitacoes NF"
    if (Test-Path (Join-Path $destino ".git")) {
        git -C $destino pull --ff-only $pasta main
    } elseif ($temGit) {
        git clone --no-hardlinks --quiet $pasta $destino
    } else {
        robocopy $pasta $destino /E /XD .git estado logs .venv /NFL /NDL /NJH /NJS | Out-Null
    }
    Ok "Instalado em $destino (pen drive: $pasta)"
    $pendrive = $pasta
    $pasta = $destino
} else {
    $pendrive = Pendrive-Com-Projeto
    if ($pendrive -and $temGit -and (Test-Path (Join-Path $pasta ".git"))) {
        git -C $pasta pull --ff-only $pendrive main
        Ok "Atualizado com a versao do pen drive ($pendrive)"
    } elseif ($temGit -and ((git -C $pasta remote get-url origin 2>$null) -like "http*")) {
        git -C $pasta pull --ff-only
        Ok "Atualizado pelo GitHub"
    } else {
        Ok "Usando a versao desta pasta ($pasta)"
    }
}
Set-Location $pasta
if ($temGit -and (Test-Path ".git")) { Ok (git log -1 --format="Versao: %h - %s") }

# 4. .venv + bibliotecas (recria se estiver quebrado / copiado de outro PC)
Passo 4 "Ambiente .venv e bibliotecas"
$venvPy = Join-Path $pasta ".venv\Scripts\python.exe"
if ((Test-Path $venvPy) -and -not (& $venvPy -c "print('ok')" 2>$null)) {
    Aviso ".venv quebrado (copiado de outro PC?) - recriando"
    Remove-Item (Join-Path $pasta ".venv") -Recurse -Force -Confirm:$false
}
if (-not (Test-Path $venvPy)) { & $python -m venv (Join-Path $pasta ".venv") }
if (-not (Test-Path $venvPy)) { Falha "Nao consegui criar o .venv" }
& $venvPy -m pip install -q --disable-pip-version-check --upgrade pip | Out-Null
& $venvPy -m pip install -q --disable-pip-version-check -r requirements.txt
if ($LASTEXITCODE -ne 0) { Falha "Instalacao das bibliotecas falhou (sem internet?)" }
Ok "Bibliotecas instaladas"

# 5. Chave do Google (copia do pen drive se estiver la)
Passo 5 "Chave do Google"
$chaveDir = Join-Path $env:APPDATA "SolicitacoesNF"
$chave = Join-Path $chaveDir "chave-api.json"
New-Item -ItemType Directory -Force $chaveDir | Out-Null
if (-not (Test-Path $chave) -and $pendrive) {
    $noPen = @((Join-Path (Split-Path $pendrive -Parent) "chave-api.json"), (Join-Path $pendrive "chave-api.json")) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($noPen) { Copy-Item $noPen $chave; Aviso "Chave copiada do pen drive - APAGUE ela do pen drive depois." }
}
if (-not (Test-Path $chave)) {
    Aviso "Falta a chave. Abrindo a pasta: cole nela o arquivo chave-api.json."
    Start-Process explorer.exe $chaveDir
    Read-Host "   Depois de colar, aperte Enter"
    if (-not (Test-Path $chave)) { Falha "Ainda nao achei $chave" }
}
Ok $chave

# 6. Identidade do PC (Outlook x Cadastro_Hoteis)
Passo 6 "Identidade deste PC (Outlook aberto?)"
$papel = (& $venvPy -c "import sys; sys.path.insert(0,'src'); from config import carregar_config; print(carregar_config()['papel'])").Trim()
if ($papel -eq "so_painel") {
    Aviso "PC so Painel (config.local.json): nao identifico pelo Outlook (nao abre o Outlook)."
} else {
    & $venvPy src\identidade.py
    if ($LASTEXITCODE -ne 0) { Aviso "Nao identifiquei agora (Outlook fechado?). O conferente tenta de novo sozinho ao ligar." }
    $papel = (& $venvPy -c "import sys; sys.path.insert(0,'src'); from config import carregar_config; print(carregar_config()['papel'])").Trim()
}
Ok "Papel deste PC: $papel"

# 7. Seguranca: segredo da rede, biblioteca de cifra, firewall e relogio (so mexe no PC se NAO for -SoConferir)
Passo 7 "Seguranca da rede entre os PCs"
$segredoDestino = Join-Path $chaveDir "segredo-rede.txt"
if (-not (Test-Path $segredoDestino) -and $pendrive) {
    $segPen = @((Join-Path (Split-Path $pendrive -Parent) "segredo-rede.txt"), (Join-Path $pendrive "segredo-rede.txt")) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($segPen) { Copy-Item $segPen $segredoDestino; Aviso "segredo-rede.txt copiado do pen drive - APAGUE ele do pen drive depois." }
}
if (Test-Path $segredoDestino) { Ok "segredo-rede.txt no lugar (este PC fala com os outros pelo segredo proprio da rede)" }
else { Aviso "Sem segredo-rede.txt: vale o segredo derivado da chave do Google (serve se a chave for a mesma dos outros PCs)." }
& $venvPy -c "import cryptography; print('cifra ok', cryptography.__version__)"
if ($LASTEXITCODE -ne 0) { Aviso "Biblioteca de cifra ausente: o conteudo entre os PCs iria aberto. Rode este instalador de novo com internet." } else { Ok "Biblioteca de cifra instalada" }
if (-not $SoConferir) {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pasta "Automacoes\liberar_rede.ps1")
    try { & w32tm /resync /nowait | Out-Null; Ok "Pedido de acerto do relogio enviado (a rede entre os PCs exige relogio certo)" } catch { Aviso "Nao consegui pedir o acerto do relogio." }
} else { Aviso "-SoConferir: firewall e relogio so serao conferidos, nao alterados." }

function Verificar-Pc {
    Passo 11 "Reconhecer e verificar este PC (chave, rede, cifra, relogio, firewall, BitLocker, ajustes)"
    & $venvPy -W ignore (Join-Path $pasta "Automacoes\testar_pc_novo.py")
    if ($LASTEXITCODE -ne 0) { Aviso "O teste achou falhas (!!). O Painel ja esta instalado, mas resolva-as antes de usar este PC." }
}

if ($SoConferir) { Verificar-Pc; Write-Host ""; Aviso "So conferencia (-SoConferir): nada foi agendado nem reiniciado."; exit 0 }

# 7. Conferente: agenda e reinicia com a versao nova (espera o robo terminar o que estiver fazendo)
Passo 8 "Conferente (liga sozinho com o Windows)"
$i = 0; while ((Test-Path (Join-Path $pasta "estado\_execucao.lock")) -and $i -lt 60) { Start-Sleep 5; $i++ }
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -like "*$pasta*conferente*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
if ($papel -eq "so_painel") {   # so visualiza e pede envio: o conferente (e o Guardiao que reabre o Outlook) nao existe aqui
    if (Get-ScheduledTask -TaskName "SolicitacoesNF_Conferente" -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName "SolicitacoesNF_Conferente" -Confirm:$false
    }
    Aviso "Pulado: PC so Painel nao roda conferente nem abre o Outlook sozinho (tarefa removida se existia)."
} else {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pasta "Automacoes\agendar_conferente.ps1") | Out-Null
    Ok "Tarefa SolicitacoesNF_Conferente ligada"
}

# 8. Copia + envio: so no PC principal
Passo 9 "Copia das planilhas + envio"
if ($papel -eq "principal") {
    & powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pasta "Automacoes\agendar_sincronizacao.ps1") -Minutos 10 | Out-Null
    Ok "Tarefa SolicitacoesNF_CopiaHoteis (a cada 10 min)"
} else {
    Aviso "Pulado: este PC e conferente. Copia e envio rodam so no PC principal."
}

# 9. App (atalho na Area de Trabalho, todo PC)
Passo 10 "Painel Notas Fiscais"
Get-CimInstance Win32_Process -Filter "Name like 'python%'" |
    Where-Object { $_.CommandLine -like "*$pasta*app_servidor*" } |
    ForEach-Object { Stop-Process -Id $_.ProcessId -Force -Confirm:$false }
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pasta "Automacoes\agendar_painel.ps1") | Out-Null
& powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $pasta "Automacoes\criar_atalho_app.ps1") | Out-Null
Ok "Painel em segundo plano (tarefa SolicitacoesNF_Painel) + atalho na Area de Trabalho"

Verificar-Pc

Write-Host ""
Write-Host "PRONTO. Pasta: $pasta  |  Papel: $papel" -ForegroundColor Green
Read-Host "Aperte Enter pra fechar"
