---
tipo: decisao
pasta: "4 Histórico"
pai: "[[Decisões]]"
tags: [cerebro/historico, decisao]
---
# ADR-09 A tela de carregamento (K) trava a tela inteira enquanto a ação roda

**Data:** 28/10/2026 · **Quem decidiu:** João

## Contexto
O João pediu uma tela só, com a logo K desenhada, para qualquer ação demorada, e que nada possa ser clicado até acabar.

## Decisão
Ação acima de 3 s (o Enviar/Receber, na hora) mostra o K em aquarela no meio e **bloqueia cliques e atalhos** até terminar, certo ou com erro. Segurança: se a ação não responder em 90 s, deixa de travar.

## Consequências
O cartãozinho do canto (barra, tempo, PCs) fica clicável. Ver [[Padrão de design]].
