---
tipo: regra
pasta: "1 Regras"
pai: "[[00 Início]]"
prioridade: P0
tags: [cerebro/regras]
---
# O que não mexer

Ordem de importância: ver [[Hierarquia de prioridades]]. Credenciais: ver [[Credenciais]].

## P0 · Segurança e privacidade (nunca)
- **Nenhuma credencial** (chave do Google, token, senha, login do GitHub, segredo do Mail Analytics) em arquivo do repositório, no cofre, em commit, em log ou em mensagem. Nem "só para testar".
- **Nunca imprimir** o conteúdo de `chave-api.json` nem variáveis com segredo no terminal. Ler só o nome do arquivo e se existe.
- **Dados de hóspedes** (nome, CPF/CNPJ, e-mail, endereço) ficam no Outlook, nas planilhas e em `estado/`. Nunca no GitHub, no cofre ou em ferramenta externa.
- **E-mail para hóspede:** o Claude nunca envia por conta própria. Testes só para `joaocarlossilvazeroum@hotmail.com`.
- Pasta `estado/`, `logs/`, `config.local.json` e `.venv/` **nunca** sobem (estão no `.gitignore`).

## P1 · Produção (não mexer sem pedido explícito)
| Não mexer | Onde | Pode? |
|---|---|---|
| **Mail Analytics: código** | `Desktop\Mail Analitycs` (outro sistema, em produção nos 4 PCs) | **Nada.** Nem abrir para editar |
| **Mail Analytics: planilha** | abas `Agente_Joao/Clara/Cristian/Bernardo` | **Só ler** (`src/relatorio_semana.py`) |
| **Fiscal Intelligence** | planilha gravada pelo Mail Analytics | **Só ler** (`src/fiscal_intelligence.py`) |
| **Planilhas dos hotéis** | pasta do Drive (outra conta) | **Só ler** (`src/sincronizar.py`) |
| **TRUE na coluna "Enviado" dos hotéis** | vem de um script do próprio João | Não mexer nem questionar |
| **Dropbox** (pastas de NF dos agentes) | `%USERPROFILE%\Dropbox...` | **Só olhar**; não abrir PDF "somente online" |
| **Outlook real** | caixas `notafiscal@` dos 4 PCs | Em teste: não abrir não lidos, não enviar, não excluir, não mover |
| **Modo Professor / preferências do PC** | `POST /api/professor` | Scripts de teste não mexem |
| **Branches dos colegas** | `Bernardo`, `Christian`, `clara` | Só fast-forward da `main` (nunca forçar) |
| **Tarefas do Windows** | `SolicitacoesNF_CopiaHoteis`, `_Conferente`, `_Painel`, `_Reiniciar` | Não apagar nem renomear |
| **Firewall / rede dos PCs** | perfil de rede, porta 8766 | Decisão do João; precisa de administrador |
| **PCs dos colegas** | "nada de .bat" lá; sem administrador | Pedir pela sessão Remote Control; não insistir |

## Sempre
- Português simples, sem jargão. Datas absolutas.
- Perguntar antes de decisões grandes de design/organização; se o João já explicou o problema, executar e mostrar antes/depois.
- Todo processo tem **log**; todo botão mostra **carregamento**; sempre um **plano B** quando algo falha em silêncio.
- **Capturas com zoom** depois de mudança visual.
- `git pull` antes de começar (o João mexe no trabalho **e** em casa). Ver [[Como entregar]].
- Ler [[Onde mexer]] antes de procurar no código.
