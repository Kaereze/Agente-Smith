---
tipo: documento
pasta: "6 Documentos"
pai: "[[00 Início]]"
prioridade: P0
tags: [cerebro/documentos, lgpd]
---
# Dados de hóspedes (LGPD)

> Onde ficam o nome, o CPF e o e-mail dos hóspedes, por quanto tempo e quem vê.
> Revisão feita em 19/10/2026 com as skills `gdpr-data-handling` e `security-and-hardening`. Regra que manda: [[Hierarquia de prioridades]] (P0).

## Por que a rede pode usar esses dados
A base legal é a **obrigação legal** e a **execução do contrato**: para emitir a NF, o CPF/CNPJ e o nome do tomador são obrigatórios. O e-mail serve para mandar a nota.
Por isso **não** precisa de consentimento, mas o uso fica **só para emitir e mandar a NF**. Nada de marketing, nada de relatório com nome de hóspede.
CNPJ e nome de **empresa** não são dado pessoal (a LGPD protege pessoa física).

## Onde os dados ficam
| Onde | O quê | Por quanto tempo | Quem vê |
|---|---|---|---|
| Planilha do formulário de cada hotel (Google) | Tudo o que o hóspede digitou | Sem limite (é a origem; quem decide é o hotel) | Hotel + robô (só leitura) |
| Planilha Central, abas "(respostas)" | Cópia das planilhas dos hotéis | Igual à origem | Equipe fiscal + robô |
| Central, aba Tratamento | NFs, para quem foi, avisos | Detalhe 3 dias, depois vira resumo; sai inteira com 150 dias (`faxina.py`) | Equipe + robô |
| Central, `Correio_<PC>` / `CorreioTexto_<PC>` | Espelho da caixa de entrada (remetente, assunto, texto) | Reescritas a cada volta, janela de 14 dias | Equipe |
| Central, `Envios_NF` / `Envios_NF_Anexos` / `Eventos_Correio` | Fila de envio, anexos, lido/excluído | 3 dias (`faxina.py`) | Equipe + robô |
| Outlook de cada PC | E-mails dos hóspedes e as NFs enviadas | Regra do Outlook de cada PC | Dono do PC |
| `estado/backup_central_*.json` (PC do João) | Cópia da Central para recuperar erro | 24 h (144 cópias, `sincronizar._limpar_backups_antigos`) | Só o PC |
| `estado/backup_tratamento_*.json` (PC do João) | Cópia do Tratamento antes da faxina | Últimos dias (`faxina._backup`) | Só o PC |
| `logs/solicitacoes_nf.log` | Avisos do robô (às vezes hotel e e-mail) | 5 arquivos de 5 MB, giram sozinhos | Só o PC |
| `logs/saida_console_sincronizar.txt` (PC do João) | Tudo o que a cópia escreve na tela | ⚠️ **sem limite**: 30 MB desde 24/09/2026 | Só o PC |
| `logs/Historico_de_Envios.csv` | Histórico de envios (e-mails) | Sem limite | Só o PC |
| Painel Fiscal (tela) | Pedidos, e-mails, ficha com CPF | Não fica gravado: o servidor manda `no-store` e só atende `127.0.0.1` | Agente do PC |
| GitHub (`Kaereze/Notas-Fiscais`, privado) | **Nada de hóspede** desde 19/10/2026 | — | Quem tem acesso ao repositório |

## O que foi corrigido em 19/10/2026
- 4 arquivos de teste tinham **dados reais**, copiados de casos de verdade: 9 nomes de hóspedes, 5 CPFs e 1 e-mail. Um comentário do código e o rascunho do guia de design também tinham nomes reais. **Tudo trocado por dados inventados**, com os testes conferindo a mesma coisa (377 passando).
- **Trava nova** no commit (`ferramentas/checar_commit.py`): compara os CPFs do que vai subir com os CPFs reais dos backups da Central deste PC. Achou CPF de hóspede = commit barrado (o número nunca aparece na mensagem). CPF-exemplo (123.456.789-09, 111.111.111-11…) passa.
- Cópias de teste com os dados antigos apagadas do espaço temporário do Claude.

## Decisões que esperam o João
| # | O quê | Recomendação | Por quê |
|---|---|---|---|
| 1 | Os dados reais **continuam no histórico do git** (commits de 09/10 a 19/10/2026) | **Deixar** e manter o repositório **privado**, com acesso só da equipe | Apagar o histórico exige reescrever o git e forçar o envio: os 4 PCs quebrariam a atualização automática. Risco maior que o ganho, num repositório privado |
| 2 | `saida_console_sincronizar.txt` cresce sem limite | Fazer girar como o log do robô (5 arquivos de 5 MB) | Guarda texto do robô desde 24/09/2026 sem necessidade |
| 3 | `saida_simulacao/` tem 2 e-mails simulados de 24/09/2026 com CPFs reais | Apagar | Era só teste do modo simulação |
| 4 | `estado/backup_cristian_0508_*.json` (01/10/2026) | Apagar se o caso já foi resolvido | Backup avulso, fora da rotação de 24 h |
| 5 | `logs/Historico_de_Envios.csv` sem limite | Guardar só 12 meses | Histórico velho não ajuda a emitir NF |
| 6 | Espaço temporário do Claude no PC do João (capturas e planilhas de trabalho das sessões) | Limpar de tempos em tempos | Algumas capturas antigas do Painel podem ter dados reais |

## Se um hóspede pedir para ver ou apagar os dados dele
1. Responda pelo e-mail do hotel em **até 15 dias** (prazo da LGPD).
2. **Ver:** mande o que está no pedido dele (o formulário e a NF).
3. **Apagar:** a NF emitida **não pode ser apagada** (obrigação fiscal, guarda de 5 anos). O resto, peça ao **hotel** para apagar a linha do formulário: a Central copia de lá e, quando a linha some na origem, o Tratamento dela sai em 30 dias (`faxina.DIAS_SEM_SOLICITACAO`).
4. Anote o pedido (data, hotel, o que foi feito) **sem** copiar CPF.

## Regras do dia a dia
- Teste, exemplo, design e documentação: **sempre** com dados inventados (ex.: "Marina Exemplo Costa", CPF gerado). Nunca copiar caso real, nem "só para testar".
- Não colar CPF, e-mail ou nome de hóspede no grupo, no Claude ou em print, sem necessidade.
- Relatórios (quartis, contagens): só números por hotel/agente, nunca o nome de quem pediu.

Voltar: [[00 Início]] · Ver também: [[Credenciais]] · [[O que não mexer]] · [[Se o robô parar]]
