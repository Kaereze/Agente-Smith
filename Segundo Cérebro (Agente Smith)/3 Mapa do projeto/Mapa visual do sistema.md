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

## O que tem nele (atualizado em 28/10/2026: o mapa completo)
- **156 blocos** e **452 ligações**. Entram **todos os 63 módulos de `src/`**, os 14 scripts de `Automacoes/`, os `.bat` e `.vbs` de `Bat/` e da raiz, `robo.py`, as ferramentas (`ferramentas/`, `.githooks`, GitHub Actions), o Apps Script da Planilha Central, a interface (`app_ui`: página, 4 scripts e 7 peças únicas), os 625 testes, os arquivos locais de cada PC (`estado/`, `logs/`, `config`), a Planilha Central (10 grupos de abas), o Outlook, o Dropbox, o Mail Analytics, o GitHub e os 4 computadores.
- **198 ligações de dados** (setas coloridas, tracejadas e animadas: por onde a informação anda) e **254 dependências** (quem usa quem, tiradas das importações do código). **As dependências ficam numa camada escondida**, chamada "Quem usa quem (dependências)": no draw.io, abra o painel de Camadas (Ctrl+Shift+L) e ligue a camada para vê-las.
- **15 quadros** (etapas): 1 Fora do sistema, 2 Google e Outlook, 3 Cópia e envio, 4 Conferência de cada PC, 5 Planilha Central, 6 Arquivos deste PC, 7 Painel (dados e regras), 8 Painel (rede, saúde e manutenção), 9 Telas, 10 Ação e saída, Leitura da Gerência, Apoio comum, Instalar e manter os PCs, Qualidade e ferramentas, Os 4 computadores.
- **Linha grossa** = a produção de ponta a ponta (do pedido do hóspede até a nota chegar nele). As outras cores de linha: pedido, e-mails e telas, nota e envio, os 4 PCs, código e testes, Gerência, faxina e saúde, instalação (legenda no canto do desenho). Sem verde ([[ADR-03 Telas novas na paleta da Auditoria, sem verde]]).
- Dois módulos de `src/` são **ferramentas de linha de comando**, não código morto: `classificador` (só lê e mostra o que falta emitir) e `organizador_emails` (aplica as categorias do Outlook).

## A aba dentro do Painel (no ar na versão 2026.10.28.2)
- Fica no grupo **Admin**, abaixo de Monitoramento, e **só o João vê, no PC principal** (`e_admin_aqui`). O servidor também recusa (403) quem pedir por fora, e o mapa não está na lista pública de arquivos. Ver [[ADR-11 Aba Agentes do Smith - só o administrador, só sinal real]].
- **Onde está:** a página do mapa é `app_ui/agentes/mapa.html` (HTML único, sem internet), carregada num quadro (`iframe`) só quando a aba abre. O estado ao vivo vem de `src/agentes_smith.py`, pela rota `/api/agentes`.
- **Estado ao vivo é só o que o Painel já sabe de verdade** (aba `PCs_Painel`): PC ligado, versão, Outlook, conferência, rede local, e-mails presos, e cópia e robô de envio do PC principal. O resto aparece como **"sem sinal ao vivo"**. Hoje (28/10) há sinal para **8 dos 19** agentes (o robô de envio entra quando o PC principal publica o horário do último envio); medir os outros (faxina, índice, notas achadas, espelho, vigias…) pede que cada um publique um sinal próprio, e fica para uma próxima entrega.
- **Teste de completude:** `testes/test_agentes_smith.py` falha se um módulo de `src/` não tiver bloco no mapa. Ao criar um módulo, acrescente o bloco em `var N` e as ligações em `var E` do `mapa.html` e no `.drawio`. (O gerador que montou o mapa ainda não está no repositório: por enquanto é à mão.)

## Para o Claude: como ler e conferir
- É XML de texto. **Não leia o arquivo inteiro** (430 KB). Procure pelo id: `grep -n 'id="n_srv"' "Mapa do sistema.drawio"`.
- Cada bloco é `n_<nome>`; os módulos de `src/` usam o **nome do arquivo** (ex.: `n_main`, `n_conferente`, `n_app_servidor`, `n_sincronizar`) e as abas da Central usam `n_c_...` (ex.: `n_c_pcs`) e tem estes campos (Editar dados no draw.io): `tipo`, `quando`, `roda_em`, `o_que_faz`, `regras` (separadas por ` | `) e `codigo` (arquivo no repositório). Cada ligação é `e_<n>_<de>__<para>` e tem `caminho`, `de`, `para` e o texto da seta.
- **Conferir o diagrama contra o código:** abra o arquivo do campo `codigo` e veja se o que o bloco diz (frequência, quem roda, regra) ainda é verdade. Se divergir, diga qual bloco e o que está certo, e proponha a correção ao João antes de mexer.
- **Quando o João mudar o diagrama** (movendo, apagando ou criando ligação): leia só os ids tocados, compare com o código e responda: "esta ligação existe no código?", "esta ação funciona do jeito desenhado?", "este bloco está fora do lugar (etapa errada)?".
- **Quando o código mudar o fluxo** (nova rota, novo robô, nova fila): atualize o diagrama no mesmo passo (item na lista de fim de etapa do [[Manual do Claude (receitas)]]).

## Regras para editar
- Mantenha os ids (`n_…`, `e_…`); outros arquivos e o Claude dependem deles.
- **Só dado inventado ou genérico.** Nunca nome, CPF, e-mail de hóspede, nem ID de planilha, chave ou senha ([[Dados de hóspedes (LGPD)]]).
- Cor da linha = caminho, não fique trocando; para um caminho novo, crie a cor na legenda.
- Depois de editar, o Claude abre o `.drawio` pelo XML para confirmar que não sobrou ligação sem ponta.

## Origem e limites
- Feito em 28/10/2026 lendo o código de ponta a ponta. As ligações de dados vêm das notas do cofre e dos comentários dos módulos; as dependências vêm das importações do código (análise automática). Versão animada em página web (com painel de detalhes ao clicar) foi publicada na conversa do dia, e a mesma base alimenta a aba nova do Painel ([[Designs]], 28/10/2026); **o `.drawio` é a fonte de verdade daqui para frente**.
- Não foi aberto o app rodando nem as planilhas: o mapa mostra o que o **código** faz. O que o João vir diferente na prática é justamente o que vale a pena apontar.
- Na versão do VS Code não há ícones nos blocos nem o painel de detalhes; os detalhes ficam nos campos do bloco (Editar dados).

Voltar: [[00 Início]]
