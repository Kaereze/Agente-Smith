---
tipo: documento
pasta: "6 Documentos"
pai: "[[00 Início]]"
prioridade: P1
tags: [cerebro/documentos, manual]
---
# Se o robô parar: manual de incidentes

> Para qualquer pessoa da equipe (João, Clara, Cristian, Bernardo) e para o Claude.
> Escrito para ser seguido com pressa: **um passo de cada vez, e confira se funcionou antes do próximo.**

| Campo | Valor |
|---|---|
| Última conferência | 19/10/2026 |
| Dono | João (DESKTOP-GA8IJAU, PC principal) |
| Revisar | depois de todo incidente grave (G1 ou G2) |
| Onde aparecem os alarmes | Painel → caixinha de avisos no canto e **Monitoramento** · tela **Máquinas** |

## Lista rápida (comece aqui)
- [ ] 1. **Leia o aviso do Painel** e ache o card dele abaixo (o texto do Painel está entre aspas).
- [ ] 2. **Robô fazendo coisa errada** (e-mail duplicado, remetente errado, e-mail para hóspede)? → **[[#G1 · Desligar o robô agora]]**.
- [ ] 3. Veja a **gravidade** do card e avise a equipe com o [[#Aviso para a equipe|modelo]].
- [ ] 4. Siga os passos do card, **conferindo cada um**.
- [ ] 5. Não resolveu no tempo do card? → [[#Quem chamar]].
- [ ] 6. Resolvido: anote em [[Problemas resolvidos]] (sintoma, causa, correção).

## Gravidade
| Nível | O que é | Agir em | Exemplo |
|---|---|---|---|
| **G1** | Robô fazendo **errado** ou credencial vazada | **na hora** | E-mail duplicado, remetente errado, chave no GitHub |
| **G2** | Pedidos **parados** (nada sai ou nada entra) | 30 min | Robô de envio parado, Caixa de Saída travada, Outlook fechado |
| **G3** | Um pedaço parado, sem perder pedido | 2 h | Painel não abre num PC, robô de um PC parado |
| **G4** | Incômodo, sem efeito no hóspede | próximo dia útil | PC em outra versão, Mail Analytics atrasado |

---

## G1 · Desligar o robô agora
**Quando:** o robô está mandando e-mail duplicado, da caixa errada, para um hóspede ou qualquer coisa estranha.
1. Abra a **Planilha Central** → aba **Status** → **desmarque a caixa B1 ("Robô ligado?")**.
2. **Confira:** na próxima volta (até 10 min), o log diz `⏸️ Robô DESLIGADO no painel`. Nada mais é enviado.
3. Avise o João e anote **o que viu, a hora e o hotel** (sem copiar CPF nem e-mail do hóspede).
4. Só religue (marcar B1) depois de o João e o Claude acharem a causa.

> Desligar é seguro: o robô anota antes de enviar e confere em Itens Enviados, então **nada se perde e nada sai duas vezes** quando religar.

## G1 · Suspeita de credencial vazada
**Quando:** a chave do Google, uma senha ou um token apareceu no GitHub, num print, num e-mail ou num log.
1. **Não** copie nem repasse o valor. Avise o João na hora.
2. O João troca a credencial na origem (Google Cloud → conta de serviço → nova chave; apagar a antiga). Onde cada uma fica: [[Credenciais]].
3. O Claude tira o arquivo do repositório e confere se a trava pegaria da próxima vez (`testes/test_segredos.py`, `ferramentas/checar_commit.py`).
4. **Confira:** o robô volta a ler as planilhas com a chave nova (Monitoramento sem erro de Google).

---

## G2 · "O robô de envio não roda desde …"
**Impacto:** solicitações novas **não vão para os hotéis**.
1. No **PC do João**, a tarefa `SolicitacoesNF_CopiaHoteis` está ligada? (Agendador de Tarefas → Biblioteca). Se estiver desativada, **ative**.
2. A aba **Status → B1** está marcada? Se não, alguém desligou: pergunte antes de religar.
3. Abra `logs\solicitacoes_nf.log` e procure as últimas linhas com ❌.
4. Para ver tudo na tela: `Bat\executar_robo.bat` (**só no PC do João**; nos outros PCs a regra é nada de .bat).
5. Existe `FALHA_CRITICA.txt` na pasta do projeto? O robô nem iniciou: mande o arquivo para o Claude.
6. **Confira:** em até 10 min o aviso some e o Monitoramento mostra a hora nova do robô.

## G2 · "A cópia dos hotéis não roda desde …"
**Impacto:** formulários novos **não entram na Central** (e por isso não são enviados).
1. Mesmos passos 1 a 3 do card acima (é a mesma tarefa: copia e depois envia).
2. Erro de Google no log ("quota", "429", "PERMISSION_DENIED")? Cota: espere 2 min, ela volta sozinha. Permissão: a planilha do hotel deixou de estar compartilhada com a conta do robô (veja [[Credenciais]]).
3. **Confira:** aviso some em até 35 min. Menu da Central → 🔍 **Conferir Cópia dos Hotéis** mostra tudo copiado.
> Já aconteceu: 11/10/2026 (função com argumento a mais) e 15/10/2026 (formulário novo noutra planilha). Ver [[Problemas resolvidos]].

## G2 · "N pedido(s) de formulário sem envio ao hotel há mais de 2 h"
**Impacto:** esses hóspedes estão esperando.
1. Veja os avisos de **robô de envio** e **cópia** acima: quase sempre a causa é um deles.
2. Se o robô está rodando e só esses hotéis ficaram, veja o hotel no Monitoramento:
   - **"robô antigo ativo"**: o robô novo espera até 75 min para não enviar em dobro. Passou disso, avise o Claude.
   - **PC dono da caixa desligado**: o e-mail sai **só** do PC dono da caixa do hotel. Ligue o PC dono e abra o Outlook dele.
3. **Nunca** reenvie à mão pela caixa do Ondina: o remetente é sempre a caixa do próprio hotel ([[O que não mexer]]).
4. **Confira:** os pedidos ganham TRUE na coluna Enviado e o aviso some.

## G2 · "Caixa de Saída do Outlook de X travada"
**Impacto:** e-mails já "enviados" pelo robô ou pelo Painel **não saíram de verdade**.
1. No PC de X, abra o Outlook → **Caixa de Saída**. Aperte **F9** (Enviar/Receber).
2. Ainda parado? Veja se a internet está ok e se o Outlook pede senha (janela escondida atrás).
3. Se o provedor estiver fora (vários PCs travados ao mesmo tempo), **espere**: já aconteceu em 15/10/2026, das 11:28 às 12:34, e saiu sozinho.
4. **Não apague** nada da Caixa de Saída: o robô não reenvia o que está lá (é assim que ele evita duplicar).
5. **Confira:** a Caixa de Saída esvazia e o aviso some em até 2 min.

## G2 · "Outlook fechado no PC de X" / "aberto sem janela"
**Impacto:** o robô não lê as caixas desse PC; **sem janela, o Outlook não baixa e-mail** (contas POP3).
1. No PC de X: feche o Outlook (se estiver aberto sem janela, pelo Gerenciador de Tarefas → `OUTLOOK.EXE`).
2. Abra o Outlook **pelo ícone** e aperte **F9**.
3. O guardião (`outlook_vivo.py`) tenta sozinho a cada 60 s; se o aviso continuar por mais de 5 min, faça os passos acima.
4. **Confira:** o aviso some e os e-mails novos aparecem no Painel.
> Já aconteceu: 13/10/2026, PC do Cristian 4 dias sem receber (Outlook sem janela). Ver [[Problemas resolvidos]].

## G2 · "Nenhum e-mail novo chega ao Outlook de X desde …"
**Impacto:** pedidos por e-mail desse PC **não aparecem**.
1. No PC de X: Outlook → **F9**. Veja a barra de baixo ("Enviando/Recebendo", erro de senha).
2. Faça o card **Outlook sem janela** acima.
3. **Confira:** e-mails novos entram e o aviso some.

---

## G3 · "Robô do PC de X parado (sem conferir o Outlook há mais de 10 min)"
1. O PC de X está ligado e com alguém logado? (As tarefas só rodam com o usuário logado.)
2. A tarefa `SolicitacoesNF_Conferente` está ligada nesse PC?
3. Reiniciar o PC resolve na maioria das vezes (a tarefa sobe ao entrar no Windows).
4. **Confira:** o aviso some em até 10 min.

## G3 · Painel não abre, tela branca ou código aparecendo
1. Feche a janela do Painel e abra de novo pelo atalho.
2. No PC do João: `ATUALIZAR_PAINEL.bat` (deixa igual ao GitHub e reinicia). Nos outros PCs: botão **"Atualizar todos os PCs"** em Máquinas, do PC do João.
3. Código aparecendo embaixo da tela = página lida pela metade durante uma atualização: ela recarrega sozinha; se não, feche e abra.
4. **Confira:** o Painel abre e o rodapé mostra a mesma versão dos outros PCs.

## G3 · "Cadastro incompleto: … sem cadastro"
**Impacto:** as planilhas desses hotéis **não são copiadas**.
1. Planilha Central → **Cadastro_Hoteis**: falta a linha do hotel (ou o nome da aba não bate com o da planilha).
2. Peça ao João para cadastrar (é ele quem decide agente e caixa do hotel).
3. **Confira:** o aviso some na próxima volta (até 10 min).

---

## G4 · "PC de X rodando outra versão"
- No PC do João: **Máquinas → "Atualizar todos os PCs"**. Confira em Máquinas se todos ficaram na mesma versão.
- Atualização falhou? O atualizador nunca apaga mudança feita à mão: ele para e avisa. Chame o Claude.

## G4 · "Mail Analytics: a planilha não tem dados de X desde …"
- **Não mexa** no Mail Analytics (nem código, nem planilha). Só avise o João: o relatório da semana fica incompleto até ele normalizar.

## G4 · Busca ao vivo não acha o PC da Clara
- Conhecido: o PC dela está noutra faixa de rede (10.80.x) e o firewall só aceita a mesma faixa. Os envios dela vão pela fila da Central (plano B), então **nada se perde**. Para a busca voltar, alguém com administrador amplia a regra (`Automacoes/liberar_rede.ps1`).

---

## Voltar uma versão (quando a atualização quebrou)
1. Se o robô está fazendo errado: **primeiro** [[#G1 · Desligar o robô agora]].
2. Peça ao Claude para **desfazer o último commit com um commit novo** (`git revert`), nunca apagando histórico. A guarda do git do Claude bloqueia `reset --hard` e push forçado de propósito.
3. Enviar para as 4 branches e **"Atualizar todos os PCs"**.
4. **Confira:** todos os PCs na versão nova (a do revert) em Máquinas, e o aviso que causou a volta sumiu.

## Quem chamar
| Ordem | Quem | Quando |
|---|---|---|
| 1 | Agente do PC com o aviso | Passos do card no próprio PC (Outlook, F9, reiniciar) |
| 2 | **João** | Passou do tempo do card, precisa de planilha/cadastro/tarefa, ou é G1 |
| 3 | **Claude** (no PC do João; nos outros PCs pela sessão Remote Control) | Erro no log, `FALHA_CRITICA.txt`, código ou atualização |
| — | Administrador do Windows | Firewall, regra da porta 8766, coisas que pedem senha de admin |

## Aviso para a equipe
Mande no grupo assim que achar o card, e de novo a cada 30 min até resolver (mesmo sem novidade):

```text
[G2] Robô de envio parado desde 14:10
O que acontece: pedidos do formulário não estão indo para os hotéis
Quem é afetado: todos os hotéis
O que estamos fazendo: conferindo a tarefa no PC do João
Próximo aviso: 14:50
```

Quando resolver: `[RESOLVIDO] … voltou às 14:35. Causa: …` e anote em [[Problemas resolvidos]].

## Regras que valem mesmo com pressa
- Nunca mandar e-mail a hóspede por conta própria; teste só para `joaocarlossilvazeroum@hotmail.com`.
- Nunca copiar CPF, e-mail ou nome de hóspede para o grupo ou para o Claude sem necessidade.
- Planilhas dos hotéis e Mail Analytics: **só leitura**.
- Não abrir e-mail **não lido** para "testar" (vira lido para a equipe toda).
- Nunca apagar `estado/`: é a memória do robô (o que já foi enviado).

Voltar: [[00 Início]] · Ver também: [[README técnico]] · [[Problemas resolvidos]] · [[Instalação e pendências]]
