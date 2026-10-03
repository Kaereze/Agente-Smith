# Instalação, sincronia entre PCs e pendências

Guia para deixar **qualquer PC funcionando igual ao PC do João**: robô de solicitações, conferente
e **Painel Notas Fiscais**, todos na **mesma versão**.

Siga as seções **na ordem**. Os comandos são para o **PowerShell** (menu Iniciar → "PowerShell").

---

## 1. Como os PCs ficam em sincronia (entenda antes de instalar)

O que precisa ficar igual em todos os PCs se divide em três tipos:

| O quê | Onde fica | Como fica igual nos PCs |
|---|---|---|
| **Dados** (solicitações, quem assumiu, NFs, tratativas, fila de envio) | **Planilha Central** (Google Sheets) | Sozinho, em tempo real. Todo PC lê e grava na mesma planilha. Não há nada para copiar. |
| **Código** (robô, conferente, Painel) | Pasta `Solicitacoes NF` de cada PC | **Você atualiza**: muda num PC só e roda o `INSTALAR_OU_ATUALIZAR.bat` em cada PC (seção 6). |
| **Coisas que são de cada PC** | Cada PC tem as suas | **Nunca são copiadas pelo código** (veja abaixo). |

**Coisas que são de cada PC e não viajam no GitHub nem no pendrive do código:**

