---
nivel: "7 · Pastas do projeto"
pai: "[[Pastas do projeto]]"
risco: azul
tags: [cerebro/pastas, risco/azul]
---
# app_ui

> [!p3] Risco azul · Tela do Painel
> o que a equipe vê; mexer seguindo o Padrão de design e com capturas.

A tela do Painel (HTML, CSS e JavaScript), servida pelo `app_servidor.py`.

## O que tem dentro
- `index.html`: estrutura, todo o CSS, Notas fiscais, ficha, Professor.
- `painel.js`: Visão geral, Gerência, Máquinas, Enviar NF.
- `correio.js`: Caixa de entrada, Urgência, busca, leitura.
- `graficos.js`: gráficos.
- `fontes/`: IBM Plex (local).
- `assinaturas/`: selos dos 4 agentes (PNG).
- `icone.ico/png`: ícone do app.

## Como o Claude mexe
- Seguir o [[Padrão de design]]: regra de CSS nova **no fim** do `<style>`.
- Conferir a sintaxe (`node --check`) e capturar a tela (Edge sem janela, claro e escuro).
- Mandar capturas com zoom ao João.

## Nunca
- Cor por agente, emojis, iniciais em bolinha (decisão de 11/10).
- Trocar as assinaturas sem pedido.
- Carregar fonte ou script de fora (o Painel funciona sem internet).

Voltar: [[Pastas do projeto]] · [[Onde mexer]]
