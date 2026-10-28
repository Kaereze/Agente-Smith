---
tipo: pasta
pasta: "3 Mapa do projeto/Pastas"
pai: "[[Pastas e arquivos]]"
risco: vermelho
tags: [cerebro/pastas, risco/vermelho]
---
# logs

> [!risco-vermelho] Risco vermelho · Não mexer à mão
> gerado pelo programa ou sensível; nunca editar, nunca subir ao GitHub.

Registros do que o programa fez.

## O que tem dentro
- Um log por programa (desde 20/10/2026), cada um com os antigos `.1`…`.5` (5 MB cada):
  - `solicitacoes_nf.log`: o **robô** (cópia dos hotéis + envio, `robo.py`, `main.py`);
  - `conferente.log`: o conferente (sempre ligado em cada PC);
  - `painel.log`: o servidor do Painel;
  - outros scripts (`confirmar_nfs.py`…) ganham o seu, com o nome do script (`log_util.arquivo_do_programa`).
  - Antes de 20/10 os três escreviam no mesmo `solicitacoes_nf.log` e a rotação falhava ("Logging error").
- `atualizacao.log`: atualizações e reinícios.
- `Historico_de_Envios.csv`: envios.
- `saida_console_sincronizar.txt` (+ `.1`, `.2`): o que a cópia agendada escreve na tela; gira em 5 MB (desde 20/10/2026).

## Como o Claude mexe
- Ler para investigar problema (procurar o horário).

## Nunca
- Editar ou apagar.
- Subir ao GitHub.
- Copiar trechos com dados de hóspede para fora.

Voltar: [[Pastas e arquivos]] · [[Onde mexer]]
