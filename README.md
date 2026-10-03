# Robô Solicitações NF — Rede Andrade

Hóspede pede NF no Google Forms → a planilha do hotel recebe → o robô copia pra **Planilha Central** →
envia **1 e-mail por hotel** pelo Outlook → marca **Enviado = TRUE** → o conferente marca **NF enviada / Tratativa**.

## Fluxo

| Quando | O quê | Arquivo |
|---|---|---|
| A cada 30 min | Cópia das planilhas dos hotéis (Drive) → Central, depois envio do que estiver pendente | `src/sincronizar.py` → `src/main.py` |
| Sempre ligado | Conferente: menu da planilha, NF enviada/Tratativa no e-mail, cota | `src/conferente.py` |
| Pelo menu | Ativar Claudio · Envio Separado · Log · Cota · Conferir Cópia | `apps_script/menu_planilha_central.gs` |

Tarefas do Windows: `SolicitacoesNF_CopiaHoteis` (30 min) e `SolicitacoesNF_Conferente` (ao entrar no Windows).

## Estrutura

```text
robo.py                  entrada do envio manual (Bat/executar_robo.bat)
config.json              configuração (modo, destino, pastas, colunas)
src/
  main.py                robô de envio — raiz do fluxo
  sincronizar.py         cópia Drive → Central
  conferir_copia.py      conferência da cópia (só lê)
  conferente.py          processo sempre ligado
  sheets.py              Google Sheets
  outlook.py             envio e confirmação no Outlook
  montar_email.py        assunto + HTML do e-mail
  controle_nf.py         NF enviada / Tratativa
  historico.py           Log de Envios + lista de já enviadas
  diario_envios.py       anti-duplicidade (anota antes de enviar)
  cota_envio.py          cota do servidor (KingHost 250/h)
  tratamento.py          datas, CPF/CNPJ, CEP
  lock_execucao.py       uma execução por vez
  identidade.py          quem é este PC (contas do Outlook × Cadastro_Hoteis)
  robo_antigo.py         convivência com o Apps Script antigo
  arquivos.py · config.py · log_util.py · rede_util.py · modelos.py · console_utf8.py
apps_script/             menu da Planilha Central (colar no Apps Script)
Bat/                     atalhos (.bat) · Automacoes/ agendamentos (.ps1)
estado/                  memória do robô (não apagar) · logs/ registros
testes/                  testes automáticos (Bat/rodar_testes.bat)
```

## Garantias

- **TRUE só depois** de o e-mail aparecer em Itens Enviados (código `NF-XXXXXXXXXX` no rodapé).
- **Anota antes de enviar** (`estado/envios_pendentes.json`): se cair no meio, a próxima rodada confere e não reenvia.
- **Lista de já enviadas** (`estado/ja_enviadas.json`): linha sem TRUE que já saiu só ganha o TRUE.
- **Robô ligado?** (aba Status, B1) desmarcado = nada é enviado.

## Chave do Google

`%APPDATA%\SolicitacoesNF\chave-api.json` (conta de serviço, APIs Sheets + Drive ativas).
Planilhas precisam estar compartilhadas com o `client_email` da chave (Central: Editor · pasta dos hotéis: Leitor).

## Parou?

- Outlook aberto? · Aba Status → B1 marcado? · `logs/solicitacoes_nf.log` (❌ erro, ⚠️ aviso)
- `Bat\executar_robo.bat` mostra tudo na tela · Menu → 🔍 Conferir Cópia dos Hotéis

## Outro PC

Passo a passo completo (instalar, conferir, manter todos os PCs na mesma versão, trocar o PC principal e
pendências): **[INSTALACAO_E_PENDENCIAS.md](INSTALACAO_E_PENDENCIAS.md)**.

Resumo: Outlook clássico aberto → duplo clique em **`INSTALAR_OU_ATUALIZAR.bat`** (do pendrive gerado por
`Bat\gerar_pacote_pendrive.bat` ou de um `git clone`) → cola a chave do Google se pedir. O mesmo `.bat`
atualiza o PC depois de cada mudança.
