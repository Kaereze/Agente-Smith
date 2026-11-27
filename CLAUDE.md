# Projeto Notas Fiscais (Rede Andrade)

Antes de qualquer coisa, leia o Segundo Cérebro: `Segundo Cérebro (Agente Smith)/0 Comece aqui/00 Início.md` (cofre do Obsidian nesta pasta) e o que ele apontar, principalmente `1 Regras/` (hierarquia, o que não mexer, credenciais) e `2 Como trabalhar/` (onde mexer, como entregar).
Depois leia `Segundo Cérebro (Agente Smith)/2 Como trabalhar/Manual do Claude (receitas).md` e `Armadilhas conhecidas.md` (comandos exatos e o que já deu errado). A memória do Claude também está em `1 Regras/Memória do Claude (migrada).md`.
No fim de cada etapa, atualize o cofre seguindo `Segundo Cérebro (Agente Smith)/0 Comece aqui/Como usar este cérebro.md`.
Vale para toda skill, plugin e MCP (impeccable, frontend-design, web-design-guidelines, superpowers, claude-mem, shadcn, 21st, chrome-devtools): o Segundo Cérebro vem primeiro, e o que ele diz vence o padrão da skill. `PRODUCT.md` e `DESIGN.md` na raiz resumem o produto e o design para as skills de design e apontam para o cofre.
Nunca guarde senhas, tokens, a chave do Google ou o segredo do Mail Analytics no cofre nem no repositório.
Num PC fora do trabalho (sem Outlook dos hotéis e sem a chave do Google), use `PAINEL_DEMO_EM_CASA.bat` (dados fictícios) e veja `Segundo Cérebro (Agente Smith)/6 Documentos/Instalação e pendências.md`.

## Navegação rápida (leia isto em vez de procurar arquivo por arquivo)
- Mapa das pastas em linguagem simples: `COMECE_AQUI.md`. Cada módulo e para que serve: `Segundo Cérebro (Agente Smith)/3 Mapa do projeto/Módulos por pasta.md` (gerado do código; não edite).
- `src/`: soltos só os programas que os PCs abrem pelo caminho (`app_servidor`, `conferente`, `sincronizar`, `main`, `config`... **não mover nem renomear**). O resto está em `src/painel`, `emails`, `notas`, `central`, `rede`, `sistema`, `privacidade`; importe assim: `from emails import envio_nf`.
- Tela: React em `app_react/src/` (Vite; `componentes/`, `moldura/`, `telas/`, `dados/`). Mudou a tela? `cd app_react` e `npm run build` (sai em `app_ui/v2/`, que vai no commit; os PCs não instalam nada). Tempo ou limite da tela: `aj("grupo.nome", padrão)` com o padrão igual ao de `src/sistema/ajustes_tabela.py`.
- Dado novo em `estado/`: declare em `src/sistema/armazem.py` e rode `python ferramentas/mapa_dos_dados.py`. Nos testes: código via `testes/codigo_fonte.py`; regras da tela via Node (`testes/test_regras_tela.py`); tela no navegador via Playwright (`testes/test_tela_react_correio.py`).

## Decisões já tomadas (não pergunte de novo; avise só no relatório)
- Testes: `.venv\Scripts\python.exe -m pytest -q`. Lint: `.venv\Scripts\python.exe -m ruff check src testes`. Painel em casa: `src/app_servidor.py --visualizar`; demonstração: `--demo --sem-janela`.
- Trabalhe numa ramificação nova e faça um commit por etapa, com teste verde. **Não suba nem etiquete sem o OK do João** (a etiqueta reinicia os 4 PCs). Com o "pode subir": `git push origin HEAD:main HEAD:Bernardo HEAD:Christian HEAD:clara` e depois `git push origin <etiqueta>`.
- Nunca abrir, fotografar nem colar dado real de hóspede. Foto de tela só da demonstração, em servidor isolado (como `testes/test_tela_react_correio.py`).
- Antes de entregar tela: medir texto cortado e espaçamento em 1440 e 1100 px. Tela nova: desenho para o João aprovar antes de construir.
- **Mudou uma peça do casco (barra lateral, topo, rodapé, margens)? Redesenhe e fotografe o conjunto inteiro**, a janela toda em 1920×1080 e 1100 px, e confira canto vazio, rodapé cortado e rolagem. Foto só da peça isolada não vale (08/11/2026: a barra flutuante foi entregue com a coluna, o topo e o rodapé do desenho antigo).
- Responder em português simples, curto: o que foi feito, o que não deu para verificar, e a pergunta no fim.

