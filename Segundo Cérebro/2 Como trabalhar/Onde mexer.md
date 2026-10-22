---
tipo: guia
pasta: "2 Como trabalhar"
pai: "[[00 Início]]"
prioridade: P1
tags: [cerebro/trabalho]
---
# Onde mexer — vá direto ao ponto

> Antes de procurar no código, ache a tarefa aqui. Tela = `app_ui/`. Servidor = `src/app_servidor.py` (classe `Estado`). Tamanho, propósito e risco de cada pasta e arquivo: [[Pastas e arquivos]].

## Telas do Painel
| Quero mexer em… | Tela (front) | Dados (servidor) |
|---|---|---|
| **Notas fiscais**: lista, colunas, abas de agente, filtros de situação | `index.html` → `desenharFiltros`, `linhaHtml`, `desenhar`, `segOperadores`, `detalheOperador`, `desenharAbasNotas`, `colunaSituacao` | `fila_da_tela`, `fila`, `resumo_caixa`; ligação pedido↔e-mail em `app_dados.py` → `ligar_caixa` |
| **Ficha da solicitação** | `index.html` → `desenharDetalhe`, `fichaResumoHtml` (resumo no topo; acha os campos pelo nome, sem acento), botão `data-pedir-dados`; seletor do topo em `desenharSeletorCaixa` (mostrado só em fila/correio por `trocarVista` no `painel.js`), `noOutlookHtml`, `quadrosEtapa` | `conversa`, `_alertas_documento`, `_hospedes` |
| **Caixa de entrada / Urgência / Itens enviados** (igual ao Outlook) | `correio.js` → `desenharCorreio`, `desenharPastas` (caixas de entrada à esquerda), `linhaEmail`, `desenharLeituraCorreio`, faixa de comandos `[data-cx-faixa]`; estilo em `index.html` (`#v-correio.ol`) | `_montar_correio`, `lista_correio`; juntar PCs em `correio.py` (`juntar`, `lido_atual`); o que cada PC publica em `espelho_emails.py` |
| **Busca de cima** (índice local; Outlook ao vivo no botão) | `correio.js` → `buscarNoOutlook(busca, vivo)`, `agendarBusca`, `secoesDaBusca` (selo e botão `[data-busca-vivo]`) | `buscar_outlook(termo, vivo)`, `rede_buscar` (responde pelo índice); `indice_emails.py` (`Indice`, `Montador`, linha de fundo `iniciar_indice`); ao vivo em `busca_outlook.py`; entre PCs `rede_local.py` (porta 8766) |
| **Botão direito no e-mail** (lido/não lido, urgente/tirar urgência) | `correio.js` → `abrirMenuEmail`, `acaoMenuEmail`; estilo `.cx-ctx` em `index.html` | `marcar_urgencia` (`POST /api/correio/urgencia`) → evento URGENTE/NAO_URGENTE + fila `envio_nf.URGENCIA` → `marcar_urgencia_no_outlook` no PC dono; categoria lida em `espelho_emails.marca_das_categorias`; regra em `correio.juntar` (Ouvidoria em `motivo_urgencia`) |
| **Resumo fixo do hóspede** (faixa parada no topo do e-mail) | `correio.js` → `resumoFixoHtml`, `dadosDoResumo`, botão `[data-resumo-ficha]` (`cx.fichaAberta`, `localStorage painel.fichaAberta`); estilo `.ol-resumo` em `index.html` | — |
| **Aviso de pedido repetido** (faixa laranja embaixo do resumo, comparar) | `correio.js` → `avisoRepetidoHtml`, `outroDoRepetido`, `linhasComparacao`, botão `[data-repetido-comparar]` (`cx.compararRep`); estilo `.ol-repetido` em `index.html` | só lê `repetido_de`/`repetidos` (junção automática em `hospedes.marcar`) |
| **Histórico embaixo do e-mail** (formulário: pelo e-mail de quem preencheu, só esta hospedagem) | `correio.js` → `alvoHistorico` (`DIAS_ANTES_CHECKIN`), `carregarHistorico`, `historicoHtml(h, e, alvo)`, botão `[data-hist-tudo]` | `/api/correio/conversa`, `/api/correio/buscar` |
| **Peças únicas** (uma vez só, todas as telas usam) | `app_ui/pecas/` — `filtro.js` (pílula + menu); `etiqueta.js`/`etiqueta.css` (situações e alertas, com as regras); o servidor serve a pasta (`ESTATICOS`) e a janela recarrega quando uma peça muda (`_marca_pagina`) | Teste `test_pecas.py` |
| **Notas fiscais: Situação ▾** (peça do Filtro) | `index.html` → `desenharFiltros` (`#status-cards`, `nfFiltroAberto`, `TOPO`/`AGIR`/`HISTORICO`), clique `data-st` / `data-nf-filtro-abrir` | — |
| **Monitoramento: escolher o PC** (peça do Filtro) | `painel.js` → `menuPcLog`, estado `at.pc` / `at.pcAberto`; estilo `.ol-filtro*` em `index.html` |
| **Lido / não lido** | `correio.js` → `abrirEmail`, `marcarNaoLido` | `evento_correio`, `_lido_no_outlook`; regra dos 5 min em `espelho_emails.lido_confirmado` |
| **Novo e-mail ao hóspede** (Caixa de entrada → "Novo e-mail") | `correio.js` → clique `#cx-novo`; `painel.js` → `abrirEnvioNF(null, {novo:true})`, `modeloSolicitacaoDados` | `contas_de_hotel`, `opcoes_email_novo`, `enviar_email_novo` (`GET/POST /api/email/novo`); `envio_nf.pedir(..., livre=True)` |
| **Responder / encaminhar / excluir** (formulário: Para = "Enviado por", original em tabela) | `correio.js` → `escrever`, `encaminhar`, `excluir`, `mostrarDesfazer`, `citacaoHtml`, `dadosDoFormulario`, `emailDoFormulario`; `painel.js` → Para do formulário em `abrirEnvioNF` | `responder_email`, `encaminhar_email`, `excluir_email` |
| **Visão geral** | `painel.js` → `desenharVisao`, `faixaAgora`, `contarNumeros` | `painel`, `atividade_resumo` |
| **Gerência / relatório dia e semana** | `painel.js` → `desenharGerencia`, `carregarRelatorio`, `htmlRelatorio` | `relatorio_semana`, `_contagem_fim_de_semana`; `relatorio_semana.py`, `contagem_painel.py` |
| **Máquinas / saúde (faixa vermelha)** | `painel.js` → `desenharMaquinas`; `index.html` → `desenharSaude`, `desenharPcsCabecalho` | `problemas_de_saude`, `_extras_pc`, `pcs`; regras em `saude.py`; PCs em `rede_pcs.py` |
| **Cadastro de hotéis** (cartão Cadastrar) | `painel.js` → `carregarCadastro`, `htmlCadastro` | `cadastro_faltando`, `adicionar_cadastro`; `saude.cadastro_faltando` |
| **Enviar NF ao hóspede** | `painel.js` → `abrirEnvioNF`, `validarEnvioNF`, `enviarNF`, `acompanharNF`, `escolherSelo` | `pedir_envio`, `conferir_anexos`, `situacao_envio`; `envio_nf.py` |
| **Enviar pendentes** (robô pela tela) | `painel.js` → `abrirEnvio`, `acompanharEnvio` | `app_envio.py` |
| **Assinaturas** (selos do Painel e imagem das assinaturas do Outlook) | `app_ui/assinaturas/<agente>.png` (1200×380) | `envio_nf.LARGURA_SELO`; no Outlook de cada PC: `python Automacoes	rocar_assinatura_outlook.py <agente>` (só troca a imagem, mantém o texto, guarda cópia `_arquivos.antes-AAAAMMDD`) |
| **Respostas prontas** | `painel.js` → `MODELOS_RESPOSTA`, `linhaModelos`, `dadosDoModelo` | — |
| **Modo Professor** (frases azuis) | `index.html` → `DICAS_BOTOES`, `aplicarDicasBotoes`, `aplicarProfessor` | `POST /api/professor` |
| **Agente do PC / menu do operador** | `index.html` → `desenharOperador`, `menuOperador` | `identidade.py`, `nome_do_agente` |
| **Cores, letras, espaçamento** | `index.html` → bloco `<style>`: base (início) → camada "Design fiscal" (~l.885) → "Organização" (~l.1015) → "limpeza" (fim). **Regra nova vai no fim**; tokens `--chao --folha --verde --creme` | — |
| **Gráficos** | `graficos.js` | — |

