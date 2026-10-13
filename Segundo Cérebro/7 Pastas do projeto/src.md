---
nivel: "7 · Pastas do projeto"
pai: "[[Pastas do projeto]]"
risco: laranja
tags: [cerebro/pastas, risco/laranja]
---
# src

> [!p1] Risco laranja · Produção — com cuidado
> roda nos 4 PCs; mexer só com teste, commit e atualização dos PCs.

Todo o código Python: Painel (servidor), robô de envio, cópia dos hotéis, conferente, espelho do Outlook, envio de NF.

## O que tem dentro
- `app_servidor.py`: servidor do Painel (classe `Estado`).
- `sincronizar.py`, `main.py`, `conferente.py`, `espelho_emails.py`, `envio_nf.py`: os robôs.
- `config.py`, `sheets.py`, `cota_google.py`: base.
- Lista completa: [[Mapa do código]].

## Como o Claude mexe
- Achar a função em [[Onde mexer]] antes de abrir o arquivo.
- Teste novo ou ajustado em `testes/` para cada mudança.
- `python -m pytest -q` + `python -m pyflakes src/*.py` antes do commit.
- Depois: [[Como entregar]] (push nas 4 branches + Atualizar todos os PCs).

## Nunca
- Leitura nova do Google sem refazer a conta da cota (P3).
- Gravar em planilha do Mail Analytics, dos hotéis ou no Dropbox (P1).
- Mexer no Outlook real em teste (abrir não lido, enviar, excluir).

Voltar: [[Pastas do projeto]] · [[Onde mexer]]
