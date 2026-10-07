# Instalação completa, ambientes, sincronia entre PCs e pendências

Guia para deixar **qualquer PC funcionando exatamente igual ao PC do João**: robô de solicitações,
conferente e **Painel Notas Fiscais**, todos na **mesma versão** e com o **próprio ambiente Python**
criado dentro da máquina.

- Siga as seções **na ordem**.
- Os comandos são para o **PowerShell** (menu Iniciar → digite "PowerShell" → Enter).
- Copie **uma linha de comando por vez** e leia a explicação logo abaixo dela.
- O que estiver entre `< >` você troca pelo valor certo (ex.: `<letra do pendrive>` vira `E:`).

---

## Índice

1. [Visão geral: as três camadas](#1-visão-geral-as-três-camadas)
2. [Os ambientes (cada tipo de PC e cada modo do robô)](#2-os-ambientes-cada-tipo-de-pc-e-cada-modo-do-robô)
3. [O que é cada pasta e arquivo do projeto](#3-o-que-é-cada-pasta-e-arquivo-do-projeto)
4. [Pré-requisitos de cada PC (e como conferir cada um)](#4-pré-requisitos-de-cada-pc-e-como-conferir-cada-um)
5. [Instalação automática (pendrive ou GitHub)](#5-instalação-automática-pendrive-ou-github)
6. [Instalação manual, criando o próprio ambiente `.venv`](#6-instalação-manual-criando-o-próprio-ambiente-venv)
7. [A chave do Google](#7-a-chave-do-google)
8. [O `config.json`, chave por chave, e o `config.local.json`](#8-o-configjson-chave-por-chave-e-o-configlocaljson)
9. [Tarefas do Windows](#9-tarefas-do-windows)
10. [Conferir se o PC ficou igual ao do João](#10-conferir-se-o-pc-ficou-igual-ao-do-joão)
11. [A regra de ouro da sincronia](#11-a-regra-de-ouro-da-sincronia)
12. [Passar uma alteração para TODOS os PCs](#12-passar-uma-alteração-para-todos-os-pcs)
13. [PC de casa (só para editar código e design)](#13-pc-de-casa-só-para-editar-código-e-design)
14. [Os atalhos `.bat`](#14-os-atalhos-bat)
15. [Logs: onde olhar quando algo parece errado](#15-logs-onde-olhar-quando-algo-parece-errado)
16. [Erros comuns e como resolver](#16-erros-comuns-e-como-resolver)
17. [Trocar o PC principal ou formatar um PC](#17-trocar-o-pc-principal-ou-formatar-um-pc)
18. [O que NUNCA vai para o GitHub nem para o pendrive](#18-o-que-nunca-vai-para-o-github-nem-para-o-pendrive)
19. [Cola de comandos úteis](#19-cola-de-comandos-úteis)
20. [Pendências](#20-pendências)

---

## 1. Visão geral: as três camadas

```text
 Hóspede preenche o Google Forms do hotel
                │
                ▼
 Planilha do hotel (Drive) ──► robô do PC PRINCIPAL copia ──► PLANILHA CENTRAL (Google Sheets)
                                                                 ▲        ▲        ▲
                                         lê/grava em tempo real  │        │        │
                                      ┌──────────────────────────┘        │        └───────────────┐
                                PC do João                         PC da Clara               PC do Cristian ...
                          (principal: copia, envia,          (conferente + Painel)      (conferente + Painel)
                           conferente + Painel)
```

O que precisa ficar igual em todos os PCs se divide em três camadas:

| Camada | O quê | Onde fica | Como fica igual nos PCs |
|---|---|---|---|
| **Dados** | Solicitações, quem assumiu, NFs, tratativas, fila de envio de NF, PCs ligados | **Planilha Central** (Google Sheets) | **Sozinho, em tempo real.** Todo PC lê e grava na mesma planilha. Nada para copiar. |
| **Código** | Robô, conferente, Painel (pastas `src\`, `app_ui\`, `Bat\`, `Automacoes\`, `config.json`) | Pasta `Solicitacoes NF` de cada PC | **Você atualiza**: muda num lugar só, sobe pelo git e roda o `INSTALAR_OU_ATUALIZAR.bat` em cada PC (seção 12). |
| **Ambiente** | Python, `.venv`, bibliotecas, chave, Outlook, Dropbox, tarefas do Windows | **Cada PC tem o seu** | **Criado dentro de cada máquina** (seções 5 e 6). **Nunca é copiado** de um PC para outro. |

**O que é de cada PC e nunca viaja no GitHub nem no pendrive do código:**

| Item | Onde fica | Por que não viaja |
|---|---|---|
| Ambiente Python **`.venv`** | `Solicitacoes NF\.venv\` | Guarda caminhos do Python **daquele** PC. Copiado para outro PC, quebra. |
| **Chave do Google** | `%APPDATA%\SolicitacoesNF\chave-api.json` | Dá acesso às planilhas. É a mesma em todos os PCs, mas é copiada **à mão**. |
| Pasta **`estado\`** | `Solicitacoes NF\estado\` | Memória do robô naquele PC, com dados de hóspedes (nome, CPF, e-mail). |
| Pasta **`logs\`** | `Solicitacoes NF\logs\` | Registro do que aconteceu **naquele** PC. |
| **`config.local.json`** | `Solicitacoes NF\config.local.json` | Ajustes que valem **só** para aquele PC. |
| **Outlook** com as caixas e assinaturas | Perfil do Outlook do usuário | Cada operador tem as caixas dos seus hotéis. |
| **Dropbox** | `%USERPROFILE%\REDE ANDRADE Dropbox\` | Sincronizado pelo próprio Dropbox. |
| **Tarefas do Windows** | Agendador de Tarefas | Criadas pelo instalador em cada PC (seção 9). |

---

## 2. Os ambientes (cada tipo de PC e cada modo do robô)

### 2.1 Os três tipos de PC

| Ambiente | Qual PC | O que roda | Instalação |
|---|---|---|---|
| **Principal** | **Só um**: o do agente em `"agente_principal"` no `config.json` (hoje **João**) | Cópia das planilhas dos hotéis para a Central, envio do e-mail consolidado aos hotéis, menu da planilha, conferente e Painel | Seção 5 ou 6, completa |
| **Conferente** | Todos os outros operadores (Clara, Cristian, Bernardo) | Conferente (marca NF enviada / tratativa, confirma NFs) e Painel (fila, envio de NF ao hóspede) | Seção 5 ou 6, completa |
| **Desenvolvimento** | PC de casa ou qualquer PC onde só se edita código e design | Só o Painel, aberto à mão. Nenhuma tarefa agendada. | **Seção 13** (só o ambiente `.venv`, sem o instalador) |

O papel **principal** ou **conferente** é descoberto **sozinho**: o instalador lê as caixas do Outlook do PC
e compara com a coluna C (agente) da aba `Cadastro_Hoteis` da Central. O resultado fica em `estado\maquina.json`.

> ⚠️ **Nunca deixe dois PCs como principal.** A proteção contra envio repetido fica na pasta `estado\`
> de cada PC. Com dois principais, os hotéis podem receber o e-mail consolidado em dobro.

### 2.2 Os três modos do robô (`"modo"` no `config.json`)

| Modo | O que acontece | Quando usar |
|---|---|---|
| `PRODUCAO` | Envia de verdade aos hotéis e marca `Enviado = TRUE` | **Normal**, é o que está configurado hoje |
| `TESTE` | Envia tudo **só** para o `email_teste` | Testar uma mudança no e-mail sem incomodar os hotéis |
| `SIMULACAO` | **Não envia nada**: só gera os e-mails em `saida_simulacao\` | Ver como ficaria, sem nenhum risco |

> O modo vale para o **robô de envio aos hotéis**. O conferente e o Painel não mudam de comportamento.
> Para mudar o modo **só num PC**, use o `config.local.json` (seção 8.3). Assim não muda para todos.

---

## 3. O que é cada pasta e arquivo do projeto

```text
Solicitacoes NF\
├── INSTALAR_OU_ATUALIZAR.bat   ← duplo clique: instala OU atualiza tudo neste PC (o "coração")
├── INSTALACAO_E_PENDENCIAS.md  ← este guia
├── README.md                   ← visão técnica do robô (fluxo, garantias)
├── config.json                 ← configuração igual para todos os PCs (vai no git)
├── config.local.json           ← (opcional) ajustes só deste PC (NÃO vai no git)
├── requirements.txt            ← lista exata das bibliotecas Python e versões
├── robo.py                     ← envio manual (usado pelo Bat\executar_robo.bat)
├── .gitignore                  ← o que o git nunca sobe (estado, logs, .venv...)
├── .venv\                      ← AMBIENTE PYTHON deste PC (criado aqui, nunca copiado)
├── src\                        ← código Python
│   ├── main.py                 robô de envio aos hotéis
│   ├── sincronizar.py          cópia das planilhas dos hotéis → Central
│   ├── conferente.py           processo sempre ligado (NF enviada / tratativa)
│   ├── confirmar_nfs.py        confirma NFs pelo e-mail e pelo Dropbox
│   ├── identidade.py           descobre de quem é este PC (Outlook × Cadastro_Hoteis)
│   ├── config.py               lê o config.json + config.local.json
│   ├── app_servidor.py         servidor do Painel (porta 8765, roda escondido)
│   ├── app_janela.py           janela do Painel (o atalho da Área de Trabalho abre este)
│   ├── app_dados.py            fila, assumir, NF, tratativa (eventos na Central)
│   ├── app_envio.py            botão "Enviar pendentes"
│   ├── envio_nf.py             enviar NF ao hóspede (inclusive por outro PC)
│   ├── fiscal_intelligence.py  leitura do Mail Analytics (Visão geral / Hotéis)
│   ├── painel_metricas.py      números e gráficos do Painel
│   └── ...                     sheets.py, outlook.py, montar_email.py, hoteis.py, tratamento.py etc.
├── app_ui\                     ← tela do Painel: index.html (CSS/cores), painel.js, graficos.js, ícones
├── apps_script\                ← menu da Planilha Central (colado uma vez no Apps Script da planilha)
├── Bat\                        ← atalhos de duplo clique (seção 14)
├── Automacoes\                 ← scripts PowerShell: agendar tarefas, atalho, pacote do pendrive, OCR
├── testes\                     ← testes automáticos (não usam Google nem Outlook de verdade)
├── estado\                     ← memória do robô deste PC (NÃO vai no git, NÃO apagar)
├── logs\                       ← registros deste PC (NÃO vai no git)
└── saida_simulacao\            ← e-mails gerados no modo SIMULACAO (NÃO vai no git)
```

---

## 4. Pré-requisitos de cada PC (e como conferir cada um)

Confira **cada linha** no PC novo **antes** de instalar.

| # | Requisito | Como conferir | Se faltar |
|---|---|---|---|
| 1 | **Windows 10 ou 11**, 64 bits | Iniciar → "Sobre o seu PC" → "Tipo de sistema: 64 bits" | O projeto não roda em 32 bits |
| 2 | **Usuário do operador logado** | É o usuário que abre o Outlook dele | As tarefas só rodam com alguém logado (o Outlook exige) |
| 3 | **Outlook clássico** (Office), **não** o "Novo Outlook" | No Outlook: menu **Arquivo** existe e, no topo, a chave "Novo Outlook" está **desligada** | Desligue a chave "Novo Outlook". O robô usa automação que o Novo Outlook não tem. |
| 4 | **Todas as caixas dos hotéis** do operador no Outlook | Painel de pastas à esquerda: uma caixa `notafiscal@...` por hotel | Adicione as contas no Outlook (Arquivo → Adicionar Conta) |
| 5 | **Uma assinatura por caixa** | Arquivo → Opções → Email → Assinaturas: uma assinatura vinculada a cada conta | Crie. O Painel envia a NF com a assinatura da caixa e a mensagem padrão. |
| 6 | **Dropbox** logado, sincronizando `Notas Fiscais Hóspedes` | Abra `%USERPROFILE%\REDE ANDRADE Dropbox\Guilherme Heisler\FINANCEIRO ANDRADE HOTEIS\Financeiro sede\Notas Fiscais Hóspedes\` no Explorador | Instale/entre no Dropbox. Se a pasta estiver em outro lugar, veja a seção 8.3. |
| 7 | Operador cadastrado no **`Cadastro_Hoteis`** | Planilha Central → aba `Cadastro_Hoteis` → coluna C com o nome dele nos hotéis das caixas dele | Preencha a coluna C. Sem isso o PC não se identifica. |
| 8 | **Internet** | Abrir qualquer site | O instalador baixa Python, Git e bibliotecas |
| 9 | **`chave-api.json`** à mão | Num pendrive ou copiada do PC do João (`%APPDATA%\SolicitacoesNF\`) | Seção 7 (inclusive como gerar uma nova) |
| 10 | **WebView2** (motor da janela do Painel) | Comando abaixo | Já vem no Windows 11. No Windows 10, baixe em developer.microsoft.com/microsoft-edge/webview2 ("Evergreen Bootstrapper"). |
| 11 | Acesso ao **código** | Pendrive gerado pelo João **ou** conta do GitHub com acesso ao repositório **privado** | Seção 5 |

**Conferir o WebView2 (item 10):**

```powershell
Get-ItemProperty "HKLM:\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}" -ErrorAction SilentlyContinue | Select-Object pv
```

- Mostrou um número (ex.: `pv 130.0.2849.80`): está instalado.
- Não mostrou nada: instale pelo link da tabela.

**Python e Git não precisam estar instalados antes**: o instalador automático (seção 5) baixa os dois.
Na instalação manual (seção 6) você instala os dois no começo.

---

## 5. Instalação automática (pendrive ou GitHub)

É o jeito **recomendado**: um duplo clique faz tudo, incluindo **criar o ambiente `.venv` dentro do PC**.
Se preferir fazer cada passo à mão e entender cada linha, use a **seção 6**. O resultado é o mesmo.

### 5.1 O que o `INSTALAR_OU_ATUALIZAR.bat` faz (os 9 passos)

| Passo | O que faz | Detalhe |
|---|---|---|
| 1 | **Python 3.14** | Procura um Python 3.12 ou mais novo. Se não achar, instala o 3.14.6 pelo `winget` ou baixa do python.org. |
| 2 | **Git** | Se faltar, instala pelo `winget`. Sem Git a instalação funciona, mas as atualizações ficam manuais. |
| 3 | **Projeto** | Rodando do pendrive: copia para `Área de Trabalho\Solicitacoes NF`. Já instalado: pega a versão nova (pendrive conectado ou GitHub). |
| 4 | **Ambiente `.venv` + bibliotecas** | **Cria o `.venv` dentro deste PC** e instala as bibliotecas do `requirements.txt`. Se o `.venv` estiver quebrado, apaga e recria. |
| 5 | **Chave do Google** | Copia do pendrive, se estiver lá. Senão **abre a pasta** para você colar o `chave-api.json`. |
| 6 | **Identidade do PC** | Roda `src\identidade.py` (Outlook × `Cadastro_Hoteis`) e mostra o papel: `principal` ou `conferente`. |
| 7 | **Conferente** | Para o conferente antigo e agenda a tarefa `SolicitacoesNF_Conferente` com a versão nova. |
| 8 | **Cópia + envio** | **Só no principal**: agenda `SolicitacoesNF_CopiaHoteis` (a cada 30 min). |
| 9 | **Painel** | Agenda `SolicitacoesNF_Painel` (segundo plano) e cria o atalho **Painel Notas Fiscais** na Área de Trabalho. |

### 5.2 Pelo pendrive (não precisa de conta no GitHub)

**No PC do João:**

1. Garanta que tudo está salvo no git (seção 12, passo 1).
2. Conecte o pendrive.
3. Dê duplo clique em **`Bat\gerar_pacote_pendrive.bat`**.
4. Ele cria ou atualiza `<letra do pendrive>:\KARUZO\Solicitacoes NF`, sem `estado\`, `logs\` nem `.venv\`.
5. Quando perguntar *"Levar a chave do Google junto?"*:
   - **s**: o PC novo instala sem pedir nada;
   - **n**: você cola a chave à mão no passo 5 do instalador.
6. No fim aparece `PRONTO: E:\KARUZO\Solicitacoes NF` e a versão (ex.: `Versao: 13c8cfd - ...`). **Anote a versão.**

**No PC novo:**

1. Abra o **Outlook** e espere carregar **todas** as caixas.
2. Conecte o pendrive.
3. Dê duplo clique em **`<letra do pendrive>:\KARUZO\Solicitacoes NF\INSTALAR_OU_ATUALIZAR.bat`**.
4. Se o Windows perguntar se permite, clique **Sim / Executar assim mesmo**.
5. Acompanhe os 9 passos (tabela 5.1). Linhas **verdes** = ok, **amarelas** = aviso, **vermelhas** = parou.
6. Tem que terminar com **`PRONTO. Pasta: ...\Desktop\Solicitacoes NF | Papel: conferente`**
   (ou `principal` no PC do João).
7. **Apague o `chave-api.json` do pendrive**, se ele foi junto.
8. Faça a conferência da **seção 10**.

### 5.3 Pelo GitHub

**Uma vez só, no GitHub (conta Kaereze):**

1. Abra o repositório `Kaereze/Notas-Fiscais`.
2. **Settings → Collaborators → Add people**.
3. Convide a conta do GitHub do operador. Ele aceita o convite no e-mail.
   (Ou faça o login com a sua conta no PC dele.)

**No PC novo:**

```powershell
winget install -e --id Git.Git
```

Instala o Git. Depois **feche e abra o PowerShell** para ele passar a reconhecer o comando `git`.

```powershell
git clone https://github.com/Kaereze/Notas-Fiscais.git "$env:USERPROFILE\Desktop\Solicitacoes NF"
```

- Baixa o código para `Área de Trabalho\Solicitacoes NF`.
- `$env:USERPROFILE` é a pasta do usuário (ex.: `C:\Users\Cristian`).
- Na primeira vez abre uma janela de **login do GitHub**: entre com a conta que tem acesso.

Depois:

1. Abra o **Outlook** e espere carregar.
2. Dê duplo clique em **`Área de Trabalho\Solicitacoes NF\INSTALAR_OU_ATUALIZAR.bat`**.
3. No passo 5 ele abre uma pasta: **cole o `chave-api.json`** nela e aperte Enter na janela do instalador.
4. Tem que terminar com **`PRONTO. ... | Papel: conferente`**.
5. Faça a conferência da **seção 10**.

---

## 6. Instalação manual, criando o próprio ambiente `.venv`

Use esta seção se:

- quiser **entender e fazer cada passo à mão**;
- o instalador automático falhar num passo;
- precisar **recriar o ambiente** de um PC.

> **Sobre o nome do ambiente:** o ambiente Python do projeto é a pasta **`.venv`** (com **v**:
> *virtual environment*, "ambiente virtual"). É dentro dela que fica o Python e as bibliotecas **só deste projeto**,
> separados de qualquer outro Python do PC.
>
> **O projeto não usa arquivo `.env`.** Em muitos projetos o `.env` guarda senhas. Aqui o único segredo é a
> **chave do Google**, e ela fica **fora** da pasta do projeto, em `%APPDATA%\SolicitacoesNF\chave-api.json`
> (seção 7). Assim ela nunca vai parar no GitHub por engano.
>
> **Cada PC cria o seu próprio `.venv`.** Nunca copie a pasta `.venv` de um PC para outro: ela guarda o caminho
> do Python do PC onde foi criada e quebra em outra máquina.

### 6.1 Instalar o Python 3.14

```powershell
winget install -e --id Python.Python.3.14 --scope user
```

- Instala o Python 3.14 **só para este usuário** (não precisa de administrador).
- Sem `winget`: baixe em **python.org/downloads**, rode o instalador e **marque "Add python.exe to PATH"**.
- Depois **feche e abra o PowerShell**.

```powershell
py -3.14 --version
```

- Tem que responder `Python 3.14.x`.
- `py` é o "lançador" do Python no Windows: com `-3.14` ele escolhe essa versão, mesmo havendo outras.
- Se der erro `py não é reconhecido`, use o caminho completo:
  `& "$env:LOCALAPPDATA\Programs\Python\Python314\python.exe" --version`.

### 6.2 Instalar o Git

```powershell
winget install -e --id Git.Git
```

Feche e abra o PowerShell. Depois confira:

```powershell
git --version
```

Tem que responder `git version 2.x`.

### 6.3 Baixar o código

**Pelo GitHub:**

```powershell
git clone https://github.com/Kaereze/Notas-Fiscais.git "$env:USERPROFILE\Desktop\Solicitacoes NF"
```

**Ou pelo pendrive** (gerado pelo `Bat\gerar_pacote_pendrive.bat` no PC do João):

```powershell
git clone --no-hardlinks "<letra do pendrive>:\KARUZO\Solicitacoes NF" "$env:USERPROFILE\Desktop\Solicitacoes NF"
```

Depois, entre na pasta. **Todos os próximos comandos são rodados de dentro dela:**

```powershell
cd "$env:USERPROFILE\Desktop\Solicitacoes NF"
```

### 6.4 Criar o ambiente `.venv` dentro do PC

```powershell
py -3.14 -m venv .venv
```

- `-m venv` é o módulo do Python que cria ambientes virtuais.
- `.venv` é o nome da pasta que ele cria aqui dentro.
- Leva uns segundos. No fim existe a pasta `.venv\` com:
  - `Scripts\python.exe`: o Python do ambiente, com janela;
  - `Scripts\pythonw.exe`: o mesmo Python sem janela, usado pelas tarefas;
  - `Lib\site-packages\`: onde as bibliotecas vão ficar.

```powershell
.\.venv\Scripts\python.exe --version
```

Confere se o ambiente nasceu certo: tem que responder `Python 3.14.x`.

### 6.5 Usar o ambiente (com ou sem "ativar")

O projeto **sempre chama o Python do ambiente pelo caminho completo**: `.venv\Scripts\python.exe`.
Os `.bat` e as tarefas fazem isso. Então **não é obrigatório ativar** o ambiente.

Se quiser ativar, para digitar só `python` em vez do caminho:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
```

Permite rodar scripts do PowerShell criados localmente. Precisa só **uma vez** por usuário. Responda `S`.

```powershell
.\.venv\Scripts\Activate.ps1
```

- Ativa o ambiente: aparece `(.venv)` no começo da linha.
- A partir daí, `python` e `pip` são os do ambiente.
- Para sair: `deactivate`.

> Neste guia os comandos usam o caminho completo `.\.venv\Scripts\python.exe`, que funciona **com ou sem** ativar.

### 6.6 Instalar as bibliotecas

```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
```

Atualiza o `pip`, o instalador de bibliotecas, dentro do ambiente.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Instala **as versões exatas** do `requirements.txt`. Versões iguais em todos os PCs = comportamento igual.
Leva de 1 a 3 minutos. As bibliotecas e para que cada uma serve:

| Biblioteca | Versão | Para que serve no projeto |
|---|---|---|
| `pywin32` | 312 | Conversa com o **Outlook** (ler caixas, enviar, Itens Enviados) e com o Windows |
| `gspread` | 6.2.1 | Lê e grava no **Google Sheets** (Central, planilhas dos hotéis, Fiscal Intelligence) |
| `google-auth` | 2.57.0 | Faz o login no Google com a **chave da conta de serviço** |
| `pypdf` | 6.16.2 | Lê o texto dos **PDFs das NFs** (conferir número, CNPJ, nome) |
| `pytest` | 9.1.1 | Roda os **testes automáticos** |
| `pywebview` | 6.2.1 | Abre a **janela própria do Painel** (traz junto o `pythonnet`, que liga o Python ao WebView2) |

As outras bibliotecas que aparecem no `pip list` (`requests`, `cryptography`, `pythonnet`, `bottle`...) são
**dependências** dessas seis: o `pip` instala sozinho.

### 6.7 Conferir o ambiente

```powershell
.\.venv\Scripts\python.exe -c "import win32com.client, gspread, google.auth, pypdf, webview; print('ambiente ok')"
```

Importa todas as bibliotecas principais. Tem que imprimir **`ambiente ok`**.
Se der `ModuleNotFoundError: No module named 'x'`, repita o passo 6.6.

```powershell
$env:PYTHONIOENCODING = "utf-8"
```

- Faz o PowerShell aceitar os emojis (✅ ⚠️ ❌) que o robô escreve.
- Vale **só para esta janela** do PowerShell.
- Sem isso, rodar o Python à mão pode dar `UnicodeEncodeError: 'charmap' codec`.
- Os `.bat` e as tarefas já fazem isso sozinhos.

### 6.8 Colocar a chave do Google

```powershell
New-Item -ItemType Directory -Force "$env:APPDATA\SolicitacoesNF"
```

Cria a pasta da chave (`C:\Users\<usuário>\AppData\Roaming\SolicitacoesNF`), se ainda não existir.

```powershell
Copy-Item "<letra do pendrive>:\chave-api.json" "$env:APPDATA\SolicitacoesNF\chave-api.json"
```

Copia a chave do pendrive. Ou abra a pasta com `explorer "$env:APPDATA\SolicitacoesNF"` e cole à mão.

```powershell
Test-Path "$env:APPDATA\SolicitacoesNF\chave-api.json"
```

Tem que responder **`True`**. Depois **apague a chave do pendrive**.

### 6.9 Testar a configuração

```powershell
.\Bat\TESTAR_CONFIG.bat
```

- Lê o `config.json` (+ `config.local.json`, se houver) e valida.
- Mostra os problemas com a linha do erro, se houver.
- Aperte uma tecla para fechar.

### 6.10 Identificar o PC (descobrir o papel)

Abra o **Outlook** e espere carregar todas as caixas. Depois:

```powershell
.\.venv\Scripts\python.exe src\identidade.py
```

- Lê as contas do Outlook e compara com a coluna C do `Cadastro_Hoteis`.
- Mostra o agente, a confiança (%) e grava em `estado\maquina.json`.
- Com poucas caixas carregadas ou empate, ele **não atribui** (é de propósito). Espere o Outlook carregar e rode de novo.

```powershell
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'src'); from config import carregar_config; print(carregar_config()['papel'])"
```

Mostra o papel final: `principal` (só o PC do João) ou `conferente`.

### 6.11 Agendar as tarefas do Windows

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Automacoes\agendar_conferente.ps1
```

Cria e liga a tarefa **`SolicitacoesNF_Conferente`** (todo PC).

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Automacoes\agendar_painel.ps1
```

Cria e liga a tarefa **`SolicitacoesNF_Painel`** (todo PC).

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Automacoes\agendar_sincronizacao.ps1 -Minutos 30
```

Cria a tarefa **`SolicitacoesNF_CopiaHoteis`**. ⚠️ **Rode SÓ no PC principal.**

- `-NoProfile`: não carrega personalizações do PowerShell.
- `-ExecutionPolicy Bypass`: deixa rodar o script só desta vez, sem mudar a política do PC.

### 6.12 Criar o atalho do Painel

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File Automacoes\criar_atalho_app.ps1
```

Cria **Painel Notas Fiscais** na Área de Trabalho, com o ícone do app.

### 6.13 Rodar os testes automáticos

```powershell
.\Bat\rodar_testes.bat
```

- Roda os testes **sem** usar Google nem Outlook de verdade.
- Tem que terminar com `passed` e **nenhum** `failed`.
- Aperte uma tecla para fechar.

### 6.14 Pronto

Faça a conferência da **seção 10**. O PC agora está igual ao instalado pelo instalador automático.

### 6.15 Recriar um `.venv` quebrado

Sinais de `.venv` quebrado:

- `No Python at 'C:\Users\...\python.exe'`;
- `.venv` copiado de outro PC;
- erros estranhos de importação depois de atualizar o Python do Windows.

**Primeiro pare o que usa o ambiente:**

```powershell
Get-ScheduledTask SolicitacoesNF_* | Stop-ScheduledTask
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'Solicitacoes NF' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
```

- A primeira linha para as tarefas.
- A segunda fecha qualquer Python do projeto que ainda esteja aberto.

**Apague e crie de novo:**

```powershell
Remove-Item .venv -Recurse -Force
```

Apaga só o ambiente. O código, a `estado\` e a chave **não** são afetados.

```powershell
py -3.14 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Cria o ambiente de novo e reinstala as bibliotecas (passos 6.4 e 6.6).

```powershell
Get-ScheduledTask SolicitacoesNF_* | Start-ScheduledTask
```

Liga as tarefas de novo.

> Atalho: rodar o **`INSTALAR_OU_ATUALIZAR.bat`** faz essa verificação sozinho. Se o `.venv` não responde, ele apaga e recria.

---

## 7. A chave do Google

### 7.1 O que é e onde fica

- É um arquivo JSON de uma **conta de serviço** do Google: um "usuário robô" que acessa as planilhas.
- Fica em **`%APPDATA%\SolicitacoesNF\chave-api.json`** (o `config.json` aponta para lá em `caminho_chave_google`).
- **É a mesma chave em todos os PCs.**
- Dentro dela há um campo `client_email` (algo como `...@...iam.gserviceaccount.com`): é o e-mail do robô.
- **Nunca** coloque a chave dentro da pasta do projeto, num e-mail ou no WhatsApp.

### 7.2 O que precisa estar compartilhado com o `client_email`

| Planilha / pasta | ID (no `config.json`) | Permissão |
|---|---|---|
| **Planilha Central** | `planilha_central_id` | **Editor** |
| **Pasta do Drive** com as planilhas dos hotéis | `fontes_hoteis.pasta_drive_id` | **Leitor** |
| **Planilha de Registros** | `registro_central.planilha_id` | **Editor** |
| **Fiscal Intelligence** (Mail Analytics) | `painel.fiscal_intelligence_id` | Leitor basta. Hoje está como **Editor**, mas o Painel **só lê**. Gravar exige autorização do João. |

### 7.3 Se a chave for perdida ou vazar: gerar uma nova

1. Entre em **console.cloud.google.com** com a conta Google dona do projeto.
2. No topo, escolha o **projeto** onde a conta de serviço foi criada.
3. Menu **APIs e serviços → Biblioteca**: confirme que **Google Sheets API** e **Google Drive API** estão **ativadas**.
4. Menu **IAM e administrador → Contas de serviço** → clique na conta de serviço do robô.
5. Aba **Chaves → Adicionar chave → Criar nova chave → JSON → Criar**. O navegador baixa um `.json`.
6. Renomeie o arquivo para **`chave-api.json`** e coloque em `%APPDATA%\SolicitacoesNF\` **em todos os PCs**.
7. **Se a chave antiga vazou:** na mesma aba **Chaves**, **exclua a chave antiga**. Ela para de funcionar na hora.
8. Se criou uma **conta de serviço nova** (não só uma chave nova), compartilhe tudo da tabela 7.2 com o novo `client_email`.
9. Reinicie as tarefas em cada PC: `Get-ScheduledTask SolicitacoesNF_* | Stop-ScheduledTask` e depois `Start-ScheduledTask`.

---

## 8. O `config.json`, chave por chave, e o `config.local.json`

### 8.1 Como funciona

- O **`config.json` é igual em todos os PCs** e vai no git. Mudou nele = mudou para todos, depois da atualização (seção 12).
- Chaves que começam com `_` (ex.: `_ajuda_modo`) são **só anotações**: o robô ignora.
- Depois de editar, rode **`Bat\TESTAR_CONFIG.bat`**: ele aponta vírgula ou aspas faltando, com a linha.
- O **`config.local.json`** (opcional) fica só naquele PC e **sobrescreve** o que estiver nele (seção 8.3).

### 8.2 Cada chave

| Chave | Valor hoje | O que faz |
|---|---|---|
| `modo` | `PRODUCAO` | `PRODUCAO` envia · `TESTE` só para `email_teste` · `SIMULACAO` não envia (seção 2.2) |
| `email_teste` | caixa do Ondina | Para onde vai tudo no modo `TESTE` |
| `conta_remetente` | caixa do Ondina | Conta que envia quando a caixa do hotel não está neste Outlook |
| `caminho_chave_google` | `%APPDATA%\SolicitacoesNF\chave-api.json` | Onde está a chave (seção 7) |
| `planilha_central_id` | `1OT-ypZA...` | ID da **Planilha Central** (o trecho do link entre `/d/` e `/edit`) |
| `aba_cadastro_hoteis` | `Cadastro_Hoteis` | Aba com hotel (A), e-mail (B) e agente (C) |
| `aba_status` | `Status` | Aba com o interruptor "robô ligado" (B1) |
| `limite_solicitacoes_por_email` | 40 | Máximo de solicitações num e-mail consolidado |
| `agrupar_email` | `solicitacao` | `solicitacao` = 1 e-mail por solicitação · `hotel` = junta as do hotel num e-mail |
| `max_emails_por_execucao` | 150 | Teto de e-mails por rodada do robô |
| `formato_data_planilha` | `americano` | Formato padrão de data (cada aba é detectada sozinha) |
| `outlook` | 5 tentativas, 60 s, 180 s | Quantas vezes tenta conectar no Outlook, espera entre tentativas, espera da confirmação do envio |
| `colunas` | nomes das colunas | Como se chamam as colunas nas planilhas (aceita listas de nomes alternativos) |
| `colunas_documento` | `Documento Tomador` | Colunas tratadas como CPF/CNPJ |
| `colunas_ocultas` | lista | Colunas que **não** aparecem no e-mail ao hotel |
| `cadastro_colunas` | A, B, C | Letras das colunas do `Cadastro_Hoteis` |
| `agente_principal` | `João` | **Quem é o PC principal** (seção 2.1 e 17) |
| `agentes` | e-mail por agente | Usado só se `destino_envio` = `agente` |
| `marcador_aba_respostas` | `(respostas)` | Como o robô reconhece as abas de hotel na Central |
| `abas_ignoradas` | aba de teste | Abas que o robô **nunca** lê |
| `apelidos_hoteis` | lista | Nome na planilha/aba → nome no `Cadastro_Hoteis` |
| `fontes_hoteis` | pasta do Drive | Pasta com as planilhas dos hotéis e o nome da aba de respostas |
| `robo_antigo` | remetente Gmail, 75 min | Convivência com o Apps Script antigo (espera antes de enviar, não reenvia) |
| `visual_email` | `classico` | Visual do e-mail ao hotel: `classico` (branco + verde) ou `verde` |
| `destino_envio` | `hotel` | `hotel` = e-mail da coluna B · `agente` = e-mail em `agentes` |
| `cota_envio` | KingHost, 250/h | Limite do servidor de e-mail por hora |
| `conferencia` | 60 s, pdf/xml/zip, 45 dias | De quanto em quanto tempo o conferente olha, quais anexos contam como NF, até quantos dias atrás |
| `dropbox_notas` | 4 pastas, 5 min | Pastas do Dropbox com as NFs (**só leitura**). `%USERPROFILE%` vira a pasta do usuário de cada PC. |
| `app` | 15 s / 60 s | Painel relê a Central a cada 15 s com a janela aberta e a cada 60 s fechada |
| `painel.desde` | `2026-09-01` | Visão geral/Hotéis mostram dados a partir desta data |
| `painel.fiscal_intelligence_id` | `1e78L9...` | ID do Fiscal Intelligence (só leitura) |
| `painel.fi_minutos` | 5 | De quanto em quanto tempo relê o Fiscal Intelligence |
| `painel.ignorar_hoteis` | `RENASSENÇA` | Hotéis que o Painel desconsidera |
| `painel.lacunas_conhecidas` | 06/09 (todos), 25–27/09 (Cristian) | Dias sem dado já aceitos: não geram aviso |
| `somente_hoteis` | `[]` | Teste: processa só esses hotéis (`[]` = todos) |
| `registro_central` | ativo | Cópia das enviadas para a aba `Registros` de outra planilha |

### 8.3 O `config.local.json` (ajustes só de um PC)

Crie o arquivo `config.local.json` na pasta `Solicitacoes NF` **daquele PC**. Ele não vai para o git.
Coloque **só** o que quer mudar: o resto continua vindo do `config.json`.

**Forçar o papel do PC** (sem depender do Outlook):

```json
{ "papel": "conferente" }
```

**Dropbox em outro lugar neste PC:**

```json
{ "dropbox_notas": { "pastas": [
    "D:\\Dropbox\\...\\PC 1 - JOÃO\\2026 - JOÃO",
    "D:\\Dropbox\\...\\PC 2 - CLARA\\Notas Fiscais Hóspedes\\2026 - CLARA",
    "D:\\Dropbox\\...\\PC 3 - CRISTIAN\\2026 - CRISTIAN",
    "D:\\Dropbox\\...\\PC 4 - BERNARDO\\2026"
] } }
```

- No JSON, cada `\` do caminho é escrito **dobrado** (`\\`).
- A lista inteira substitui a do `config.json`, então coloque as 4 pastas.

**Testar envio só neste PC:**

```json
{ "modo": "TESTE" }
```

Depois de criar ou editar: rode `Bat\TESTAR_CONFIG.bat` e reinicie as tarefas (seção 9.3).

---

## 9. Tarefas do Windows

### 9.1 As três tarefas

| Tarefa | Em qual PC | Quando liga | O que faz |
|---|---|---|---|
| `SolicitacoesNF_Conferente` | Todos | 3 min depois de entrar no Windows; religa a cada 10 min se cair | Marca NF enviada / tratativa nos e-mails consolidados, confirma NFs pelo e-mail e pelo Dropbox, atende o menu da planilha (no principal) |
| `SolicitacoesNF_Painel` | Todos | 1 min depois de entrar no Windows; religa a cada 10 min se cair | Servidor do Painel escondido (porta 8765): dados sempre atualizados, publica as caixas deste PC na aba `PCs_Painel` e envia as NFs que chegarem para elas |
| `SolicitacoesNF_CopiaHoteis` | **Só no principal** | 3 min depois de entrar no Windows; repete a cada 30 min | Copia as planilhas dos hotéis para a Central e envia o que estiver pendente |

- Todas rodam como o **usuário logado** e **sem janela** (`pythonw.exe` / `_rodar_oculto.vbs`).
- Se já estiverem rodando, a repetição não abre outra cópia.

### 9.2 Ver o estado

```powershell
Get-ScheduledTask SolicitacoesNF_* | Select-Object TaskName, State
```

- `Running` = rodando agora.
- `Ready` = pronta, esperando a próxima vez.
- `Disabled` = desligada.

Também dá para ver no **Agendador de Tarefas** (Iniciar → "Agendador de Tarefas" → Biblioteca).

### 9.3 Ligar, desligar e reiniciar

```powershell
Get-ScheduledTask SolicitacoesNF_* | Stop-ScheduledTask       # para todas agora
Get-ScheduledTask SolicitacoesNF_* | Start-ScheduledTask      # liga todas agora
Disable-ScheduledTask -TaskName SolicitacoesNF_CopiaHoteis    # desliga de vez (não liga mais sozinha)
Enable-ScheduledTask  -TaskName SolicitacoesNF_CopiaHoteis    # religa
```

**Reiniciar só o Painel** (depois de mudar código ou config):

```powershell
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'app_servidor' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-ScheduledTask -TaskName SolicitacoesNF_Painel
```

- A primeira linha fecha o servidor do Painel.
- A segunda liga de novo. Em uns 10 segundos ele volta e a janela aberta se recarrega sozinha.

---

## 10. Conferir se o PC ficou igual ao do João

Faça **todos** os testes, na ordem:

1. **Tarefas ligadas:**
   ```powershell
   Get-ScheduledTask SolicitacoesNF_* | Select-Object TaskName, State
   ```
   - Conferente: `SolicitacoesNF_Conferente` e `SolicitacoesNF_Painel` como `Running` ou `Ready`.
   - Principal: também aparece `SolicitacoesNF_CopiaHoteis`.
2. **Mesma versão do João:**
   ```powershell
   git -C "$env:USERPROFILE\Desktop\Solicitacoes NF" log -1 --oneline
   ```
   O código no começo da linha (ex.: `13c8cfd`) tem que ser **igual** ao do PC do João.
3. **Ambiente certo:**
   ```powershell
   & "$env:USERPROFILE\Desktop\Solicitacoes NF\.venv\Scripts\python.exe" --version
   ```
   Tem que ser `Python 3.14.x`.
4. **Painel abre com dados:** abra o atalho **Painel Notas Fiscais**. A fila aparece, e a faixa do topo mostra
   "sincronizado" com o horário de agora e "robô ligado".
5. **Operador certo:** no canto superior direito do Painel aparece o nome do operador do PC.
   Se não, escolha no seletor.
6. **PC aparece para os outros:** na Planilha Central, aba **`PCs_Painel`**, em até 2 minutos aparece uma linha com:
   - o nome do PC;
   - o operador;
   - as caixas do Outlook dele;
   - o horário em "Visto em".

   **Sem essa linha, os outros PCs não conseguem enviar NF pela caixa deste PC.**
7. **Dropbox lido:** abra um pedido no Painel → **✉ Enviar NF por e-mail**. As notas do Dropbox com o nome
   parecido aparecem como sugestão. Se nunca aparece nada, veja a seção 8.3 e a pendência 4.
   **Não clique em Enviar no teste.** Feche no ×.
8. **Assinatura certa:** na mesma janela, embaixo, aparece a mensagem padrão com o **selo da Andrade Hotéis**
   da caixa do hotel. Se aparecer "Sem assinatura do Outlook", crie a assinatura daquela caixa (seção 4, item 5).
9. **Sem erros no log:** abra `logs\solicitacoes_nf.log` (seção 15) e procure linhas com ❌ nos últimos minutos.

---

## 11. A regra de ouro da sincronia

> **O código só é alterado em UM lugar** (o PC do João, ou o PC de casa: seção 13) e **sempre passa pelo git**.
> Nos outros PCs **ninguém edita nada** dentro da pasta `Solicitacoes NF`, nem o `config.json`.
> Eles só **recebem** a versão nova.

Por quê:

- O instalador atualiza com `git pull --ff-only`: ele só aceita a versão nova se o PC não tiver nenhuma mudança própria.
- Se alguém editou um arquivo num PC conferente, a atualização daquele PC **trava** até a mudança ser desfeita (seção 16).
- Ajuste que deve valer só para um PC vai no **`config.local.json`** (seção 8.3), que o git ignora.

---

## 12. Passar uma alteração para TODOS os PCs

Faça **toda vez** que mudar algo no código ou no `config.json`.

### Passo 1. No PC onde você alterou

```powershell
cd "$env:USERPROFILE\Desktop\Solicitacoes NF"
```

Entra na pasta do projeto.

```powershell
.\Bat\rodar_testes.bat
```

Roda os testes. Tem que terminar com `passed` e **nenhum** `failed`. Aperte uma tecla para fechar.

```powershell
git status
```

Mostra os arquivos alterados. Confira se **não** aparece nada de `estado\`, `logs\` ou chave.
O `.gitignore` já barra esses itens.

```powershell
git add -A
git commit -m "o que mudou, em poucas palavras"
```

- `git add -A` prepara todas as mudanças.
- `git commit` salva uma "foto" com a descrição.

```powershell
git push
```

Manda para o GitHub. Se pedir login, entre com a conta Kaereze.

### Passo 2. Em CADA um dos outros PCs, no mesmo dia, começando pelo principal

1. Feche a janela do Painel, se estiver aberta.
2. Dê duplo clique em **`INSTALAR_OU_ATUALIZAR.bat`** (na pasta `Solicitacoes NF` da Área de Trabalho).
3. No passo 3 ele pega a versão nova:
   - do **pendrive**, se houver um conectado com o projeto;
   - senão, do **GitHub**.
4. No passo 4 ele atualiza as bibliotecas, se o `requirements.txt` mudou.
5. Nos passos 7 a 9 ele **reinicia o conferente e o Painel** já na versão nova.
6. Confira o `Versao: xxxxxxx` que ele mostra: **tem que ser o mesmo do seu commit**.

### Atualização rápida: `ATUALIZAR_PAINEL.bat` (só código, PC já instalado)

Para o dia a dia, depois do push. Duplo clique em **`ATUALIZAR_PAINEL.bat`** (na pasta `Solicitacoes NF`). Ele:

1. acha a pasta do projeto sozinho (funciona até copiado para outro lugar, como a Área de Trabalho);
2. baixa a `main` do GitHub e aplica neste PC, mesmo que o PC esteja na branch do operador;
3. confere as bibliotecas do `.venv` (`pip install -r requirements.txt`);
4. reinicia o conferente e o Painel (`Automacoeseiniciar_servicos.ps1`) e espera o Painel responder;
5. mostra `PRONTO. Versao neste PC: xxxxxxx (GitHub: xxxxxxx)`: os dois números têm que ser iguais.

Ele **nunca apaga** o que foi alterado à mão no PC: se a versão nova mexer no mesmo arquivo, para, lista os arquivos
e não aplica nada. Pelo Remote Control, rode `ATUALIZAR_PAINEL.bat --sem-pausa` (não espera tecla no fim).
O resultado fica em `logstualizacao.log`. Se faltar Git, `.venv` ou as tarefas, ele manda rodar o
`INSTALAR_OU_ATUALIZAR.bat` (instalação completa).

### Atualizar pelo pendrive em vez do GitHub

1. Depois do commit, rode `Bat\gerar_pacote_pendrive.bat` no PC onde alterou. Ele atualiza o pendrive.
2. Leve o pendrive em cada PC e rode o `INSTALAR_OU_ATUALIZAR.bat`. Pode ser o do pendrive ou o da pasta do PC:
   com o pendrive conectado, os dois atualizam a pasta da Área de Trabalho.

### PC instalado pelo pendrive que deve passar a atualizar pelo GitHub

```powershell
cd "$env:USERPROFILE\Desktop\Solicitacoes NF"
git remote set-url origin https://github.com/Kaereze/Notas-Fiscais.git
```

- Troca a "origem" das atualizações, que era o pendrive, pelo GitHub. Precisa só **uma vez** por PC.
- Esse PC precisa ter acesso ao repositório privado (seção 5.3).

```powershell
git remote -v
```

Confere: tem que mostrar `https://github.com/Kaereze/Notas-Fiscais.git`.

> **Por que todos no mesmo dia:** os Painéis conversam entre si pela Planilha Central (fila de envio de NF,
> aba `PCs_Painel`). Versões muito diferentes podem não se entender.

---

## 13. PC de casa (só para editar código e design)

No PC de casa **não rode o `INSTALAR_OU_ATUALIZAR.bat`**. Ele ligaria o conferente e as tarefas, o que não
faz sentido num PC sem as caixas dos hotéis. Lá você cria **só o ambiente**.

### Primeira vez

```powershell
git clone https://github.com/Kaereze/Notas-Fiscais.git "$env:USERPROFILE\Desktop\Solicitacoes NF"
```

Baixa o código (peça o login do GitHub na primeira vez).

```powershell
cd "$env:USERPROFILE\Desktop\Solicitacoes NF"
```

Entra na pasta.

```powershell
py -3.14 -m venv .venv
```

**Cria o ambiente `.venv` do PC de casa** (seção 6.4). Sem o `py`, instale o Python 3.14 antes (seção 6.1).

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Instala as bibliotecas (seção 6.6).

```powershell
.\Bat\rodar_testes.bat
```

Confirma que o ambiente funciona: tem que dar `passed`.

**Para o Painel mostrar os dados reais:** copie o `chave-api.json` para `%APPDATA%\SolicitacoesNF\` (seção 6.8).
**Nunca** coloque a chave dentro da pasta do projeto.

### Toda vez que for mexer

```powershell
cd "$env:USERPROFILE\Desktop\Solicitacoes NF"
git pull
```

Pega o que foi feito no trabalho **antes** de mexer. Sem isso, as versões se desencontram.

```powershell
.\Bat\abrir_app.bat
```

Abre o Painel. Ele liga o servidor escondido sozinho, se não estiver rodando.

**Onde mexer no design:**

| Arquivo | O que tem |
|---|---|
| `app_ui\index.html` | Cores no topo (bloco `:root`, ex.: `--verde`, `--creme`, `--fundo`), todo o CSS e a estrutura das telas |
| `app_ui\painel.js` | O que cada tela mostra e faz. A janela de envio de NF está em `abrirEnvioNF`. |
| `app_ui\graficos.js` | Gráficos da Visão geral e dos Hotéis |
| `app_ui\icone.png` / `icone.ico` | Logo da janela e do atalho |

**Ver a mudança:**

- Mexeu em `.html`, `.js` ou `.css`: feche e abra a janela do Painel.
- Mexeu em arquivo `.py`: reinicie o servidor:
  ```powershell
  Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'app_servidor' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  .\Bat\abrir_app.bat
  ```

**Ao terminar:** seção 12, passo 1 (testes, commit, `git push`).

**No trabalho, antes de mexer em qualquer coisa:** rode `git pull` no PC do João e depois o passo 2 da seção 12 nos outros PCs.

> ⚠️ Com a chave, o Painel de casa trabalha com **dados reais**.
>
> - **Assumir**, **Marcar NF**, **Tratativa** e **Anotar** gravam de verdade na Central.
> - **Enviar NF** manda o pedido para o PC do trabalho que tem a caixa, e **o e-mail sai de verdade** para o hóspede.
> - **Enviar pendentes** dispara o envio aos hotéis.
>
> Para só olhar o design, **não clique nesses botões**.
>
> Sem a chave, o Painel abre mas fica sem dados.

---

## 14. Os atalhos `.bat`

| Atalho | O que faz | Quando usar |
|---|---|---|
| `INSTALAR_OU_ATUALIZAR.bat` | Os 9 passos da seção 5.1 | Instalar e **toda atualização** |
| `Bat\atualizar.bat` / `Bat\configurar_este_pc.bat` | Atalhos para o `INSTALAR_OU_ATUALIZAR.bat` | Mesma coisa |
| `Bat\instalar.bat` | Só cria o `.venv` e instala as bibliotecas | Recriar o ambiente sem mexer em tarefas |
| `Bat\TESTAR_CONFIG.bat` | Valida o `config.json` + `config.local.json` | Depois de editar a configuração |
| `Bat\rodar_testes.bat` | Testes automáticos | Antes de todo commit |
| `Bat\abrir_app.bat` | Abre a janela do Painel | Igual ao atalho da Área de Trabalho |
| `Bat\executar_robo.bat` | Roda o robô de envio **com janela**, mostrando tudo | Ver o que o robô está fazendo (respeita o `modo`) |
| `Bat\conferente.bat` | Roda o conferente **com janela** | Diagnóstico (normalmente roda escondido pela tarefa) |
| `Bat\sincronizar_agendado.bat` | Cópia dos hotéis + envio | Usado pela tarefa `SolicitacoesNF_CopiaHoteis` (não precisa clicar) |
| `Bat\gerar_pacote_pendrive.bat` | Cópia limpa do projeto para o pendrive | Levar a versão nova para outros PCs |
| `Bat\_rodar_oculto.vbs` | Roda um `.bat` sem janela | Usado pelas tarefas |

---

## 15. Logs: onde olhar quando algo parece errado

| Arquivo | O que tem |
|---|---|
| `logs\solicitacoes_nf.log` | **Principal.** Tudo que robô, conferente e Painel fizeram. ❌ = erro, ⚠️ = aviso. Os antigos viram `.log.1`, `.log.2`... |
| `logs\saida_console_sincronizar.txt` | Saída da cópia + envio agendados (só no principal) |
| `logs\Historico_de_Envios.csv` | Histórico dos e-mails enviados aos hotéis |
| Aba **`Status`** da Central | Interruptor "robô ligado" (B1) e sinais de vida |
| Aba **`PCs_Painel`** da Central | Quais PCs estão com o Painel ligado e com quais caixas |
| Faixa de saúde no topo do Painel | Robôs e operadores (verde = ok) |

**Ver as últimas 40 linhas do log:**

```powershell
Get-Content "$env:USERPROFILE\Desktop\Solicitacoes NF\logs\solicitacoes_nf.log" -Tail 40 -Encoding UTF8
```

**Ver só os erros de hoje:**

```powershell
Select-String -Path "$env:USERPROFILE\Desktop\Solicitacoes NF\logs\solicitacoes_nf.log" -Pattern "❌" -Encoding UTF8 | Select-Object -Last 20
```

---

## 16. Erros comuns e como resolver

| Mensagem / sintoma | O que é | O que fazer |
|---|---|---|
| `Not possible to fast-forward` / `would be overwritten` | Alguém editou um arquivo nesse PC | `git status` mostra o arquivo. Fale com o João. Para **descartar** as mudanças daquele PC e ficar igual ao GitHub: `git fetch` e depois `git reset --hard origin/main`. A `estado\` e a chave não são afetadas. |
| `Authentication failed` / pede login sempre | Repositório privado sem acesso | Entre com conta que tenha acesso (seção 5.3) ou atualize pelo pendrive |
| `py não é reconhecido` | Python não instalado ou PowerShell aberto antes da instalação | Seção 6.1. Feche e abra o PowerShell. |
| `No Python at '...python.exe'` | `.venv` quebrado (copiado de outro PC ou Python removido) | Seção 6.15 |
| `ModuleNotFoundError: No module named ...` | Biblioteca faltando no `.venv` | `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` |
| `UnicodeEncodeError: 'charmap' codec` | PowerShell sem UTF-8 ao rodar o Python à mão | `$env:PYTHONIOENCODING = "utf-8"` antes do comando (seção 6.7) |
| `Instalacao das bibliotecas falhou` | Sem internet ou bloqueio de rede | Verifique a internet e rode de novo |
| `Nao identifiquei agora (Outlook fechado?)` | Outlook fechado ou ainda carregando | Abra o Outlook, espere carregar e rode de novo |
| Papel errado (principal num PC que não é o do João) | `Cadastro_Hoteis` com agente errado | Corrija a coluna C, rode o instalador de novo ou force no `config.local.json` |
| `Falta a chave` / erro 403 no Google | Chave ausente ou planilha não compartilhada | Seção 7 |
| Painel não abre / porta 8765 ocupada | Servidor travado | Reinicie o Painel (seção 9.3) ou o PC |
| Painel abre sem dados | Sem chave ou sem internet | Seção 6.8. Veja o log. |
| "Nenhum PC ligado agora tem a caixa ..." ao enviar NF | O PC com aquela caixa está desligado, sem Outlook aberto ou sem o Painel atualizado | Ligue aquele PC com o Outlook aberto e rode o instalador nele. Ou envie pela caixa oferecida. |
| Sugestões do Dropbox nunca aparecem | Pasta do Dropbox diferente neste PC | Seção 8.3 |
| "Sem assinatura do Outlook para ..." | Caixa sem assinatura neste PC | Crie a assinatura no Outlook (seção 4, item 5) |

---

## 17. Trocar o PC principal ou formatar um PC

A **Planilha Central já é o banco de dados**: trocar de PC não perde nenhuma solicitação, NF ou tratativa.
O que pode precisar ir junto é só a **memória local do robô** (`estado\`) **do PC principal**.

**Se o PC que sai é um conferente:** basta instalar o novo (seção 5 ou 6). Não precisa copiar nada.

**Se o PC que sai é o principal:**

1. **No PC antigo**, desligue tudo, para não haver dois principais:
   ```powershell
   Get-ScheduledTask SolicitacoesNF_* | Disable-ScheduledTask
   Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'Solicitacoes NF' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
   ```
2. Copie para um pendrive, da pasta `Solicitacoes NF\estado\` do PC antigo, **só estes arquivos**:

   | Copiar | Para que serve |
   |---|---|
   | `ja_enviadas.json` | Lista do que já foi enviado (evita reenvio) |
   | `envios_pendentes.json` | Envio anotado e ainda não confirmado |
   | `controle_nf.json` | NF enviada / tratativa já marcadas |
   | `sincronizacao.json`, `ultima_copia.txt` | Até onde a cópia das planilhas já foi |
   | `robo_antigo.json` | Convivência com o Apps Script antigo |
   | `confirmar_nfs.json`, `cache_textos_nf.json` | NFs já confirmadas (evita reler tudo) |
   | `relatorios\` e `backup_*.json` (opcional) | Histórico e backups |

   **Não copie:**
   - `maquina.json`: é a identidade do PC antigo; o novo cria a dele;
   - arquivos `*.lock`, `*.mutex` e `*.trava`;
   - as pastas `app_edge\` e `app_webview\`: são da janela do Painel daquele PC;
   - `painel_cache.pkl`: o Painel refaz sozinho.
3. **No PC novo:** instale (seção 5 ou 6). Depois, com as tarefas paradas, cole os arquivos em `Solicitacoes NF\estado\`:
   ```powershell
   Get-ScheduledTask SolicitacoesNF_* | Stop-ScheduledTask
   # cole os arquivos em estado\ e depois:
   Get-ScheduledTask SolicitacoesNF_* | Start-ScheduledTask
   ```
4. **Se o operador do principal mudou** (ex.: deixa de ser o João):
   - troque `"agente_principal": "João"` no `config.json`;
   - faça commit e `git push`;
   - rode o `INSTALAR_OU_ATUALIZAR.bat` em **todos** os PCs.

   Para forçar o papel num PC só, sem mexer no `config.json`, use o `config.local.json` (seção 8.3).
5. **Copie a chave** para o PC novo, se o instalador ainda não colocou (seção 6.8).
6. **Confira** com a seção 10 e veja na aba **Status** da Central se o robô continua ligado (B1 marcado).

---

## 18. O que NUNCA vai para o GitHub nem para o pendrive

O `.gitignore` já barra estes itens. **Não force** a entrada deles (`git add -f`):

| Item | Por quê |
|---|---|
| `estado\` | Dados de hóspedes (nome, CPF, e-mail) e memória do robô |
| `logs\`, `saida_simulacao\` | Registros e e-mails gerados, com dados de hóspedes |
| `config.local.json` | Ajustes só daquele PC |
| `.venv\` | Cada PC cria o seu (seção 6) |
| a chave do Google | Fica fora da pasta, em `%APPDATA%`. Quem tem a chave tem acesso às planilhas. |

**Antes de cada `git push`**, olhe o `git status`. Se aparecer algum desses, **pare** e fale com o João.

---

## 19. Cola de comandos úteis

```powershell
# entrar na pasta do projeto
cd "$env:USERPROFILE\Desktop\Solicitacoes NF"

# versão do código deste PC (compare com a do João)
git log -1 --oneline

# trazer a versão nova do GitHub (sem reiniciar nada; o INSTALAR_OU_ATUALIZAR faz tudo)
git pull --ff-only

# estado das tarefas
Get-ScheduledTask SolicitacoesNF_* | Select-Object TaskName, State

# reiniciar o Painel
Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'app_servidor' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Start-ScheduledTask -TaskName SolicitacoesNF_Painel

# reiniciar tudo
Get-ScheduledTask SolicitacoesNF_* | Stop-ScheduledTask
Get-ScheduledTask SolicitacoesNF_* | Start-ScheduledTask

# conferir o ambiente .venv
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -c "import win32com.client, gspread, google.auth, pypdf, webview; print('ambiente ok')"

# reinstalar as bibliotecas
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

# a chave está no lugar?
Test-Path "$env:APPDATA\SolicitacoesNF\chave-api.json"

# papel deste PC
.\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0,'src'); from config import carregar_config; print(carregar_config()['papel'])"

# últimas linhas do log
Get-Content logs\solicitacoes_nf.log -Tail 40 -Encoding UTF8
```

---

## 20. Pendências

Situação em **06/10/2026**.

### Já resolvido (era pendência em 03/10)

- **Código no GitHub.** Está tudo lá. Os quatro operadores trabalham por **branch com o nome de cada um**
  (`clara`, `Bernardo`, `Christian`), e o que é aprovado entra na `main`. Não precisou mais de pendrive.
- **Os quatro PCs com o Painel ligado.** João, Clara, Cristian e Bernardo aparecem na aba `PCs_Painel`,
  cada um publicando as próprias caixas. Com isso **já dá para enviar NF pela caixa de um hotel que está
  em outro PC**, que era a maior limitação de antes.
- **Identidade do PC.** O `estado\maquina.json` passou a gravar o **nome do PC**. Um arquivo copiado de
  outra máquina não vale mais, e o PC se reconhece sozinho pelas caixas do Outlook (seção 6.10).
- **Classificação dos e-mails.** O `src\organizador_emails.py` lê a caixa de entrada e marca cada
  solicitação com as categorias do Outlook (`⏳ NF pendente`, `✅ NF concluído`, `💬 Tratativa`,
  `Nota dividida`, `⚠️ Faltando dados`, `🔁 Duplicada`, `📨 Fora do padrão`). Ele **não cria pasta
  nenhuma** e preserva as categorias que a equipe marcou à mão. As caixas saem do cruzamento entre o
  Outlook do PC e o `Cadastro_Hoteis`, então o mesmo arquivo roda em qualquer máquina.

### Ainda em aberto

1. **Outlook clássico e uma assinatura por caixa** em cada PC (seção 4). O e-mail da NF sai com a
   assinatura do PC que envia. **Confira em cada máquina**: não dá para verificar isso de fora.
2. **WebView2 nos PCs com Windows 10** (seção 4, item 10). Sem ele a janela do Painel não abre.
3. **Caminho do Dropbox em cada PC.** O `config.json` usa `%USERPROFILE%`, então serve para qualquer
   usuário do Windows, mas a parte `Guilherme Heisler\FINANCEIRO ANDRADE HOTEIS\...` precisa ser igual
   em todos. No PC da Clara as quatro pastas abrem. Faça o teste 7 da seção 10 nos outros.
4. **Três caixas do Outlook fora do `Cadastro_Hoteis`:**

   | Caixa | Está no Outlook de | Situação |
   |---|---|---|
   | `notafiscal@redeandradepousadajeri.com.br` | João | O cadastro tem `JERI` e `VILA JERI`, com outros endereços |
   | `notafiscal@redeandradepalace.com.br` | Cristian | Não existe no cadastro |
   | `notafiscal@redeandradecampogrande.com.br` | Bernardo | Não existe no cadastro |

   **Não há formulário ativo para nenhuma das três** — nenhuma solicitação de hóspede chega por elas,
   então nada está sendo perdido hoje. Decida se é hotel novo que falta cadastrar, ou caixa antiga que
   pode sair do Outlook. Enquanto estiverem fora do cadastro, o robô não envia o consolidado para elas
   e o organizador não classifica os e-mails delas.

5. **Sincronia automática** (proposta, não existe). Hoje cada PC só fica na versão nova quando alguém
   atualiza. Nada avisa se um PC ficou para trás. Duas melhorias possíveis:
   - **Aviso de PC desatualizado:** cada Painel grava a versão do código na aba `PCs_Painel`, e a faixa
     de saúde mostra "PC do Cristian desatualizado".
   - **Atualização automática:** uma tarefa diária pega a versão nova do GitHub e reinicia o conferente
     e o Painel sozinha.
6. **PC que reinicia e fica na tela de login para de trabalhar.** As tarefas rodam como usuário logado
   (exigência do Outlook), e não há logon automático. Enquanto ninguém entra na conta, o conferente não
   marca NF e o Painel some da aba `PCs_Painel` — e aí os outros PCs não conseguem enviar NF por aquelas
   caixas. **Bloquear a tela com `Win+L` não causa isso**: a sessão continua e tudo segue rodando. O que
   derruba é sair da conta, desligar ou reiniciar. No PC da Clara o Windows registrou 6 desligamentos
   inesperados entre agosto e outubro de 2026, então vale combinar quem religa cada máquina.
7. Há um e-mail de teste **"[TESTE] NF 0000 - TESTE DO PAINEL"** na caixa do Ondina, que pode ser apagado.
8. Recomendado apagar o `credentials.json` da pasta do Dropbox `RELATORIOS\Mail Analitycs`
   (o robô não mexe nessa pasta).
9. **Migrar o Mail Analytics para dentro do Painel:** planejado, ainda não começou. Até lá o Painel só
   **lê** o Fiscal Intelligence. A pasta `Desktop\Mail Analitycs` nunca é alterada pelo robô.
