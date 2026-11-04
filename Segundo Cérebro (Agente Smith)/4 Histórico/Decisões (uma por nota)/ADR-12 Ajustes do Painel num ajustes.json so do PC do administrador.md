---
tipo: decisao
pasta: "4 Histórico"
pai: "[[Decisões]]"
tags: [cerebro/historico, decisao]
---
# ADR-12 Ajustes do Painel num ajustes.json só do PC do administrador

**Data:** 04/11/2026 · **Quem decidiu:** João

## Contexto
Mudar um tempo, um limite ou o texto de uma assinatura exigia pedir alteração de código, subir versão e atualizar os PCs. O João quis um jeito de **achar a chave e trocar o valor sozinho** ("chave e valor, mais fácil de localizar e alterar sem gastar tokens") e pediu que **tudo** que pode ser ajustado entre, inclusive nomes e assinaturas.

## Decisão
- Um arquivo `ajustes.json`, com 14 grupos e 177 ajustes (tempos, limites, textos, cores, assinaturas), cada um com explicação em português, mínimo e máximo.
- O arquivo fica **somente no PC do administrador** e **nunca sobe ao GitHub** (`.gitignore`). Palavras do João: "deixa somente nesse PC porque ele é o administrador de tudo".
- Valor inválido ou chave com erro de digitação **não derruba o Painel**: vale o valor de fábrica e aparece um aviso na faixa de saúde.
- O que depende de nome exato (portas, abas e colunas das planilhas, identificadores do Windows/Outlook) **não** vira ajuste. Hotéis, agentes e planilhas continuam no `config.json`.
- Mudanças valem depois de reiniciar o Painel.

## Consequências
- O ajuste vale só no PC do administrador; para mudar em **todos** os PCs, o Claude altera o valor de fábrica e publica por versão.
- O `ajustes.json` congela os valores que estiverem escritos nele (se o valor de fábrica mudar depois, ele não acompanha). `python src\ajustes.py` mostra o que foi mudado.
- Guia de uso: [[Ajustes (ajustes.json)]].

Voltar: [[Decisões]]
