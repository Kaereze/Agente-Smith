---
tipo: andamento
pasta: "5 Em andamento"
pai: "[[00 Início]]"
prioridade: P2
atualizado: 2026-10-28
tags: [cerebro/andamento, desempenho]
---
# Otimização e desempenho

> Pedido do João (28/10/2026): "deixar mais otimizado e fluído o meu programa". Regra que seguimos: **medir antes de mexer**, numa cópia separada, em partes, com o antes e o depois em números ([[Manual do Claude (receitas)]], R1).

## Retrato de base (28/10/2026, 15h30, PC principal, só leitura)
| O quê | Resultado |
|---|---|
| Resposta de `/api/estado` | 104 a 483 ms, **225 KB** (compactado) a cada leitura |
| Resposta de `/api/painel` | 232 a 524 ms para só 4 KB (é conta do servidor, não rede) |
| Outras respostas | `/api/correio` 63 a 100 ms (218 KB); `/api/emails` 24 a 42 ms; `/api/atividade` 10 a 389 ms; a página 8 a 24 ms (73 KB) |
| Tela no navegador | abre o menu em ~1,2 s; quase sem tarefa longa (0 a 1 em 25 s); 11 a 17 MB de memória; 1.200 a 2.500 elementos |
| Chamadas à API por janela aberta | ~30/min na Visão geral, ~34/min em Notas fiscais, ~70/min na Caixa de entrada (33/min só para buscar o texto de e-mails) |
| Pasta `estado/` | **715 MB**: ~400 MB são cache do navegador da janela (`app_edge`, `app_webview`); índice de e-mails 52 MB; logs 71 MB; 144 cópias de segurança 18 MB; dois `painel_cache*.pkl` (13 e 12 MB) |
| Memória e CPU | Painel (servidor) 169 MB em 2 processos; conferente 36 MB; Outlook 250 MB e ~7,7 h de CPU acumuladas |

**Leitura:** a tela já é leve. O peso está no **servidor** (contas repetidas a cada leitura, 225 KB reenviados mesmo sem mudança) e na **pasta de dados**. Medido em um momento só, em um PC só.

## Plano (do mais seguro ao mais arriscado)
1. **Medir** (no ar na versão 2026.10.28.3): medidor de desempenho, `/api/desempenho` e avisos no log. Deixar rodar algumas horas para ver o que pesa de verdade.
2. **Ganhos seguros** (aguardam o OK do João): limpar o cache da janela (~400 MB); trocar os `.pkl` por JSON; girar os logs; responder "sem mudança" em vez de reenviar 225 KB; guardar o resultado de `/api/painel` até os dados mudarem.
3. **Aliviar o Outlook:** agrupar ou espaçar os laços que o consultam (vigias, espelho, índice, notas achadas), só depois da medição.
4. **Interface:** separar o CSS e o JavaScript de dentro do `index.html` (3.400 linhas) em arquivos que o navegador guarda em cache.
5. **Dividir o servidor** (`app_servidor.py`, 2.500 linhas): maior ganho de manutenção e maior risco; por último.

## Como ler as medições
- No Painel real: `GET /api/desempenho` (só o administrador no PC principal) devolve, por etapa, `n`, `medio_ms`, `p95_ms`, `max_ms` e `lentas`.
- Nos logs: linhas `⏱️ Lento: <etapa> levou X s` (no máximo 1 por minuto por etapa) e, no `conferente.log`, `⏱️ Desempenho (etapas mais pesadas)` a cada 10 min.
- Medir a tela de novo: o script de medição usa o Edge sem janela, só lê e troca de tela pelo menu (não grava nada).

## Diagnóstico de fluidez (28/10/2026, 17h): "fluido = o clique responde na hora"
A régua do João: **cada ação responde no instante do clique**, porque os dados já estão no PC e o Painel só espelha. Medido no Painel real (só leitura) e no mapa (Edge sem janela; os valores absolutos de quadros por segundo são piores que num PC com placa de vídeo, a comparação entre versões vale).

