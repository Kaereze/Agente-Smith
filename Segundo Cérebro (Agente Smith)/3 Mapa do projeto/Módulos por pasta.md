---
tipo: mapa
pasta: "3 Mapa do projeto"
pai: "[[00 Início]]"
tags: [cerebro/mapa]
---
# Módulos por pasta

> Gerado por `ferramentas/mapa_dos_modulos.py` a partir do código. **Não edite à mão.** Mapa das pastas em linguagem simples: `COMECE_AQUI.md` (raiz do projeto).

## Programas que os PCs abrem pelo nome (ficam em `src/`)

| Arquivo | Para que serve |
|---|---|
| `src/ajustes.py` | Ajustes do Painel: tempos, limites, textos e assinaturas num arquivo de chave e valor (04/11/2026, pedido do João). |
| `src/app_janela.py` | Janela do Painel Notas Fiscais: aplicativo próprio (pywebview + WebView2), sem navegador. |
| `src/app_servidor.py` | Painel Notas Fiscais: servidor HTTP só em 127.0.0.1 + janela do Edge em modo aplicativo. |
| `src/atualizador.py` | Mantém o código de cada PC igual ao do GitHub (pedido do usuário, 06/10/2026: alterar num PC, |
| `src/avisos_windows.py` | Aviso do Windows (notificação no canto da tela) quando um PC da equipe sai do normal (pedido do usuário, |
| `src/conferente.py` | Processo contínuo de cada PC. |
| `src/conferir_copia.py` | Auditoria da cópia: compara a planilha de cada hotel com a aba correspondente na Central. |
| `src/config.py` | Leitura e validação do config.json (+ config.local.json por PC). |
| `src/confirmar_nfs.py` | Confirma NFs já emitidas para todas as solicitações da Central e publica na aba Tratamento. |
| `src/identidade.py` | Descobre de qual agente é este PC votando com as contas do Outlook contra o Cadastro_Hoteis. |
| `src/main.py` | Envio: lê pendentes, envia, confirma em Itens Enviados e só então marca TRUE. |
| `src/sincronizar.py` | Copia as respostas das planilhas dos hotéis (pasta do Drive) para as abas da Central. |

## `src/central/`: A Planilha Central e o Google: ler, gravar, respeitar a cota

Mexa aqui quando o problema é a planilha: aba que não atualiza, limite do Google, cadastro de hotéis, limpeza diária.

| Módulo | Para que serve |
|---|---|
| `cota_google` | Orçamento da cota do Google Sheets, dividido entre os programas dos 4 PCs. |
| `faxina` | Faxina diária da Central (só no PC principal) — pra nada virar bola de neve (usuário, 08/10/2026). |
| `fiscal_intelligence` | Leitura (somente) da planilha Fiscal Intelligence, gravada pelo Mail Analytics. |
| `hoteis` | Cadastro único de hotéis: casa os nomes que cada fonte usa com o nome do Cadastro_Hoteis. |
| `rede_util` | Retry com backoff exponencial para erros passageiros da API do Google. |
| `sheets` | Planilha Central: abas de respostas dos hotéis, aba Status (painel/menu) e Log. |
| `tratamento` | Tratamento dos campos do formulário: datas, CPF/CNPJ, CEP. |
| `vigia_formularios` | Cópia rápida dos formulários (23/10/2026, OK do João): pedido do hóspede no Painel em ~10-20 s, e não 6-12 min. |

## `src/emails/`: Tudo de e-mail e Outlook: ler, espelhar, buscar, enviar a NF

Mexa aqui quando o problema é com o e-mail: a lista não mostra um e-mail, o envio da NF falha, a busca não acha, o Outlook trava.

| Módulo | Para que serve |
|---|---|
| `aviso_certificado` | Outlook: responde "Sim" sozinho ao "Aviso de Segurança da Internet" do nome do certificado (usuário, 09/10/2026). |
| `busca_outlook` | Busca ao vivo no Outlook DESTE PC (pedido do usuário, 08/10/2026): o Painel não guarda histórico; quando alguém |
| `correio` | Caixa de correio do Painel: junta os espelhos dos 4 PCs (abas Correio_<PC>) com o lido/excluído da equipe. |
| `cota_envio` | Cota por hora do servidor de e-mail, medida pelos Itens Enviados. |
| `diario_envios` | Write-ahead log dos envios: anotado antes do Send, resolvido na execução seguinte. |
| `enviar_receber` | Botão "Enviar/Receber todas" (27/10/2026, desenho aprovado: opção C, anel no botão). |
| `envio_nf` | Envio da NF ao hóspede pelo Painel, saindo da caixa do próprio hotel. |
| `envio_pc_dono` | Envio pelo PC dono da caixa do hotel (usuário, 15/10/2026: "por que está sendo utilizado meu e-mail do Ondina? |
| `espelho_emails` | Espelho do Outlook de cada PC: Caixa de Entrada e Itens Enviados das caixas dos hotéis. |
| `indice_emails` | Índice local dos e-mails das caixas dos hotéis DESTE PC (usuário, 20/10/2026: pesquisa instantânea; muda a regra |
| `ligacoes` | Pedido que veio por ligação (usuário, 22/10/2026): os telefones não ligam no PC, então quem marca é o agente, no botão |
| `montar_email` | Assunto e HTML dos e-mails de solicitação. HTML com estilo inline: é o que o Outlook respeita. |
| `outlook` | Envio pelo Outlook (COM) e confirmação em Itens Enviados. |
| `outlook_vivo` | Guardião do Outlook (usuário, 13/10/2026: "deixa o Outlook obrigatoriamente aberto enquanto o PC estiver ativo"). |
| `vigia_outlook` | Vigia do Outlook: a cada 20 s só OLHA as caixas deste PC (pedido do usuário, 07/10/2026). |

## `src/notas/`: Tudo da nota fiscal: pedido, NF achada no Dropbox, regras de conferência

Mexa aqui quando a regra da NF muda: o que conta como NF pronta, como casar nota e pedido, prazo, hóspede repetido.

| Módulo | Para que serve |
|---|---|
| `analise_nf` | Urgência: o hóspede diz que a NF está errada (valor, data, mês, nome, CPF/CNPJ, descrição) ou pede pra cancelar / |
| `canceladas` | NFs canceladas e substituídas = arquivos renomeados no Dropbox (só leitura): |
| `controle_nf` | Registro das solicitações enviadas e reconhecimento da NF que sai para o hóspede. |
| `historico` | Log de Envios (aba da Central + CSV local) e registro das solicitações já confirmadas. |
| `hospedes` | Hóspede único e pedido repetido — Etapa 2 (usuário, 09/10/2026). |
| `modelos` |  |
| `nf_achadas` | NF achadas nas pastas do Dropbox pelo CPF/CNPJ de dentro do PDF (27/10/2026, desenho aprovado pelo João). |
| `nf_cobre` | A NF já enviada cobre o que o hóspede pede agora? (27/10/2026, desenho aprovado pelo João). |
| `prazos` | Prazo de resposta (SLA) por tipo de pedido — Etapa 2 (usuário, 09/10/2026). |
| `robo_antigo` | Convivência com o robô antigo (Apps Script via Gmail), que ainda atende alguns hotéis. |

## `src/painel/`: O Painel por dentro: o servidor, as rotas da API e o que cada tela precisa

Mexa aqui quando uma TELA precisa de um número novo, uma rota nova ou um jeito novo de contar (resumo do dia, equipe, saúde, rede entre PCs).

| Módulo | Para que serve |
|---|---|
| `agentes_smith` | Aba "Agentes do Smith" (28/10/2026, desenho aprovado pelo João): o estado ao vivo dos agentes no mapa do sistema. |
| `app_dados` | Dados do app: monta a fila de solicitações a partir da Central e da aba Tratamento. |
| `app_envio` | Botão "Enviar pendentes" do Painel, com o andamento ao vivo. |
| `atividade` | O que os robôs de TODOS os PCs fizeram, numa aba só da Planilha Central (Atividade_Robo). |
| `cache_disco` | Leitura segura do cache em disco (painel_cache.pkl). |
| `contagem_painel` | Contagem do fim de semana pelo Painel (usuário, 11/10/2026). |
| `demo` | Modo demonstração: o Painel inteiro com dados FICTÍCIOS — pra abrir no PC de casa, sem Google, sem Outlook, |
| `desempenho` | Medidor de desempenho (28/10/2026, pedido do João: "deixar o programa mais otimizado e fluido"). |
| `estado_correio` | Estado do correio: o espelho do Outlook dos 4 PCs, busca, ações sobre e-mails e conferência de NF. |
| `estado_envio` | Estado do envio: pedir e conferir o envio da NF, ligações, Enviar/Receber todas e caixas com problema. |
| `estado_rede` | Estado da rede entre os PCs: o que este PC responde aos outros e o que pergunta a eles. |
| `estado_sistema` | Estado do sistema: versão e atualização, comandos entre PCs, saúde e os vigias em segundo plano. |
| `painel_metricas` | Números das telas Visão geral e Hotéis, juntando a Central (solicitações), o Mail Analytics e as |
| `relatorio_semana` | Relatório do dia e da semana na Gerência (usuário, 11/10/2026): os números que o Mail Analytics já grava na planilha dele |
| `resposta_http` | Resposta da API para a tela: gzip e a assinatura que decide se "não mudou nada" (`__igual`). |
| `rotas_api` | Tabela de rotas da API do Painel (30/10/2026): o que cada endereço faz, num lugar só. |
| `saude` | Saúde do sistema — uma faixa vermelha no topo do Painel quando algo sai do normal (usuário, 11/10/2026). |

## `src/privacidade/`: LGPD: quem viu o dado e o pedido do titular

Mexa aqui para registrar quem abriu o quê ou para atender quem pede para ver ou apagar os dados.

| Módulo | Para que serve |
|---|---|
| `acessos` | Registro de quem viu o dado do hóspede (LGPD, 08/11/2026). |
| `titular` | Pedido do titular (LGPD, 08/11/2026): onde os dados de UMA pessoa estão neste PC e como tirar do que dá para tirar daqui. |

## `src/rede/`: Os PCs da equipe conversando entre si

Mexa aqui quando um PC não enxerga outro: pedido assinado, cifra, código único, quem está ligado.

| Módulo | Para que serve |
|---|---|
| `rede_local` | Conversa direta entre os Painéis dos 4 PCs pela rede do escritório (os 4 ficam na mesma rede — usuário, 08/10/2026). |
| `rede_pcs` | Os PCs da equipe conversando pela Planilha Central (pedido do usuário, 06/10/2026: "mexer nos outros |

## `src/sistema/`: A base do programa: gravar arquivo, log, trava, limpeza

Mexa aqui só quando for algo que vale para o programa inteiro. Quase sempre não é aqui.

| Módulo | Para que serve |
|---|---|
| `ajustes_tabela` | Tabela dos ajustes: valor de fábrica, mínimo, máximo e explicação de cada chave. |
| `armazem` | Armazém: o catálogo de TODO dado que o Painel grava neste PC (08/11/2026). |
| `arquivos` | Gravação atômica de JSON. |
| `console_utf8` | Console em UTF-8 (acentos e emojis no Windows). |
| `limpeza` | Limpeza do que cresce sozinho (27/10/2026, auditoria): cache da janela do Painel e sobra de registros. |
| `lock_execucao` | Trava entre processos: cópia, envio e conferência nunca rodam juntos. |
| `log_util` | Log de cada programa em logs/ (20/10/2026): robô = solicitacoes_nf.log, conferente.log, painel.log. |
