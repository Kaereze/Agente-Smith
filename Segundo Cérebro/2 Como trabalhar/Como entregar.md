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
3. **Commit** em português, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Acrescentar a entrega no topo do `CHANGELOG.md` (versão = data, `AAAA.MM.DD`) e, no último commit do dia, a etiqueta: `git tag -a AAAA.MM.DD -m "Versão AAAA.MM.DD"` e `git push origin AAAA.MM.DD`. Já tem etiqueta do dia? A próxima entrega é `AAAA.MM.DD.1`, `.2`…: etiqueta publicada **nunca** é movida (exigiria push forçado, que a guarda do git bloqueia).
4. **Etiqueta antes do push (desde 27/10/2026, canal de teste):** os PCs só se atualizam sozinhos até a **última versão com etiqueta**. Sem etiqueta, o commit fica no GitHub e não chega. Para subir de verdade: etiquetar (`git tag AAAA.MM.DD[.n]`) e `git push origin main --tags` (mais o passo 5). "Atualizar todos os PCs" vai até o último commit, com ou sem etiqueta.
4. **Push** na `main`. **Atenção (23/10/2026): commit de código na pasta do projeto do PC do João já é subir.** Os PCs se
   atualizam sozinhos a cada 15 min (`painel.atualizar_sozinho`) e o Painel do João reinicia ~5 min depois que o código da
   pasta muda (`_conferir_reinicio`). Mudança que ainda espera o OK do João fica **só na cópia de teste**, sem commit aqui.
5. Conferir se `Bernardo`, `Christian` e `clara` estão atrás da main (`git merge-base --is-ancestor`) e deixá-las iguais: `git push origin main:Bernardo main:Christian main:clara`.
6. **"Atualizar todos os PCs"** (botão em Máquinas ou o comando `atualizar` para TODOS).
7. Mandar as capturas com zoom ao João e explicar em português simples.
8. Atualizar este cérebro (ver [[Como usar este cérebro]]).

**Por quê:** os 4 PCs se atualizam pelo GitHub; um erro derruba a equipe toda.
