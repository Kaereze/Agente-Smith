# Histórico de versões

O que mudou em cada entrega do robô Solicitações NF e do Painel Fiscal, da mais nova para a mais antiga.

- **Versão = data da entrega** (`AAAA.MM.DD`), com uma etiqueta no git de mesmo nome. Segunda entrega no mesmo dia:
  `AAAA.MM.DD.1`, `.2`… (etiqueta publicada nunca é movida). O Painel
  continua mostrando o commit (ex.: `f9d21f1 19/10`) em Máquinas.
- Categorias: **Adicionado**, **Mudou**, **Corrigido**, **Removido**, **Segurança**.
- Entradas antigas não são reescritas; só se acrescenta no topo. O detalhe de cada dia fica no diário do
  [Segundo Cérebro](Segundo%20C%C3%A9rebro/4%20Hist%C3%B3rico/Di%C3%A1rio/).

## [2026.10.27.15] — 2026-10-27

### Mudou

- **Logo K desenhada como aquarela** (pedido do João: mais fluida, leve e limpa, mesma animação): antes o desenho riscava o contorno dos dois
  lados de cada traço, o que dava linhas duplas "sujas" durante o desenho. Agora a tinta cheia do K aparece por uma máscara que corre
  pelos mesmos contornos, no mesmo ritmo; a borda começa suave e levemente desfocada e vai ficando nítida, com curva de movimento mais
  macia. Sem movimento se o computador pedir menos animação. Código: `app_ui/pecas/carregando.js` e `carregando.css`.
- **A tela de carregamento trava a tela inteira enquanto a ação roda** (pedido do João): não dá para clicar em mensagem, lista, botões
  flutuantes (avisos, caixas) nem usar atalhos até a ação terminar, certa ou com erro; só o cartãozinho do canto continua clicável. Libera
  na hora ao terminar. Segurança: se a ação não responder em 90 s, a tela deixa de travar (não prende ninguém para sempre).

## [2026.10.27.14] — 2026-10-27

### Adicionado

- **Botão direito > "Tirar da caixa de entrada"** (pedido do João: a Caixa de Entrada é só dos e-mails que ainda esperam resposta): move
  ESTE e-mail para a pasta "NF enviada" da caixa do hotel, no Outlook do PC dono, mesmo que já tenha sido respondido. Some na hora
  para a equipe, tem "Desfazer" de 10 s (só depois o pedido sai) e nada é apagado. A linha cinza (já respondida) agora também abre o
  menu, só com essa ação. Sempre um clique da pessoa, nunca automático. Código: `Estado.mover_email_nf`, rota
  `POST /api/correio/mover_nf`, `tirarDaEntrada` em `correio.js` (reaproveita `envio_nf.MOVER_NF`).

## [2026.10.27.13] — 2026-10-27

### Adicionado

- **O Painel compara o histórico INTEIRO do hóspede com as notas** (pedido do João): ao abrir o e-mail, junta tudo o que o hóspede
  escreveu (texto novo e a parte citada "mensagens anteriores" de todos os e-mails dele), tira cada item pedido (serviço, valor,
  datas: "hospedagem 19 a 23/10 R$ 1.188,00", "estacionamento R$ 120,00"), acha as notas prontas nas pastas pelo CPF/CNPJ e confere
  item por item: "hospedagem → NF 1391 ✓ valor e datas conferem · estacionamento → NF 1392 ✓". Diz quando todas as notas pedidas já
  estão prontas ("falta enviar") ou o que ainda falta. Código: `nf_cobre.pedido_do_historico`/`comparar_historico`,
  `Estado._textos_do_hospede`/`nf_cobre`, `correio.js` `historicoNfHtml`. Só compara; nada é enviado nem movido.

### Corrigido

- O CPF/CNPJ que só aparece na parte citada de uma resposta agora conta (antes o Painel só lia o texto novo), e a resposta herda o
  documento dos outros e-mails do mesmo remetente. Era o caso do e-mail "Re: Nf de hospedagem e estacionamento".

## [2026.10.27.12] — 2026-10-27

### Corrigido

- **Nota nova na pasta agora aparece no próprio e-mail do hóspede (gatilho).** Na 2026.10.27.10 o cruzamento só aparecia dentro do
  Enviar NF e só para pedido do formulário: e-mail "sem formulário" (o hóspede escreve o CPF no texto) não mudava nada. Agora,
  quando o Painel lê uma nota nova das pastas do Dropbox, recalcula na hora a etiqueta "NF pronta, falta enviar · nº" dos e-mails
  (`ao_novas` → `atualizar_notas_emails`). A nota é ligada ao e-mail pelo CPF/CNPJ do tomador, que pode vir do pedido OU estar escrito
  no texto do e-mail (`documentos_do_texto`; o texto de e-mail de outro PC é buscado só para candidatos, que têm palavra do nome da
  nota, no máximo 8 por volta). Vale as notas dos últimos 7 dias. A nota achada também vira sugestão no Enviar NF do e-mail.
  Código: `nf_achadas.notas_por_documento`, `Estado._notas_por_documento`/`_documentos_do_email`.

## [2026.10.27.11] — 2026-10-27

### Adicionado

- **NF já enviada x o que o hóspede pede agora** (desenho do João): ao abrir o e-mail de um hóspede cujo pedido já tem NF, uma
  caixa "NF enviada" compara, no conjunto, o que o e-mail novo pede (datas, serviço, CPF/CNPJ e a descrição, quando o corpo pede
  uma específica) com o que o PDF da nota enviada traz (lido das pastas do Dropbox). Se algo não bate, o e-mail ganha a
  etiqueta "Pede nova nota" e vai para Urgência (na lista, só pela prévia do e-mail; ao abrir, pelo texto inteiro). Só dispara
  quando o e-mail realmente pede algo ("obrigado pela nota" nunca dispara). Tag ✅ sem envio nos Itens Enviados: avisa.
- **Botão Concluir** (sempre um clique da pessoa): move a conversa inteira do hóspede para a pasta "NF enviada" da caixa do hotel,
  no Outlook do PC dono (cria a pasta se não existir). Pede confirmação, tem "Desfazer" de 10 s e não apaga nada. Quando tudo
  bate, o Painel só destaca o botão. **O Painel nunca tira nem apaga e-mail sozinho.**
  Código: `src/nf_cobre.py`, `Estado.nf_cobre`/`concluir_conversa`/`_alertas_nova_nota`, `envio_nf.MOVER_NF`,
  `mover_para_nf_enviada_no_outlook`, rotas `/api/nf_cobre` e `/api/correio/concluir`, `correio.js`.

## [2026.10.27.10] — 2026-10-27

### Adicionado

- **NF achadas nas pastas, dentro do Enviar NF** (desenho do João): um fio em segundo plano (`src/nf_achadas.py`) olha as
  pastas de notas do Dropbox a cada 45 s (só leitura; arquivo ainda só na nuvem não é lido), lê o PDF novo (texto ou
  imagem/OCR) e guarda o CPF/CNPJ do tomador; vale também para as notas dos últimos 30 dias. Ao abrir o Enviar NF de um pedido,
  as notas cujo CPF/CNPJ bate aparecem em "Do Dropbox": uma só e confirmada já vem anexada; "outra nota" (pedido já com
  NF e nota de outras datas/valor), "possível" (o mesmo CNPJ tem outros pedidos) e várias notas (a mais nova em destaque)
  **nunca vêm marcadas**. A tag ✅ não é prova: o aviso "Marcado como enviado, mas não achei o envio…" aparece quando a NF
  da tag não está nos Itens Enviados, e a resposta do hóspede com a nota anexada não conta como envio. A mesma nota já ligada
  ao pedido (ou a outro pedido do mesmo hotel) não volta a aparecer. **Nunca envia sozinho.**
  Código: `Estado.iniciar_nf_achadas`, `_nf_achadas`, `opcoes_envio` (`avisos_nf`), `app_ui/painel.js`.

