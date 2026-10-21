---
tipo: documento
pasta: "6 Documentos"
pai: "[[00 Início]]"
prioridade: P2
tags: [cerebro/documentos, painel, guia]
---
# Guia do Painel Fiscal

> Para a equipe (João, Clara, Cristian, Bernardo) e para quem chegar depois.
> Como cada tela funciona desde a **Prévia 5** (20/10/2026): o visual do Outlook escuro, com espaçamento folgado.
> Prévia aprovada no quadro de design "Painel Fiscal — Repaginação", página "Prévia 5" (dados inventados).

## O que é
O Painel é o **espelho do Outlook dos 4 PCs**: mostra os e-mails das caixas dos hotéis e os pedidos do formulário,
sem guardar histórico próprio. Ele deixa responder, mandar a NF e encaminhar **pela caixa do próprio hotel**, no PC
dono dela. Regras de fundo: [[Painel em casa]] (PC de casa), [[O que não mexer]], [[Dados de hóspedes (LGPD)]].

## A tela, de cima para baixo
| Parte | O que é |
|---|---|
| Trilho da esquerda | Ícones das telas: E-mails, Notas fiscais, Visão geral, Gerência, Monitoramento (só admin). Urgência e Itens Enviados ficam dentro dos e-mails (Favoritos e cada caixa). O traço azul marca onde você está; o número vermelho é o que espera. |
| Abas do topo | Página Inicial · Enviar/Receber · Exibir, como no Outlook, **só na tela de e-mails**, junto com a faixa de botões (nas outras telas, nenhuma das duas aparece). "Caixa de" filtra por agente. A **pesquisa** fica à direita (atalho Ctrl+E). |
| Faixa de comandos | A caixa cinza com os botões da tela (Novo e-mail, Responder, Encaminhar, Enviar NF…). Botão apagado = ainda não dá pelo Painel; faça no Outlook. |
| Barra de baixo | Itens e não lidos; Central sincronizada, robô, PCs no ar, tema, Modo professor e ajuda (tecla ?). |
| Avisos | A caixinha no canto direito de baixo mostra o que saiu do normal. O que fazer com cada aviso: [[Se o robô parar]]. |

## E-mails (igual ao Outlook)
- **Pastas** à esquerda: Favoritos (Caixa de Entrada de todas as caixas, Urgência, Formulários do robô, Itens Enviados) e as caixas de cada PC.
  Cada PC tem um cabeçalho (pessoa, bolinha verde = ligado / cinza = desligado, nome do PC, quantas caixas e o total de não lidos);
  cada caixa mostra o hotel em cima e o e-mail embaixo, com os não lidos na pílula azul. "Mostrar mais N caixas" abre o resto.
- **Lista** no meio, por dia (Hoje, Ontem…): quem mandou e a hora; o assunto em azul; a prévia.
  - Traço azul = não lido. Linha **avermelhada com bandeira** = urgente. Clipe = tem anexo. Quadradinho azul = formulário.
  - Setas ↑ ↓ andam pela lista e já abrem o e-mail.
  - **Botão direito** num e-mail (ou Shift+F10): **Marcar como lido / não lido** e **Marcar como urgente / Tirar urgência**.
    A urgência vale na hora para a equipe toda e fica guardada no Outlook do PC dono (categoria vermelha "Urgente (Painel)").
    "Tirar urgência" vence a urgência automática (fica a categoria "Sem urgência (Painel)"). Esc fecha o menu.
  - **E-mail da Ouvidoria** chega já como urgente (motivo "E-mail da Ouvidoria").
  - **Filtro** (botão ao lado de "Por Data"): Pedido de correção · Sem resposta · Com anexo · Nota dividida, com quantos e-mails cada um tem na caixa aberta. Um por vez; o ✕ limpa.
- **Leitura** à direita, como o Outlook: assunto; o círculo com as iniciais; quem mandou, Para; os botões Responder, Responder a todos, Encaminhar e ⋯; a data.
  Embaixo: de onde veio (hotel e PC), os **anexos** (clique abre o visualizador), a **ficha do pedido** e o texto.
- **Ficha do pedido** (3 faixas): título com o hotel, quem cuida, NF e prazo; os 5 dados (**Tomador · CNPJ/CPF · O que pede · Hóspede · CPF do hóspede**: o CPF do hóspede aparece **sempre**, mesmo com a nota no CNPJ); os botões Enviar NF, Pedir o que falta e Marcar tratativa. O que falta aparece em âmbar ("falta pedir").
- Abriu = lido para a equipe toda. "Não lido/Lido" (Ctrl+U / Ctrl+Q) volta.

## Resumo fixo do hóspede (topo do e-mail, 21/10/2026)
- Ao abrir um e-mail, a faixa de cima fica **parada** enquanto você rola: **quem é**, as **etiquetas**, o **prazo** e os botões
  **Pedir o que falta · Marcar tratativa · Enviar NF**.
- Linha **Quer**: "Nota no nome de … · CNPJ/CPF", o que entra na nota e hotel + datas (com as diárias). O que falta aparece em âmbar.
- **Ver ficha completa** abre a tabela verde/creme do pedido logo abaixo; o Painel lembra se você deixou aberta.

## Etiquetas (iguais em todas as telas, 21/10/2026)
- **Situação do pedido** (uma por vez, pílula cheia): **Sem NF** · **Falta dado** (mostra o que falta) · **NF pronta,
  falta enviar** (a nota existe e não saiu) · **NF enviada** (com o número) · **Correção**.
- **Alertas** (somam, com contorno): **Urgente** (prazo, dias sem resposta, Ouvidoria, marcado à mão) · **Pediu de novo /
  Possível repetido** · **Nota dividida** · **CPF/CNPJ diferente** · **Diz que não recebeu**.
