# Plano da API central (servidor)

Criado em 24/11/2026, a pedido do João, a partir da conversa com o dev. **Estado: etapa 1 pronta (servidor, cliente e testes); nada ligado nos PCs ainda.**

## A ideia em uma frase
Hoje a "Planilha Central" do Google faz o papel de banco de dados e de correio entre os PCs. Passa a existir **um servidor** (o PC **Servidor RA**) que guarda os dados e atende os outros PCs. Os PCs deixam de ler e gravar a planilha e deixam de falar entre si pela rede.

## Por que
- O Google deixa 60 leituras por minuto para **todos os PCs somados**. O Painel de cada PC só pode usar 6 por minuto. Foi isso que deixou o envio "carregando" e o Painel lento (240 esperas medidas em 12/11/2026).
- A conversa direta entre PCs falha quando a porta de um deles está fechada (timeout até o PC da Clara e o do João em 12/11/2026).
- Cada leitura da planilha leva de 1 a 40 segundos. No servidor é questão de milésimos.

## O que NÃO muda
- **Os formulários dos hotéis** (80 abas "(respostas)") continuam no Google: é o Google Forms que alimenta. O `sincronizar` (que já roda no PC principal) continua copiando dali, só que para o servidor.
- **O envio de e-mail** continua sendo feito pelo Outlook do PC dono da caixa. Muda só como ele recebe a ordem: em vez de o PC de quem pediu falar direto com ele, o PC dono **pergunta ao servidor** "tem envio para mim?" (de dentro para fora, o que o firewall quase nunca bloqueia).
- O Painel de cada PC, a tela e o Outlook. A API é por trás.

## Como fica por dentro (decisão de desenho)
O código já conversa com a planilha por uma única "porta": `BackendGoogle` (`src/central/sheets.py`), com 11 métodos. A API oferece **os mesmos 11 métodos** (`BackendAPI`, `src/central/backend_api.py`). Assim:
1. o resto do código (Painel, conferente, robô, envio) não precisa ser reescrito;
2. troca-se o backend por **uma linha de configuração**, PC por PC;
3. se o servidor cair, volta-se ao Google mudando a mesma linha (a planilha fica como espelho na transição).

O servidor (`src/servidor_central/`):
- `armazem.py`: guarda as abas num arquivo SQLite (um arquivo só, fácil de copiar). Cada gravação é uma transação: dois PCs anexando ao mesmo tempo nunca perdem nem misturam linhas (testado com 8 PCs × 25 linhas).
- `servidor.py`: HTTP na porta 8770, rota `POST /v1/chamar`, cabeçalho `X-Token`. Só os 11 métodos da lista podem ser chamados. Sem a variável `CENTRAL_TOKEN` (32+ caracteres) o servidor nem sobe. O token **nunca** vai para o repositório.
- `backup.py`: cópia diária do banco, guarda 14 dias.
- `docker/servidor_central/`: `Dockerfile` e `docker-compose.yml` (`restart: unless-stopped`, banco na pasta `dados/` fora do container).

Um teste (`testes/test_api_central.py`) compara os métodos e argumentos do `BackendGoogle`, do `BackendAPI` e do `Armazem`: se alguém mudar um e esquecer o outro, ele avisa.

## Etapas
| # | O que | Estado |
|---|---|---|
| 1 | Servidor + cliente + testes + Docker + backup | **pronto** (26 testes) |
| 2 | Ferramenta que **copia** a Central do Google para o servidor (só leitura no Google) e confere linha a linha | a fazer |
| 3 | Escolher o backend por configuração (`central.backend`: `google` ou `api`); ligar **um** PC de teste (o Servidor RA) | a fazer |
| 4 | O PC dono da caixa pergunta ao servidor pelos envios (substitui o aviso direto entre PCs e a leitura de 1 min da fila) | a fazer |
| 5 | Ligar os outros PCs, um por vez, com o Google como espelho | a fazer |
| 6 | `sincronizar` grava no servidor; Google fica só com os formulários | a fazer |
| 7 | Telas e rotas que hoje "fingem" ser planilha ganham tabelas de verdade (envios, correio, PCs), mais rápidas | depois, se valer a pena |

Cada etapa só vai para os PCs com o "pode subir" do João. Nada é desligado antes de a seguinte estar provada.

## Para colocar no ar no Servidor RA (DESKTOP-7M6539V)
1. Instalar o WSL2 e o Docker Desktop (este PC ainda **não** tem nenhum dos dois).
2. Windows: nunca suspender nem hibernar; entrar sozinho na conta; Docker Desktop iniciando com o Windows.
3. Reservar um IP fixo para o PC no roteador.
4. Copiar `.env.exemplo` para `.env` (pasta `docker/servidor_central`), pôr um token longo e aleatório (só o João e quem administra sabem) e rodar `docker compose up -d --build`.
5. Tarefa agendada diária no Windows: `docker exec <container> python -m servidor_central.backup /dados/copias`.
6. Liberar a porta 8770 para a rede do escritório (só rede privada).

## Riscos que continuam de pé
- **Servidor desligado = ninguém trabalha.** Mitigação: o Google fica como espelho e a volta é uma linha de configuração. O ideal a longo prazo é uma máquina sempre ligada (nuvem).
- **Disco do PC falhar.** Mitigação: cópia diária também para fora do PC (Dropbox).
- **Dados de hóspedes** (nomes, CPF) passam a morar nesse PC: seguir `Dados de hóspedes (LGPD).md` (disco protegido, acesso só da equipe, token fora do repositório).
- HTTP simples na rede interna (sem HTTPS). Aceitável só dentro do escritório; para a nuvem será preciso HTTPS.