| O quê | Medido | Causa (evidência) |
|---|---|---|
| Abrir o Painel do zero | menu na tela em ~0,9 s | página e fontes; dá para pintar o último estado guardado no navegador e atualizar por trás |
| Trocar de tela depois da 1ª vez | 22 a 73 ms (instantâneo) | a tela já tem os dados |
| 1ª abertura de Notas fiscais | 1,5 s para trocar, 8,8 s até os dados | `/api/correio` levou 7,4 s e até `/api/versao` (6 ms em média) esperou 4 s: o servidor está ocupado |
| Monitoramento | 2,3 s | `/api/atividade` lê o Google **na hora do clique** (média 4,7 s, pico 37 s) |
| Caixa de entrada | 2,3 s | ~33 buscas de texto de e-mail por minuto (`/api/correio/texto`, até 3,5 s) |
| Volta de leitura da Central | média 5,5 s, pico 75 s | lê e interpreta a planilha inteira a cada 15 s; clique espera na fila do mesmo processo |
| Enviar NF | a medir | `Envio.pedir` grava no Google (1 ou 2 idas e voltas) **antes** de responder e de começar a enviar |
| Mapa (Agentes do Smith) ao arrastar | 11 quadros/s | desenha ~450 linhas e 156 blocos mesmo os apagados (só esmaecidos); escondendo de verdade as linhas apagadas: 30 quadros/s; com blocos apagados mais leves: 46 |

**Conclusão:** não é a quantidade de código. São cinco causas de projeto: (1) clique que espera trabalho remoto (Google/Outlook/rede); (2) leitura completa da planilha a cada volta, disputando o mesmo processo com os cliques; (3) respostas grandes e repetidas sem "sem mudança"; (4) envio que grava no Google antes de responder; (5) mapa que desenha tudo a cada quadro.

**Regra proposta:** o clique só lê da memória. Tudo que é remoto roda por trás e a tela mostra o último valor sabido (e atualiza quando chegar).

Auditoria estática (ruff): 219 `except` largos (escondem erro), 56 funções complexas demais, 29 arquivos abertos sem `with`, 6 laços que viram compreensão de lista. Auditoria de rotas: 36 das 43 rotas têm algum caminho para trabalho remoto (é uma lista de **suspeitos**, superestima; os tempos reais acima é que valem).

### Ordem sugerida (aguarda OK do João)
1. Mapa: esconder de verdade as linhas apagadas, blocos apagados leves, pausar pontinhos e rótulos enquanto arrasta.
2. Telas do Monitoramento, Atividade e Visão geral servidas só da memória (atualizadas por trás).
3. Envio: responder na hora e gravar no Google por trás (com o diário local de envios como garantia).
4. Primeira tela instantânea: guardar o último estado no navegador e atualizar por trás.
5. Leitura da Central incremental (só o que mudou) e medir dentro de `atualizar` (ler × interpretar).
6. "Sem mudança" (ETag) nas respostas de 225 KB; texto de e-mail em lote.

## Feito em 29/10/2026 (itens 1 a 3 da ordem sugerida)
| Item | Mudança | Resultado |
|---|---|---|
| 1. Mapa | linha apagada escondida de verdade; bloco apagado leve; pontinhos e rótulos somem enquanto move | **12 → 35 quadros/s** ao arrastar (mesmo teste, navegador sem GPU) |
| 2. Monitoramento | `/api/atividade` só da memória; o laço lê o Google (`atualizar_atividade`) | clique deixa de esperar o Google (antes média 4,7 s, pico 37 s); conferir com `/api/desempenho` depois de algumas horas |
| 3. Envio | responde na hora; gravar o pedido no Google e enviar seguem por trás; falha de gravação vira "falhou" e nada sai | tempo do clique medido depois do uso real (`POST /api/envio_nf` no medidor) |

