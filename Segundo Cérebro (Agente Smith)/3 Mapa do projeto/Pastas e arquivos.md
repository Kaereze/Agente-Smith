---
tipo: mapa
pasta: "3 Mapa do projeto"
pai: "[[00 Início]]"
tags: [cerebro/mapa]
---
# Pastas e arquivos

> Cada pasta de `Desktop\NOTAS\Solicitacoes NF` tem uma nota em `3 Mapa do projeto/Pastas/`, com o **risco** (escala na [[Legenda de cores]]), o que tem dentro, como o Claude mexe e o que nunca fazer. **Os arquivos ficam no lugar deles**: mover uma pasta do programa quebraria os 4 PCs.
> Quer mexer numa função específica? Vá direto em [[Onde mexer]]. Visual: [[Mapa das pastas.canvas|Mapa das pastas]].

## As pastas e o risco
| Pasta | Risco | O que é |
|---|---|---|
| [[src]] | 🟧 produção | Código Python: Painel (servidor) e robôs |
| [[app_ui]] | 🟦 tela | HTML, CSS e JavaScript do Painel |
| [[Automacoes]] | 🟧 produção | PowerShell: instalar, agendar, reiniciar |
| [[Bat]] | 🟧 produção | Atalhos de dois cliques |
| [[apps_script]] | 🟧 produção | Menu da Planilha Central |
| [[Arquivos da raiz]] | 🟧 produção | `config.json`, `robo.py`, instaladores `.bat` |
| [[testes]] | 🟩 livre | Testes automáticos |
| `ferramentas/` · `.githooks/` · `.github/` | 🟦 entrega | Travas: pre-commit, guarda do git e testes no GitHub (19/10/2026) |
| [[Cofre (Segundo Cérebro)]] | 🟩 livre | Este cofre |
| [[NOTAS (pasta de cima)]] | 🟩 livre | `CLAUDE.md`, `.mcp.json` (só no PC do trabalho) |
| [[estado]] | 🟥 não mexer à mão | Memória local, backups, dados de hóspedes |
| [[logs]] | 🟥 não mexer à mão | Registros |
| [[saida_simulacao]] | 🟥 não mexer à mão | E-mails simulados |
| [[Python do projeto (.venv)]] | 🟥 não mexer à mão | Python e bibliotecas |

## Arquivos de código (tamanho = onde está o peso)
**Tela (`app_ui/`)**: `index.html` 2.211 linhas (estrutura, todo o CSS, Notas fiscais, ficha) · `painel.js` 822 (Visão geral, Gerência, Máquinas, Enviar NF) · `correio.js` 494 (e-mails, busca) · `graficos.js` 237.

**Painel (`src/`)**
| Arquivo | Linhas | Para quê |
|---|---|---|
| `app_servidor.py` | 1.576 | Servidor 8765 + classe `Estado` (tudo que a tela pede) |
| `app_dados.py` | 305 | Fila a partir da Central; liga pedido ↔ e-mail |
| `app_janela.py` | 195 | Janela, X que esconde, abrir com o Windows |
| `correio.py` | 123 | Junta os espelhos dos 4 PCs com lido/excluído |
| `saude.py` | 134 | Regras da faixa vermelha |
| `relatorio_semana.py` / `contagem_painel.py` | 179 / 178 | Relatório (Mail Analytics, só leitura) / fim de semana |
| `rede_pcs.py` / `rede_local.py` / `busca_outlook.py` | 109 / 166 / 126 | PCs pela Central / rede 8766 / busca ao vivo |
| `demo.py` | 372 | Modo demonstração |

**Robôs (`src/`)**
| Arquivo | Linhas | Para quê |
|---|---|---|
| `sincronizar.py` | 636 | Cópia das planilhas dos hotéis (a cada 10 min; junta todas as planilhas do hotel) + TRUE de volta na planilha do hotel |
| `main.py` · `montar_email.py` · `outlook.py` | 447 · 281 · 126 | Envio das solicitações |
| `envio_pc_dono.py` | 341 | E-mail do robô pelo PC dono da caixa do hotel (rede 8766; plano B: fila Envios_NF) |
| `conferente.py` | 794 | Processo contínuo de cada PC |
| `vigia_formularios.py` | 140 | Cópia rápida dos formulários (23/10/2026): a cada 10 s, só no principal, dentro do conferente |
| `espelho_emails.py` | 790 | Espelho do Outlook de cada PC |
| `envio_nf.py` | 996 | Envio da NF ao hóspede + fila de envio entre PCs (também o e-mail do robô, plano B) |
| `controle_nf.py` · `confirmar_nfs.py` | 703 · 582 | Reconhecer/confirmar NF |
| `analise_nf.py` · `faxina.py` | 270 · 210 | Urgência · limpeza da Central |
| `outlook_vivo.py` | 160 | Guardião do Outlook (aberto com janela) e porta única do COM |
| `sheets.py` · `config.py` · `cota_google.py` | 646 · 144 · 123 | Google Sheets (+ `BackendSoLeitura`) · configuração · cota |

Pequenos: `prazos`, `hospedes`, `canceladas`, `tratamento`, `identidade`, `atualizador`, `cota_envio`, `vigia_outlook`, `avisos_windows`, `aviso_certificado`, `lock_execucao`, `diario_envios`, `historico`, `atividade`, `hoteis`, `fiscal_intelligence`, `robo_antigo`, `log_util`, `arquivos`, `rede_util`, `console_utf8`, `modelos`, `conferir_copia`, `classificador`, `organizador_emails`.

**Tarefas do Windows:** `SolicitacoesNF_CopiaHoteis`, `SolicitacoesNF_Conferente`, `SolicitacoesNF_Painel`, `SolicitacoesNF_Reiniciar`.
