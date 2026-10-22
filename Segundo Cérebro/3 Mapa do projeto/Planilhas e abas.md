---
tipo: mapa
pasta: "3 Mapa do projeto"
pai: "[[00 Início]]"
tags: [cerebro/mapa]
---
# Planilhas e abas

IDs: Central em `config.json` → `planilha_central_id`; Mail Analytics em `src/relatorio_semana.py` → `PLANILHA_MAIL_ANALYTICS`. (IDs não são senha: o acesso depende do compartilhamento.)

## Planilha Central! (Krz) — o hub da equipe
| Aba | Quem grava | Quem lê | Observação |
|---|---|---|---|
| Uma aba por hotel (respostas copiadas) | `sincronizar.py` (PC principal) | Painel, robô | Cópia das planilhas dos hotéis |
| `Cadastro_Hoteis` | João / cartão Cadastrar | Todos | **Sem cabeçalho**: hotel · e-mail · agente |
| `Status` | João | Robô | B1 liga/desliga o painel do robô |
| `Tratamento` | Conferente / robô | Painel | A:H, uma linha por solicitação |
| `Log de Envios` | Robô | — | Histórico de envios |
| `Envios_NF`, `Envios_NF_Anexos` | Painel (Enviar NF) e robô (e-mail do formulário, 15/10/2026) | PC dono da caixa | Fila de envio entre PCs. Pedido do robô: `acao` "formulario", PC em `pc_formulario`, HTML na Envios_NF_Anexos (apagado depois) |
| `PCs_Painel` | Cada PC | Todos | Versão, Outlook, saúde (coluna L) |
| `Comandos_PC` | Painel ("Atualizar todos") | Cada PC | Respostas na mesma aba |
| `Eventos_Correio` | Painel (lido/excluído/urgência) | Todos | Faxina 3 dias |
| `Correio_<PC>` | `espelho_emails.py` do PC | Painel | Caixa de entrada espelhada (coluna "Lido Outlook") |
| `CorreioTexto_<PC>` | idem | Painel | Texto dos e-mails |
| `CaixaPedidos_<PC>` | idem | Painel | Solicitações do robô na Caixa de Entrada |
| `ContagemPainel_<PC>` | `contagem_painel.py` (João/Cristian) | Relatório | Fim de semana |
| `Atividade_Robo` | Todos os robôs | Log da tela | Faxina 7 dias |
| `Ligacoes` | Painel (botão Ligação no envio e botão direito em Itens Enviados) | Painel (etiqueta, filtro, cartão da Visão geral) | Quando · Chave (ENV-… ou id do e-mail) · Ação (LIGACAO/SEM_LIGACAO) · Agente · PC · Hotel · Caixa · Para · Assunto. Faxina 400 dias |
| `Conferência da Cópia` | `conferir_copia.py` | — | Auditoria da cópia |

## Fora da Central (só leitura)
| Planilha | Abas | Regra |
|---|---|---|
| Planilhas dos hotéis (Drive de outra conta) | respostas do formulário | Só ler, exceto TRUE na coluna Enviado depois do envio (15/10/2026) |
| Mail Analytics | `Agente_Joao`, `Agente_Clara`, `Agente_Cristian`, `Agente_Bernardo` (Data, Hotel, Recebidos, Enviados, Ligações, Subst./Canc., NFs) | Só ler · fim de semana vira linha de domingo, gravada segunda de manhã |
| Fiscal Intelligence (gravada pelo Mail Analytics) | — | Só ler |

## Cota
60 leituras/min somando os 4 PCs, dividida em `cota_google.py`. Toda leitura nova entra na conta ([[Hierarquia de prioridades]] P3).

## Formulário antigo e formulário novo (15/10/2026)
- **Antigo:** "Nota Fiscal (Hotel) (respostas)", 36 colunas ("Endereço de e-mail", "Nome do Hóspede"...).
- **Novo:** "Solicitação Nota Fiscal (Hotel) (respostas)", 18 colunas ("Termos de aceite", "Documento Tomador", "Nome Tomador",
  "E-mail", "Check-in/Check-out da Hospedagem", "Valor da Nota Fiscal"...). Criado em abril para 15 hotéis; Boa Viagem e
  São Francisco já usam (desde 07/10 e 06/10).
- A cópia junta as duas na **mesma aba da Central** do hotel (colunas do novo no fim). Ver `sincronizar.juntar_planilhas`.

