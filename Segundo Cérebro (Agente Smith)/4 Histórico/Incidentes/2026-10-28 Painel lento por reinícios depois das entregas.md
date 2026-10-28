---
tipo: incidente
pasta: "4 Histórico"
pai: "[[Incidentes]]"
tags: [cerebro/historico, incidente]
---
# Painel lento por reinícios depois das entregas (28/10/2026)

**Gravidade:** baixa · **Quem percebeu:** o João, às 09:30: "o Painel não está carregando as informações, está demorando".

## O que aconteceu
O Painel respondia rápido (página em 30 ms, dados em 70 a 430 ms), mas **reiniciou duas vezes** pela manhã (09:22 e 09:36). Cada reinício deixa uns 12 s fora do ar e uns 15 s mostrando dado antigo, e a janela recarrega.

## Causa
A pasta do projeto **é a mesma onde o Painel do João roda**. Cada commit do Claude nessa pasta faz o Painel pedir reinício sozinho ("Código novo na pasta…"). Ontem foram 19 reinícios no PC do João e 16 versões entregues (cada uma reinicia o Painel dos 4 PCs). Ainda **não comprovado**: uma volta de atualização de uns 100 s às 09:34, possivelmente trabalho pesado quando entra nota nova no Dropbox.

## O que muda
- O Claude passa a **desenvolver numa cópia separada** e a **entregar em lotes**, fora do horário de pico, avisando antes.
- Proposta aguardando o OK: registrar no log quanto leva cada volta de atualização e qual etapa demorou (aviso quando passar de 30 s).
- Ver [[ADR-01 PCs só atualizam com versão etiquetada]].
