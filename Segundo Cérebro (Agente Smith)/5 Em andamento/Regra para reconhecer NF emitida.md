# Regra para reconhecer NF emitida

**Situação (29/10/2026):** o João não gostou de o Painel reconhecer sozinho que a nota já foi emitida e oferecer o botão **Concluir** ao lado do e-mail. Isso foi **desligado**. A regra concreta ainda vai ser escrita por ele.

## O que está desligado
Na tela do e-mail (`correio.js`, constante `RECONHECE_NF = false`):
- etapas "NF pronta" e "NF enviada" da ficha do pedido (ficam só "Recebido" e "Dados completos");
- o botão azul **Concluir** (o botão principal passa a ser "Pedir o que falta" ou "Enviar NF");
- as linhas "NF na pasta / Ainda não emitida", "Pede nova nota" e o aviso "marcada como enviada, mas não achei o envio";
- a caixa "Histórico do hóspede x notas prontas" e a busca `/api/nf_cobre` por e-mail aberto.

## O que continua como estava
- Mover a conversa para a pasta "NF enviada" **na mão** (menu do e-mail, "Tirar da caixa de entrada").
- O código de reconhecimento (`nf_achadas.py`, `nf_cobre.py`) e a urgência por "pede nova nota" no servidor: não foram mexidos. A tela é que não os usa mais.

## O que falta o João definir
1. O que prova que a nota **foi emitida** (arquivo na pasta do Dropbox? número da NF? PDF com o CPF/CNPJ certo?).
2. O que prova que ela **foi enviada** (e-mail nos Itens Enviados com o PDF anexado? só pelo Painel?).
3. Quando o Painel pode **sugerir** concluir e quando não pode.

Para religar: mudar `RECONHECE_NF` para `true` em `app_ui/correio.js` e rodar os testes de `testes/test_resumo_fixo.py`.

Voltar: [[00 Início]]
