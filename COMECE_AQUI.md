# Comece aqui: onde mexer em cada coisa

Este arquivo é para qualquer pessoa, programadora ou não. Diz **o que cada pasta é** e **para onde ir** quando você quer mudar algo.
Se você é o Claude: leia também `CLAUDE.md` e o índice `Segundo Cérebro (Agente Smith)/3 Mapa do projeto/Módulos por pasta.md` antes de procurar arquivos.

## Quero mudar... (o caminho mais curto)

| Quero mudar | Vá para |
|---|---|
| Um **texto, cor, botão ou espaçamento** da tela | `app_ui/` (estilo em `estilo.css`; a tela de e-mail em `correio_*.js`; o resumo em `pecas/resumo_dia.js`) |
| Uma **regra da nota fiscal** (o que falta para emitir, prazo, NF pronta) | `src/notas/` e, para o que "falta dado", `app_ui/pecas/regras_nf.js` |
| O jeito de **enviar a NF** ou o assunto do e-mail | `src/emails/envio_nf.py` e `app_ui/painel_enviar_nf.js` |
| **Quanto tempo** algo espera, limites, assinaturas, mensagens padrão | `ajustes.json` (copie de `ajustes.exemplo.json`); **não precisa mexer em código** |
| Um **número novo** numa tela | `src/painel/` (a conta) e `app_ui/` (o desenho) |
| Algo de **Planilha, Google, cota** | `src/central/` |
| **Um PC não enxerga outro** | `src/rede/` |
| **LGPD**: quem viu o dado, pedido de um titular | `src/privacidade/` e `ferramentas/pedido_titular.py` |
| **Instalar ou atualizar** um PC | `INSTALAR_OU_ATUALIZAR.bat`, `ATUALIZAR_PAINEL.bat`, `INSTALAR_PC_SO_PAINEL.bat` (dê dois cliques) |
| Abrir o Painel em casa, com dados fictícios | `PAINEL_DEMO_EM_CASA.bat` |

## As pastas, uma por uma

| Pasta | O que é | Pode mexer? |
|---|---|---|
| `app_ui/` | **A tela** que você vê: HTML, estilo e JavaScript, dividido por assunto (`telas_*`, `correio_*`, `painel_*`); `pecas/` guarda as peças que se repetem (filtro, etiqueta, janela, resumo) | Sim, para mudar a aparência |
| `src/` | **O programa** (Python). Aqui ficam só os programas que os PCs abrem pelo nome (`app_servidor.py`, `conferente.py`, `sincronizar.py`...). O resto está nas pastas abaixo | Sim, com cuidado |
| `src/painel/` | O servidor do Painel e as contas das telas | Sim |
| `src/emails/` | Outlook, espelho dos e-mails, busca, envio da NF | Sim |
| `src/notas/` | Regras da nota fiscal | Sim |
| `src/central/` | A Planilha Central e o Google | Sim |
| `src/rede/` | Os PCs conversando entre si | Com muito cuidado (segurança) |
| `src/sistema/` | Base: gravar arquivo, log, trava, catálogo dos dados | Quase nunca |
| `src/privacidade/` | LGPD | Sim |
| `testes/` | Os testes automáticos (mais de 800). Rodam antes de toda entrega | Só junto com a mudança |
| `ajustes.json` | Tempos, limites, textos e assinaturas (não sobe para o GitHub; fica em cada PC) | **Sim, sem código** |
| `ferramentas/` | Programas de apoio: conferir antes do commit, pedido do titular, mapas gerados | Raramente |
| `Automacoes/` | Scripts de instalação e das tarefas do Windows nos PCs | **Não renomear nem mover**: as tarefas dos 4 PCs apontam para eles |
| `Bat/` | Atalhos antigos (instalar, rodar testes, cópia agendada) | **Não renomear**: tarefas agendadas usam |
| `apps_script/` | O código do Google Apps Script (formulários) | Só no Google |
| `.github/` e `.githooks/` | Testes automáticos no GitHub e a trava antes do commit | Raramente |
| `Segundo Cérebro (Agente Smith)/` | **O cofre de documentação** (Obsidian): regras, como trabalhar, mapas, diário, auditorias | Sim, é a memória do projeto |
| `estado/` e `logs/` | **O que o Painel guarda neste PC** e os registros. Nunca sobem para o GitHub | **Não mexer** (dado de hóspede) |

## Regras que valem para tudo
- **Dado de hóspede (nome, CPF, e-mail) nunca vai para o GitHub, para o cofre nem para conversa.** Teste e exemplo usam dados inventados.
- **Só versão etiquetada chega aos 4 PCs.** Commit solto não muda nenhum PC; etiqueta reinicia o Painel de todos.
- Arquivo novo em `estado/`: declare em `src/sistema/armazem.py`. Módulo novo em `src/`: ponha na pasta do assunto.
- Antes de entregar: `.venv\Scripts\python.exe -m pytest -q` e `.venv\Scripts\python.exe -m ruff check src testes`.