- Responder o hóspede não muda a situação: só vira "NF enviada" quando a nota sai.

## Formulário aberto (tabela verde e creme em grupos, 20/10/2026)
1. **Enviado por:** o e-mail de quem preencheu.
2. **Dados para emissão de Nota Fiscal:** a tabela **Campo / Valor** como chega no e-mail (cabeçalho verde, linhas creme),
   separada em 3 grupos:
   - **Tomador da nota:** Nome · CPF/CNPJ · CEP · Telefone
   - **Estadia:** Hotel · Titular da reserva · CPF do titular · Datas (check-in → check-out, com o número de diárias)
   - **Como quer a nota:** O que pede · Nota dividida · Dividir em · Valor · Enviar para
   CPF/CNPJ, CEP e telefone aparecem formatados (com "CPF" ou "CNPJ" ao lado). Campo fora da lista vai para "Outros
   campos"; campo vazio não aparece. O **botão de copiar** (fim da linha) copia o valor como o hóspede escreveu, para
   colar na emissão.
3. Rodapé: **Aceitou os termos** e **Enviado em**.
4. **Histórico deste hóspede nesta hospedagem** (embaixo): os e-mails trocados com quem preencheu o formulário (e os outros
   e-mails dele com o mesmo CPF/CNPJ), só do mesmo hotel e a partir de 30 dias antes do check-in. "ver tudo do hóspede"
   mostra o histórico inteiro dele. Sem o check-in no formulário: aparece tudo do hóspede.
Os dois formulários (antigo e novo) caem nos mesmos quadros. Se o pedido não está na lista do Painel (ex.: já respondido
há dias), os campos saem do próprio texto do e-mail do Emissor Automático.
A etiqueta azul "Nota dividida" aparece embaixo do remetente quando a nota é dividida.

## Pesquisa (instantânea)
Digite 3 letras de um nome, CPF/CNPJ, e-mail, hotel ou número de NF.
- **Na hora:** os **pedidos do formulário** (selo verde "na hora", com o tempo) e os **e-mails dos 4 PCs pelo índice**
  (selo "índice · 0,03 s"): 12 meses de Caixa de Entrada, Itens Enviados e Itens Excluídos das caixas dos hotéis.
  Acha sem acento e com palavra pela metade ("conceicao" acha "Conceição", "Pereg" acha "Perego"), CPF com ou sem pontos.
- **Procurar também direto no Outlook** (botão embaixo do título "E-mails"): pesquisa ao vivo no Outlook de cada PC,
  como antes (alguns segundos). Use quando o e-mail é de mais de 12 meses ou acabou de chegar e não apareceu.
- Selo "montando": o índice de algum PC ainda está sendo montado (do mais novo pro mais velho; o 1º leva poucos minutos).
- Clicar num pedido abre a **ficha** em Notas fiscais; clicar num e-mail abre a leitura.
- PC desligado: os e-mails dele que já estavam no espelho continuam aparecendo.

## Responder e enviar a NF (sem espera)
1. Responder, Responder com a NF ou Encaminhar abre a mensagem **dentro da leitura**, com o original citado embaixo.
   Num **formulário**, o original aparece na mesma tabela verde e creme e o **Para** já vem com o e-mail de quem
   preencheu ("Enviado por"), nunca o do Emissor Automático. Sem esse e-mail no formulário, o Para fica vazio.
2. Anexe a NF (arraste ou escolha); o Painel **confere a NF com o pedido** (CPF/CNPJ, valor, nome) e só avisa se algo não bate.
3. Clicou em **Enviar**: a janela **fecha na hora**. O aviso no canto esquerdo de baixo acompanha:
   *Entregue ao PC de …* → *Saindo pela caixa do hotel* → *Conferido em Itens Enviados* (✓ com a hora).
4. Deu errado (ex.: PC dono desligado)? O aviso fica vermelho com o motivo e o botão **Escrever de novo** reabre a
   mensagem com o texto (o anexo precisa ser escolhido de novo).
O e-mail sai **sempre da caixa do hotel**, no PC dono dela. Nunca por outra caixa.

## Notas fiscais
Os pedidos do formulário que estão na Caixa de Entrada dos 4 PCs. Lista em 2 andares (hóspede e hora; hotel, agente e
prazo; etiquetas) e a ficha sempre à direita. Prazo: 48 h corridas do pedido (verde → âmbar → vermelho).
- **Situação: Todas ▾** (em cima da lista): Todas as solicitações · Minhas · Urgentes · Atrasadas · Falta dado ·
  CPF/CNPJ diferente · Nota dividida · Envio pendente · NF emitida, cada uma com a contagem. Um por vez; o ✕ tira.
  Do lado, o **Hotel ▾**.

## Visão geral · Gerência · Monitoramento
- **Visão geral:** resumo de ontem (ou hoje até agora), o que precisa de atenção e a equipe.
- **Gerência:** relatório do mês contra o mês anterior, onde os pedidos se perdem e o que melhorar.
- **Monitoramento** (só o administrador): Máquinas (os 4 PCs, Outlook, conferente, versão) e Log.

## Atalhos
Ctrl+E pesquisar · ↑ ↓ andar na lista · Enter abrir · Esc fechar · Ctrl+R responder · Ctrl+Shift+R responder com NF ·
Ctrl+F encaminhar · Delete excluir · Ctrl+U não lido · Ctrl+Q lido · Shift+F10 menu do e-mail (= botão direito) · ? ajuda.

## Para quem mexe no código
Onde fica cada coisa: [[Onde mexer]] (linhas "Prévia 5"). Regras de visual: [[Padrão de design]].

Voltar: [[00 Início]]
