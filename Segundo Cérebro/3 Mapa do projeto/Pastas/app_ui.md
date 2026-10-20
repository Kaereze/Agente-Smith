---
tipo: pasta
pasta: "3 Mapa do projeto/Pastas"
pai: "[[Pastas e arquivos]]"
risco: azul
tags: [cerebro/pastas, risco/azul]
---
# app_ui

> [!risco-azul] Risco azul · Tela do Painel
> o que a equipe vê; mexer seguindo o Padrão de design e com capturas.

A tela do Painel (HTML, CSS e JavaScript), servida pelo `app_servidor.py`.

## O que tem dentro
- `index.html`: estrutura, todo o CSS, Notas fiscais, ficha, Professor.
- `painel.js`: Visão geral, Gerência, Máquinas, Enviar NF.
- `correio.js`: Caixa de entrada, Urgência, busca, leitura.
- `graficos.js`: gráficos.
- `fontes/`: IBM Plex (local; desde a Prévia 5 a tela usa Segoe UI, que já vem no Windows).
- `assinaturas/`: selos dos 4 agentes (PNG).
- `icone.ico/png`: ícone do app.

## Como o Claude mexe
- Seguir o [[Padrão de design]]: regra de CSS nova **no fim** do `<style>`.
- Conferir a sintaxe (`node --check`) e capturar a tela (Edge sem janela, claro e escuro).
- Mandar capturas com zoom ao João.

## Nunca
- Cor por agente, emojis. ~~Iniciais em bolinha~~: desde 20/10 só no remetente do e-mail, como o Outlook.
- Declarar no topo de um script um nome que já existe noutro arquivo da tela (derruba o arquivo inteiro; `testes/test_previa5.py` barra).
- Trocar as assinaturas sem pedido.
- Carregar fonte ou script de fora (o Painel funciona sem internet).

Voltar: [[Pastas e arquivos]] · [[Onde mexer]]
