---
tipo: documento
pasta: "6 Documentos"
pai: "[[00 Início]]"
prioridade: P0
tags: [cerebro/documentos, lgpd, dados]
---
# Mapa dos dados

> Gerado de `src/armazem.py` por `ferramentas/mapa_dos_dados.py`. **Não edite à mão**: mude o catálogo e rode a ferramenta.
> Tudo fica em `estado/` de cada PC, fora do GitHub. "Pessoal" = tem nome, CPF/CNPJ, e-mail ou texto de hóspede.

| Arquivo | Para que serve | Pessoal | Quanto tempo fica | Quem escreve |
|---|---|---|---|---|
| `app.json` | Preferências deste PC: tema e operador escolhido | não | enquanto o Painel precisa | `app_servidor` |
| `maquina.json` | Identidade deste PC (nome e papel: principal ou comum) | não | enquanto o Painel precisa | `config` |
| `versao_rodando.txt` | Versão do Painel que está rodando (para pedir reinício quando chega código novo) | não | enquanto o Painel precisa | `estado_sistema` |
| `painel_cache.pkl` | Último estado do Painel, para abrir já carregado depois de reiniciar | **sim** | só o último | `app_servidor` |
| `painel_cache_casa.pkl` | O mesmo, do modo casa | **sim** | só o último | `app_servidor` |
| `painel_cache_demo.pkl` | O mesmo, da demonstração (dados fictícios) | não | só o último | `app_servidor` |
| `canceladas.json` | NFs canceladas ou substituídas achadas nas pastas do Dropbox | **sim** | recalculado a cada leitura | `canceladas` |
| `nf_achadas.json` | NFs achadas nas pastas (documento, valores, datas), ligadas aos pedidos e e-mails | **sim** | últimos 30 dias de pasta | `nf_achadas` |
| `cache_textos_nf.json` | Texto lido de PDFs de NF, para não ler duas vezes | **sim** | enquanto o PDF existe | `confirmar_nfs` |
| `confirmar_nfs.json` | Quais e-mails e notas o conferente já viu | **sim** | enquanto o conferente precisa | `confirmar_nfs` |
| `confirmar_status.json` | Resultado da última volta do conferente (o Painel publica para os outros PCs) | não | enquanto o Painel precisa | `confirmar_nfs` |
| `controle_nf.json` | Registro do que o conferente achou em cada NF | **sim** | enquanto o conferente precisa | `conferente` |
| `espelho_emails.json` | Espelho da Caixa de Entrada deste PC (remetente, assunto, prévia) | **sim** | janela de 14 dias | `espelho_emails` |
| `indice_emails.sqlite` | Índice de pesquisa dos e-mails das caixas deste PC (inclui texto do hóspede) | **sim** | 12 meses (ajustes.json: email.indice_dias) | `indice_emails` |
| `lido_aplicado.json` | Marcas de lido/não lido que o Painel já aplicou no Outlook | não | enquanto o Painel precisa | `app_servidor` |
| `envios_pendentes.json` | Diário de envios do robô que ainda esperam confirmação | **sim** | 3 dias | `diario_envios` |
| `ja_enviadas.json` | Solicitações que o robô já atendeu (para não repetir envio) | **sim** | 150 dias (faxina) | `main` |
| `robo_antigo.json` | Hotéis ativos no robô antigo | não | enquanto o Painel precisa | `robo_antigo` |
| `planilhas_sem_cadastro.json` | Planilhas de hotel que ainda não estão no Cadastro_Hoteis | não | enquanto o Painel precisa | `sincronizar` |
| `sincronizacao.json` | Estado da cópia das planilhas dos hotéis para a Central | **sim** | enquanto o Painel precisa | `sincronizar` |
| `sincronizacao_versoes.json` | Versão de cada planilha de hotel na última cópia (para copiar só o que mudou) | **sim** | enquanto o Painel precisa | `sincronizar` |
| `ultima_copia.txt` | Hora da última cópia concluída | não | enquanto o Painel precisa | `sincronizar` |
| `_ciclo_copia.txt` | Marca de que a rodada da cópia está rodando | não | enquanto o Painel precisa | `sincronizar` |
| `faxina.json` | Quando foi a última faxina das abas da Central | não | enquanto o Painel precisa | `faxina` |
| `contagem_painel.json` | Contagem dos e-mails do fim de semana por operador | não | enquanto o relatório precisa | `contagem_painel` |
| `enviar_receber_tempos.json` | Quanto tempo cada PC levou no Enviar/Receber (para estimar o próximo) | não | enquanto o Painel precisa | `enviar_receber` |
| `cota_google` | Consumo da cota do Google deste PC, por programa | não | enquanto o Painel precisa | `cota_google` |
| `acessos` | Registro de quem abriu e-mail, anexo ou ficha (sem nome nem CPF do hóspede) | não | 12 meses | `acessos` |
| `app_webview` | Cache do navegador da janela do Painel (limpo ao abrir) | não | enquanto o Painel precisa | `limpeza` |
| `app_edge` | Cache do navegador da janela, quando abre pelo Edge (limpo ao abrir) | não | enquanto o Painel precisa | `limpeza` |
| `_painel.lock` | Trava: um servidor do Painel por PC | não | enquanto o Painel precisa | `app_servidor` |
| `_janela.lock` | Trava: uma janela do Painel por PC | não | enquanto o Painel precisa | `app_janela` |
| `_execucao.lock` | Trava: uma execução do robô por PC | não | enquanto o Painel precisa | `lock_execucao` |
| `_conferente.lock` | Trava: um conferente por PC | não | enquanto o Painel precisa | `conferente` |
| `backup_tratamento_AAAAMMDD.json` | Cópia do Tratamento antes da faxina | **sim** | poucos dias | `faxina` |
| `backup_central_AAAAMMDD_HHMMSS.json` | Cópia da Central para recuperar erro | **sim** | 24 h (144 cópias) | `sincronizar` |

## Onde mexer
- Arquivo novo em `estado/`: declare em `src/armazem.py` e peça o caminho com `armazem.caminho(...)`. O teste barra caminho montado à mão.
- Pedido de titular (ver ou apagar dados de uma pessoa): `ferramentas/pedido_titular.py` e [[Dados de hóspedes (LGPD)]].
- Quem abriu o quê: `estado/acessos/AAAA-MM.jsonl` (`src/acessos.py`), 12 meses, sem nome nem CPF.
