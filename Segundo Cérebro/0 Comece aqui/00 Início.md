---
tipo: guia
pasta: "0 Comece aqui"
atualizado: 2026-10-21
tags: [cerebro/inicio]
---
# Segundo Cérebro — Projeto Notas Fiscais

> A memória do projeto: o João tem as ideias, o Claude programa, os dois leem e escrevem aqui.
> Fica dentro do repositório `Kaereze/Notas-Fiscais` (todas as branches) e chega a qualquer PC pelo clone. Cores: [[Legenda de cores]].

## Ordem de leitura (Claude: sempre nesta ordem)
1. **Esta página** → onde paramos.
2. [[Hierarquia de prioridades]] → o que vence quando duas coisas brigam.
3. [[O que não mexer]] e [[Credenciais]] → proibições e onde ficam as chaves (nunca o valor).
4. [[Onde mexer]] → a tarefa aponta o arquivo e a função. **Só então** abrir o código.
5. Ao terminar: [[Como entregar]] e atualizar o cofre ([[Como usar este cérebro]]).

## Onde paramos (22/10/2026)
- 22/10 (noite): **todos os designs no cofre**: [[Designs]] (prévia de cada um, link para abrir, o que o João escolheu e
  em que versão entrou), o catálogo de peças com a ferramenta para refazer ([[LEIA-ME (catálogo)]]) e o catálogo antigo
  em fotos. Pendente do João: medir o atraso do Drive (cópia rápida, opção A).
- 22/10 (tarde): **marcar ligação** no ar (2026.10.22.7): botão Ligação no envio, etiqueta e filtro em Itens Enviados,
  cartão na Visão geral; e a pasta **Itens Enviados voltou a listar** (vazia desde 11/10). Antes: barra de rolagem da
  lateral (2026.10.22.6). Pedidos do João para depois: desenhos de cada animação do projeto, por página; medir o atraso
  do Drive para a cópia rápida (pedidos em 10-20 s, opção A). Ver [[2026-10-22]].
- 22/10 (fim da manhã): **tela do robô v3** no ar (2026.10.22.4): janela grande no lugar da aba Robô e da tela de Log. Falta "Ligar" e "Pausar" (só João). Ver [[2026-10-22]].
- 22/10 (manhã): **Itens Enviados com 72 h** (2026.10.22.1) e **aba Robô etapa 1** + usuário João só no PC dele (2026.10.22.2). Falta o chip em segundo plano e o "Ver registro". Ver [[2026-10-22]].
- 22/10: **aviso de envio em pílula** no ar (2026.10.22, `f070aa6`); notas e apresentação enviadas ao GitHub para o PC de casa. Ver [[2026-10-22]].
- 21/10: versões 2026.10.21 a **2026.10.21.5** nos 4 PCs: etiquetas e resumo fixo do hóspede, aviso de pedido repetido,
  tela que não trava (fila do servidor 128, F5), "NF emitida" respeita o nº da estada, janelas por cima no cinza com
  animação nova. **Documentação oficial** em PDF e PowerPoint: [[Apresentação do projeto]]. Ver [[2026-10-21]].
- 21/10 (fim do dia): **velocidade no ar nos 4 PCs (2026.10.21.6, `3f43103`)** (envio direto pela rede,
  e-mail novo e NF do Dropbox na hora, tela só com o que mudou, documentação sem reiniciar + 2 riscos antigos de e-mail
  duplicado consertados). PDF da apresentação com a seção 11 "Velocidade: antes e depois". Ver [[2026-10-21]].
- 20/10: **Prévia 5 no Painel** (Outlook escuro, e-mail e formulário idênticos ao Outlook, pesquisa instantânea, envio sem espera). Como usar: [[Guia do Painel Fiscal]]. Falta o OK do João para o índice local e o envio direto pela rede ([[Ideias e pendências]]).
- 20/10: decisões de LGPD feitas (recomendação do Claude): saída da cópia gira em 5 MB, simulações velhas apagadas, espaço temporário limpo. Achado: log disputado (14 mil "Logging error"), conserto proposto em [[Ideias e pendências]]. Ver [[2026-10-20]].
- 19/10: travas de empresa no repositório: testes automáticos no GitHub a cada push, pre-commit que barra credenciais e `estado/`, guarda do git no Claude Code e README novo. Depois: manual [[Se o robô parar]], [[Dados de hóspedes (LGPD)]] (dados reais tirados do repositório; 6 decisões esperam o João), CHANGELOG com versões por data e ruff. Ver [[2026-10-19]].
- 15/10: robô copia e envia **a cada 10 min**, marca TRUE também na planilha do hotel, **junta as planilhas do formulário
  antigo e do novo** e manda o e-mail **pelo PC dono da caixa do hotel** (nunca mais pela caixa do Ondina). Versão `68b0539`
  nos 4 PCs. Ver [[2026-10-15]].
- GitHub e PC do trabalho na mesma versão (4 branches iguais). Painel e robô no ar.
- Modo casa pronto ([[Painel em casa]]); falta o João criar a chave de casa.
- 13/10: Guardião do Outlook nos 4 PCs; Dia do administrador concluído (busca ao vivo entre os 4 PCs funcionando).
- Commit do PC de casa (`1dbdac4`, conserto do modo demonstração) ainda **não enviado**: vai para a branch `casa`, o Claude revisa e junta.
- O que fazer a seguir e o que espera decisão: **[[Ideias e pendências]]** (lista única).

## As pastas do cofre
> [!cat-inicio] 0 Comece aqui
> [[00 Início]] · [[Como usar este cérebro]] · [[Legenda de cores]]

> [!cat-regras] 1 Regras — o que vence e o que não se mexe
> [[Hierarquia de prioridades]] · [[O que não mexer]] · [[Credenciais]] · [[Padrão de design]]

> [!cat-trabalho] 2 Como trabalhar — passo a passo
> [[Onde mexer]] · [[Como entregar]] · [[Painel em casa]] · [[Dia do administrador]]

> [!cat-mapa] 3 Mapa do projeto — como o sistema é
> [[Visão geral do projeto]] · [[Pastas e arquivos]] (+ uma nota por pasta) · [[Planilhas e abas]] · [[API do Painel]] · [[Pessoas e PCs]] · [[Glossário]]

> [!cat-historico] 4 Histórico — por que é assim
> [[Marcos do projeto]] · [[Decisões]] · [[Problemas resolvidos]] · `Diário/` (um arquivo por dia)

> [!cat-andamento] 5 Em andamento
> [[Ideias e pendências]] · rascunho do guia de design (`guia-painel-fiscal.html`)

> [!cat-docs] 6 Documentos — guias longos
> **[[Apresentação do projeto]]** (PDF + PowerPoint) · **[[Designs]]** (todos os designs e o catálogo de peças) · **[[Guia do Painel Fiscal]]** (cada tela) · **[[Se o robô parar]]** (manual de incidentes) · [[Dados de hóspedes (LGPD)]] · [[README técnico]] · [[Instalação e pendências]] · [[Exemplos de e-mail]]