## [2026.10.27.9] — 2026-10-27

### Adicionado

- **Ligar o robô e Pausar o envio automático** na janela do robô (só o usuário João, no PC dele): grava a caixa
  "Robô ligado?" da aba Status, a mesma que o robô confere antes de cada rodada. Pausar pede um segundo clique em 5 s e
  deixa os pedidos esperando; "Enviar agora" fica travado enquanto desligado. Rota `POST /api/robo/ligado`
  (`Estado.definir_robo_ligado`), botões em `app_ui/robo.js`.

### Corrigido

- **Botão de caixas com problema:** o texto do resultado do reinício saía espremido em coluna, porque a classe `.av` que
  ele usava já é o círculo de avatar do Painel. As classes do quadro agora têm prefixo próprio (`cp-*`).

## [2026.10.27.8] — 2026-10-27

### Adicionado

- **O aviso de Outlook parado diz qual caixa está pedindo senha.** O PC lê o título da janela "Email da Internet -
  caixa@dominio" (só o título, nunca a senha) e publica a caixa na Saúde (`cxs=`); o aviso vira "parado com uma janela
  pedindo senha aberta (caixa BAHIA)". O passo para a senha agora também diz: se a janela voltar com a senha certa, o
  servidor está recusando o login (erro `[SYS/TEMP]`), então espere uns 15 min sem apertar F9 e chame a TI.
  Código: `saude.caixas_pedindo_senha`, `saude.motivo_texto`, `coluna(..., caixas_senha)`.

## [2026.10.27.7] — 2026-10-27

### Mudou

- **Tela de carregamento do K na paleta da Auditoria** (sem verde, pedido do João): K de sucesso, barra e bolinhas em azul,
  cartão em cinza neutro, erro em vermelho, aviso em âmbar. Mesmas cores do botão de caixas com problema.

## [2026.10.27.6] — 2026-10-27

### Corrigido

- **Janela "Email da Internet" (usuário e senha do POP3) agora é reconhecida.** O Painel só procurava a palavra "senha" no
  título; a janela do Outlook se chama "Email da Internet - caixa@dominio", então o aviso saía como "motivo não
  identificado" (era o caso do Outlook do Cristian com 15 e-mails presos). Agora diz "parado com uma janela pedindo senha
  aberta", com o passo "digite a senha na janela do Outlook e aperte F9".

## [2026.10.27.5] — 2026-10-27

### Adicionado

- **Botão de caixas com problema** (desenho do João, cores da Auditoria, sem verde): uma caixa de entrada com sinal de
  perigo, pequena, logo abaixo da bolha de avisos; só aparece enquanto um PC está com o Outlook sem enviar/receber. O
  clique abre um quadro do tamanho do de avisos com as caixas que têm e-mail preso (por conta de envio), o motivo e o
  botão **Reiniciar o Outlook de [PC]**, que fecha o Outlook à força e abre de novo (o que o João fazia à mão), manda o
  que estava preso e diz o resultado; pede confirmação antes e abre a tela do K. O × só guarda o quadro: o botão fica
  enquanto houver problema. Também funciona para o PC de outro agente, pela rede assinada dos PCs. Código:
  `app_ui/pecas/caixas.js/.css`, `outlook_vivo.reiniciar`, `saude.presos_por_conta`, rotas `/api/caixas`,
  `/api/outlook/reiniciar`, `/rede/caixas`, `/rede/reiniciar_outlook`.

## [2026.10.27.4] — 2026-10-27

### Mudou

- Fundo da tela do K só escurecido e desfocado, sem o tom verde (pedido do João).

## [2026.10.27.3] — 2026-10-27

### Adicionado

- **Tela de carregamento do K** (desenho do João): em qualquer ação que passe de 3 s (e na hora no Enviar/Receber), a logo
  K é desenhada traço a traço no meio do Painel, repetindo enquanto a ação dura; termina em K verde (deu certo) ou
  vermelho que treme (falhou). O Enviar/Receber ganha um cartão separado no canto (barra, tempo estimado, os 4 PCs); um PC
  que falha treme em vermelho com o motivo, e ações sem lista de PCs mostram o motivo do erro no cartão. Sem movimento se
  o computador pedir menos animação. Código: `app_ui/pecas/carregando.js` e `carregando.css` (62 contornos do PNG do
  João vetorizados, sem React), `acaoLonga(..., {limiteMs})` em `painel.js`.

### Mudou

- A faixa do rodapé "Pedindo o envio ao robô…" não mostra mais "carregando" (só o erro rápido). Ações rápidas
  (`/api/tema`, `/api/professor`, `/api/correio/evento`) não abrem a tela.

## [2026.10.27.2] — 2026-10-27

### Adicionado

- **"Enviar/Receber todas" pede aos 4 PCs** (desenho do João, opção C): manda um pedido assinado pela rede dos PCs
  (`/rede/enviar_receber`, sem usar a cota do Google); cada PC roda o Enviar/Receber do próprio Outlook (o F9, que também
  manda o que estiver preso na Caixa de Saída) e responde quando a Caixa de Saída esvazia. O botão vira um anel que enche
  e mostra "✓ Atualizado" ou o motivo de cada falha (Trabalhar Offline, desligado, presos). A estimativa é a mediana dos
  últimos 8 tempos de cada PC (`estado/enviar_receber_tempos.json`). Um pedido por vez, 10 s entre pedidos.
  Código: `src/enviar_receber.py`, `Estado.enviar_receber_todas` e `rede_enviar_receber`, `pintarSync`/`enviarReceberTodas`.
- **Gancho de ação longa:** toda ação que passa de 3 s (`LIMITE_ACAO_LONGA_MS`) dispara `painel:acao-longa` e, ao acabar,
  `painel:acao-longa-fim` (`acaoLonga` em `painel.js`; o `api()` liga em todo POST). A animação de carregamento com a logo
  (do João, em React) escuta esses eventos.

## [2026.10.27.1] — 2026-10-27

### Mudou

- **Botão Ligação põe a categoria LIGAÇÃO do Outlook no e-mail.** Ao enviar (Enviar NF, Novo e-mail ou Responder) com o
  botão ligado, o PC dono da caixa aplica a categoria **LIGAÇÃO** (a que o João já tem, verde) no e-mail, mantendo as
  que ele já tiver. Se o Outlook daquele PC não tiver a categoria, cria igual (verde). Erro na categoria nunca impede
  o envio. A categoria aparece no e-mail dos Itens Enviados do Outlook (`envio_nf.aplicar_categoria_ligacao`).

## [2026.10.27] — 2026-10-27

### Mudou

