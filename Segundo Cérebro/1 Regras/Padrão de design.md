---
tipo: regra
pasta: "1 Regras"
pai: "[[00 Início]]"
tags: [cerebro/regras]
---
# Padrão de design

**Objetivo (12/10/2026):** o Painel vai ser apresentado a uma empresa grande. Ter **um padrão fixo** em todas as telas (mesma letra, tamanho, aba, card, seleção, tabela, cor), bonito e simples, com animação discreta, tabelas, gráficos e porcentagens, fácil para quem não é de TI, e **rápido**, porque a equipe usa o tempo todo, em ligação e por e-mail.

## Valendo desde 20/10/2026: Prévia 5 (Outlook escuro)
> Aprovada pelo João ("Design ficou perfeito!" e "use exatamente esse design dentro do painel fiscal"). Prévia no quadro
> "Painel Fiscal — Repaginação", página "Prévia 5". Guia de uso: [[Guia do Painel Fiscal]].

| Item | Valor |
|---|---|
| Fundo · painéis · cartões | `#1f1f1f` · `#1f1f1f` (cantos 6 px, 10 px entre eles) · `#242424` com borda `#333` |
| Faixa de comandos | caixa `#292929`, cantos 6 px; botão passa a `#3a3a3a` ao passar o mouse |
| Texto | `#f0f0f0` · secundário `#d0d0d0` · apagado `#a8a8a8` |
| Destaque (selecionado, não lido, abas) | azul `#479ef5`; assunto e hora na lista `#6cb8f6`; selecionado `#3a3a3a` com borda `#6b6b6b` |
| Urgente | linha `#3a2326`, texto `#ff8d95`, bandeira `#e8484f` |
| Ficha do pedido | verde escuro `#1d2620`, título `#24362a`, botão principal verde `#3da755` |
| Tabela do formulário | cabeçalho dourado `#a8895c` (texto `#1d1d1d`), linhas `#262626`, bordas `#4a4a4a`, Arial 15 px |
| Letra | Segoe UI (a do Outlook), números alinhados; rótulos pequenos 11 px em maiúsculas com 0,05em |
| Espaços | leitura 20/28 px; texto do e-mail alinhado com o nome (86 px da borda); linha da lista 11 px; ficha 12/16 px |
| Animação | entrar suave (0,24 s) ao abrir e-mail; aviso de envio sobe do canto; nada anima com "reduzir movimento" do Windows |

- **Exceções vindas do Outlook** (o João pediu idêntico): círculo com as iniciais de quem mandou e o roxo dos ícones de Responder.
- Código: camada "Prévia 5 no Painel" no fim do `<style>` do `app_ui/index.html` (vence as camadas antigas).

## ~~Já decidido~~ (antes de 20/10/2026; trocado pela Prévia 5 acima)
- Paleta fiscal: grafite/cinzas + **um verde** (ação principal e selecionado); vermelho/âmbar/verde-claro **só para situação**.
- Verde no fundo + **creme** (cabeçalho de tabela, faixa do dia, selecionado).
- Letras: IBM Plex Sans (texto) e IBM Plex Mono (números). Cantos de 6 px.
- Sem cor por operador, sem emojis, ~~sem bolinhas com inicial, sem roxo~~ (20/10: só onde copia o Outlook), sem laranja/rosa.
- Cada tela: título + resumo de 1 linha → abas → filtros → conteúdo.
- Agentes em abas sublinhadas (nome + número); detalhes só ao clicar no agente.
- Avisos do sistema em 1 linha com "+N avisos".

## Em aprovação
- Rascunho do guia: `guia-painel-fiscal.html` (nesta pasta) (abrir no navegador). Seções: princípios, cores, letras (6 tamanhos), espaços, cabeçalho, abas e filtros, botões e selos, tabela, números e gráficos, ficha-resumo, vazio/carregando, o que não fazer.

Ver: [[Decisões]].

## Figma (14/10/2026)
- Arquivo **Painel Fiscal - Design** (rascunhos da conta Joao Carlos): https://www.figma.com/design/jCfxJgHjuqApxnL1ziu0ec
- Variáveis "Painel Fiscal · Cores" (24 cores) e componentes (Botão, Aba, Selo) na página Componentes.
- Telas aprovadas: **Notas fiscais** (ficha-resumo à direita) e o **seletor "Caixa de"** aberto.
- Regra: no Figma, só **dados fictícios** (é serviço externo, P0).

## Menus que abrem (20/10/2026)
- Todo menu que abre de um botão segue o **menu Filtro** da lista: fundo #2b2b2b, borda #4a4a4a, cantos 8 px; itens 9×12 px com cantos 6 px; passar o mouse #3a3a3a; escolhido #173b63 com texto branco; número à direita, 12 px, #a8a8a8 (no escolhido #cfe5fb); títulos de grupo 11 px cinza; busca escura (#1f1f1f).
- Vale para o Filtro, os menus das pílulas (`#pop`: Hotel e os outros) e o botão direito no e-mail.

## Formulário do hóspede (20/10/2026)
- Quadros por grupo (Tomador da nota · Estadia · Como quer a nota): rótulo em faixa **verde #2f6b4f** (texto #e9f6ee, 12 px 600) e valor em **creme #f6efdc** (texto #2a2418, 14 px 600); cantos 6 px; grade `minmax(160px, 1fr)` com 10 px; valor com mais de 20 letras ocupa 2 colunas; texto sempre quebra (nunca cortado). Pedido do João: "cores verdes e creme em uma tabela quadrada informando 'nome' e o nome do hóspede abaixo".
