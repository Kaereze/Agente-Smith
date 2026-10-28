---
tipo: decisao
pasta: "4 Histórico"
pai: "[[Decisões]]"
tags: [cerebro/historico, decisao]
---
# ADR-08 Ligar e pausar o robô só pelo usuário João, com confirmação

**Data:** 27/10/2026 · **Quem decidiu:** João

## Contexto
Faltava "Ligar o robô" e "Pausar o envio automático" na janela do robô.

## Decisão
Os botões só aparecem para o usuário João, no PC dele. Gravam a caixa "Robô ligado?" da aba Status. Pausar pede um segundo clique em 5 s.

## Consequências
Desligado = nada é copiado nem enviado, os pedidos esperam e "Enviar agora" fica travado.