- **Canal de teste:** a atualização automática dos PCs (a cada 15 min) agora só vai até a **última versão com etiqueta**
  (`2026.10.27`…). Commit sem etiqueta fica no GitHub e não chega sozinho: o que espera o OK do João não derruba ninguém
  por engano (foi o tropeço de 23/10). O botão "Atualizar" / "Atualizar todos os PCs" continua indo até o último commit.
- **E-mail de hóspede mascarado nos registros** (`logs/*.log`): `maria@gmail.com` vira `m***@gmail.com`. Ficam inteiros
  os da empresa (caixas dos hotéis, agentes). LGPD: registro técnico não precisa do dado.

## [2026.10.26] — 2026-10-26

### Adicionado

- **Outlook parado: o aviso diz o motivo e o que fazer.** Cada PC olha a cada 2 min se o Outlook está em "Trabalhar
  Offline", com janela pedindo senha ou com aviso de certificado aberto (`saude.motivo_outlook`, publicado na Saúde como
  `mot=`). Um aviso só por PC (Caixa de Saída travada já cobre "nenhum e-mail chega").
- **Alerta do Windows de Outlook parado** no PC dono e no principal, repetindo de 30 em 30 min no horário de trabalho
  (seg–sex 8h–18h, sábado 8h–12h), e "Outlook voltou" quando resolve (`avisos_windows.Avisos.outlook`).

### Mudou

- "Nenhum e-mail novo chega" avisa depois de 3 h (era 6 h), comparando com os outros PCs.

## [2026.10.24.1] — 2026-10-24

### Mudou

- **"Enviar NF" azul em todo lugar** (era verde no topo do e-mail): azul é a ação principal; verde fica para "deu certo".
- **Formatos únicos** na ficha do pedido: data `dd/mm/aaaa hh:mm` (vinha `10/23/2026 19:43:40` da planilha), CPF
  `000.000.000-00`, CNPJ `00.000.000/0000-00`, CEP `00000-000` (volta o zero que a planilha perde).
- **Visão geral compara em quantidade**: "+109 que na quinta passada (12)" no lugar de "▲ 908% · eram 12"; % só com base
  de 20 ou mais; verde quando melhora, vermelho quando piora, neutro em pedidos recebidos; tempo até a NF em "mais
  rápido/mais lento".

## [2026.10.24] — 2026-10-24

### Corrigido

- **Visão geral abria com "E-mails na caixa: 0" e "Enviados 72 h: 0"** até a próxima atualização: a tela era desenhada
  antes de os e-mails chegarem e não era redesenhada quando eles chegavam (`carregarCorreio`).

## [2026.10.23.1] — 2026-10-23

### Mudou

- (A etiqueta `2026.10.23` foi o mesmo código, voltado minutos depois porque subiu antes do OK do João.)

- **Pedido do formulário chega no Painel em ~10-20 s** (antes 6 a 12 min; OK do João). No PC principal, uma vigia nova
  (`src/vigia_formularios.py`, linha própria dentro do conferente) pergunta ao Drive a cada 10 s quais planilhas dos hotéis
  mudaram, copia só aqueles hotéis para a Central e avisa os 4 Painéis pela rede, que releem as abas dos hotéis na hora.
  Medido em 22/10: o Drive mostra o pedido novo em 1-2 s (num caso, 3 min: dois pedidos seguidos na mesma planilha).
  O e-mail para o hotel continua de 10 em 10 min (opção A do João).
- **A rodada das 10 em 10 espera a trava** até 45 s em vez de pular a cópia ou o envio (`adquirir_lock(esperar=)`); a
  vigia não copia enquanto a rodada roda (`estado/_ciclo_copia.txt`).
- **Cota do Google:** a vigia tem fatia própria (4 leituras/min); o Painel de cada PC passou de 7 para 6 (usa ~4).
  Soma dos 4 PCs continua 57 de 60.

## [2026.10.22.7] — 2026-10-22

### Adicionado

- **Marcar quando o pedido veio por ligação** (desenho aprovado pelo João: opção B). Na tela de escrever (Enviar NF,
  Novo e-mail, Responder), um botão **Ligação** embaixo do Enviar: começa desligado em todo e-mail, um clique liga (fica
  verde-água com ✓ e a etiqueta "Ligação" aparece no topo), outro desliga; atalho Alt+L. A marca **não vai no e-mail**,
  só conta no Painel. Fica na aba nova **Ligacoes** da Planilha Central (uma linha por marca, guardada 400 dias).
- **Itens Enviados:** etiqueta verde-água "Ligação", filtro **"Só ligações"** e, no botão direito, **"Marcar como
  ligação"** / "Tirar marca de ligação" (para quando esqueceu de marcar no envio).
- **Visão geral:** cartão **Ligações** com hoje, 7 dias e o mês, e os últimos 7 dias por hotel ou por agente.
- Envio marcado que falhar perde a marca sozinho (o reenvio é que conta, para não contar 2 vezes).

### Corrigido

- **Itens Enviados aparecia vazio** desde 11/10 (no Painel real: 0 na tela, com 602 enviados nas 72 h). O filtro dos
  4 agentes recebia a posição do e-mail no lugar do agente. A pesquisa pelo e-mail do hóspede não era afetada.

## [2026.10.22.6] — 2026-10-22

### Corrigido

- **Barra de rolagem para o lado na lateral:** ao clicar em "Mostrar os nomes", os nomes surgiam antes da barra chegar aos
  232 px e a área das abas criava uma barra de rolagem horizontal. Agora a área das abas só rola para baixo; tudo fica
  dentro da largura (56 px só ícones, 232 px com os nomes).

## [2026.10.22.5] — 2026-10-22

### Mudou

- **Menu da lateral** (desenho aprovado pelo João: Opção A + nomes que empurram a tela): a barra abre só com os ícones
  (56 px, espaços iguais, número vermelho no canto do ícone). O botão do pé da barra mostra os nomes das abas (232 px,
  empurra a tela) e volta a só ícones, com animação de 0,22 s; o Painel lembra neste PC.
- **"Quem está neste PC"** abre ao lado da barra (264 px), com nome inteiro, "você, neste PC", iniciais que não se
  repetem (Cristian "CR", Clara "CL") e "Fechar o Painel" separado embaixo, com o ícone de desligar e a explicação.
  Antes abria espremido na largura dos ícones.

## [2026.10.22.4] — 2026-10-22

### Corrigido

- **Tela do robô, "Esperando a NF":** mostrava todos os pedidos abertos (906 no Painel real, de semanas atrás). Agora só a
  última semana, com um link "N mais antigos ficam em Notas fiscais".

## [2026.10.22.3] — 2026-10-22

### Mudou

- **Tela do robô** (desenho aprovado pelo João; substitui a aba Robô e a tela de Log): uma janela grande, quase da tela
  toda (o Painel aparece atrás), calma e centralizada. Aba **Agora**: frase de como está o robô, barra da rodada, avisos em
  vermelho com "Como resolver", pedidos agrupados por situação (em andamento, esperando a NF, concluídos) em linhas
  compactas com uma trilha de 4 passos, e o resumo do dia ao lado. Clicar num pedido abre o **caminho completo** (passos,
  horas e as linhas do log). Aba **Registro**: o log em frases, com filtros, busca, "Seguir ao vivo" e o texto original ao
  clicar. "Enviar agora" sem janela de confirmação. Fechar ou minimizar não para o robô: um **chip na barra de baixo**
  mostra o andamento (vermelho se houver problema), abre uma gaveta curta, e um aviso discreto diz quando a rodada
  termina. "Registro do robô" no Monitoramento abre a mesma janela. Ficam para depois: "Ligar o robô" e "Pausar o envio
  automático" (só o usuário João), por mexerem na aba Status.

