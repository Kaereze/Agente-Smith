# Comece aqui: onde mexer em cada coisa

Este arquivo é para qualquer pessoa, programadora ou não. Diz **o que cada pasta é** e **para onde ir** quando você quer mudar algo.
Se você é o Claude: leia também `CLAUDE.md` e o índice `Segundo Cérebro (Agente Smith)/3 Mapa do projeto/Módulos por pasta.md` antes de procurar arquivos.

## Quero mudar... (o caminho mais curto)

| Quero mudar | Vá para |
|---|---|
| Um **texto, cor, botão ou espaçamento** da tela | `app_react/src/` (cores em `estilo/tema.css`; a caixa de e-mail em `telas/CaixaEntrada.jsx` e `telas/correio/`; a moldura em `moldura/`). Depois: `cd app_react` e `npm run build` |
| Uma **regra da nota fiscal** (o que falta para emitir, prazo, NF pronta) | `src/notas/` e, na tela, `app_react/src/dados/formulario.js` |
| O jeito de **enviar a NF** ou o assunto do e-mail | `src/emails/envio_nf.py` e `app_react/src/telas/correio/Escrever.jsx` |
| **Quanto tempo** algo espera, limites, assinaturas, mensagens padrão | `ajustes.json` (copie de `ajustes.exemplo.json`); **não precisa mexer em código** |
| Um **número novo** numa tela | `src/painel/` (a conta) e `app_react/src/telas/` (o desenho) |
| Algo de **Planilha, Google, cota** | `src/central/` |
| **Um PC não enxerga outro** | `src/servidor_central/` | O **servidor da API** (em construção): um PC guarda os dados e atende os outros PCs | Com muito cuidado (guarda dados de hóspedes) |
| `src/rede/` |
| **LGPD**: quem viu o dado, pedido de um titular | `src/privacidade/` e `ferramentas/pedido_titular.py` |
| **Instalar ou atualizar** um PC | `INSTALAR_OU_ATUALIZAR.bat`, `ATUALIZAR_PAINEL.bat`, `INSTALAR_PC_SO_PAINEL.bat` (dê dois cliques) |
| Abrir o Painel em casa, com dados fictícios | `PAINEL_DEMO_EM_CASA.bat` |

## As pastas, uma por uma

| Pasta | O que é | Pode mexer? |
|---|---|---|
| `app_ui/` | O que o servidor do Painel entrega pronto: `v2/` é **a tela montada** (gerada pelo `app_react`; não edite à mão), `assinaturas/` os selos dos e-mails, `agentes/mapa.html` o mapa dos Agentes do Smith e o ícone. A tela antiga em JavaScript saiu em 27/11/2026 | Só `assinaturas/` e o mapa |
| `app_react/` | **A tela do Painel em React** (27/11/2026), em componentes: `src/componentes/` (botões, ícones, gráficos, janela, avisos, tela de carregamento K; ex.: um só `BotaoEnviarNF.jsx` para todas as telas), `src/moldura/` (cápsula, topo, rodapé, menu "Quem está neste PC", ajuda), `src/telas/` (Visão geral, Caixa de entrada e `correio/`, Robô, Monitoramento…), `src/dados/` (as contas e regras, só com dados reais). Montar: `cd app_react`, `npm install` (1ª vez), `npm run build` → sai em `app_ui/v2/`. Os 4 PCs não instalam nada | Sim, para mudar a tela |
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
| `docker/` | Arquivos para colocar o servidor central no ar no PC "Servidor RA" (Dockerfile, compose, token de exemplo) | Só junto com o servidor; o `.env` com o token **nunca** sobe |
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
