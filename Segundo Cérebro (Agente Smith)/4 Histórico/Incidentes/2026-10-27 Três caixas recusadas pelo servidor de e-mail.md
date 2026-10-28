---
tipo: incidente
pasta: "4 Histórico"
pai: "[[Incidentes]]"
tags: [cerebro/historico, incidente]
---
# Três caixas recusadas pelo servidor de e-mail (27/10/2026)

**Gravidade:** média · **Quem percebeu:** o João, ao ver o resultado do "Enviar/Receber todas" no Outlook.

## O que aconteceu
No Outlook do PC do João, 3 das 38 tarefas de envio e recebimento falharam (as caixas de Rondonópolis, Pousada Jeri e Bahia). Erro: `0x800CCC92` e resposta do servidor `-ERR [SYS/TEMP] Account is temporarily unavailable`. O Outlook abriu a janela de senha, **mesmo com a senha certa**.

## Causa
**Do lado do servidor de e-mail** (recusa temporária do login). Não foi a senha, a rede nem um segundo Outlook (conferido: um só Outlook, com janela). Hipótese ainda aberta: muitos logins seguidos do mesmo IP do escritório (o "Enviar/Receber todas" roda nos 4 PCs ao mesmo tempo; foi apertado 4 vezes em 26 minutos). O Cristian e a Pousada Jeri já estavam presos desde 24/10, antes do botão existir, então **não é só o botão**.

## Impacto
E-mails do robô presos na Caixa de Saída. O robô **não duplica**: antes de mandar ele procura o código `NF-…` em Itens Enviados e na Caixa de Saída. Os presos saem sozinhos quando o servidor voltar.

## O que muda
- Orientação à equipe: esperar uns 15 min, não apertar F9 sem parar, clicar Cancelar na janela de senha.
- **Proposta estacionada:** 5 min entre uma rodada e outra do "Enviar/Receber todas".
- **Pendente:** quem administra o e-mail da rede precisa olhar as 3 contas (bloqueio, trava ou caixa cheia).
