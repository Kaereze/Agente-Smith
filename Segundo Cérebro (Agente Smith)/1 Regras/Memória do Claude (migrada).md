---
tipo: regra
pasta: "1 Regras"
pai: "[[00 Início]]"
prioridade: P1
atualizado: 2026-10-28
tags: [cerebro/regras, memoria]
---
# Memória do Claude (migrada para o cofre em 28/10/2026)

> A memória do Claude fica **só no PC onde a sessão roda** e some em casa ou em outro PC. Tudo o que ela guardava está aqui, para valer em qualquer sessão. Cada item diz se **ainda vale**. As regras mais fortes também estão em [[Preferências do João]] e [[Hierarquia de prioridades]].
> **Regra daqui para a frente:** o que o Claude aprender e importar para a próxima sessão vai **para o cofre** (esta nota, uma nota de decisão ou o manual), não só para a memória.

## 1. O projeto (23/09/2026)
- O João é do financeiro da **Rede Andrade** (~73 hotéis). O robô novo "Solicitações NF" lê as solicitações do Google Sheets (uma aba por hotel, coluna **Enviado**), e manda o e-mail do formulário pela caixa do hotel. Substituiu um Apps Script que estourou a cota do Gmail.
- **Regra de ouro:** nunca alterar o **Mail Analytics** (produção nos 4 PCs). Só ler.
- **Fluxo (vale hoje):** a Planilha Central é a principal. As respostas caem nas planilhas dos hotéis; a tarefa do Windows copia para a Central e roda o robô de envio **a cada 10 min**. A cópia junta as planilhas do formulário antigo e do novo numa aba só. O destino é o e-mail do próprio hotel. Desde 15/10/2026 (autorizado) o robô também marca **TRUE na coluna Enviado** da planilha do hotel depois do envio confirmado; o resto das planilhas dos hotéis é só leitura. O painel liga/desliga é a caixa "Robô ligado?" da aba Status.
- Chave do Google: pasta própria (`%APPDATA%\SolicitacoesNF`). Reusar a chave do Mail Analytics foi **bloqueado** (decisão do João).
- Os campos "[PREENCHER]" (conta remetente, e-mail de teste, coluna "Dividida em quantas") o João informa ao longo do projeto: não perguntar de novo.
- Ver [[Visão geral do projeto]] e [[Planilhas e abas]].

## 2. O Painel é um espelho do Outlook (08/10, 11/10, 20/10/2026)
- O Painel **não guarda histórico**: quem guarda é o Outlook e as planilhas dos hotéis.
- **Caixa de Entrada** = a Caixa de Entrada inteira do Outlook dos 4 PCs, menos respondidos e solicitações do robô. Filtro por agente (abre no agente do PC). Respondido ou enviado fica cinza por segundos e **some**.
- **Notas fiscais** = só as solicitações do robô que estão na Caixa de Entrada. O João trabalha **tirando o e-mail da caixa** quando resolve ([[ADR-02 O Painel nunca tira nem apaga e-mail da entrada sozinho]]).
- **Lido:** abrir no Painel marca lido no Outlook; o lido do Outlook só vai ao Painel após 5 min; excluído no Outlook some na hora.
- **Excluir:** qualquer um, com confirmação e Desfazer de 10 s. Sem botão "Assumir" (cada um faz as suas notas).
- **Urgência:** mais de 7 dias sem resposta ou pedido de correção. Aviso do Windows só quando entra em Urgência.
- **Faxina na Central:** registros 3 dias, atividade do robô 7 dias ([[Dados de hóspedes (LGPD)]]).
- **Busca:** em 20/10/2026 o João aprovou o **índice local** (12 meses, em cada PC, nada no Google), que responde na hora, e o Outlook ao vivo só para conferir. Também aprovou o **envio direto pela rede** ao PC dono, com a fila da Central como reserva. Mudança de 28/10: a caixa de busca guarda as últimas 24 h ([[ADR-04 Histórico de pesquisa de 24 horas, só no navegador de cada PC]]).
- **Maior medo do João:** estourar a cota do Google (60 leituras/min somando os 4 PCs) e a "bola de neve" de dados nos PCs. Nada novo pode acumular sem prazo; toda leitura do Google conta.
- Tomar cuidado: nunca abrir e-mail **não lido** no Painel real em teste.