## Robôs e bastidores
| Quero mexer em… | Arquivo → função |
|---|---|
| **Cópia das planilhas dos hotéis → Central** | `sincronizar.py` → `rodar_agendado`, `sincronizar`, `_ler_planilha_hotel`, `hoteis_que_mudaram` · hotel com mais de uma planilha (formulário antigo + novo): `juntar_planilhas` · e-mail/nome por linha: `sheets._achar_colunas`, `_coluna_da_linha` · TRUE de volta no hotel: `linhas_para_marcar_no_hotel`, `escrever_true_no_hotel`, `espelhar_true_nos_hoteis` (chamado na cópia e em `main._marcar_e_registrar`) |
| **Envio das solicitações por e-mail** | `main.py` → `executar`; corpo do e-mail em `montar_email.py`; envio COM em `outlook.py`; diário em `diario_envios.py` · caixa de outro PC: `envio_pc_dono.py` → `OutlookComPcDono` (rede: `enviar_aqui`/`conferir_aqui`, ações `/rede/enviar` e `/rede/conferir_envio` em `app_servidor`; plano B: `FilaCentral` + `envio_nf.ServicoEnvio` com `ACAO_FORMULARIO`) |
| **Conferente** (lê Outlook, acha NF no Dropbox, etiquetas) | `conferente.py` → `uma_volta`, `varrer_dropbox`, `varrer_enviados`, `marcar_notas_divididas` |
| **Espelho do Outlook de cada PC** (Correio_, CaixaPedidos_, CorreioTexto_) | `espelho_emails.py` → `Espelho`, `pedidos_do_robo`, `classificar`, `resolver` |
| **Etiqueta "🧾 NF emitida"** no e-mail do hóspede (põe e tira) | `espelho_emails._marcar_nf_emitida` (reconfere a já posta; tira a que não passa, só com a NF ainda na lista); qual NF é do e-mail: `envio_nf.notas_do_email` (1: nº da estada + nome; 2: nome inteiro + PDF, e se o e-mail diz a estada o arquivo tem que ser dela), `_reservas_do_arquivo` |
| **Reconhecer a NF que saiu / confirmar NFs** | `controle_nf.py`, `confirmar_nfs.py` |
| **Urgência (NF errada, cancelar)** | `analise_nf.py` |
| **Prazo por tipo de pedido** | `prazos.py` |
| **Hóspede único / pedido repetido** | `hospedes.py` |
| **Canceladas / substituídas (Dropbox)** | `canceladas.py` |
| **Atualizar os 4 PCs** | `atualizador.py` (`pedir_reinicio`); `Automacoes/reiniciar_servicos.ps1`; servidor `_verificar_atualizacao`, `_executar_comando` |
| **Faxina da Central** | `faxina.py` |
| **Cota do Google** | `cota_google.py`, `rede_util.py` (retry) |
| **Janela, X que esconde, abrir com o Windows** | `app_janela.py` |
| **Janela que abre por cima** (cinza + animação de abrir/fechar, peça única) | `app_ui/pecas/janela.css` (cores e entrar), `app_ui/pecas/janela.js` (`fecharJanela`: o `.remove()` de toda `.modal-fundo` sai animado); o foco volta no observador de janelas do `index.html` |
| **Tela que não trava** (fila do servidor, "Recarregando o Painel…", faixa "Sem dados", F5, janela que confere) | servidor: `app_servidor.ServidorPainel` (fila 128); página: guarda no fim do `index.html` (`window.__telaInteira`, sem limite de tentativas), `avisoParado`/`recarregarTela`/`window.__painelVivo` depois de `carregar`; janela: `app_janela.tela_viva`, `conferir_ao_mostrar`, `vigiar_tela` (log em `logs/janela.log`) |
| **Outlook: guardião (abrir com janela), porta única do COM** | `outlook_vivo.py` → `estado`, `garantir`, `aplicativo`, `iniciar_guardiao` (ligado no `conferente.main`); estado no Painel via `rede_pcs.outlook_aberto` |
| **Saúde: último e-mail recebido, alarme "nenhum e-mail chega"** | `saude.py` → `ultimo_recebido`, `problemas`; coletado no `app_servidor.vigiar_caixa_de_saida` |
| **Modo demonstração / modo casa** | `demo.py`; servidor `main()` (`--demo`, `--visualizar`); `sheets.BackendSoLeitura`; `PAINEL_DEMO_EM_CASA.bat` |
| **Avisos do Windows** | `avisos_windows.py` |
| **Prévia 5: visual do Outlook escuro** (cores, espaços, ficha em 3 faixas, faixa de comandos) | `index.html`: camada "Prévia 5 no Painel" no fim do `<style>` |
| **Leitura do e-mail igual ao Outlook** (cabeçalho, de onde veio, anexos em cima, ficha, texto) | `correio.js` → `desenharLeituraCorreio`, `fichaPedidoOl`, `linhaEmail` (urgente, formulário) |
| **Formulário aberto** (tabela verde/creme em grupos, botão copiar) | `correio.js` → `formularioHtml(s, e)`, `GRUPOS_FORM`, `valorDoForm` (formata CPF/CNPJ, CEP, telefone, diárias), `SEM_COPIAR_FORM`, `OCULTOS_FORM`; sem o pedido na lista: `formDoTexto` (lê "Campo<tab>Valor" do texto, `ROTULOS_FORM`); estilo `.ol-form.fg` em `index.html` |
| **Filtro da lista dos e-mails** (Pedido de correção, Sem resposta, Com anexo, Nota dividida) | `correio.js` → `FILTROS_LISTA`, `filtroDaListaHtml`, `itensDaTela` (`cx.filtroL`); clique: `data-ol-filtro`, `data-ol-filtro-abrir` |
| **Pesquisa instantânea** (pedidos na hora + espelho; Outlook ao vivo depois) | `correio.js` → `secoesDaBusca`, `pedidosDaBusca`, `linhaPedidoBusca`, `marcarBusca`; ao vivo: `agendarBusca`/`buscarNoOutlook` |
| **Envio sem espera** (janela fecha na hora; aviso no canto) | `painel.js` → `enviarNF` (fim), `seguirEnvio`, `verEnvio`, `desenharEnvio`, `fecharEnvio`; status: `/api/envio_nf/status` |
| **Contagem exata da Caixa de Entrada** (Outlook x espelho, caixa por caixa, a cada volta) | `espelho_emails.py` → `Espelho.volta` (filtro por `LastModificationTime`), `_conferir_contagem` (`contagem`, `contagem_relida` em `estado/espelho_emails.json`); teste `testes/test_contagem_exata.py` |
| **Verificação da NF: texto que o hóspede pede na nota** (aspas) e busca no PDF inteiro | `analise_nf.py` → `textos_pedidos`, `onde_aparece`, `motivo_principal`, `comparar(…, texto_nf)`, `completo(…, texto_nf)`; teste `testes/test_texto_na_nota.py` |
| **Logs** (um arquivo por programa) | `log_util.py` → `arquivo_do_programa`, `PROGRAMAS` (script de entrada → arquivo); teste `testes/test_log_util.py` |
| **Configuração** | `config.json` (todos), `config.local.json` (só do PC, papel principal/conferente), `config.py` |
| **Travas de entrega** (pre-commit, guarda do git, testes no GitHub) | `ferramentas/checar_commit.py` (via `.githooks/pre-commit`), `ferramentas/guarda_git.py` (hook do Claude Code em `NOTAS/.claude/settings.json`), `.github/workflows/testes.yml`; testes em `testes/test_ferramentas.py`; padrão do código `ruff.toml` (+ `requirements-dev.txt`); versões em `CHANGELOG.md` |

