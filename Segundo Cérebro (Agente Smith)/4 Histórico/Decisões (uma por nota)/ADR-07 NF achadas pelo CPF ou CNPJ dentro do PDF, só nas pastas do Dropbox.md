---
tipo: decisao
pasta: "4 Histórico"
pai: "[[Decisões]]"
tags: [cerebro/historico, decisao]
---
# ADR-07 NF achadas pelo CPF ou CNPJ dentro do PDF, só nas pastas do Dropbox

**Data:** 27/10/2026 · **Quem decidiu:** João

## Contexto
O João queria que a nota emitida fosse reconhecida sozinha quando entra numa pasta.

## Decisão
O Painel lê o PDF novo, guarda o CPF/CNPJ do tomador e liga ao pedido ou e-mail do hóspede (inclusive e-mail sem formulário, com o documento escrito no texto). **Só sugere, nunca envia.** Só as pastas do Dropbox, notas dos últimos 30 dias (7 dias para a etiqueta "NF pronta"). PDF escaneado é lido por imagem em segundo plano. Pedido já com NF só ganha "outra nota" quando datas ou valor diferem.

## Consequências
Guarda texto das notas em `estado/nf_achadas.json` (a enxugar: ver [[Plano até dezembro]]). Ver [[2026-10-27 NF achadas nas pastas]] em [[Designs]].
