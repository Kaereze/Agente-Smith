# Instalar um PC novo (só Painel)

Para um computador **sem Outlook e sem caixas de hotel**, como o da Ingrid (outro setor). Ele abre o Painel, vê a fila, emite a nota e **pede o envio**: quem envia o e-mail ao hóspede é o PC dono da caixa do hotel, pelo Outlook dele, com a assinatura certa. Este PC não copia planilhas, não roda conferente e não guarda e-mail.

Para um PC **com** Outlook (conferente), use [[Instalação e pendências]].

## O que este PC tem e o que não tem

| Tem | Não tem (de propósito) |
|---|---|
| Painel completo de operador: fila, NF, tratativa, pedido de envio | Outlook e caixas dos hotéis |
| Leitura e escrita na Planilha Central (pela chave do Google) | Conferente, cópia das planilhas, envio pelo robô |
| Conversa com os outros 4 PCs (porta 8766, rede local) | Opções de administrador (aba Agentes, desempenho, robô ligado, Delete direto): são só do João, no PC dele |
| Atualização sozinha pelo GitHub | Papel de principal |

## O que você precisa ter em mãos

1. **Conta do GitHub com convite aceito** para o repositório privado `Kaereze/Notas-Fiscais`. O convite chega por e-mail; abra o link e aceite.
2. **`chave-api.json`**: chave do Google criada só para este PC (veja "A chave" abaixo).
3. **`segredo-rede.txt`**: gerado no PC do João (veja "O segredo da rede" abaixo).
4. Windows 10 ou 11 de 64 bits, com internet.
5. A TI deve liberar a **porta 8766 (TCP)** entre os PCs da rede, se o firewall da empresa bloquear.

> Nada disso (chave, segredo) vai para o GitHub nem para este cofre. Os arquivos são colocados à mão.

## Passo a passo

### 1. Instalar o Git e baixar o projeto
Abra o **PowerShell** (menu Iniciar, digite PowerShell) e rode:

```powershell
winget install -e --id Git.Git
```

Feche e abra o PowerShell de novo. Depois:

```powershell
git clone https://github.com/Kaereze/Notas-Fiscais.git "$env:USERPROFILE\Desktop\Solicitacoes NF"
```

Na primeira vez abre uma janela do navegador pedindo o login do GitHub: entre com a conta que recebeu o convite. Se aparecer "repositório não encontrado", o convite ainda não foi aceito.

### 2. Rodar o instalador
Abra a pasta **Solicitacoes NF** na Área de Trabalho e dê duplo clique em **`INSTALAR_PC_SO_PAINEL.bat`**. Ele pergunta o nome do operador (ex.: `Ingrid`) e faz 10 etapas, mostrando OK, aviso (`--`) ou falha (`!!`):

| # | O que faz |
|---|---|
| 1 | Instala o Python 3.14, se faltar |
| 2 | Confere o Git |
| 3 | Atualiza o projeto pelo GitHub |
| 4 | Cria o ambiente `.venv` dentro deste PC e instala as bibliotecas |
| 5 | Abre a pasta `%APPDATA%\SolicitacoesNF` para você colar `chave-api.json` e `segredo-rede.txt` |
| 6 | Grava a configuração deste PC (papel "só Painel" e o nome do operador) |
| 7 | Confere o WebView2 (a janela do Painel) e instala se faltar |
| 8 | Libera a porta 8766 no firewall do Windows (pede senha de administrador uma vez) |
| 9 | Liga o Painel em segundo plano e cria o atalho "Painel Notas Fiscais" |
| 10 | Teste final: lê a Planilha Central e chama cada PC ligado |

O teste final tem que mostrar **OK** na chave, na Planilha Central e em cada PC ligado. Para repetir só o teste, a qualquer hora:

```powershell
& "$env:USERPROFILE\Desktop\Solicitacoes NF\.venv\Scripts\python.exe" "$env:USERPROFILE\Desktop\Solicitacoes NF\Automacoes\testar_pc_novo.py"
```

