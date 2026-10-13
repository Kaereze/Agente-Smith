---
tipo: pasta
pasta: "3 Mapa do projeto/Pastas"
pai: "[[Pastas e arquivos]]"
risco: verde
tags: [cerebro/pastas, risco/verde]
---
# testes

> [!risco-verde] Risco verde · Livre
> pode mexer à vontade, seguindo as regras do cofre.

Testes automáticos (~40 arquivos, 300+ testes) com dados de mentira.

## O que tem dentro
- `test_caixa_pedidos.py`, `test_etapa2.py`, `test_painel_*.py`: Painel.
- `test_segredos.py`: trava contra vazamento de credenciais.
- `conftest.py`: preparação comum.

## Como o Claude mexe
- Todo conserto ganha um teste que falharia antes.
- Rodar tudo: `python -m pytest -q`.

## Nunca
- Teste que usa o Google, o Outlook ou e-mail de verdade.
- Apagar teste para fazer passar.

Voltar: [[Pastas e arquivos]] · [[Onde mexer]]
