---
tipo: mapa
pasta: "3 Mapa do projeto"
pai: "[[00 Início]]"
tags: [cerebro/mapa]
---
# Visão geral do projeto

## Em uma frase
Robô que leva cada pedido de NF dos hotéis até a caixa do agente, e um **Painel Fiscal** que é o espelho do Outlook dos 4 PCs, para a equipe emitir e enviar a nota sem caçar informação.

## Quem e por quê
- **Quem:** setor fiscal da Rede Andrade (~73 hotéis). 4 agentes: João, Clara, Cristian, Bernardo ([[Pessoas e PCs]]).
- **Problema:** pedidos espalhados entre planilhas dos hotéis e e-mails; muitas trocas com o hóspede; o Apps Script antigo estourava a cota do Gmail.
- **Futuro:** apresentar a uma empresa grande; depois reservas, ligações internas e um banco central (Supabase).

## O caminho de um pedido
1. Hóspede preenche o **formulário** → cai na **planilha do hotel** (só lemos).
2. A cada 30 min o PC principal **copia** as planilhas que mudaram para a **Planilha Central** (`src/sincronizar.py`).
3. O **robô** manda um e-mail por pedido para a caixa `notafiscal@` do hotel (`src/main.py`).
4. O **conferente** de cada PC lê o Outlook, liga e-mail ↔ pedido, acha a NF no Dropbox e põe etiquetas (`src/conferente.py`).
5. O agente emite e envia a NF; resolvido, **tira o e-mail da Caixa de Entrada** → some do Painel.

## O Painel Fiscal
- Aplicativo local (`127.0.0.1:8765`). O X só esconde; liga escondido com o Windows.
- **Espelho**: Notas fiscais = solicitações na Caixa de Entrada dos 4 PCs; Caixa de entrada = a caixa inteira menos os respondidos; a busca pergunta ao vivo aos Outlooks.
- **Lido**: abrir no Painel marca no Outlook; do Outlook para o Painel só depois de 5 min; excluído some na hora.
- Os PCs trocam dados pela **Planilha Central** ([[Planilhas e abas]]) e, na busca ao vivo, pela rede local (porta 8766).
- **Gerência** lê o Mail Analytics (só leitura). **Saúde** = faixa vermelha quando algo sai do normal.
- **Modo casa**: no PC de casa, dados reais só para ver ([[Painel em casa]]).

## Atualizar os 4 PCs
Commit → `main` → branches `Bernardo`, `Christian`, `clara` iguais → "Atualizar todos os PCs". Cada PC baixa e reinicia pela tarefa `SolicitacoesNF_Reiniciar` (log em `logs/atualizacao.log`). Passo a passo: [[Como entregar]].

## Limites que mandam em tudo
- **Cota do Google**: 60 leituras/min somando os 4 PCs.
- **Nada acumula sem prazo** (faxina de 3 a 7 dias nas abas de registro).
- Ordem do que vence: [[Hierarquia de prioridades]].

Detalhe técnico completo: [[README técnico]] · instalação: [[Instalação e pendências]].
