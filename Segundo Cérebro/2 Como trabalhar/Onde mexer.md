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
| **Ficha da solicitação** (onde entra a ficha-resumo) | `index.html` → `desenharDetalhe`, `noOutlookHtml`, `quadrosEtapa` | `conversa`, `_alertas_documento`, `_hospedes` |
| **Caixa de entrada / Urgência / Itens enviados** | `correio.js` → `desenharCorreio`, `linhaEmail`, `desenharLeituraCorreio`, `desenharFiltroHotel` | `_montar_correio`, `lista_correio`; juntar PCs em `correio.py` (`juntar`, `lido_atual`); o que cada PC publica em `espelho_emails.py` |
| **Busca de cima** (ao vivo no Outlook) | `correio.js` → `buscarNoOutlook`, `agendarBusca` | `buscar_outlook`, `_buscar_local`; `busca_outlook.py`; entre PCs `rede_local.py` (porta 8766) |
| **Lido / não lido** | `correio.js` → `abrirEmail`, `marcarNaoLido` | `evento_correio`, `_lido_no_outlook`; regra dos 5 min em `espelho_emails.lido_confirmado` |
| **Responder / encaminhar / excluir** | `correio.js` → `escrever`, `encaminhar`, `excluir`, `mostrarDesfazer` | `responder_email`, `encaminhar_email`, `excluir_email` |
| **Visão geral** | `painel.js` → `desenharVisao`, `faixaAgora`, `contarNumeros` | `painel`, `atividade_resumo` |
| **Gerência / relatório dia e semana** | `painel.js` → `desenharGerencia`, `carregarRelatorio`, `htmlRelatorio` | `relatorio_semana`, `_contagem_fim_de_semana`; `relatorio_semana.py`, `contagem_painel.py` |
| **Máquinas / saúde (faixa vermelha)** | `painel.js` → `desenharMaquinas`; `index.html` → `desenharSaude`, `desenharPcsCabecalho` | `problemas_de_saude`, `_extras_pc`, `pcs`; regras em `saude.py`; PCs em `rede_pcs.py` |
| **Cadastro de hotéis** (cartão Cadastrar) | `painel.js` → `carregarCadastro`, `htmlCadastro` | `cadastro_faltando`, `adicionar_cadastro`; `saude.cadastro_faltando` |
| **Enviar NF ao hóspede** | `painel.js` → `abrirEnvioNF`, `validarEnvioNF`, `enviarNF`, `acompanharNF`, `escolherSelo` | `pedir_envio`, `conferir_anexos`, `situacao_envio`; `envio_nf.py` |
| **Enviar pendentes** (robô pela tela) | `painel.js` → `abrirEnvio`, `acompanharEnvio` | `app_envio.py` |
| **Respostas prontas** | `painel.js` → `MODELOS_RESPOSTA`, `linhaModelos`, `dadosDoModelo` | — |
| **Modo Professor** (frases azuis) | `index.html` → `DICAS_BOTOES`, `aplicarDicasBotoes`, `aplicarProfessor` | `POST /api/professor` |
| **Agente do PC / menu do operador** | `index.html` → `desenharOperador`, `menuOperador` | `identidade.py`, `nome_do_agente` |
| **Cores, letras, espaçamento** | `index.html` → bloco `<style>`: base (início) → camada "Design fiscal" (~l.885) → "Organização" (~l.1015) → "limpeza" (fim). **Regra nova vai no fim**; tokens `--chao --folha --verde --creme` | — |
| **Gráficos** | `graficos.js` | — |

## Robôs e bastidores
| Quero mexer em… | Arquivo → função |
|---|---|
| **Cópia das planilhas dos hotéis → Central** | `sincronizar.py` → `rodar_agendado`, `sincronizar`, `_ler_planilha_hotel`, `hoteis_que_mudaram` |
| **Envio das solicitações por e-mail** | `main.py` → `executar`; corpo do e-mail em `montar_email.py`; envio COM em `outlook.py`; diário em `diario_envios.py` |
| **Conferente** (lê Outlook, acha NF no Dropbox, etiquetas) | `conferente.py` → `uma_volta`, `varrer_dropbox`, `varrer_enviados`, `marcar_notas_divididas` |
| **Espelho do Outlook de cada PC** (Correio_, CaixaPedidos_, CorreioTexto_) | `espelho_emails.py` → `Espelho`, `pedidos_do_robo`, `classificar`, `resolver` |
| **Reconhecer a NF que saiu / confirmar NFs** | `controle_nf.py`, `confirmar_nfs.py` |
| **Urgência (NF errada, cancelar)** | `analise_nf.py` |
| **Prazo por tipo de pedido** | `prazos.py` |
| **Hóspede único / pedido repetido** | `hospedes.py` |
| **Canceladas / substituídas (Dropbox)** | `canceladas.py` |
| **Atualizar os 4 PCs** | `atualizador.py` (`pedir_reinicio`); `Automacoes/reiniciar_servicos.ps1`; servidor `_verificar_atualizacao`, `_executar_comando` |
| **Faxina da Central** | `faxina.py` |
| **Cota do Google** | `cota_google.py`, `rede_util.py` (retry) |
| **Janela, X que esconde, abrir com o Windows** | `app_janela.py` |
| **Modo demonstração / modo casa** | `demo.py`; servidor `main()` (`--demo`, `--visualizar`); `sheets.BackendSoLeitura`; `PAINEL_DEMO_EM_CASA.bat` |
| **Avisos do Windows** | `avisos_windows.py` |
| **Configuração** | `config.json` (todos), `config.local.json` (só do PC, papel principal/conferente), `config.py` |

## Armadilhas conhecidas
- `index.html` tem várias camadas de CSS com `!important`: regra nova sempre no **fim** do `<style>`.
- Script de alteração: escrever o `.py` pelo editor (heredoc quebra as barras invertidas do Windows).
- Capturas de tela: scripts `cdp_*.js` no scratchpad, Edge sem janela, porta 8765; **nunca** abrir e-mail não lido, nunca Enviar/Cadastrar, nunca mexer no Professor.
- Dois Painéis no mesmo PC disputam o arquivo de log (erro de rotação): normal em teste, não em uso.
- Porta **8765** = Painel (só 127.0.0.1) · porta **8766** = rede entre os PCs.
- `POST` da tela exige o `X-Token` (fica no HTML servido); só de 127.0.0.1.
