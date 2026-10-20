# Histórico de versões

O que mudou em cada entrega do robô Solicitações NF e do Painel Fiscal, da mais nova para a mais antiga.

- **Versão = data da entrega** (`AAAA.MM.DD`), com uma etiqueta no git de mesmo nome no último commit do dia. O Painel
  continua mostrando o commit (ex.: `f9d21f1 19/10`) em Máquinas.
- Categorias: **Adicionado**, **Mudou**, **Corrigido**, **Removido**, **Segurança**.
- Entradas antigas não são reescritas; só se acrescenta no topo. O detalhe de cada dia fica no diário do
  [Segundo Cérebro](Segundo%20C%C3%A9rebro/4%20Hist%C3%B3rico/Di%C3%A1rio/).

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
