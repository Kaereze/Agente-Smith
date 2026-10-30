---
tipo: plano
pasta: "5 Em andamento"
pai: "[[00 Início]]"
prioridade: P1
tags: [cerebro/plano]
---
# Plano de reestruturação do Painel Fiscal (revisão de 29/10/2026)

Revisão só de leitura, feita com as skills `codebase-design` e `software-design-philosophy` (vocabulário: módulo fundo x raso, costura, vazamento de informação). Nada do código foi mudado.

## O que foi medido
- `src/`: 63 módulos, 17.836 linhas, todos soltos numa pasta. Testes: 95 arquivos.
- `app_servidor.py`: 2.575 linhas. A classe `Estado` tem 118 métodos em 1.914 linhas; o `Handler` tem 44 rotas num `criar_handler` de 264 linhas. Depende de 40 módulos.
- Mais usados: `log_util` (34), `tratamento` (20), `config` (19), `arquivos` (15), `sheets` (14).
- `index.html`: 3.448 linhas (2.160 de estilo, o resto tela e lógica). `painel.js` 1.269 e `correio.js` ~1.300, tudo em funções globais.
- Guardado em 3 estilos: Planilha Central (10 abas), arquivos JSON/pkl em `estado/` e índice local (SQLite).
- Sem nenhum importador: `classificador.py` e `organizador_emails.py` (só aparecem no CHANGELOG).

## Nota (software-design-philosophy): ~5/10
Passa: peças únicas novas (`pecas/`), testes fortes, regras de negócio escritas no cofre. Falha: módulos rasos e vazamento (a `Estado` sabe de tudo), decomposição por tempo, configuração demais.

## Ordem proposta
1. **Limpar** (baixo risco): código sem uso, estilos e telas antigas, mapa do sistema atualizado.
2. **Partir a `Estado`** em módulos fundos por assunto (correio, pedidos, envio, rede, saúde) e trocar o `if` de rotas por uma tabela de rotas. Meta: `app_servidor.py` abaixo de 600 linhas.
3. **Pastas por assunto em `src/`** (envio, correio, robô, dados, rede, sistema); programas de entrada ficam na raiz de `src/`.
4. **Uma porta para os dados:** um módulo só fala com a Planilha/Supabase; JSON e pkl entram no SQLite. Decisão do Supabase é do João.
5. **Tela em arquivos:** estilo fora do `index.html`; um arquivo de lógica por tela.
6. **App completo:** relatórios (PDF/Excel), perfis de acesso, continuidade (segundo PC de envio) e, só depois, o assunto financeiro (boleto, caixa, faturamento) como contexto próprio.
Cada etapa: uma versão, testes verdes, teste de tela, e só sobe com OK do João.

## Andamento (29/10/2026)
- Passo 1 (limpar) e passo 2 (partir a `Estado`): feitos no PC de casa, sem etiqueta. `app_servidor.py` 2.575 → 1.093 linhas. Falta a tabela de rotas.
- Supabase: por último, não usar agora (decisão do João). Foco: só NF e e-mail.