### 3. Abrir o Painel
Use o atalho **Painel Notas Fiscais** na Área de Trabalho. Escolha o nome do operador, se pedir.

## A chave do Google (um arquivo só para este PC)
No Google Cloud (console.cloud.google.com), no projeto do Painel: menu, **IAM e administrador**, **Contas de serviço**, a conta `solicitacoes-nf-bot@...`, aba **Chaves**, **Adicionar chave**, **Criar nova chave**, **JSON**. O arquivo baixa sozinho e só dá para baixar uma vez. Renomeie para `chave-api.json`. A conta é a mesma dos outros PCs, então as permissões já são as mesmas. Quando o PC novo estiver funcionando, apague no Google as chaves que passaram por mensagem.

## O segredo da rede (por que ele existe)
Os PCs só confiam um no outro se assinarem os pedidos com o mesmo segredo. Até hoje esse segredo era calculado a partir do conteúdo da chave do Google, então uma chave nova (diferente) seria recusada pelos outros PCs (erro 403). O arquivo `segredo-rede.txt` guarda só esse resumo, **sem a chave privada**, e o PC novo passa a usá-lo no lugar do cálculo.

Para gerar, no **PC do João** (ou qualquer PC que já fala com os outros):

```powershell
& "$env:USERPROFILE\Desktop\Solicitacoes NF\.venv\Scripts\python.exe" "$env:USERPROFILE\Desktop\Solicitacoes NF\Automacoes\gerar_segredo_rede.py"
```

O arquivo aparece na Área de Trabalho (o valor nunca é mostrado na tela). Leve para o PC novo pelo Compartilhamento por proximidade do Windows, por cabo ou pelo WhatsApp só para você mesmo, cole em `%APPDATA%\SolicitacoesNF\` e **apague a cópia do PC do João**.

Os 4 PCs atuais não precisam de nenhum arquivo: continuam calculando o mesmo segredo de sempre.

## Se algo falhar

| Sintoma | Causa provável | O que fazer |
|---|---|---|
| `repositório não encontrado` no clone | Convite do GitHub não aceito | Aceitar o convite no e-mail e tentar de novo |
| Teste: chave `!!` | Arquivo errado ou incompleto | Criar outra chave no Google Cloud |
| Teste: Planilha Central `!!` | Chave de outro projeto | Usar uma chave da conta `solicitacoes-nf-bot` |
| Teste: PC `não respondeu (HTTPError)` | `segredo-rede.txt` ausente ou diferente | Gerar de novo no PC do João |
| Teste: PC `não respondeu (URLError/timeout)` | Firewall ou PC em outra rede | Rodar a etapa 8 de novo; pedir à TI a porta 8766 |
| "Nenhum PC ligado agora tem a caixa..." ao enviar | O PC dono daquela caixa está desligado | Esperar: o pedido fica na fila até 24 h |

## Como o envio funciona neste PC
1. O operador anexa a nota e aperta Enviar.
2. O Painel grava o pedido na Planilha Central, na fila de envios, com o anexo.
3. O Painel do PC dono da caixa do hotel vê o pedido e envia pelo Outlook dele, com a assinatura da caixa.
4. A tela deste PC mostra: aguardando, enviado ou falhou.

## Para quem mantém o sistema
- O papel vem de `config.local.json` (`"papel": "so_painel"`), gravado por `Automacoes\configurar_pc_so_painel.py`. No código: `config.sem_outlook`.
- Neste papel o Painel não indexa nem vigia o Outlook, publica o Outlook como "sem Outlook" (os outros PCs não alertam "Outlook fechado") e responde "sem caixa" à pesquisa pela rede.
- O segredo: `rede_local.segredo_da_chave` usa `segredo-rede.txt` ao lado da chave quando existe.
- Testes: `testes/test_so_painel.py`, `test_segredo_rede.py`, `test_instalador_so_painel.py`.

Voltar: [[00 Início]]