**Ainda faltam** (ordem sugerida): primeira tela instantânea (último estado no navegador), leitura incremental da Central, "sem mudança" nas respostas de 225 KB e texto de e-mail em lote. Outras ações que ainda esperam o Google no clique: marcar lido, excluir, urgência, mover para NF enviada, concluir conversa e a Gerência (`relatorio_semana`).

## Diagnóstico do travamento (29/10/2026): o amostrador achou a causa
O João: "tá muito travado". O Painel estava pior que na medição de 28/10: `/api/estado` média 1,1 s (27% das respostas acima de 1 s, pico de 66 s); volta de leitura média 9 s (pico de 217 s); conferente 31 s por volta. A CPU do PC estava baixa (nada acima de 4%), o Outlook respondia em 50 ms e não havia processo duplicado: o travamento era **espera dentro do próprio servidor**.

Amostrei o servidor e o conferente por 75 s com o **py-spy** (só observa, sem parar o processo; instalado fora do projeto em `C:\Users\Usuário\pdev_tools`; comando: `py-spy record --pid <PID> --duration 75 --gil --nonblocking --format raw`). Resultado:

| Onde | Peso (das amostras com o GIL em uso) |
|---|---|
| Servidor: laço de leitura da planilha | 52% |
| Servidor: `tratamento.normalizar` (sozinha) | 19% (a função mais pesada de todas) |
| Servidor: montar a fila por clique (`fila_da_tela`) | 15% |
| Conferente: renovar credencial do Google (assinatura RSA) | 14% |
| Conferente: `normalizar` | 18% |

**Causa:** o Python só executa um trabalho de CPU por vez no processo (o "GIL"). O laço de leitura interpretava a planilha inteira a cada volta recalculando `normalizar` para os mesmos textos, e o clique da tela esperava na fila.

**Correção (versão 2026.10.29, ainda não publicada):** lembrar o resultado de funções puras (`normalizar`, `tipo_documento`, cabeçalhos normalizados) e reaproveitar a credencial do Drive. Medido no mesmo teste (3.650 pedidos, 73 abas, dados inventados): **1.864 ms → 310 ms**. 14 testes novos. O efeito no Painel real aparece em `/api/desempenho` depois de publicar.

**Ainda aberto:** montar a fila por clique (15%); `confirmar_nfs` do conferente (31 s por volta: ler PDFs e Outlook); `faxina.rodar`, que reinterpreta todas as solicitações.

## Resultado medido depois da versão 2026.10.29 (29/10/2026, ~8 min após atualizar; mesmo teste de antes, Painel real, só leitura)
| O quê | Antes | Depois |
|---|---|---|
| Abrir o Painel (menu na tela) | 931 ms | **385 ms** |
| 1ª abertura de Notas fiscais (tela trocou / dados prontos) | 1.493 ms / 8.831 ms | **52 ms / 0 ms** |
| Monitoramento (dados prontos) | 2.284 ms | **102 ms** |
| `/api/atividade` (média, pico) | 4.399 ms, 37.045 ms | **17 ms, 53 ms** |
| `/api/estado` (média, p95, pico; respostas acima de 1 s) | 1.125 ms, 3.558 ms, 66.566 ms; 27% | **278 ms, 839 ms, 1.367 ms; 6%** |
| `/api/correio` (média, pico) | 186 ms, 7.193 ms | **140 ms, 458 ms** |
| Volta de leitura da planilha (média, p95) | 9.055 ms, 23.030 ms | 7.621 ms, 20.684 ms (ainda alta: é espera do Google, não CPU) |

Amostra pequena (26 voltas, 51 respostas de `/api/estado`). **Ainda aberto:** a Caixa de entrada leva ~2,9 s para buscar ~15 textos de e-mail em segundo plano (cada um 160 a 815 ms, ao vivo); a volta de leitura ainda leva ~6,4 s por espera do Google; envio de NF só dá para medir com uso real (`POST /api/envio_nf`).

Voltar: [[00 Início]] · Pendências: [[Ideias e pendências]]
