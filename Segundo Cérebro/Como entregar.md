# Como entregar cada mudança

> **Dois PCs do João (12/10/2026):** ele modifica o projeto no PC do trabalho **e** no PC de casa. Sempre `git pull` antes de começar (em qualquer PC) e enviar ao GitHub no fim, senão um PC apaga o trabalho do outro. O PC de casa roda o Painel em modo demonstração (sem chave do Google, sem `estado/`, sem Outlook dos hotéis).

0. `git pull` (pegar o que veio do outro PC).
1. Rodar os testes (`python -m pytest -q` na pasta do projeto; 309 passando em 11/10).
2. Conferir a tela de verdade (captura no Edge sem janela, temas claro e escuro), sem erro de JavaScript.
3. **Commit** em português, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
4. **Push** na `main`.
5. Conferir se `Bernardo`, `Christian` e `clara` estão atrás da main (`git merge-base --is-ancestor`) e deixá-las iguais: `git push origin main:Bernardo main:Christian main:clara`.
6. **"Atualizar todos os PCs"** (botão em Máquinas ou o comando `atualizar` para TODOS).
7. Mandar as capturas com zoom ao João e explicar em português simples.
8. Atualizar este cérebro (ver [[Como usar este cérebro]]).

**Por quê:** os 4 PCs se atualizam pelo GitHub; um erro derruba a equipe toda.
