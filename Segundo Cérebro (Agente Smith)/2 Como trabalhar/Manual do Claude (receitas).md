---
tipo: guia
pasta: "2 Como trabalhar"
pai: "[[00 Início]]"
prioridade: P1
atualizado: 2026-10-28
tags: [cerebro/trabalho, receitas]
---
# Manual do Claude: receitas passo a passo

> Para uma sessão **nova**, sem memória, que só tem este cofre. Cada receita tem o comando exato. O que já deu errado está em [[Armadilhas conhecidas]]; as preferências do João em [[Preferências do João]] e [[Memória do Claude (migrada)]].
> Projeto: `C:\Users\Usuário\Desktop\NOTAS\Solicitacoes NF` (GitHub `Kaereze/Agente-Smith`, **privado**). O PC do trabalho é `DESKTOP-GA8IJAU`.

## R0. Começar uma sessão (sempre)
1. `cd "C:\Users\Usuário\Desktop\NOTAS\Solicitacoes NF"` e depois `git fetch --tags origin`, `git status --short`, `git log -3 --oneline`.
2. Ler [[00 Início]] (a parte **Onde paramos**), [[Hierarquia de prioridades]], [[O que não mexer]] e [[Onde mexer]]. Só então abrir o código, no arquivo que **Onde mexer** apontar.
3. `git status` com arquivos alterados que você não fez (o Obsidian troca o fim de linha e cria canvas vazio)? **Não use `git add -A` às cegas**: veja [[Armadilhas conhecidas]].
4. Responder em **português simples** ([[Preferências do João]]).

