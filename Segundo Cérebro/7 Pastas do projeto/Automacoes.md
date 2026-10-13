---
nivel: "7 · Pastas do projeto"
pai: "[[Pastas do projeto]]"
risco: laranja
tags: [cerebro/pastas, risco/laranja]
---
# Automacoes

> [!p1] Risco laranja · Produção — com cuidado
> roda nos 4 PCs; mexer só com teste, commit e atualização dos PCs.

Scripts PowerShell que instalam, agendam e reiniciam o robô nos PCs.

## O que tem dentro
- `reiniciar_servicos.ps1`: reinício depois de atualizar (com log).
- `agendar_*.ps1`: criam as tarefas do Windows.
- `coracao.ps1`: instalador único.
- `liberar_rede.ps1`: firewall da porta 8766 (precisa de administrador).
- `gerar_exemplo_email.py`: gera os [[Exemplos de e-mail]].

## Como o Claude mexe
- Testar primeiro só neste PC; o reinício roda nos 4.
- Registrar no `logs/atualizacao.log` o que o script fez.

## Nunca
- Apagar ou renomear as tarefas `SolicitacoesNF_*`.
- Pedir administrador nos PCs dos colegas.

Voltar: [[Pastas do projeto]] · [[Onde mexer]]
