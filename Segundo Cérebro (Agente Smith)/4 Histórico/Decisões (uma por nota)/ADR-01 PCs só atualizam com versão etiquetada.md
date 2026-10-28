---
tipo: decisao
pasta: "4 Histórico"
pai: "[[Decisões]]"
tags: [cerebro/historico, decisao]
---
# ADR-01 PCs só atualizam com versão etiquetada

**Data:** 27/10/2026 · **Quem decidiu:** João

## Contexto
Antes, todo commit virava atualização nos 4 PCs (puxam a cada 15 min; o do João reinicia em 5). Foi o tropeço de 23/10.

## Decisão
Os PCs só se atualizam sozinhos quando existe uma **etiqueta de versão** (ex.: `2026.10.28`). Commit sem etiqueta fica só no GitHub. O botão "Atualizar todos os PCs" vai ao último commit.

## Consequências
- **Nunca mover nem apagar etiqueta já publicada, nunca `push --force`:** os PCs usam `fetch --tags` e `merge --ff-only` e parariam de atualizar.
- Pasta com arquivos alterados à mão bloqueia a atualização daquele PC ("há arquivos alterados à mão").
- Entregar em lotes: cada etiqueta reinicia o Painel dos 4 PCs ([[2026-10-28 Painel lento por reinícios depois das entregas]]).
