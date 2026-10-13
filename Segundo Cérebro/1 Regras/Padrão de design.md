---
tipo: regra
pasta: "1 Regras"
pai: "[[00 Início]]"
tags: [cerebro/regras]
---
# Padrão de design

**Objetivo (12/10/2026):** o Painel vai ser apresentado a uma empresa grande. Ter **um padrão fixo** em todas as telas (mesma letra, tamanho, aba, card, seleção, tabela, cor), bonito e simples, com animação discreta, tabelas, gráficos e porcentagens, fácil para quem não é de TI, e **rápido**, porque a equipe usa o tempo todo, em ligação e por e-mail.

## Já decidido
- Paleta fiscal: grafite/cinzas + **um verde** (ação principal e selecionado); vermelho/âmbar/verde-claro **só para situação**.
- Verde no fundo + **creme** (cabeçalho de tabela, faixa do dia, selecionado).
- Letras: IBM Plex Sans (texto) e IBM Plex Mono (números). Cantos de 6 px.
- Sem cor por operador, sem emojis, sem bolinhas com inicial, sem roxo/laranja/rosa.
- Cada tela: título + resumo de 1 linha → abas → filtros → conteúdo.
- Agentes em abas sublinhadas (nome + número); detalhes só ao clicar no agente.
- Avisos do sistema em 1 linha com "+N avisos".

## Em aprovação
- Rascunho do guia: `guia-painel-fiscal.html` (nesta pasta) (abrir no navegador). Seções: princípios, cores, letras (6 tamanhos), espaços, cabeçalho, abas e filtros, botões e selos, tabela, números e gráficos, ficha-resumo, vazio/carregando, o que não fazer.

Ver: [[Decisões]].