- **Chave do Google**, em `%APPDATA%\SolicitacoesNF\chave-api.json`. É a mesma chave em todos os PCs, mas é copiada à mão (ela dá acesso às planilhas).
- **Pasta `estado\`**, a memória do robô naquele PC, com dados de hóspedes.
- **Pasta `logs\`**.
- **`config.local.json`**, se existir: ajustes só daquele PC.
- **Outlook com as caixas dos hotéis** e as **assinaturas** de cada caixa.
- **Dropbox** sincronizando as pastas de notas.

### Os dois papéis

| Papel | Qual PC | O que roda |
|---|---|---|
| **principal** | **Só um PC**, o do agente em `"agente_principal"` no `config.json` (hoje: **João**) | Cópia das planilhas dos hotéis, envio do e-mail consolidado, conferente e Painel |
| **conferente** | Todos os outros | Conferente e Painel |

O papel é descoberto sozinho: o instalador olha as caixas do Outlook do PC e compara com a coluna C
(agente) da aba `Cadastro_Hoteis`.

> ⚠️ **Nunca deixe dois PCs como principal.** A proteção contra envio repetido fica na pasta `estado\`
> de cada PC. Com dois principais, os hotéis podem receber e-mail em dobro.

### Tarefas do Windows que o instalador cria

| Tarefa | Em qual PC | O que faz |
|---|---|---|
| `SolicitacoesNF_Conferente` | Todos | Liga ao entrar no Windows. Marca NF enviada/tratativa e confirma NFs pelo e-mail e pelo Dropbox. |
| `SolicitacoesNF_Painel` | Todos | Painel em segundo plano. Mantém os dados atualizados e envia as NFs que chegarem para as caixas deste PC. |
| `SolicitacoesNF_CopiaHoteis` | **Só no principal** | A cada 30 min: copia as planilhas dos hotéis para a Central e envia o que estiver pendente. |

---

## 2. Checklist antes de instalar num PC

Confira **tudo** isto no PC novo:

- [ ] **Windows 10 ou 11**, com o usuário do operador logado. As tarefas só rodam com alguém logado, porque o Outlook exige isso.
- [ ] **Outlook clássico** (o "Outlook" do Office, **não** o "Novo Outlook"), **aberto**, com **todas as caixas dos hotéis** daquele operador. O robô não funciona com o Novo Outlook.
- [ ] **Uma assinatura no Outlook para cada caixa** (Arquivo → Opções → Email → Assinaturas). O Painel envia a NF com a assinatura da caixa que estiver neste PC.
- [ ] **Dropbox** instalado, logado e sincronizando a pasta `Notas Fiscais Hóspedes`. O caminho esperado é `%USERPROFILE%\REDE ANDRADE Dropbox\Guilherme Heisler\FINANCEIRO ANDRADE HOTEIS\Financeiro sede\Notas Fiscais Hóspedes\` (veja a pendência 4 se for diferente).
- [ ] Na **Planilha Central**, aba `Cadastro_Hoteis`: a **coluna C** tem o nome do operador nos hotéis das caixas dele.
- [ ] **Internet** funcionando.
- [ ] O arquivo **`chave-api.json`** à mão (num pendrive ou copiado do PC do João, de `%APPDATA%\SolicitacoesNF\`).
- [ ] Acesso ao código, de um destes jeitos:
  - **Pendrive**, gerado no PC do João (seção 3A). Não precisa de GitHub.
  - **GitHub**: o repositório é **privado**, então o PC precisa entrar com uma conta que tenha acesso (seção 3B).

Python e Git **não precisam estar instalados**: o instalador baixa os dois sozinho.

---

## 3. Instalar num PC novo

Escolha **um** dos dois caminhos.

### 3A. Pelo pendrive (recomendado: não precisa de conta no GitHub)

**No PC do João:**

1. Garanta que tudo está salvo no git (seção 6, passo 1).
2. Conecte o pendrive e dê duplo clique em **`Bat\gerar_pacote_pendrive.bat`**.
3. Quando ele perguntar *"Levar a chave do Google junto?"*:
   - **s**: o PC novo instala sem pedir nada;
   - **n**: você cola a chave à mão no passo 4 abaixo.
4. No fim aparece `PRONTO: E:\KARUZO\Solicitacoes NF` e a versão (ex.: `Versao: c80188b`).

**No PC novo:**

1. Abra o **Outlook** e espere carregar todas as caixas.
2. Conecte o pendrive e dê duplo clique em **`E:\KARUZO\Solicitacoes NF\INSTALAR_OU_ATUALIZAR.bat`**. A letra pode ser outra.
3. Ele faz os 9 passos sozinho:

   | Passo | O que faz |
   |---|---|
   | 1–2 | Instala Python 3.14 e Git, se faltarem |
   | 3 | Copia o projeto para **`Área de Trabalho\Solicitacoes NF`** |
   | 4 | Cria o `.venv` e instala as bibliotecas |
   | 5 | Chave do Google: copia do pendrive ou **abre a pasta para você colar** o `chave-api.json` |
   | 6 | Descobre de quem é o PC pelo Outlook e mostra o papel |
   | 7 | Liga o conferente |
   | 8 | Liga a cópia e o envio (**só no principal**) |
   | 9 | Liga o Painel em segundo plano e cria o atalho **Painel Notas Fiscais** na Área de Trabalho |

4. Tem que terminar com **`PRONTO. Pasta: ... | Papel: conferente`** (ou `principal` no PC do João).
5. **Apague o `chave-api.json` do pendrive** se ele foi junto.

### 3B. Pelo GitHub

**Uma vez só, no GitHub (conta Kaereze):** abra o repositório → **Settings → Collaborators → Add people**
e convide a conta do operador. Ou faça o login com a sua conta no PC dele.

**No PC novo:**

1. Instale o Git, se não tiver: `winget install -e --id Git.Git`. Depois feche e abra o PowerShell.
2. Baixe o código para a Área de Trabalho:
   ```powershell
   git clone https://github.com/Kaereze/Notas-Fiscais.git "$env:USERPROFILE\Desktop\Solicitacoes NF"
   ```
   Na primeira vez abre uma janela de **login do GitHub**: entre com a conta que tem acesso.
3. Abra o **Outlook** e espere carregar.
4. Dê duplo clique em **`Área de Trabalho\Solicitacoes NF\INSTALAR_OU_ATUALIZAR.bat`**.
5. No passo 5 ele abre uma pasta: **cole o `chave-api.json`** nela e aperte Enter.
6. Tem que terminar com **`PRONTO. ... | Papel: conferente`**.

---

## 4. Conferir se o PC ficou igual ao do João

Faça **todos** os testes:

1. **Tarefas ligadas:**
   ```powershell
   Get-ScheduledTask SolicitacoesNF_* | Select-Object TaskName, State
   ```
   - Conferente: `SolicitacoesNF_Conferente` e `SolicitacoesNF_Painel` aparecem como `Running` ou `Ready`.
   - Principal: também aparece `SolicitacoesNF_CopiaHoteis`.
2. **Mesma versão do João:** dentro da pasta, rode `git log -1 --oneline`. O código no começo da linha
   (ex.: `c80188b`) tem que ser **igual** ao do PC do João.
3. **Painel abre com dados:** abra o atalho **Painel Notas Fiscais**. A fila aparece e a faixa do topo mostra
   "sincronizado" com o horário atual.
4. **PC aparece para os outros:** na Planilha Central, aba **`PCs_Painel`**, em até 2 minutos aparece uma linha
   com o nome do PC, o operador e as caixas do Outlook dele. **Sem essa linha, os outros PCs não conseguem
   enviar NF pela caixa deste PC.**
5. **Dropbox lido:** abra um pedido no Painel → **✉ Enviar NF por e-mail**. As notas do Dropbox com o nome
   parecido aparecem como sugestão. Se nunca aparece nada, veja a pendência 4. **Não clique em Enviar no teste.**
6. **Sem erros:** abra `logs\solicitacoes_nf.log` e veja se não há linhas com ❌.

---

## 5. A regra de ouro da sincronia

> **O código só é alterado em UM lugar** (o PC do João, ou o PC de casa: seção 7) e **sempre passa pelo git**.
> Nos outros PCs **ninguém edita nada** dentro da pasta `Solicitacoes NF`. Eles só **recebem** a versão nova.

Se alguém editar um arquivo num PC conferente, a atualização daquele PC **trava** (seção 8) até a mudança ser desfeita.

---

## 6. Passar uma alteração para TODOS os PCs (toda vez que mudar algo)

**Passo 1. No PC onde você alterou:**

```powershell
cd "$env:USERPROFILE\Desktop\Solicitacoes NF"
.\Bat\rodar_testes.bat            # tem que terminar com "passed", sem "failed" (depois aperte uma tecla)
git add -A
git commit -m "o que mudou"
git push                          # manda para o GitHub
```

**Passo 2. Em CADA um dos outros PCs, no mesmo dia, começando pelo principal:**

- Dê duplo clique em **`INSTALAR_OU_ATUALIZAR.bat`** (na pasta `Solicitacoes NF` da Área de Trabalho).
- Ele pega a versão nova:
  - do **pendrive**, se houver um conectado com o projeto;
  - senão, do **GitHub**.
- Depois atualiza as bibliotecas e **reinicia o conferente e o Painel** já na versão nova.
- Confira o `Versao: xxxxxxx` que ele mostra: tem que ser o mesmo do seu commit.

**Pelo pendrive em vez do GitHub:** depois do commit, rode `Bat\gerar_pacote_pendrive.bat`. Ele
atualiza o pendrive. Leve o pendrive em cada PC e rode o `INSTALAR_OU_ATUALIZAR.bat`. Pode ser o do pendrive ou o da pasta
do PC: com o pendrive conectado, os dois atualizam a pasta da Área de Trabalho.

**PC instalado pelo pendrive que deve passar a atualizar pelo GitHub:** rode uma vez nele:

```powershell
cd "$env:USERPROFILE\Desktop\Solicitacoes NF"
git remote set-url origin https://github.com/Kaereze/Notas-Fiscais.git
```

> **Por que todos no mesmo dia:** os Painéis conversam entre si pela Planilha Central (fila de envio de NF).
> Versões muito diferentes podem não se entender.

---

## 7. PC de casa (só para editar o código e o design)

No PC de casa **não rode o `INSTALAR_OU_ATUALIZAR.bat`**. Ele ligaria o conferente e as tarefas, o que não
faz sentido num PC sem as caixas dos hotéis.

**Primeira vez:**

```powershell
git clone https://github.com/Kaereze/Notas-Fiscais.git "$env:USERPROFILE\Desktop\Solicitacoes NF"
cd "$env:USERPROFILE\Desktop\Solicitacoes NF"
py -3.14 -m venv .venv            # sem o "py": instale o Python 3.14 em python.org (marque "Add to PATH")
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Para o Painel mostrar os dados reais, copie o `chave-api.json` para `%APPDATA%\SolicitacoesNF\` (crie a pasta).
**Nunca** coloque a chave dentro da pasta do projeto.

**Toda vez que for mexer:**

```powershell
cd "$env:USERPROFILE\Desktop\Solicitacoes NF"
git pull                          # pega o que foi feito no trabalho ANTES de mexer
.\Bat\abrir_app.bat               # abre o Painel
```

- **Onde mexer no design:**
  - `app_ui\index.html`: cores no topo, em `:root`, e todo o CSS;
  - `app_ui\painel.js`: o que cada tela mostra.
- **Ver a mudança:** feche e abra a janela do Painel. Se mexeu em arquivo `.py`, reinicie o servidor:
  ```powershell
  Get-CimInstance Win32_Process -Filter "Name like 'python%'" | Where-Object { $_.CommandLine -match 'app_servidor' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
  .\Bat\abrir_app.bat
  ```
- **Ao terminar:** seção 6, passo 1 (testes, commit, `git push`).
- **No trabalho, antes de mexer em qualquer coisa:** `git pull` no PC do João. Depois o passo 2 da seção 6 nos outros PCs.

> ⚠️ Com a chave, o Painel de casa trabalha com **dados reais**.
> - **Assumir**, **Marcar NF** e **Tratativa** gravam de verdade na Central.
> - **Enviar NF** manda o pedido para o PC do trabalho que tem a caixa, e **o e-mail sai de verdade** para o hóspede.
>
> Para só olhar o design, não clique nesses botões.

---

## 8. Se a atualização der erro

| Mensagem | O que é | O que fazer |
|---|---|---|
| `Not possible to fast-forward` / `would be overwritten` | Alguém editou um arquivo nesse PC | Rode `git status` na pasta para ver o arquivo e fale com o João. Para **descartar** as mudanças daquele PC e ficar igual ao GitHub, use `git fetch` e depois `git reset --hard origin/main`. A pasta `estado\` não é afetada. |
| `Authentication failed` / pede login | Repositório privado | Entre com uma conta que tenha acesso (seção 3B), ou atualize pelo pendrive |
| `Instalacao das bibliotecas falhou` | Sem internet ou bloqueio | Verifique a internet e rode de novo |
| `Nao identifiquei agora (Outlook fechado?)` | Outlook fechado ou carregando | Abra o Outlook, espere carregar e rode de novo |
| Papel errado (principal num PC que não é o do João) | Cadastro_Hoteis com agente errado | Corrija a coluna C do `Cadastro_Hoteis` e rode de novo |
| Painel não abre / porta 8765 ocupada | Servidor travado | Reinicie o servidor (comando da seção 7) ou reinicie o PC |

---

## 9. Trocar o PC principal ou formatar um PC (passar os dados para outra máquina)

A **Planilha Central já é o banco de dados**: trocar de PC não perde nenhuma solicitação, NF ou tratativa.
O que pode precisar ir junto é só a **memória local do robô** (`estado\`) **do PC principal**.

**Se o PC que sai é um conferente:** basta instalar o novo (seção 3). Não precisa copiar nada.

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
   - arquivos `*.lock` e `*.mutex`;
   - as pastas `app_edge\` e `app_webview\`;
   - `painel_cache.pkl`: o Painel refaz sozinho.
3. **No PC novo:** instale (seção 3). Depois, com as tarefas paradas, cole os arquivos em `Solicitacoes NF\estado\`:
   ```powershell
   Get-ScheduledTask SolicitacoesNF_* | Stop-ScheduledTask
   # cole os arquivos em estado\ e depois:
   Get-ScheduledTask SolicitacoesNF_* | Start-ScheduledTask
   ```
4. **Se o operador do principal mudou** (ex.: deixa de ser o João):
   - troque `"agente_principal": "João"` no `config.json`;
   - faça commit e `git push`;
   - rode o `INSTALAR_OU_ATUALIZAR.bat` em **todos** os PCs.

   Para forçar o papel num PC só, sem mexer no `config.json`, crie nele um `config.local.json` com
   `{"papel": "principal"}` (ou `"conferente"`).
5. **Copie a chave** para o PC novo, de `%APPDATA%\SolicitacoesNF\chave-api.json`, se o instalador ainda não colocou.
6. **Confira** com a seção 4 e veja na aba **Status** da Central se o robô continua ligado (B1 marcado).

---

## 10. O que NUNCA vai para o GitHub nem para o pacote do pendrive

O `.gitignore` já barra estes itens. Não force a entrada deles (`git add -f`):

- **`estado\`**: dados de hóspedes (nome, CPF, e-mail) e a memória do robô;
- **`logs\`** e `saida_simulacao\`;
- **`config.local.json`**: ajustes só daquele PC;
- **`.venv\`**: cada PC cria o seu;
- **a chave do Google**, que fica fora da pasta do projeto, em `%APPDATA%`.

---

## 11. Pendências (situação em 03/10/2026)

**Para os outros PCs funcionarem igual ao do João:**

1. **Subir o código para o GitHub.** O PC do João tem commits que **ainda não estão no GitHub**.
   Rode `git push` antes de instalar ou atualizar qualquer PC pelo GitHub.
2. **Instalar ou atualizar o Painel novo nos outros PCs** (Clara, Cristian, Bernardo) com o
   `INSTALAR_OU_ATUALIZAR.bat`. Hoje **só o PC do João** aparece na aba `PCs_Painel`. Por isso:
   - os outros PCs ainda não têm o Painel atualizado;
   - **não dá para enviar NF pela caixa de um hotel que está em outro PC** (ex.: Novo Vernon, que está em
     outro PC). O Painel oferece uma caixa deste PC no lugar.
3. **Repositório privado.** Decidir como os outros PCs pegam o código:
   - pelo **pendrive** (3A, não precisa de nada no GitHub);
   - ou **convidar cada operador como colaborador** (3B).
4. **Caminho do Dropbox em cada PC.** O `config.json` já usa `%USERPROFILE%`, então serve para qualquer
   usuário do Windows. Mas a parte `Guilherme Heisler\FINANCEIRO ANDRADE HOTEIS\...` precisa ser **igual** no
   Dropbox de cada PC. Faça o teste 5 da seção 4. Se num PC a pasta estiver em outro lugar, crie nele um
   `config.local.json` com as pastas certas (esse arquivo não vai para o git):
   ```json
   { "dropbox_notas": { "pastas": [
       "D:\\Dropbox\\...\\PC 1 - JOÃO\\2026 - JOÃO",
       "D:\\Dropbox\\...\\PC 2 - CLARA\\Notas Fiscais Hóspedes\\2026 - CLARA",
       "D:\\Dropbox\\...\\PC 3 - CRISTIAN\\2026 - CRISTIAN",
       "D:\\Dropbox\\...\\PC 4 - BERNARDO\\2026"
   ] } }
   ```
5. **Outlook clássico e assinaturas** em cada PC (checklist da seção 2). O e-mail da NF sai com a assinatura do PC que envia.

**Sincronia automática (ainda não existe; proposta):**

6. Hoje cada PC só fica na versão nova quando alguém roda o `INSTALAR_OU_ATUALIZAR.bat` nele (seção 6).
   Nada avisa se um PC ficou para trás. Duas melhorias possíveis:
   - **Aviso de PC desatualizado:** cada Painel grava a versão do código na aba `PCs_Painel`, e a faixa de
     saúde do Painel mostra "PC do Cristian desatualizado".
   - **Atualização automática:** uma tarefa diária em cada PC pega a versão nova do GitHub e reinicia o
     conferente e o Painel sozinha. Exige que todos os PCs tenham acesso ao GitHub (pendência 3).

**Outras pendências já conhecidas:**

7. Há um e-mail de teste **"[TESTE] NF 0000 - TESTE DO PAINEL"** na caixa do Ondina, que pode ser apagado.
8. Recomendado apagar o `credentials.json` da pasta do Dropbox `RELATORIOS\Mail Analitycs`
   (o robô não mexe nessa pasta).
9. **Migrar o Mail Analytics para dentro do Painel:** planejado, ainda não começou. Até lá o Painel só
   **lê** o Fiscal Intelligence. A pasta `Desktop\Mail Analitycs` nunca é alterada pelo robô.