## Armadilhas conhecidas
- **Nunca** chamar `win32com.client.Dispatch("Outlook.Application")` direto: use `outlook_vivo.aplicativo()` (o Dispatch com o Outlook fechado cria um Outlook **sem janela**, que não baixa e-mail POP3).
- `index.html` tem várias camadas de CSS com `!important`: regra nova sempre no **fim** do `<style>`. Há um `h3{…!important}` antigo: título h3 novo precisa de `!important` também.
- Nome novo no topo de `correio.js`/`painel.js`/`index.html`: conferir que não existe (o `test_previa5.py` barra).
- Script de alteração: escrever o `.py` pelo editor (heredoc quebra as barras invertidas do Windows).
- Capturas de tela: scripts `cdp_*.js` no scratchpad, Edge sem janela, porta 8765; **nunca** abrir e-mail não lido, nunca Enviar/Cadastrar, nunca mexer no Professor.
- Dois Painéis no mesmo PC disputam o arquivo de log (erro de rotação): normal em teste, não em uso.
- Porta **8765** = Painel (só 127.0.0.1) · porta **8766** = rede entre os PCs.
- `POST` da tela exige o `X-Token` (fica no HTML servido); só de 127.0.0.1.
| **Repaginação v2 (14/10)** | `index.html`: bloco CSS "Repaginação v2" no fim do `<style>`; `faltaDados`, `motivoUrgente`, `tagsPedido`, `faltaBanner`, `desenharSaude` (caixinha de avisos), `aplicarMenu` (menu recolhível); `painel.js`: `resumoDiaHtml` (resumo de ontem), `numerosPainel` + `htmlRelatorio` (Gerência), `modeloPedirFalta`, abas do Monitoramento em `trocarVista`; `correio.js`: `tagsEmail`, `faixaPedido` | `relatorio_semana.periodo(..., "mes")`; `admin` em `/api/estado` |
| **Velocidade (21/10, 2026.10.21.6)** | Envio direto: `envio_nf.ServicoEnvio.pedir` → `_acordar_dono` / `receber_pela_rede` (o PC dono relê a fila) e `app_servidor._avisar_dono_envio` + ação de rede `envio_nf`. Envio interrompido: `_reconferir_envio` + `conferir_envio_painel` (marca invisível termina em `|ENV-…`; só para ASSUMIDO com `marca_id`). Um Painel por PC: `app_servidor.travar_instancia_unica` (`estado/_painel.lock`). Novidade do robô: `conferente.avisar_paineis` → `Estado.rede_novidade` (repassa 1 vez) → `esperar_proxima_volta` (`ACORDAR_MIN_SEGUNDOS` 12) e `Estado.olhar_dropbox` (10 s). Tela: `/api/versao` (`Estado.marca_tela`), `_json(..., comparar=True)` + `assinatura_tela` (fora: `VOLATEIS_TELA`); no `index.html` `api()` (`GUARDADAS`), `carregar(soSeMudou)` e o relógio de 3 s; `carregarCorreio(soSeMudou)`. Só documentação: `atualizador.so_documentos` + `Estado._adotar_versao_sem_reiniciar` | testes em `test_velocidade.py`, `test_envio_nf.py`, `test_instancia_unica.py`, `test_reiniciar_versao.py` |
| **Aviso de envio em pílula (22/10, 2026.10.22)** | `painel.js`: `seguirEnvio`, `verEnvio`, `desenharEnvio` (pílula; erro vira pílula vermelha e `data-env-ver` abre o cartão); CSS `.env-pilula` e `#envios-andamento` no `index.html` | — |
| **Tela do robô v3 (22/10, 2026.10.22.3/.4)** | `app_ui/robo.js` (tudo com prefixo `rb`: `rbAbrir`, `rbRender`, `rbModelo`, `rbAgora`, `rbRegistro`, `rbGavetaPedido`, `rbChip`, `rbVigiar`); CSS `.rb-*` no `index.html`; `painel.js`: `trocarVista("log")` abre a janela; servidor: `ESTATICOS["/robo.js"]` | `test_tela_robo.py` |
| ~~Aba Robô etapa 1~~ (trocada pela tela v3) e usuário João (22/10, 2026.10.22.2) | `painel.js`: `desenharRobo`, `carregarRobo`, `enviarAgora`, `etapaDaRodada`, `caminhoDoPedido` (usa `ETAPAS_ENVIO` e `/api/envio`); CSS `.rb-*` e a seção `#v-robo` no `index.html`; servidor: `operadores_deste_pc`, `e_admin_aqui` | `test_aba_robo.py` |
| **Ligação (22/10, 2026.10.22.7)** | `src/ligacoes.py` (aba `Ligacoes`, `dobrar`, `resumo`, `chave_do_enviado`); servidor: `_marcar_ligacao_do_envio`, `marcar_ligacao` (`/api/ligacao`), `_ligacoes_de_envios_falhos`, `resumo_ligacoes` (vai em `/api/estado`); espelho: `via_do_item`; tela: `alternarLigacao` e `#nf-lig` (`painel.js`), `cartaoLigacoes` (Visão geral), `tagsEmail`/`FILTROS_LISTA.ligacao`/`marcarLigacao` (`correio.js`), `pecaLigacao` (`pecas/etiqueta.js`) | `test_ligacoes.py` |
| **Itens Enviados 72 h (22/10, 2026.10.22.1)** | `espelho_emails.RECENTE_HORAS` e `VERSAO_ESTADO`; pesquisa: `buscar_outlook` + `_enviados_rapido` (`ENVIADOS_RAPIDO_SEGUNDOS`), `busca_outlook.buscar(pastas=)` | `test_enviados_72h.py` |
