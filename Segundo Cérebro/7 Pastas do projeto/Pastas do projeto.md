---
nivel: "7 · Pastas do projeto"
pai: "[[00 Início]]"
tags: [cerebro/pastas]
---
# Pastas do projeto

> Cada pasta de `Desktop\NOTAS\Solicitacoes NF` tem uma nota aqui. **Os arquivos continuam no lugar deles**: mover uma pasta do programa quebraria o robô e o Painel nos 4 PCs (P1). Visual: [[Mapa das pastas.canvas|Mapa das pastas]].

> [!p0] Vermelho · Não mexer à mão
> gerado pelo programa ou sensível; nunca editar, nunca subir ao GitHub.
> [[estado]] · [[logs]] · [[saida_simulacao]] · [[Python do projeto (.venv)]]

> [!p1] Laranja · Produção — com cuidado
> roda nos 4 PCs; mexer só com teste, commit e atualização dos PCs.
> [[src]] · [[Automacoes]] · [[Bat]] · [[apps_script]] · [[Arquivos da raiz]]

> [!p3] Azul · Tela do Painel
> o que a equipe vê; mexer seguindo o Padrão de design e com capturas.
> [[app_ui]]

> [!p5] Verde · Livre
> pode mexer à vontade, seguindo as regras do cofre.
> [[testes]] · [[Segundo Cérebro]] · [[NOTAS (pasta de cima)]]

## Árvore
```text
Desktop\NOTAS\
├── CLAUDE.md, .mcp.json            (verde)  → NOTAS (pasta de cima)
└── Solicitacoes NF\
    ├── src\                        (laranja) código Python
    ├── app_ui\                     (azul)    tela do Painel
    ├── testes\                     (verde)   testes automáticos
    ├── Automacoes\                 (laranja) PowerShell: instalar, agendar, reiniciar
    ├── Bat\                        (laranja) atalhos de dois cliques
    ├── apps_script\                (laranja) menu da Planilha Central
    ├── Segundo Cérebro\            (verde)   este cofre
    ├── estado\                     (vermelho) memória local, dados de hóspedes
    ├── logs\                       (vermelho) registros
    ├── saida_simulacao\            (vermelho) e-mails simulados
    ├── .venv\                      (vermelho) Python do projeto
    └── config.json, robo.py, *.bat (laranja) → Arquivos da raiz
```
