---
tipo: decisao
pasta: "4 Histórico"
pai: "[[Decisões]]"
tags: [cerebro/historico, decisao]
---
# ADR-05 Dado real nunca em testes nem documentos

**Data:** 27/10/2026 · **Quem decidiu:** João

## Contexto
Um caso real foi copiado para testes e diário da versão .12 ([[2026-10-27 Dado real de hóspede num commit]]).

## Decisão
Teste, documento, diário e exemplo usam **só dados inventados**. Há uma trava automática nos testes contra CPF/CNPJ válido. O histórico da versão .12 **fica como está** (decisão do João em 28/10): o repositório é privado e reescrever quebraria a atualização dos PCs.

## Consequências
Prova com dado real: só na conversa, nunca salvo. Ver [[Dados de hóspedes (LGPD)]] e [[Preferências do João]].
