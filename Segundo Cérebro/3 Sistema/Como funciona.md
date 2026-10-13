---
nivel: "3 · Como o sistema é"
pai: "[[00 Início]]"
tags: [cerebro/sistema]
---
# Como funciona (em português simples)

## O caminho de um pedido de NF
1. O hóspede preenche o **formulário** do hotel. A resposta cai na **planilha do hotel**, que nós só lemos.
2. A cada 30 min, o PC principal **copia** as planilhas que mudaram para a **Planilha Central** (`src/sincronizar.py`, tarefa "SolicitacoesNF_CopiaHoteis").
3. Logo depois, o **robô** manda um e-mail por pedido para a caixa `notafiscal@` do hotel e marca "Enviado" só depois de sair.
4. O e-mail cai na **Caixa de Entrada** do Outlook do agente. O **conferente** (roda em cada PC) lê a caixa, liga e-mail ↔ pedido, acha a NF no Dropbox e põe as etiquetas.
5. O agente emite a NF e envia ao hóspede. Quando resolve, **tira o e-mail da Caixa de Entrada** e o pedido some do Painel.

## O Painel Fiscal
- Aplicativo local (`127.0.0.1:8765`, janela pywebview). O X **só esconde**; ele liga escondido com o Windows.
- **Espelho do Outlook**: não guarda histórico. Notas fiscais = solicitações do robô que estão na Caixa de Entrada dos 4 PCs. Caixa de entrada = a caixa inteira, menos os respondidos. A busca de cima pergunta **ao vivo** aos Outlooks.
- **Lido**: abrir no Painel marca lido no Outlook; lido no Outlook só passa ao Painel depois de 5 minutos; excluído some na hora.
- Os PCs trocam dados pela **Planilha Central** (abas CaixaPedidos_, Correio_, PCs_Painel, Comandos_PC…) e, para a busca ao vivo, direto pela rede local na **porta 8766** (pedidos assinados, só rede local).
- **Gerência**: relatório do dia e da semana tirado do **Mail Analytics** (só leitura).
- **Saúde**: faixa vermelha no topo quando algo sai do normal (cópia parada, Outlook fechado, versão diferente, cadastro incompleto…).

## Atualizar os 4 PCs
- Commit → push na `main` → as branches `Bernardo`, `Christian` e `clara` ficam iguais → botão **"Atualizar todos os PCs"** (Máquinas).
- Cada PC baixa do GitHub e reinicia sozinho pela tarefa do Windows "SolicitacoesNF_Reiniciar". Registro em `logs/atualizacao.log`. Se o código no disco ficar 5 min diferente do que está rodando, o Painel tenta de novo.

## Limites que importam
- **Cota do Google**: 60 leituras/min somando os 4 PCs. Toda leitura nova conta.
- Nada pode acumular sem prazo nos PCs ("bola de neve"): as abas de registro são limpas em 3 a 7 dias.

Ver: [[Glossário]] · [[Pessoas e PCs]] · [[Problemas resolvidos]].
