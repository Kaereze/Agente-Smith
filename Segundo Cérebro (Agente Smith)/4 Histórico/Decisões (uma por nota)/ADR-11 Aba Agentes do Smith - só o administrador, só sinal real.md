---
tipo: decisao
pasta: "4 Histórico"
pai: "[[Decisões]]"
tags: [cerebro/historico, decisao]
---
# ADR-11 Aba Agentes do Smith: só o administrador, só sinal real

**Data:** 28/10/2026 · **Quem decidiu:** João

## Contexto
O João quis ver, dentro do Painel, o mapa de **todas** as ferramentas do projeto e o que cada agente está fazendo, numa aba só dele chamada "Agentes do Smith".

## Decisão
- A aba fica no grupo Admin e só aparece para o João no PC principal (mesma regra do Monitoramento). O servidor também recusa quem tentar por fora, e o mapa não sai pela lista pública de arquivos.
- O mapa mostra tudo (62 módulos de `src/`, `Automacoes/`, `Bat/`, interface, testes, arquivos de cada PC) e abre com o caminho de produção de ponta a ponta aceso.
- O estado ao vivo **só mostra o que o Painel já sabe de verdade**. O resto aparece como "sem sinal ao vivo". Sem estado inventado.
- Visual: mesmos ícones de linha do Painel, **sem emojis** (houve um engano com emojis, trocado); os agentes ficam atrás de um botão pequeno no canto do mapa.
- Um teste falha se um módulo novo de `src/` ficar fora do mapa.

## Consequências
Hoje há sinal real para 8 dos 19 agentes. Medir os outros pede que cada um publique um sinal próprio (próxima entrega). O gerador do mapa ainda não está no repositório: módulo novo entra no `mapa.html` à mão. Ver [[Mapa visual do sistema]] e [[Designs]].
