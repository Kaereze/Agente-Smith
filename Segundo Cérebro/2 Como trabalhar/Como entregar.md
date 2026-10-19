---
tipo: guia
pasta: "2 Como trabalhar"
pai: "[[00 Início]]"
prioridade: P1
tags: [cerebro/trabalho]
---
# Como entregar cada mudança

> **Dois PCs do João (12/10/2026):** ele modifica o projeto no PC do trabalho **e** no PC de casa. Sempre `git pull` antes de começar (em qualquer PC) e enviar ao GitHub no fim, senão um PC apaga o trabalho do outro. O PC de casa roda o Painel em modo demonstração (sem chave do Google, sem `estado/`, sem Outlook dos hotéis).

0. `git pull` (pegar o que veio do outro PC).
1. Rodar os testes (`python -m pytest -q` na pasta do projeto; 375 passando em 19/10). No PC do João o **pre-commit** já roda os testes e barra credenciais e `estado/` sozinho; depois do push, o **GitHub Actions** roda os testes de novo (aba Actions do repositório).
2. Conferir a tela de verdade (captura no Edge sem janela, temas claro e escuro), sem erro de JavaScript.
3. **Commit** em português, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
4. **Push** na `main`.
5. Conferir se `Bernardo`, `Christian` e `clara` estão atrás da main (`git merge-base --is-ancestor`) e deixá-las iguais: `git push origin main:Bernardo main:Christian main:clara`.
6. **"Atualizar todos os PCs"** (botão em Máquinas ou o comando `atualizar` para TODOS).
7. Mandar as capturas com zoom ao João e explicar em português simples.
8. Atualizar este cérebro (ver [[Como usar este cérebro]]).

**Por quê:** os 4 PCs se atualizam pelo GitHub; um erro derruba a equipe toda.