## 3. Entrega e design (11/10 a 23/10/2026)
- Depois de cada processo: testes, commit, push na `main` e as 3 branches iguais ([[Manual do Claude (receitas)]] R4). **Superado em 27/10:** antes todo commit chegava aos PCs; agora só **versão com etiqueta** ([[ADR-01 PCs só atualizam com versão etiquetada]]).
- Depois de cada ajuste visual, mandar ao João capturas **com zoom** do que mudou (ele nem sempre está no PC do trabalho). Todo processo tem log; todo botão que dispara algo mostra o que está acontecendo; sempre ter fallback se algo falhar em silêncio.
- **Estilo:** painel de setor financeiro, sóbrio e padronizado em todas as telas (mesma letra, card, aba, seleção, tabela, cor); sem cor por operador, sem emoji, sem avatar; listas em colunas alinhadas; números com % e comparação honesta; animação discreta; entendível por quem não é de TI; **rápido** (a equipe usa o dia todo, ao telefone). Cantos de 6 px; IBM Plex Sans e Mono para números. O Painel será apresentado a uma empresa grande.
- **Regras por tela (14/10/2026):** usuário primeiro (nada de códigos de máquina na tela); menu da esquerda recolhível; tema escuro primeiro; **Visão geral** abre no dia anterior; **Gerência** com dados do Mail Analytics (só leitura) comparando **mês × mês anterior**; lista de Notas fiscais com nome, hotel, agente e prazo; **etiquetas só de urgência, nota dividida e falta de dado**; botão **"Pedir o que falta"** (abre a mensagem padrão pronta); urgência = prazo perto de vencer ou hóspede cobrou de novo; conferência do envio só aparece quando tem problema; uma tela **Monitoramento** só para o administrador. Para emitir é preciso nome + CPF + o que entra na nota (diárias, consumo ou estacionamento).
- **15/10 e 20/10:** o layout do Outlook (barra fina, abas Página Inicial, Enviar/Receber, Exibir) vale para **todas** as páginas; a ficha mostra sempre tomador, CPF/CNPJ, o que pede, hóspede e CPF do hóspede; o formulário abre numa tabela Campo/Valor; **abrir um e-mail tem de ser instantâneo**; a Prévia 5 (Outlook escuro, cinzas e azul `#479ef5`, Segoe UI) foi aplicada "exatamente". O João insiste: **cuidado com o espaçamento** e a divisão das informações.
- **Paleta de hoje:** a da Auditoria, **sem verde** ([[ADR-03 Telas novas na paleta da Auditoria, sem verde]]).
- **Os dois PCs do João:** o do trabalho (`DESKTOP-GA8IJAU`, onde a sessão roda) e o de casa (modo demonstração, sem chave do Google, sem Outlook). `git pull` antes de começar e push no fim.
- **Designs ficam no cofre:** `6 Documentos/Designs` + prévia + índice [[Designs]] (e-mails só "exemplo", telefone `(00) 0000-0000`, CPF zerado).

## 4. Como o João quer trabalhar
- **Português do Brasil, simples**, inclusive relatórios finais (em 14/10 uma resposta saiu em inglês e ele pediu "TRADUZ").
- **Design primeiro, depois a confirmação** (20/10/2026): "nunca altera nada sem antes minha confirmação, mesmo que eu peça pra fazer". **Qualquer dúvida, mesmo mínima, pergunte**, dizendo se é possível. (Origem: a versão 2026.10.20.15 foi aos 4 PCs antes de ele ver o resultado.)
- **Envio pelo PC dono (15/10/2026):** o e-mail do robô sai **sempre da caixa do próprio hotel**, no PC que a tem no Outlook; a caixa do Ondina do João só manda e-mail de teste; PC dono desligado = espera, **nunca** cai no Ondina.
- **Dado real nunca em arquivo** ([[ADR-05 Dado real nunca em testes nem documentos]]).

## 5. Ideias e o que aconteceu com elas
| Ideia | Situação em 28/10/2026 |
|---|---|
| **Ficha-resumo** no e-mail (tomador, hóspede, estadia, como quer a nota, situação, histórico por regra, sem IA) | **Feita** em 12/10 a 21/10 (resumo fixo e etapas, opção C de 28/10) |
| **Aba de correção da NF**: e-mail com tag "Pedido de correção" abre numa aba própria para verificar a correção (ex.: hóspede com 2 NFs, uma errada) | **Em aberto**: só anotada, **esperar o João explicar** antes de codar. Hoje existe a verificação da NF no e-mail e "Pede nova nota" |
| **Marcar ligação** (telefone é cabo LAN, a marca é manual): botão "Ligação" no envio, etiqueta, filtro, botão direito em Itens Enviados, cartão na Visão geral; só conta quando sai um envio; sempre começa desligado | **Feita** em 22/10/2026 (aba `Ligacoes`, 400 dias). Pendentes: desenhos de **cada animação por página** e medir o atraso do Drive |
| **Tela do robô v3** (janela grande no lugar da aba Robô e do Log) | **Feita**; "Ligar" e "Pausar" feitos em 27/10 ([[ADR-08 Ligar e pausar o robô só pelo usuário João, com confirmação]]). Dúvida aberta: "impedir os outros PCs de trocar de usuário" foi feito como "não podem virar João"; confirmar se ele quis dizer "de jeito nenhum" |
| **Visão empresarial** (20/10 e 23/10): sistema interno de controle do financeiro (entra e sai, NF emitidas, cancelamentos, substituições, faturamento, contas a pagar, caixa); gerente pergunta "quantos e-mails, quantas notas" e aparece num clique; usuários gerente e operador; Supabase no futuro; peças únicas (cada botão existe uma vez); ser sincero como engenheiro sênior sobre os limites | **Virou o [[Plano até dezembro]]** |

## 6. O que é do cofre
- O cofre fica **dentro do repositório** (todas as branches). Fim de cada etapa: diário, "Onde paramos", decisões, erros resolvidos ([[Como usar este cérebro]]). Desde 28/10 o nome é **Segundo Cérebro (Agente Smith)** ([[ADR-10 O cofre se chama Segundo Cérebro (Agente Smith)]]). Nunca guardar segredo.
