---
tipo: incidente
pasta: "4 Histórico"
pai: "[[Incidentes]]"
tags: [cerebro/historico, incidente, lgpd]
---
# Dado real de hóspede num commit (27/10/2026)

**Gravidade:** média (repositório privado) · **Quem percebeu:** o bloqueio automático do Claude Code, ao tentar enviar a versão seguinte.

## O que aconteceu
Ao provar o cruzamento de notas com um caso real, o Claude copiou **CPF, nome e e-mail de um hóspede** para testes e para o diário da versão 2026.10.27.12, que foi enviada ao GitHub. A versão seguinte foi barrada pelo bloqueio automático e os dados foram trocados por inventados. **A versão .12 continua com o dado no histórico do Git.**

## Causa
Para provar algo, usou-se dado real do Painel e ele foi salvo em arquivo em vez de só conferido na conversa.

## O que fizemos
- Dados trocados por inventados na versão .13.
- Nova regra: [[Preferências do João]] (só dado inventado em testes e documentos) e uma trava automática nos testes que barra CPF/CNPJ válido (feita pelo João em 27/10).
- **Decisão do João (28/10): deixar como está.** Reescrever o histórico mudaria o número interno das versões .12 e .13, e os PCs atualizam com `git fetch --tags` e `merge --ff-only`: parariam de atualizar até alguém consertar um por um. Mesma lógica da decisão nº 1 em [[Dados de hóspedes (LGPD)]]. Ver [[ADR-05 Dado real nunca em testes nem documentos]].

## O que não conseguimos conferir
Quem teve acesso ao repositório nesse período. Deve entrar no registro de incidentes da LGPD.
