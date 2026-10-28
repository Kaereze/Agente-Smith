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

Voltar: [[00 Início]] · Pendências: [[Ideias e pendências]]
