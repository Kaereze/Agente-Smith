---
tipo: decisao
pasta: "4 Histórico"
pai: "[[Decisões]]"
tags: [cerebro/historico, decisao]
---
# ADR-03 Telas novas na paleta da Auditoria, sem verde

**Data:** 27/10/2026 · **Quem decidiu:** João

## Contexto
O João viu o desenho do botão de caixas com problema em tons de verde.

## Decisão
Telas novas usam **exatamente** a paleta da página de Auditoria: cinzas neutros, azul de destaque, âmbar e vermelho. Sem verde e sem fundo esverdeado (o véu da tela de carregamento é preto translúcido).

## Consequências
As peças novas (`caixas`, `carregando`) definem as variáveis `--cp-*`. Ver [[Padrão de design]].
