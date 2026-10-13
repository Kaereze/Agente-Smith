# Credenciais — mapa (SEM os valores)

> **Por que não guardamos os valores aqui:** este cofre está dentro do repositório do GitHub e vai para os 4 PCs e para o PC de casa. Credencial escrita aqui = credencial vazada. O cofre guarda **o que é, onde fica e o que fazer se vazar**. O valor fica só no lugar seguro da coluna "Onde fica".

| Credencial | Para que serve | Onde fica (só neste lugar) | Quem tem | Se vazar |
|---|---|---|---|---|
| **Chave do Google (trabalho)**, conta de serviço | Ler e gravar a Planilha Central e as planilhas dos hotéis | `%APPDATA%\SolicitacoesNF\chave-api.json` em cada um dos 4 PCs (caminho em `config.json` → `caminho_chave_google`) | Os 4 PCs do trabalho | Google Cloud → Contas de serviço → desativar a chave → criar nova → copiar para os 4 PCs (pen drive ou pessoalmente) |
| **Chave do Google (casa)**, conta `painel-casa`, **só Leitor** | Modo casa: ver os dados reais | `%APPDATA%\SolicitacoesNF\chave-api.json` no PC de casa | Só o PC de casa | Apagar só essa chave no Google Cloud; o trabalho não para |
| **Segredo da rede local** (assinatura entre os Painéis) | Busca ao vivo entre os PCs (porta 8766) | Não fica em arquivo: é calculado na memória a partir da chave do Google | Os 4 PCs | Troca sozinho quando a chave do Google é trocada |
| **Token do Painel** (`X-Token`) | Proteger os botões da tela contra outras páginas | Só na memória; muda toda vez que o Painel liga | O próprio PC | Reiniciar o Painel |
| **Login do GitHub** (conta Kaereze) | Baixar e enviar o código | Gerenciador de Credenciais do Windows (Git) | PCs onde o João entrou | github.com → Settings → trocar senha e apagar tokens |
| **Contas de e-mail** (`notafiscal@`…) | Outlook dos hotéis | Perfil do Outlook de cada PC | Cada agente | TI da rede troca a senha |
| **Mail Analytics: chave e segredo do webapp** | Do outro sistema | Na pasta do Mail Analytics | Mail Analytics | **Nunca usar, ler ou repetir.** Já apareceu uma vez sem querer no terminal (11/10/2026) |

## Dados sensíveis (não são senha, mas são protegidos pela LGPD)
- CPF/CNPJ, e-mails e endereços de hóspedes: Outlook, planilhas, `estado/` (565 MB no PC do trabalho). **Nunca** no GitHub, no cofre ou em conversa externa.

## Proteções automáticas
1. `.gitignore` bloqueia `estado/`, `logs/`, `config.local.json`, `.venv/` e arquivos com cara de chave (`chave*.json`, `*service-account*.json`, `*.pem`, `*.key`, `.env`).
2. **Teste `testes/test_segredos.py`**: roda junto com todos os testes antes de cada entrega e **falha** se qualquer arquivo do repositório tiver cara de chave privada, token do GitHub ou chave do Google.
3. Regra do Claude: só verifica se o arquivo **existe** (`Test-Path`), nunca abre nem mostra.

## Onde guardar o valor com segurança (se o João quiser uma cópia)
- **Gerenciador de senhas** (Bitwarden, 1Password, KeePass) ou o **Gerenciador de Credenciais do Windows**. Nunca em nota do Obsidian, e-mail, WhatsApp ou planilha.
