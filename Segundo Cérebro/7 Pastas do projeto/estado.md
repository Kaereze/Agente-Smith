---
nivel: "7 · Pastas do projeto"
pai: "[[Pastas do projeto]]"
risco: vermelho
tags: [cerebro/pastas, risco/vermelho]
---
# estado

> [!p0] Risco vermelho · Não mexer à mão
> gerado pelo programa ou sensível; nunca editar, nunca subir ao GitHub.

Memória local do programa neste PC: caches, travas, backups da Central, dados de hóspedes. ~565 MB.

## O que tem dentro
- `backup_central_*.json`: cópias da Central antes de gravar.
- `*.lock`: travas entre processos.
- `app.json`: preferências do Painel deste PC.
- `painel_cache*.pkl`: cache para abrir rápido.
- `app_edge/`, `app_webview/`: perfil da janela.

## Como o Claude mexe
- Só ler pelo programa. Para "zerar" algo, usar a função do próprio código.

## Nunca
- Editar ou apagar arquivos à mão (pode travar o robô).
- Subir ao GitHub (está no `.gitignore`; tem dados de hóspedes, P0).
- Abrir e copiar dados de hóspedes para fora.

Voltar: [[Pastas do projeto]] · [[Onde mexer]]
