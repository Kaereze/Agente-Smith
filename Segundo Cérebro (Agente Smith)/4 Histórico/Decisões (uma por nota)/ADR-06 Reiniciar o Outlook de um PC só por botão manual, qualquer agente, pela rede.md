---
tipo: decisao
pasta: "4 Histórico"
pai: "[[Decisões]]"
tags: [cerebro/historico, decisao]
---
# ADR-06 Reiniciar o Outlook de um PC só por botão manual, qualquer agente, pela rede

**Data:** 27/10/2026 · **Quem decidiu:** João

## Contexto
Quando o Outlook trava e o e-mail não sai, o João já resolvia fechando e abrindo o Outlook à mão.

## Decisão
O botão de caixas com problema tem "Reiniciar o Outlook de [PC]", com confirmação, para qualquer PC ligado, pelo pedido assinado da rede. **Só manual**: sem reinício automático. Todos os agentes veem o botão.

## Consequências
Os três padrões foram **assumidos pelo Claude** (o João não respondeu às 3 perguntas e mandou seguir): confirmar. Risco conhecido: o pedido assinado pode ser repetido por até 2 minutos ([[Plano até dezembro]], fase de segurança).
