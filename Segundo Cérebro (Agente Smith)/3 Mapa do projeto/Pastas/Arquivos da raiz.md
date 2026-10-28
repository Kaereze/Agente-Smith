---
tipo: pasta
pasta: "3 Mapa do projeto/Pastas"
pai: "[[Pastas e arquivos]]"
risco: laranja
tags: [cerebro/pastas, risco/laranja]
---
# Arquivos da raiz

> [!risco-laranja] Risco laranja · Produção — com cuidado
> roda nos 4 PCs; mexer só com teste, commit e atualização dos PCs.

Os arquivos soltos na pasta `Solicitacoes NF`.

## O que tem dentro
- `config.json`: configuração de todos os PCs (sem senha).
- `robo.py`: entrada do robô de envio.
- `requirements.txt`: bibliotecas.
- `ATUALIZAR_PAINEL.bat`, `INSTALAR_OU_ATUALIZAR.bat`, `PAINEL_DEMO_EM_CASA.bat`: instalar/atualizar/casa.
- `CLAUDE.md`: manda o Claude ler este cofre.
- `README.md`: apresentação curta (aponta para o cofre).
- `.gitignore`, `.gitattributes`: o que não sobe / fim de linha.

## Como o Claude mexe
- `config.json` vale para os 4 PCs: mudança testada e avisada.
- Ajuste só de um PC vai no `config.local.json` (não sobe).

## Nunca
- Pôr caminho de chave diferente ou senha no `config.json`.
- Tirar linhas do `.gitignore` (proteção P0).

Voltar: [[Pastas e arquivos]] · [[Onde mexer]]