## [2026.10.22.2] — 2026-10-22

### Adicionado

- **Aba Robô** (desenho A aprovado pelo João; aparece para os 4 agentes): uma frase diz como está o robô ("O robô está
  enviando 3 pedidos agora"), a barra mostra a rodada passo a passo, três números do dia, o que precisa de atenção em
  vermelho e a lista de pedidos de hoje com **uma frase por pedido** dizendo onde está (esperando o envio ao hotel,
  enviado, NF emitida, concluído) e o caminho do primeiro pedido em aberto sempre à vista. "Enviar agora" fica; o envio
  automático (a cada 10 min) segue. O botão lateral "Enviar pendentes" agora abre a aba (a janela de confirmação saiu do uso).
  Etapas seguintes: chip na barra de baixo e "Ver registro".

### Mudou

- **Usuário João só no PC dele:** os outros PCs não escolhem o usuário João e não ganham as opções de administrador
  (Monitoramento, Máquinas, Log) trocando de usuário.

## [2026.10.22.1] — 2026-10-22

### Mudou

- **Itens Enviados guardam 72 h** (pedido do João: "não está salvando os enviados, preciso ao menos 72 h para ver se já foi
  enviado"): eram 24 h. Todos os PCs releem uma vez para trazer as 72 h. Os rótulos "24 h" viraram "72 h".
- **Envio do hóspede sempre à mão:** pesquisando o e-mail do hóspede, o envio aparece mesmo com mais de 72 h (o índice
  local guarda 12 meses e responde na hora). Se o índice de algum PC ainda não está completo e nenhum envio apareceu, o
  Painel faz uma consulta rápida só nos Itens Enviados do Outlook (limite de ~1 s) e junta ao resultado.

## [2026.10.22] — 2026-10-22

### Mudou

- **Aviso de envio em pílula** (desenho aprovado pelo João, Opção B: "minimalista, nada poluente"): o cartão grande no
  canto de baixo (3 passos e barra) virou uma pílula de uma linha: "◌ Enviando NF · PC de Clara" → "✓ Enviado 08:44" e
  some sozinha em 3,5 s. Vale para Enviar NF, Responder, Encaminhar e Novo e-mail. **Erro não some:** vira a pílula
  vermelha "Não enviou · Ver" e, clicando, abre o cartão completo de antes (motivo + "Escrever de novo"). Passando o
  mouse, mostra o caminho (entregue → saindo → conferido).

## [2026.10.21.6] — 2026-10-21

### Mudou

- **Envio direto pela rede** (pedido do João: "deixar tudo mais rápido… toma mt cuidado com e-mail duplicado"):
  Responder, Enviar NF, Encaminhar, Excluir e Urgência por caixa de outro PC gravam o pedido na fila `Envios_NF` como
  sempre e avisam o PC dono pela rede do escritório; ele relê o pedido **na fila** e envia pelo mesmo caminho (trava +
  "assumido" antes de enviar). Sai em ~1 a 3 s em vez de 15 s a ~1 min. Rede fora = a fila resolve, como antes.
- **E-mail novo e NF na hora:** o robô olha o Outlook a cada 10 s (eram 20) e, quando grava e-mail ou NF na Central,
  avisa o Painel do PC, que repassa aos outros: todos releem na hora (no máximo 1 vez a cada 12 s, pela cota do Google).
  NF nova no Dropbox: o Painel olha a pasta a cada 10 s e o robô do principal confere na hora (era a cada 2 min).
- **Tela só com o que mudou:** a tela pergunta a cada 3 s se há novidade (`/api/versao`); na volta automática, dado
  igual = o Painel responde só "igual" (~1 KB em vez de ~3,4 MB) e a tela não redesenha. Ação do usuário redesenha
  sempre; tudo é redesenhado 1 vez por minuto.
- **Atualização só de documentação** (notas do cofre, `.md`) baixa sem reiniciar o robô e o Painel.

### Corrigido

- **Envio interrompido por reinício:** o Painel que reiniciava entre o envio e o "enviado" deixava o pedido
  "enviando" para sempre e a NF sem registro. Agora o e-mail leva o nº do envio na marca invisível do Painel e o PC dono
  confere em Itens Enviados: achou = enviado e NF registrada; não achou (nem na Caixa de Saída) em 5 min = "não saiu,
  confira antes de mandar de novo". Nunca reenvia sozinho.
- **Dois Painéis no mesmo PC:** abertos quase juntos, subiam os dois (o Windows deixa abrir a mesma porta) e podiam
  pegar o mesmo pedido da fila. Agora há trava de um Painel por PC, igual à do robô.

## [2026.10.21.5] — 2026-10-21

### Mudou

- **Janelas que abrem por cima no cinza, com animação nova** (desenho aprovado pelo João): Novo e-mail, Responder,
  Enviar NF, Encaminhar, Excluir, Ajuda, Enviar pendentes, o anexo e o aviso de baixo ficavam fora da área do modo cinza
  e usavam o verde antigo. Agora são uma peça única (`app_ui/pecas/janela.css` + `janela.js`): abrem subindo e crescendo
  de leve em 0,24 s e fecham em 0,15 s (com "menos movimento" no Windows, só esmaecem). "Recarregando o Painel…" no
  cinza, com o círculo azul.
- **Sem o verde antigo de tema:** a tela já abre no cinza (antes aparecia por um instante a tela antiga verde ao abrir ou
  recarregar); quadro "NF já enviada" e seleções em azul-escuro; borda da pesquisa, bolinha do operador, barra de
  rolagem e fundo da janela do app em cinza. Cores de situação e a tabela verde/creme ficam.

## [2026.10.21.4] — 2026-10-21

### Corrigido

- **Etiqueta "🧾 NF emitida" no e-mail errado** (caso do João: 3 pedidos de estadas novas ganharam a etiqueta da NF de
  outra estada do mesmo nome, salva 2 dias antes). A busca pelo nome, feita para e-mail sem nº de estada, rodava sempre
  que a busca pelo nº falhava. Agora, se o e-mail diz a estada ("Estada: 12345"), o arquivo tem que ser dela (ou não ter
  nº). O robô também reconfere as etiquetas que já pôs e tira as que não passam mais (só se a NF ainda está na lista do
  Dropbox, para um Dropbox lido pela metade não tirar etiqueta certa).

## [2026.10.21.3] — 2026-10-21

### Corrigido

- **Tela verde sem função** (PC do João, depois da atualização das 09:46): o servidor do Painel aceitava só 5 conexões
  na fila (padrão do Python). Ocupado, logo depois de reiniciar, ele fazia o Windows recusar parte dos arquivos da tela
  (medido: 20 pedidos juntos, 44 de 100 recusados). A página abria pela metade, tentava 3 vezes e desistia em silêncio.
  Agora a fila é de 128 (`ServidorPainel`).
- A página que vem pela metade mostra **"Recarregando o Painel…"** com "Tentar agora" e tenta de novo, cada vez
  esperando um pouco mais, **sem desistir**.

### Adicionado

- Faixa laranja **"Sem dados do servidor há 1 min · Recarregar agora"** (some sozinha quando os dados voltam).
- **F5** recarrega a tela dentro da janela do app; com mensagem sendo escrita, pede o 2º aperto. Ctrl+R continua sendo
  Responder.
- A **janela** (`app_janela`) confere se a tela está viva ao abrir pelo atalho e a cada 30 s; parada (ou página de erro)
  → recarrega sozinha quando o servidor estiver no ar. Anota em `logs/janela.log`. Vale quando a janela reabrir.

## [2026.10.21.2] — 2026-10-21

### Adicionado

- **Aviso de pedido repetido no e-mail** (escolha do João: "1 · Mostrar no e-mail"): quando o pedido do e-mail foi
  juntado pelo robô a outro da mesma estadia (mesmo hotel, CPF/CNPJ, datas e valor), uma faixa laranja embaixo do
  resumo fixo avisa "Este hóspede já pediu nota desta estadia", com a data e a situação do outro. Botões **Abrir o outro
  pedido** e **Comparar** (os dois lado a lado; o que difere em âmbar). Só tela: nada é gravado e a junção automática
  continua igual.

## [2026.10.21.1] — 2026-10-21

### Mudou

- **Resumo fixo do hóspede** (desenho aprovado pelo João): uma faixa parada no topo do e-mail aberto com quem é, as
  etiquetas, o prazo, o que ele quer ("Nota no nome de… · CNPJ", o que entra na nota, hotel e datas com as diárias; o
  que falta em âmbar) e os botões Pedir o que falta · Marcar tratativa · Enviar NF. "Ver ficha completa" abre a tabela
  verde/creme do pedido (o Painel lembra aberta/fechada). A ficha de 3 faixas saiu do meio do e-mail.

## [2026.10.21] — 2026-10-21

### Mudou

- **Etiquetas e situações únicas** (peça `app_ui/pecas/etiqueta.js` + `etiqueta.css`, desenho aprovado pelo João):
  5 situações, uma por pedido (Sem NF · Falta dado · NF pronta, falta enviar · NF enviada · Correção), e 5 alertas que
  somam (Urgente · Possível repetido/Pediu de novo · Nota dividida · CPF/CNPJ diferente · Diz que não recebeu), com cor,
  ícone e palavra iguais na caixa de entrada, em Notas fiscais, na ficha, no histórico e na pesquisa. As regras (qual
  situação e quais alertas) ficam na peça, então todas as telas decidem do mesmo jeito.
- Responder o hóspede não vira mais "NF enviada": só a nota que saiu. A que existe e não saiu é "NF pronta, falta enviar".
- Filtro Situação: "NF emitida" → "NF enviada" (só as que saíram), "Envio pendente" → "NF pronta, falta enviar",
  "Diz que falta nota" → "Diz que não recebeu".

## [2026.10.20.21] — 2026-10-20

### Mudou

- **Peça única do Filtro** (`app_ui/pecas/filtro.js`): o Filtro da caixa de entrada, a Situação e o Hotel de Notas
  fiscais e o PC do Monitoramento passam a ser o MESMO código (pílula "Rótulo: valor ▾", menu com contagem, ✕ para
  tirar, busca no Hotel, Esc e clique fora fecham, setas do teclado). Mudou a peça, muda em todas as telas.
- O Filtro da caixa de entrada virou a pílula **"Filtro: Todos ▾"**.

### Removido

- O menu antigo das pílulas (`#pop`, `pilula`, `desenharPop`) e as três cópias do filtro (caixa, Notas fiscais e
  Monitoramento). Um teste garante que nenhum arquivo volta a montar o filtro sozinho.

## [2026.10.20.20] — 2026-10-20

### Mudou

- **Notas fiscais:** a fileira de abas de situação virou a pílula **"Situação: Todas ▾"**, com o mesmo menu do Filtro
  da caixa de entrada (mesmos filtros e contagens; o ✕ tira o filtro). Desenho escolhido pelo João.
- **Monitoramento:** "PC: Todos ▾" embaixo das abas, com a setinha e sem o ícone, igual ao desenho aprovado.

## [2026.10.20.19] — 2026-10-20

### Mudou

- **Peças únicas, 1º passo:** o botão e o menu do Filtro da caixa de entrada passam a servir para qualquer tela.
- **Monitoramento:** escolher o PC usa essas peças (botão "PC: Todos", menu escuro com a bolinha de ligado/desligado e
  o ✕ para tirar), no lugar da lista branca do Windows.
- **Botões de alternar** (Visão geral: Ontem/Hoje e Período; Gerência: Comparação) com o mesmo visual, no azul do Filtro.

## [2026.10.20.18] — 2026-10-20

### Corrigido

- **Responder um formulário** punha no Para o e-mail do Emissor Automático (o Gmail do robô). Agora vem o e-mail de quem
  preencheu ("Enviado por"); sem ele no texto, o Para fica vazio para quem envia preencher. A NF enviada fica ligada ao
  pedido do hóspede do Para.

### Mudou

- **Responder/encaminhar um formulário**: o e-mail original embaixo aparece na mesma tabela verde e creme da leitura
  (a mesma peça, `formularioHtml`). É só da tela: o e-mail que sai leva o original que o Outlook coloca.

## [2026.10.20.17] — 2026-10-20

### Corrigido

- **Histórico dentro do formulário**: mostrava os e-mails do Emissor Automático de todos os hotéis (ex.: 119
  "Solicitação NF"), porque procurava pelo remetente. Agora vai pelo e-mail de quem preencheu (e os outros dele com o
  mesmo CPF/CNPJ) e mostra só esta hospedagem (mesmo hotel, desde 30 dias antes do check-in), com o botão "ver tudo do
  hóspede". Sem check-in: tudo do hóspede. Sem o e-mail de quem preencheu: sem histórico. E-mails do próprio hóspede:
  como antes.

## [2026.10.20.16] — 2026-10-20

### Mudou

- **Formulário com as cores da tela 1b** (aprovada pelo João): letras creme, fundo cinza, verde no cabeçalho Campo / Valor
  e nas faixas dos grupos. Só a cor mudou.

## [2026.10.20.15] — 2026-10-20

### Mudou

- **Formulário do hóspede = tela 1 do quadro de design** (escolhida pelo João), em verde e creme: a tabela Campo / Valor
  como chega no e-mail, separada em Tomador da nota, Estadia e Como quer a nota. CPF/CNPJ, CEP e telefone formatados
  (com "CPF"/"CNPJ" ao lado), número de diárias junto das datas e botão de copiar nas linhas que se digitam na emissão.
  "Aceitou os termos" e "Enviado em" no rodapé. Substitui os quadros da 2026.10.20.14.

## [2026.10.20.14] — 2026-10-20

### Mudou

- **Formulário do hóspede na caixa de entrada em quadros** verde/creme: o nome do campo em cima (verde) e o valor
  embaixo (creme), em 3 grupos como a ficha: Tomador da nota (Nome, CPF/CNPJ, CEP, Telefone), Estadia (Hotel, Titular,
  CPF do titular, Datas) e Como quer a nota (Pedido, Dividida, Enviar para). Clicar no valor copia. Termos de aceite e
  Enviado em ficam no rodapé.

### Corrigido

- E-mail do Emissor Automático cujo pedido não estava na lista do Painel aparecia como texto corrido ("Campo Valor…"):
  agora os campos saem do próprio texto do e-mail e entram nos mesmos quadros.

## [2026.10.20.13] — 2026-10-20

### Adicionado

- **Pesquisa instantânea pelo índice local de e-mails.** Cada PC monta, aos poucos e só lendo o Outlook, um índice dos
  últimos 12 meses das caixas dos hotéis (Entrada, Enviados, Excluídos) em `estado/indice_emails.sqlite`, fora do git e
  do Google. A pesquisa dos 4 PCs responde pelo índice em milissegundos (medido no PC do João: 11 a 36 ms; antes, 11 a
  13 s direto no Outlook). Sem acento e com palavra pela metade. O botão "Procurar também direto no Outlook" faz a
  pesquisa ao vivo, como antes.

### Mudou

- A regra de 08/10/2026 "pesquisa sempre ao vivo no Outlook" virou "pesquisa pelo índice, Outlook ao vivo no botão"
  (aprovado pelo João em 20/10/2026).

## [2026.10.20.12] — 2026-10-20

### Mudou

- **Menus das pílulas** (Hotel e os outros filtros de cima, nas Notas fiscais e nos E-mails) com o mesmo visual do menu
  Filtro da lista: fundo escuro, cantos arredondados, o escolhido em azul, o número à direita em cinza e a busca escura.

## [2026.10.20.11] — 2026-10-20

### Adicionado

- **Botão direito no e-mail** (lista da tela de e-mails): Marcar como lido / não lido e Marcar como urgente / Tirar
  urgência. Também abre com Shift+F10 ou a tecla de menu; Esc fecha. A marca vale na hora para a equipe e o PC dono põe a
  categoria "Urgente (Painel)" (ou "Sem urgência (Painel)") no e-mail do Outlook, onde fica guardada.
- **E-mail da Ouvidoria entra como urgente** sozinho (remetente ou nome com "ouvidoria"), com o motivo "E-mail da Ouvidoria".

## [2026.10.20.10] — 2026-10-20

### Removido

- O atalho **Itens Enviados** da barra da esquerda. Ele continua nos Favoritos e dentro de cada caixa, na tela de e-mails.

## [2026.10.20.9] — 2026-10-20

### Adicionado

- **Filtro na lista dos e-mails**: botão "Filtro" ao lado de "Por Data", com Pedido de correção, Sem resposta, Com anexo e
  Nota dividida, cada um com quantos e-mails tem na caixa aberta. Um por vez; o filtro escolhido aparece no botão e o ✕ limpa.

## [2026.10.20.8] — 2026-10-20

### Mudou

- A faixa de botões do topo (Novo e-mail, Caixa de Entrada, Notas fiscais, Enviar pendentes, Enviar/Receber) também fica
  só na tela de e-mails; some do resumo, da Gerência e das outras telas. "Enviar pendentes" segue no ícone de avião da
  barra da esquerda e "reler" no ↻ da barra de baixo.

## [2026.10.20.7] — 2026-10-20

### Corrigido

- O resumo de uma linha da verificação da NF mostrava "(texto)"; agora mostra "(texto na nota: “…”)".

## [2026.10.20.6] — 2026-10-20

### Mudou

- As abas **Página Inicial · Enviar/Receber · Exibir** aparecem só na tela de e-mails. No resumo, na Gerência e nas outras
  telas elas somem, e a faixa mostra sempre os comandos principais.

## [2026.10.20.5] — 2026-10-20

### Corrigido

- **A verificação da NF entende o texto que o hóspede pede na nota.** "Não consta a identificação “UEM / (nome)”" aparecia
  como "refazer a nota (o cliente não disse o que mudar)". Agora o texto entre aspas, num trecho que fala de constar,
  incluir ou identificação, vira o motivo ("incluir na nota: “…”"), e o robô procura esse texto em toda a NF (sem acento,
  maiúscula ou pontuação): "não aparece em nenhuma parte da nota" ou "já aparece". Conferido no caso real (NF 879 do
  NOVO CWB, no Dropbox: não aparece). As análises antigas são refeitas na próxima volta. Testes:
  `testes/test_texto_na_nota.py`.

## [2026.10.20.4] — 2026-10-20

### Corrigido

- **O Painel mostra exatamente o que está na Caixa de Entrada de cada caixa.** No PC do João, 9 de 55 e-mails ficavam de
  fora (7 caixas). As caixas são POP3: o e-mail cai no Outlook 10 a 20 minutos depois da hora do servidor, e a volta do
  espelho (a cada 2 min) olhava só 10 minutos para trás pela hora do servidor. Agora a volta procura pela hora em que o
  e-mail caiu ou mudou no Outlook (pega também o e-mail movido de volta) e, no fim de cada volta, confere o total de cada
  caixa no Outlook com o espelho; se não bater, relê aquela caixa inteira. E-mail sem data do servidor conta pela data
  de criação. Testes: `testes/test_contagem_exata.py`.

## [2026.10.20.3] — 2026-10-20

### Mudou

- **Pastas dos e-mails redesenhadas.** O nome do hotel, o e-mail e o número estavam grudados. Agora há um título pequeno
  por grupo, um cabeçalho para cada PC (pessoa, bolinha verde de ligado, nome do PC, quantas caixas e o total), cada caixa
  em 2 linhas (hotel; e-mail inteiro) com os não lidos numa pílula azul, setas desenhadas do mesmo tamanho e o link
  "Mostrar mais N caixas".

## [2026.10.20.2] — 2026-10-20

### Mudou

- **O Painel ganha o visual do Outlook escuro (Prévia 5).** Cinzas e azul `#479ef5`, letra Segoe UI, faixa de comandos
  numa caixa cinza e 10 px entre pastas, lista e leitura, em todas as telas. Aprovado pelo João no quadro de design.
- **E-mail aberto igual ao Outlook.** Cabeçalho com as iniciais, quem mandou e Para; embaixo, de onde veio (hotel e PC),
  os anexos em cima do texto, a ficha do pedido e o texto alinhado com o nome. Na lista: assunto e hora em azul, linha
  urgente avermelhada com bandeira, quadradinho azul no formulário e o nome real de quem mandou.
- **Ficha do pedido em 3 faixas** (título com prazo · Tomador, CNPJ/CPF, O que pede, Hóspede, CPF do hóspede · botões),
  com mais espaço entre os dados.
- **Formulário igual ao e-mail do Emissor Automático.** "Enviado por", "Dados para emissão de Nota Fiscal:", a tabela
  Campo / Valor de cabeçalho dourado numa ordem fixa de 13 campos (os dois formulários caem nela; campo fora da lista vai
  para o fim) e "Enviado em".

### Adicionado

- **Pesquisa instantânea.** Os pedidos do formulário aparecem na hora (com o trecho marcado e o tempo), junto com os
  e-mails que o Painel já tem; o Outlook dos 4 PCs completa depois. Clicar num pedido abre a ficha.
- **Envio sem espera.** Clicou em Enviar, a janela fecha na hora e um aviso no canto acompanha (entregue · saindo ·
  conferido em Itens Enviados). Se falhar, o aviso diz o motivo e "Escrever de novo" reabre a mensagem com o texto.
- `testes/test_previa5.py`: barra nome repetido no topo dos scripts da tela (derruba o arquivo inteiro) e confere as
  peças da Prévia 5.
- Cérebro: "Guia do Painel Fiscal" (cada tela, pesquisa, envio, atalhos); Padrão de design, Onde mexer e app_ui
  atualizados.

### Problemas conhecidos

- O índice local de e-mails em cada PC (pesquisa de e-mails antigos em ~0,2 s) e o envio direto pela rede (sem passar
  pela fila da Central) esperam o OK do João: mudam a regra de 08/10 ("busca sempre ao vivo no Outlook").

## [2026.10.20.1] — 2026-10-20

### Corrigido

- **Log disputado: um arquivo de log por programa.** O robô, o conferente e o Painel escreviam no mesmo
  `logs/solicitacoes_nf.log`. Quando ele chegava a 5 MB, o Windows não deixava girar (`PermissionError`, WinError 32) e
  cada linha virava um "Logging error" na saída da tela (14.017 vezes até 20/10). Agora o robô fica em
  `solicitacoes_nf.log`, o conferente em `conferente.log` e o Painel em `painel.log` (`log_util.arquivo_do_programa`).
  O envio nunca foi afetado.

## [2026.10.20] — 2026-10-20

### Mudou

- **A saída da tela da cópia dos hotéis gira em 5 MB.** `Bat/sincronizar_agendado.bat` guarda a atual e mais 2 antigas,
  como o log do robô. Antes crescia sem limite (30 MB desde 24/09).

### Segurança

- Decisões de LGPD: 2 e-mails simulados de 24/09 com dados reais apagados de `saida_simulacao/`; regra de 12 meses para
  `logs/Historico_de_Envios.csv`; histórico do git mantido (repositório privado).

### Problemas conhecidos

- **Log disputado.** O robô, o conferente e o Painel escrevem no mesmo `logs/solicitacoes_nf.log`. Quando ele chega a
  5 MB, o Windows não deixa girar (`PermissionError`, WinError 32) e cada linha vira um "Logging error" na saída da tela
  (14.017 vezes até 20/10). O envio não é afetado. Conserto proposto: um arquivo de log por programa.

## [2026.10.19] — 2026-10-19

### Adicionado

- **Testes rodam sozinhos no GitHub.** A cada push em `main`, `Bernardo`, `Christian` ou `clara`, o GitHub Actions roda
  todos os testes num Windows com Python 3.14 (`.github/workflows/testes.yml`).
- **Checagem antes de cada commit.** `.githooks/pre-commit` barra `estado/`, `logs/`, `config.local.json`, credenciais e
  CPF de hóspede de verdade, e roda os testes. Ligada só no PC do João (`git config core.hooksPath .githooks`).
- **Guarda do git no Claude Code.** `ferramentas/guarda_git.py` bloqueia push forçado, apagar branch, `reset --hard`,
  `clean` e descartar tudo. O push normal da entrega continua liberado.
- **Manual "Se o robô parar"** no cofre: gravidade G1 a G4, um card por alarme do Painel, desligar o robô, voltar versão
  e modelo de aviso para a equipe.
- **"Dados de hóspedes (LGPD)"** no cofre: onde ficam nome, CPF e e-mail, por quanto tempo, quem vê e como atender o
  pedido de um hóspede.
- README novo (fluxo, garantias, estrutura, qualidade, segurança) e este CHANGELOG.
- **Ruff** (`ruff.toml`) confere erro real no código (sintaxe, nome indefinido, import sem uso) no pre-commit e no
  GitHub. A formatação não é imposta, para não mexer em todo arquivo que roda nos 4 PCs. `requirements-dev.txt` traz o
  ruff só para quem mexe no código.

### Removido

- 5 imports sem uso (`faxina.py`, `rede_pcs.py` e 3 testes) e um `f` sem efeito numa mensagem de `classificador.py`.

### Segurança

- **Dados reais de hóspedes tirados do repositório.** 4 arquivos de teste, um comentário de `controle_nf.py` e o guia de
  design tinham 9 nomes, 5 CPFs e 1 e-mail de hóspedes reais, copiados de casos de verdade. Foram trocados por dados
  inventados, com os testes conferindo a mesma lógica.

### Corrigido

- Aviso de escape inválido em `testes/test_painel_fiscal.py`.

### Problemas conhecidos

- Os dados reais continuam no **histórico** do git (commits de 09/10 a 19/10). O repositório é privado; apagar o
  histórico quebraria a atualização dos 4 PCs. Decisão do João pendente ("Dados de hóspedes (LGPD)", item 1).
- `logs/saida_console_sincronizar.txt` cresce sem limite (30 MB desde 24/09).

## [2026.10.17] — 2026-10-17

### Mudou

- **Tipografia única.** Eram 14 espaçamentos diferentes em 41 rótulos em maiúsculas. Agora há um padrão só: rótulos de
  11 px com 0,05em, e números na fonte do texto, alinhados.
- **Notas fiscais em linhas de 2 andares**, como a lista de e-mails, com a ficha sempre aberta ao lado.

### Removido

- **Urgência sai da barra da esquerda e da faixa de comandos.** Ela continua nos Favoritos da caixa de entrada.

## [2026.10.15] — 2026-10-15

### Adicionado

- **E-mail do robô sai do PC dono da caixa do hotel** (`envio_pc_dono.py`). Pelo pedido na rede (porta 8766) ou, se a
  rede não chega, pela fila `Envios_NF`. PC dono desligado: o pedido espera e não sai por outra caixa.
- **TRUE na coluna Enviado da planilha do hotel**, logo depois de cada envio confirmado. É a única escrita nas planilhas
  dos hotéis. Os antigos foram corrigidos: 428 linhas em 32 hotéis.
- **Alarme de pedido parado**: pedido de formulário sem envio há mais de 2 h aparece nos avisos do Painel.
- **E-mails e todas as telas com o layout do Outlook**: barra fina de ícones, abas Página Inicial / Enviar/Receber /
  Exibir, faixa de comandos, pastas com Favoritos e caixas por agente.
- **Ficha do pedido com 5 campos**: Tomador, CNPJ/CPF, O que pede, Hóspede e **CPF do hóspede sempre**. O formulário
  aberto aparece em tabela Campo/Valor.
- Abrir e-mail mais rápido: textos pré-carregados, histórico local na hora e anexos de imagem.

### Mudou

- **Copiar e enviar a cada 10 min** (eram 30), só no PC principal.

### Corrigido

- **26 pedidos nunca enviados** (Boa Viagem e São Francisco, de 06/10 a 15/10). O formulário novo gravava noutra
  planilha e a cópia lia só a mais recente pela data do Drive. `sincronizar.juntar_planilhas` agora junta todas as
  planilhas do hotel numa aba só da Central. Os 26 saíram às 11:24, cada um da caixa do próprio hotel.
- **E-mails de hotéis de outros PCs saíam pela caixa do Ondina**: uns 25 hotéis desde setembro. Resolvido pelo envio
  pelo PC dono.
- CAMPO GRANDE e IDEAL apareciam com "robô antigo ativo" até 10/12/2026: o carimbo era lido no formato errado. Data no
  futuro não conta mais.

## [2026.10.14] — 2026-10-14

### Adicionado

- **Repaginação v2** (aprovada no Figma e na prévia):
  - tema escuro e menu recolhível;
  - Monitoramento (Log + Máquinas) só para o administrador;
  - avisos numa caixinha no canto;
  - tags Urgente / Falta dado / Nota dividida / NF e "Pedir o que falta";
  - Resumo de ontem;
  - Gerência como relatório do mês.
- **Seletor "Caixa de"** no topo, no lugar das abas de agente, só em Notas fiscais e E-mails.
- **Ficha-resumo** no topo do pedido (tomador, estadia, como quer a nota, situação), com o que falta em âmbar e botão
  "Pedir dados".
- Anexo do hóspede abre no Painel, lido ao vivo do PC dono.

### Mudou

- **Caixa de entrada = espelho literal do Outlook.** O espelho escondia respondidos, formulários e avisos: a Clara tinha
  192 e-mails no Outlook e 91 no Painel. Agora aparece tudo.
- Leitura aberta vai até o topo; a situação do sistema foi para um rodapé fino.

### Corrigido

- "Atualizar todos os PCs" não reiniciava o PC onde o commit nasceu.
- O filtro de Hotel da Caixa de entrada não abria.

## [2026.10.13] — 2026-10-13

### Adicionado

- **Guardião do Outlook** (`outlook_vivo.py`): o Outlook fica sempre aberto com janela. O Painel avisa quando está "sem
  janela" ou quando nenhum e-mail novo chega.
- **Busca ao vivo nos 4 PCs** funcionando (regra da porta 8766 criada no Dia do administrador).
- **Novo e-mail** na Caixa de entrada, saindo da caixa do hotel pelo PC dono, com o modelo Solicitação de dados.
- Trava contra vazamento de credenciais (`.gitignore` + `testes/test_segredos.py`).
- Segundo Cérebro organizado: regras, mapa do projeto, onde mexer, histórico.

### Corrigido

- **PC do Cristian 4 dias sem receber e-mail.** O robô abriu o Outlook sem janela, e as contas POP3 não baixam assim.
- Atualização falhava no PC do Bernardo ("Cannot fast-forward to multiple branches"). Agora usa `fetch` +
  `merge --ff-only`.
- E-mail enviado pelo Painel saía com duas assinaturas.

## [2026.10.12] — 2026-10-12

### Adicionado

- **Segundo Cérebro** (cofre do Obsidian dentro do repositório).
- **Modo casa** (`--visualizar`): dados reais, só leitura, para o PC de casa.
- Rascunho do guia de design (`guia-painel-fiscal.html`).

## [2026.10.11] — 2026-10-11

### Adicionado

- **Notas fiscais = espelho da Caixa de Entrada.** Lido sincronizado com o Outlook, e a busca sempre pergunta ao Outlook.
- **"Atualizar todos os PCs"** pelo Agendador do Windows, com confirmação.
- **Saúde do sistema**, abrir com o Windows, respostas prontas e conferência da NF antes de enviar.
- **Relatório do dia e da semana** (Mail Analytics, só leitura). O fim de semana de João e Cristian é contado pelo
  Painel, sem tocar no Mail Analytics.

### Mudou

- **Design fiscal**: paleta única e sóbria, sem símbolos decorativos, verde e creme no fundo, operadores em abas.

### Corrigido

- **Cópia dos hotéis parada desde 08/10 21:36**: função chamada com um argumento a mais. 95 formulários recuperados.
- Caixa da CECOMTUR nunca espelhada: o cadastro pulava a 1ª linha.
- Página chegando pela metade (código aparecendo na tela) durante uma atualização.

## [2026.10.09] — 2026-10-09

### Adicionado

- **Etapa 1**: modo professor, equipe/meus hotéis, "Sem NF", atalhos do Outlook, etiqueta "NF emitida", e
  responder/encaminhar/enviar NF dentro da leitura.
- **Etapa 2**: prazo por tipo, hóspede único, pedido repetido, CPF/CNPJ da NF comparado com o pedido e motivo principal.
- "Sim" automático no aviso de certificado do Outlook.

## [2026.10.08] — 2026-10-08

### Mudou

- **Painel = espelho do Outlook dos 4 PCs** (a maior virada do projeto). O Painel não guarda histórico, a busca é ao vivo
  e há faxina diária da Central.
- **Cota do Google dividida** entre os programas dos 4 PCs (57 de 60 por minuto).
- Repaginação corporativa, revisada com crítica de design e acessibilidade WCAG 2.1 AA.

### Adicionado

- Busca do jeito do Outlook (sem acento, pedaço de palavra) pelo índice: 1 a 5 s.
- "NF emitida" separada de "envio pendente".
- Modo demonstração para o PC de casa (`PAINEL_DEMO_EM_CASA.bat`).
- Aba Gerência (em teste).

## [2026.10.07] — 2026-10-07

### Adicionado

- **Aba E-mails**: espelho dos e-mails de hóspedes sem resposta de todos os PCs.
- **Atualização dos PCs pelo Painel** e `ATUALIZAR_PAINEL.bat`.
- Design novo com lateral verde, Log e Máquinas.
- Cópia só das planilhas que mudaram; aviso do Windows quando um PC sai do normal.
- Voucher com 2+ quartos vira nota dividida.

### Corrigido

- Resposta do hóspede virava "✅ NF concluído".

## [2026.10.06] — 2026-10-06

### Adicionado

- **Cada PC publica a versão** na aba `PCs_Painel`.
- Vigia do Outlook em todos os PCs, página Atividade e atualização sozinha.
- Enviar NF com seletor de assinatura; sugestões do Dropbox só com nota confirmada.

## [2026.10.05] — 2026-10-05

### Adicionado

- Canceladas/substituídas pelos arquivos renomeados no Dropbox.
- NF enviada ao e-mail do pedido, com o anexo, conclui o pedido.

### Mudou

- Identidade do PC só pelas contas do Outlook: `maquina.json` copiado de outro PC não vale mais.

### Corrigido

- O robô abria PDF "somente online" do Dropbox (agora não abre).

## [2026.10.03] — 2026-10-03

### Adicionado

- Guia de instalação completo (ambientes, `.venv`, tarefas).
- Organizador e classificador de e-mails do PC do Bernardo (só leitura + categorias).

## [2026.10.01] — 2026-10-01

### Adicionado

- **Painel Notas Fiscais** como aplicativo próprio (pywebview + WebView2), com a fila sincronizada pela Planilha Central.
- Confirmação de NFs emitidas para todas as solicitações.
- Telas Visão geral e Hotéis com dados do Mail Analytics.
- **Enviar NF ao hóspede pelo Painel**, saindo da caixa do hotel, no estilo Outlook.

## [2026.09.29] — 2026-09-29

### Mudou

- Limpeza de comentários e docstrings.

## [2026.09.27] — 2026-09-27

Primeira versão no git. Inclui o que veio antes: o robô novo (23/09, Outlook no lugar do Apps Script que estourava a cota
do Gmail) e a Planilha Central (24/09).

### Adicionado

- Identidade do PC pelas contas do Outlook.
- Uma solicitação por e-mail, com teto de e-mails por rodada.
- Nota dividida, leitura da descrição da NF (check-in/out, diárias, estacionamento, consumo); a NF só fecha o pedido
  certo.
- Instalador único (Python, Git, `.venv`, chave, identidade, agendamento) e pacote para pendrive.
