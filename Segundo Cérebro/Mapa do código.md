# Mapa do código (13/10/2026)

Pasta: `Desktop\NOTAS\Solicitacoes NF` · repositório `Kaereze/Notas-Fiscais`. Para "qual função", ver [[Onde mexer]].

## Tela (`app_ui/`)
| Arquivo | Linhas | O que tem |
|---|---|---|
| `index.html` | 2.211 | Estrutura, todo o CSS (camadas), Notas fiscais, ficha, operador, Professor, saúde |
| `painel.js` | 822 | Visão geral, Gerência, Máquinas, Log, Enviar NF, Enviar pendentes, relatório, cadastro |
| `correio.js` | 494 | Caixa de entrada, Urgência, Enviados, leitura, busca, responder |
| `graficos.js` | 237 | Gráficos |

## Servidor e Painel (`src/`)
| Arquivo | Linhas | Para quê |
|---|---|---|
| `app_servidor.py` | 1.576 | Servidor 127.0.0.1:8765 + classe `Estado` (tudo que a tela pede) |
| `app_dados.py` | 305 | Monta a fila a partir da Central e da Tratamento; liga pedido ↔ e-mail |
| `app_janela.py` | 195 | Janela pywebview, esconder no X, abrir com o Windows |
| `app_envio.py` | 105 | Botão "Enviar pendentes" |
| `correio.py` | 123 | Junta os espelhos dos 4 PCs com lido/excluído |
| `saude.py` | 134 | Regras da faixa vermelha |
| `relatorio_semana.py` | 179 | Relatório dia/semana do Mail Analytics (só leitura) |
| `contagem_painel.py` | 178 | Fim de semana contado pelo Painel |
| `painel_metricas.py` | 135 | Números da Visão geral |
| `rede_pcs.py` / `rede_local.py` | 109 / 166 | PCs pela Central / conversa direta (8766) |
| `busca_outlook.py` | 126 | Busca ao vivo no Outlook deste PC |
| `demo.py` | 372 | Modo demonstração (dados fictícios) |

## Robôs
| Arquivo | Linhas | Para quê |
|---|---|---|
| `sincronizar.py` | 446 | Cópia das planilhas dos hotéis → Central (30 min) |
| `main.py` | 432 | Envio das solicitações |
| `montar_email.py` | 281 | Assunto e HTML dos e-mails |
| `outlook.py` | 126 | Envio pelo Outlook e confirmação |
| `conferente.py` | 794 | Processo contínuo de cada PC |
| `espelho_emails.py` | 790 | Espelho do Outlook de cada PC |
| `envio_nf.py` | 895 | Envio da NF ao hóspede |
| `controle_nf.py` | 703 | Registro das solicitações e reconhecimento da NF |
| `confirmar_nfs.py` | 582 | Confirma NFs já emitidas |
| `classificador.py` / `organizador_emails.py` | 482 / 417 | Classificação e categorias do Outlook |
| `analise_nf.py` | 270 | Urgência (NF errada / cancelar) |
| `faxina.py` | 210 | Limpeza da Central |
| `sheets.py` | 646 | Acesso ao Google Sheets (+ `BackendSoLeitura`) |
| `config.py` | 144 | `config.json` + `config.local.json` |
| outros pequenos | — | `prazos`, `hospedes`, `canceladas`, `tratamento`, `identidade`, `atualizador`, `cota_google`, `cota_envio`, `vigia_outlook`, `avisos_windows`, `aviso_certificado`, `lock_execucao`, `diario_envios`, `historico`, `atividade`, `hoteis`, `fiscal_intelligence`, `robo_antigo`, `log_util`, `arquivos`, `rede_util`, `console_utf8`, `modelos`, `conferir_copia` |

## Scripts
- Raiz: `ATUALIZAR_PAINEL.bat`, `INSTALAR_OU_ATUALIZAR.bat`, `PAINEL_DEMO_EM_CASA.bat` (casa: demo ou modo casa).
- `Bat/`: `instalar`, `configurar_este_pc`, `executar_robo`, `conferente`, `sincronizar_agendado`, `rodar_testes`, `TESTAR_CONFIG`…
- `Automacoes/`: `reiniciar_servicos.ps1`, `agendar_*.ps1`, `coracao.ps1` (instalador), `liberar_rede.ps1` (firewall 8766), `criar_atalho_app.ps1`.
- Tarefas do Windows: `SolicitacoesNF_CopiaHoteis`, `SolicitacoesNF_Conferente`, `SolicitacoesNF_Painel`, `SolicitacoesNF_Reiniciar`.

## Testes (`testes/`)
~40 arquivos, 300+ testes, rodam com `python -m pytest -q`. Os principais para o Painel: `test_caixa_pedidos.py`, `test_etapa2.py`, `test_painel_fiscal.py`, `test_painel_leve.py`, `test_espelho_emails.py`, `test_envio_nf.py`. Segurança: `test_segredos.py`.
