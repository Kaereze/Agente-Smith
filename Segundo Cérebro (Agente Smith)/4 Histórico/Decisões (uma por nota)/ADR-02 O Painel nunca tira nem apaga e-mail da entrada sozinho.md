---
tipo: decisao
pasta: "4 Histórico"
pai: "[[Decisões]]"
tags: [cerebro/historico, decisao]
---
# ADR-02 O Painel nunca tira nem apaga e-mail da entrada sozinho

**Data:** 27/10/2026 · **Quem decidiu:** João

## Contexto
Hóspede às vezes pede outra nota depois de receber a primeira (outro dia, consumo, estacionamento), e a tag "NF enviada" às vezes está errada.

## Decisão
Mover e-mail é **sempre um clique da pessoa**: botão **Concluir** (conversa inteira) e botão direito **Tirar da caixa de entrada** (um e-mail, mesmo já respondido). Vai para a pasta "NF enviada" da caixa do hotel, com Desfazer de 10 s. Nada é apagado. O Painel só **sugere** (destaca o Concluir) quando a NF cobre o pedido.

## Consequências
- A tag "NF enviada" não é prova: confere-se o envio nos Itens Enviados.
- Se o pedido novo não bate com a NF enviada, vira "Pede nova nota" e vai para Urgência.
- O Outlook do PC dono precisa estar aberto para mover.
