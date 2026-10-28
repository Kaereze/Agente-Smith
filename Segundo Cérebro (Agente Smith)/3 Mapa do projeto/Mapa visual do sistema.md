---
tipo: mapa
pasta: "3 Mapa do projeto"
pai: "[[00 Início]]"
prioridade: P2
atualizado: 2026-10-28
tags: [cerebro/mapa, diagrama]
---
# Mapa visual do sistema (diagrama no VS Code)

> Arquivo: `3 Mapa do projeto/Mapa do sistema.drawio`. Mostra como o pedido entra, passa pelos 4 PCs e sai até o hóspede. Texto de apoio em [[Visão geral do projeto]], [[Planilhas e abas]], [[Pessoas e PCs]] e [[API do Painel]].

## Como abrir
1. No VS Code, instale a extensão **Draw.io Integration** (autor: hediet; id `hediet.vscode-drawio`). Ctrl+Shift+X, busque, Instalar.
2. Abra o arquivo `Mapa do sistema.drawio`. Ele abre como diagrama editável: arraste blocos, mude textos, ligue linhas novas.
3. As linhas são tracejadas e **animadas** (o tracejado anda no sentido do dado).

## O que tem nele
- **46 blocos** (fonte, processo, armazena, tela, ação, saída, computador), **68 ligações** e 3 notas amarelas.
- **7 quadros** (etapas): 1 De onde vêm os dados, 2 Coleta e Outlook de cada PC, 3 Planilha Central, 4 Painel Fiscal, 5 Saída, Leitura da Gerência, Os 4 computadores.
- **7 cores de linha** (legenda no canto superior esquerdo do diagrama): pedido do hóspede até o e-mail ao hotel, e-mails/Outlook/telas, nota fiscal e envio ao hóspede, os 4 PCs entre si, código e atualização, números da Gerência, faxina e saúde. Sem verde ([[ADR-03 Telas novas na paleta da Auditoria, sem verde]]).

## Para o Claude: como ler e conferir
- É XML de texto. **Não leia o arquivo inteiro** (95 KB). Procure pelo id: `grep -n 'id="n_srv"' "Mapa do sistema.drawio"`.
- Cada bloco é `n_<nome>` (ex.: `n_robo`, `n_conf`, `n_srv`, `n_c_pcs`) e tem estes campos (Editar dados no draw.io): `tipo`, `quando`, `roda_em`, `o_que_faz`, `regras` (separadas por ` | `) e `codigo` (arquivo no repositório). Cada ligação é `e_<n>_<de>__<para>` e tem `caminho`, `de`, `para` e o texto da seta.
- **Conferir o diagrama contra o código:** abra o arquivo do campo `codigo` e veja se o que o bloco diz (frequência, quem roda, regra) ainda é verdade. Se divergir, diga qual bloco e o que está certo, e proponha a correção ao João antes de mexer.
- **Quando o João mudar o diagrama** (movendo, apagando ou criando ligação): leia só os ids tocados, compare com o código e responda: "esta ligação existe no código?", "esta ação funciona do jeito desenhado?", "este bloco está fora do lugar (etapa errada)?".
- **Quando o código mudar o fluxo** (nova rota, novo robô, nova fila): atualize o diagrama no mesmo passo (item na lista de fim de etapa do [[Manual do Claude (receitas)]]).

## Regras para editar
- Mantenha os ids (`n_…`, `e_…`); outros arquivos e o Claude dependem deles.
- **Só dado inventado ou genérico.** Nunca nome, CPF, e-mail de hóspede, nem ID de planilha, chave ou senha ([[Dados de hóspedes (LGPD)]]).
- Cor da linha = caminho, não fique trocando; para um caminho novo, crie a cor na legenda.
- Depois de editar, o Claude abre o `.drawio` pelo XML para confirmar que não sobrou ligação sem ponta.

## Origem e limites
- Feito em 28/10/2026 lendo o código de ponta a ponta (61 módulos em `src/`, tarefas do Windows em `Automacoes/`, `config.json`). Versão animada em página web (com painel de detalhes ao clicar) foi publicada na conversa do dia; **o `.drawio` é a fonte de verdade daqui para frente**.
- Não foi aberto o app rodando nem as planilhas: o mapa mostra o que o **código** faz. O que o João vir diferente na prática é justamente o que vale a pena apontar.
- Na versão do VS Code não há ícones nos blocos nem o painel de detalhes; os detalhes ficam nos campos do bloco (Editar dados).

Voltar: [[00 Início]]
