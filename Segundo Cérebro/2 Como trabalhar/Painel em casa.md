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
git clone https://github.com/Kaereze/Notas-Fiscais.git "%USERPROFILE%\Desktop\NOTAS\Solicitacoes NF"
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
