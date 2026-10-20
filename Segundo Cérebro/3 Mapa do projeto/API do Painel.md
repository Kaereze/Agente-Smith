---
tipo: mapa
pasta: "3 Mapa do projeto"
pai: "[[00 Início]]"
tags: [cerebro/mapa]
---
# API do Painel (127.0.0.1:8765)

Tudo em `src/app_servidor.py` → `criar_handler`. `POST` exige o cabeçalho `X-Token` (vem no HTML servido). No **modo casa** só `professor`, `agente` e `atualizar` são aceitos.

## Leitura (GET)
| Rota | Para quê |
|---|---|
| `/api/estado` | Estado geral (PCs, saúde, demo/so_ver, agente) |
| `/api/painel`, `/api/hotel` | Visão geral, hotel |
| `/api/emails`, `/api/correio` | Listas de e-mails |
| `/api/correio/conversa`, `/api/correio/texto` | Conversa e texto de um e-mail |
| `/api/correio/buscar` | Pesquisa nos 4 PCs pelo índice local (`?q=`); `&vivo=1` = direto no Outlook de cada PC |
| `/api/email/opcoes` | Opções de resposta |
| `/api/envio`, `/api/envio_nf/opcoes`, `/api/envio_nf/status` | Envio de pendentes / NF |
| `/api/relatorio_semana?tipo=dia|semana&deslocamento=N` | Relatório (−1 = automático) |
| `/api/cadastro/faltando` | Hotéis sem cadastro |
| `/api/atividade` | Log da equipe |
| `/fontes/...` | Fontes IBM Plex (cache longo) |

## Ação (POST)
| Rota | Para quê |
|---|---|
| `/api/acao` | Marcar NF, anotar, tratativa |
| `/api/correio/evento` | Lido / não lido |
| `/api/correio/urgencia` | Botão direito: `{id, marcar: "urgente" | "normal"}` (evento na hora + categoria no Outlook do PC dono) |
| `/api/correio/excluir`, `/api/correio/encaminhar`, `/api/email/responder` | E-mails |
| `/api/envio_nf`, `/api/envio_nf/conferir` | Enviar NF (com conferência antes) |
| `/api/enviar` | Enviar pendentes |
| `/api/cadastro/adicionar` | Cadastrar hotel |
| `/api/comando` `{"para":"TODOS","comando":"atualizar"}` | Atualizar todos os PCs |
| `/api/atualizar` | Reler agora |
| `/api/professor`, `/api/tema`, `/api/agente` | Preferências deste PC |
