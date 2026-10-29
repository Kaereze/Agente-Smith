---
tipo: guia
pasta: "2 Como trabalhar"
pai: "[[00 Início]]"
tags: [cerebro/trabalho]
---
# Painel em casa (modo casa)

Decidido em 12/10/2026: no PC de casa o Painel mostra os **dados reais, só para ver**. Ele lê a Planilha Central e **não grava nada**: não aparece em Máquinas, não executa comandos da equipe, não mexe no Outlook e relê devagar (1 vez por minuto com a janela aberta) para não gastar a cota do Google dos 4 PCs.
Responder, enviar NF e marcar lido continuam **só nos PCs do trabalho**.

## Passo 1: o projeto
No PC de casa, com o Git instalado:
```
git clone https://github.com/Kaereze/Agente-Smith.git "%USERPROFILE%\Desktop\NOTAS\Solicitacoes NF"
```

## Passo 2: a chave do Google de casa (separada, só leitura)
Se um dia vazar, apaga-se só ela, sem parar os PCs do trabalho.
1. Entre em https://console.cloud.google.com com a conta dona do projeto da chave atual.
2. **IAM e administrador → Contas de serviço → Criar conta de serviço**. Nome: `painel-casa`. Não precisa dar papel nenhum.
3. Abra a conta criada → **Chaves → Adicionar chave → Criar nova chave → JSON**. O arquivo baixa sozinho.
4. Copie o e-mail da conta (termina em `iam.gserviceaccount.com`).
5. No Google Sheets, compartilhe como **Leitor** com esse e-mail:
   - a **Planilha Central! (Krz)**;
   - a planilha do **Mail Analytics** (para o relatório da Gerência).
6. No PC de casa, salve o arquivo baixado com este nome e lugar:
   `%APPDATA%\SolicitacoesNF\chave-api.json`
   (cole `%APPDATA%\SolicitacoesNF` na barra do Explorer; crie a pasta se não existir).

## Passo 3: abrir
Dê dois cliques em `PAINEL_DEMO_EM_CASA.bat` (na pasta do projeto). Ele instala o que faltar e:
- com a chave no lugar → abre com **dados reais (Modo casa · só visualização)**;
- sem a chave → abre com dados fictícios (modo demonstração).

## Lembrete
Mexeu no código em casa? Envie ao GitHub no fim. Ao chegar ao trabalho, `git pull` antes de começar. Ver [[Como entregar]].

## Otimizar ou mexer em casa: checklist (27/10/2026)
1. `git pull` antes de começar (confira que `origin/main` está na versão mais nova do [[CHANGELOG]]). Ver o plano em [[Designs]] ("Auditoria do Painel", 27/10).
2. Trabalhe no **modo demonstração** ou **modo casa**: dados fictícios ou só leitura. **Nunca** copie dado real de hóspede para teste ou documento ([[Preferências do João]]).
3. Rode os testes (`python -m pytest testes -q`) antes de enviar.
4. Envie ao GitHub: `git push origin main`. **Sem etiqueta, nada chega aos PCs do trabalho.** Para entregar, crie a etiqueta da versão (ver [[Como entregar]]).
5. **Nunca** `push --force`, nunca mover nem apagar etiqueta publicada: os PCs travariam na atualização.
6. O que **não** sobe pelo GitHub, de propósito: a pasta `estado/` e `logs/` (dados de hóspedes), `config.local.json` e a chave do Google. No PC de casa a chave é a separada, de só leitura (Passo 2 acima).