## R1. Mexer no código sem derrubar o Painel do João
A pasta do projeto **é onde o Painel do João roda**: commit de código nela reinicia o Painel dele ([[2026-10-28 Painel lento por reinícios depois das entregas]]).
1. Trabalhe numa **cópia separada**: `git clone https://github.com/Kaereze/Agente-Smith.git "%USERPROFILE%\Desktop\NOTAS_dev"` (uma vez) e depois `git pull` nela.
2. Instale as ferramentas de teste (uma vez): `python -m pip install -r requirements-dev.txt`.
3. Edite, teste ([[#R2. Testar]]), commite e dê push **da cópia**. O Painel do João se atualiza sozinho quando houver **etiqueta** ([[ADR-01 PCs só atualizam com versão etiquetada]]).
4. **Só documentação** (cofre, CHANGELOG, diário) pode ser feita na pasta do projeto: documentação não reinicia o Painel.

## R2. Testar
- Tudo: `python -m pytest testes -q` (esperado: **tudo passa**; 1 teste pode ser pulado se faltar `requirements-dev.txt`).
- Telas (Edge do Windows, modo demonstração, dados fictícios): `python -m pytest testes/test_telas.py -q`.
- **Ver uma tela à mão (cópia em outra porta, sem tocar no Painel real):**
  1. Copie `app_ui`, `src` e `config.json` para uma pasta temporária.
  2. Na cópia, troque em `src/app_servidor.py` a linha `PORTA = 8765` por `PORTA = 8795`.
  3. Rode `python src/app_servidor.py --demo --sem-janela` dentro da cópia e abra `http://127.0.0.1:8795/`.
  4. Para conferir por script, abra o Edge com `--headless=new --remote-debugging-port=<porta>` e fale com ele pelo protocolo CDP (WebSocket em `http://127.0.0.1:<porta>/json`).
  5. Ao terminar, encerre **só** o processo da cópia (procure pelo caminho dela na linha de comando; nunca pelo nome `python`).
- **Nunca** testar enviando e-mail de verdade. Testes só para `joaocarlossilvazeroum@hotmail.com`.

## R3. Olhar o Painel real (diagnóstico, **só leitura**)
1. `GET http://127.0.0.1:8765/` devolve a página; dentro dela está `TOKEN = "..."`.
2. Mande o token no cabeçalho `X-Token` em `GET /api/atividade` (versões dos PCs), `/api/estado`, `/api/correio`, `/api/caixas`.
3. **O que você ler é dado real de hóspede: só na conversa, nunca salvo em arquivo** ([[ADR-05 Dado real nunca em testes nem documentos]]). Não use rotas que mudam algo.
4. Abrir e-mail **não lido** pelo Painel marca como lido no Outlook real: só abra e-mails já lidos.

## R4. Entregar uma versão (os 4 PCs)
Faça em **lote**, fora do horário de pico, e avise o João antes ([[ADR-01 PCs só atualizam com versão etiquetada]]).
1. `git pull`. Testes passando (R2).
2. **CHANGELOG.md:** entrada nova no topo, `## [AAAA.MM.DD.N] — AAAA-MM-DD`, com Adicionado, Mudou ou Corrigido.
3. **Diário** do dia, **Onde mexer** (se arquivo ou função nova), **Decisões** (ADR) se o João decidiu algo, **Onde paramos** em [[00 Início]].
4. `git add <arquivos que você mudou>` (nunca `-A` sem conferir o `git status`) e `git commit`. O gancho `.githooks/pre-commit` barra credencial e CPF de hóspede.
5. Etiqueta: a primeira do dia é `AAAA.MM.DD`, as seguintes `AAAA.MM.DD.1`, `.2`… → `git tag AAAA.MM.DD.N`.
6. `git push origin main AAAA.MM.DD.N` e depois `git push origin main:Bernardo main:Christian main:clara` (as 3 branches dos PCs ficam iguais à `main`).
7. Conferir: `GET /api/atividade` mostra a versão de cada PC (PC desligado atualiza ao ligar). Se algum não atualizar: "Atualizar todos os PCs" em Máquinas.
8. **Nunca** `push --force`, nunca mover nem apagar etiqueta publicada, nunca reescrever histórico: os PCs usam `git fetch --tags` e `git merge --ff-only`.
9. Só documentação: `git push origin main` **sem etiqueta** (nenhum PC reinicia).

## R5. Desenhar antes de codar
1. Faça a página de design (HTML que roda ao vivo, com animação), **só com dados inventados**, na paleta da Auditoria ([[ADR-03 Telas novas na paleta da Auditoria, sem verde]]), claro e escuro.
2. Publique como artefato, mostre ao João e **espere o OK** ([[Preferências do João]]).
3. Guarde em `6 Documentos/Designs/AAAA-MM-DD Título.html`, a prévia em `previas/` e a entrada em [[Designs]] (pedido, opção escolhida, versão em que entrou).
4. Só depois do OK vá para o código (R1).

## R6. Fechar uma etapa (lista final)
- [ ] Testes passando; nada de dado real nos arquivos (`git grep` por CPF e nome).
- [ ] CHANGELOG e diário do dia.
- [ ] **Onde paramos** em [[00 Início]] (data de hoje) e **Pendências** em [[Ideias e pendências]].
- [ ] [[Onde mexer]] e [[Pastas e arquivos]] se arquivo ou função mudou.
- [ ] [[Mapa visual do sistema]] (`Mapa do sistema.drawio`) se o fluxo mudou: nova rota, robô, fila ou ligação entre PCs.
- [ ] Decisão do João → nota em `Decisões (uma por nota)` e linha em [[Decisões]]. Falha séria → [[Incidentes]]. Erro pequeno → [[Problemas resolvidos]].
- [ ] Mostrar ao João **o que foi testado e o que não foi** (sem esconder).

## R7. Quando perguntar e quando agir
- **Mudança visual ou de lógica:** mostre o desenho e pergunte "posso levar para o Painel?". Mesmo com "faz" ou "pode seguir", confirme uma vez antes de mexer no código, commitar, enviar ao GitHub ou atualizar PCs ([[ADR-01 PCs só atualizam com versão etiquetada]]).
- **Dúvida, mesmo pequena:** pergunte (com opções), dizendo se cada opção é possível.
- **Ação difícil de desfazer ou que afeta os outros** (apagar, forçar envio, mexer em produção, Outlook real, planilhas): pare e confirme em frases completas. Se o bloqueio automático negar um comando, **não contorne**: explique e deixe o João decidir.
- **Intocáveis:** Mail Analytics, planilhas dos hotéis e Dropbox (só leitura; exceção: marcar TRUE na coluna Enviado do hotel depois do envio confirmado), chaves e senhas ([[O que não mexer]], [[Credenciais]]).

## R8. Abrir o Painel em outro PC
- Casa ou PC sem Outlook: `PAINEL_DEMO_EM_CASA.bat` (dados fictícios, ou só leitura com a chave de casa) e o checklist em [[Painel em casa]].
- Atualizar o Painel de um PC: `ATUALIZAR_PAINEL.bat`.
