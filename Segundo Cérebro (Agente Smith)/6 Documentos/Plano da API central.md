# Plano da API central (servidor)

Criado em 24/11/2026, a pedido do João, a partir da conversa com o dev. **Estado: etapas 1 a 5 prontas (a ferramenta); a virada de verdade ainda NÃO foi feita. A API vem DESLIGADA em todos os PCs.**

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
| 2 | Ferramenta que **copia** a Central do Google para o servidor (só leitura no Google) e confere linha a linha | **pronta** (`ferramentas/copiar_central_para_servidor.py`; 11 testes). Ensaio real em 24/11/2026: 33 abas, 61.983 linhas, 2 min, 29 MB; 26 abas iguais de primeira e as outras 7 (que os PCs reescrevem o tempo todo) fecharam na 2ª passada |
| 3 | Escolher o backend por PC e ligar **um** PC de teste (o Servidor RA) | **pronta** (`src/central/backend_roteado.py`; 16 testes). Teste real em 24/11/2026 (servidor no próprio PC, sem Docker): Painel lendo do servidor, 1.086 pedidos, 82 hotéis, sem nenhum erro nem aviso de lentidão em 4 min; voltas regulares de ~18 s. Depois desfeito (arquivo local removido) |
| 4 | O PC dono da caixa é **avisado pelo servidor** no instante em que o pedido chega (substitui o aviso direto entre PCs, que dá timeout, e a espera pela volta de 15 s) | **pronta** (16 testes novos). Teste ao vivo em 24/11/2026: o vigia do Painel real ficou pendurado no servidor, acordou no mesmo instante da gravação e voltou a esperar em 0,5 s; derrubei o servidor e ele avisou uma vez e se reconectou sozinho. **Não mandei e-mail de verdade** (o envio ponta a ponta foi provado só em teste com Outlook falso) |
| 5 | Ferramentas e roteiro da **virada** (ligar e desligar o servidor nos PCs por comando, quem está onde, caminho de volta para o Google, servidor sem Docker) | **ferramentas prontas** (36 testes). Ensaio ao vivo em 24/11/2026 só no Servidor RA, pelo canal real do Google: `ligar_servidor` → o PC conferiu o servidor, gravou, respondeu e reiniciou ligado; `desligar_servidor` → voltou ao Google. **A virada dos outros PCs não foi feita: falta o "vai" do João, IP fixo e servidor rodando de verdade** |
| 6 | `sincronizar` grava no servidor; Google fica só com os formulários | a fazer (e talvez nem seja preciso: ele só grava as abas de formulário, que ficam no Google) |
| 7 | Telas e rotas que hoje "fingem" ser planilha ganham tabelas de verdade (envios, correio, PCs), mais rápidas | depois, se valer a pena |

Cada etapa só vai para os PCs com o "pode subir" do João. Nada é desligado antes de a seguinte estar provada.

## Como funciona a escolha (etapa 3)
- Todos os programas pedem o acesso aos dados em `criar_backend(cfg)` (`src/central/backend_roteado.py`). Sem o arquivo local, é o Google de sempre.
- Para ligar **um PC**: criar `estado/central_api.json` (fora do GitHub, porque leva o token): `{"ligada": true, "url": "http://IP:8770", "token": "..."}` e reiniciar o Painel. Para desligar: apagar o arquivo (ou `"ligada": false`) e reiniciar.
- O que vai para o servidor: as abas internas da Central. O que **fica no Google**: as 80 abas de formulário `(respostas)`, o `Cadastro_Hoteis` (a equipe edita na própria planilha), todas as outras planilhas (hotéis, Mail Analytics) e o `sincronizar` (que grava as cópias dos formulários direto no Google).
- **Cuidado:** um PC ligado vê os dados do servidor, não os do Google. Ligar só um PC dá um PC **isolado** dos outros (serve de teste). A virada de todos juntos é a etapa 5.
- Modo casa (só visualização) continua sem gravar em lugar nenhum. Servidor fora do ar: o Painel mostra erro e tenta de novo na volta seguinte, como acontece com o Google.

## Como o envio funciona com o servidor (etapa 4)
- O servidor dá a cada aba um **número de versão** que sobe a cada gravação. `esperar_mudanca(aba, versão_vista)` segura a chamada (até 20 s) e responde assim que a aba muda. É como um "toque na campainha", sem ninguém perguntar de segundo em segundo.
- Com a API ligada, cada Painel tem um **vigia** (`iniciar_vigia_de_envios`): fica pendurado esperando a fila `Envios_NF` mudar; quando muda, lê a fila e atende o que for deste PC. Também mantém em dia o status que a tela de quem pediu mostra.
- Com o vigia ligado: a volta de 15 s do Painel não sobrescreve a fila nem atende de novo, e o **aviso direto entre PCs deixa de ser usado** (era ele que dava timeout no PC da Clara).
- Rede de segurança: mesmo sem novidade, o vigia relê a fila a cada 60 s. Servidor fora do ar: o vigia avisa uma vez no log, tenta de novo (espera até 30 s) e avisa quando volta.
- `/v1/saude` informa `esperando`: quantos PCs estão pendurados agora (o normal é 1 por Painel ligado).
- Sem a API (Google), nada disso liga: o envio funciona como sempre.

## Como copiar a Central para o servidor (etapa 2)
1. `python ferramentas/copiar_central_para_servidor.py --so-listar` mostra o que seria copiado (nomes e contagens, nunca conteúdo).
2. Com o servidor no ar e a variável `CENTRAL_TOKEN` definida: `python ferramentas/copiar_central_para_servidor.py --servidor http://IP:8770` copia e confere.
3. `--conferir` só compara; `--abas A,B` limita; `--refazer` é a única forma de copiar para um servidor que já tem abas.
4. Abas "vivas" podem divergir por gravações dos PCs entre a cópia e a conferência: repita só elas com `--abas ... --refazer` (só antes de os PCs usarem o servidor).

## Virada (etapa 5): o roteiro
**O que muda de lugar:** todo PC ligado passa a ler e gravar as abas internas no servidor. **O que nunca muda de lugar:** o canal `Comandos_PC` (fica no Google: é por ele que se liga, desliga e atualiza, mesmo com o servidor fora do ar), os formulários dos hotéis, o `Cadastro_Hoteis` e as outras planilhas.

**Antes (nada disto mexe nos PCs):**
1. Reservar um **IP fixo** para o Servidor RA no roteador (hoje 10.145.150.247; o endereço do servidor vai nos comandos).
2. No Servidor RA, rodar `Automacoes\agendar_servidor_central.ps1` (cria a tarefa `ServidorCentral` e libera a porta 8770 só para a rede local; pede administrador uma vez). Isso funciona **hoje, sem Docker**; o Docker pode vir depois com o mesmo código. Conferir: `http://IP:8770/v1/saude`.
3. Primeira cópia (ensaio): `python ferramentas/copiar_central_para_servidor.py --servidor http://IP:8770`. Pode repetir à vontade com `--refazer` enquanto nenhum PC usa o servidor.
4. Combinar um **horário calmo** (fora do expediente, sem envio em andamento).

**Na hora (uns 10 minutos):**
1. Pausar o robô no Painel e esperar os envios em andamento acabarem.
2. Cópia final: `copiar_central_para_servidor.py --servidor http://IP:8770 --refazer`. As abas que os PCs reescrevem o tempo todo (correio, lista de PCs, caixa de pedidos) podem diferir por poucas linhas: repita só elas com `--abas`.
3. Ligar todos: `python ferramentas/virada_servidor_central.py --ligar http://IP:8770 --para TODOS --confirmo`. Cada PC confere o servidor, grava a escolha e reinicia sozinho; quem não conseguir responde o motivo (`--ver` mostra as respostas).
4. Conferir **quem está onde**: `python ferramentas/virada_servidor_central.py --onde http://IP:8770`. Tem que mostrar todos os PCs em `servidor`. Se aparecer `google` e `servidor` ao mesmo tempo, o aviso `ATENCAO` diz: reenvie o comando ao que ficou para trás (o comando vale 60 minutos; um PC desligado que ligar depois disso perde e fica isolado) ou volte todos.
5. Teste de verdade: um e-mail de teste de um PC para uma caixa de outro PC; olhar `/v1/saude` (`esperando` = PCs ligados).
6. Religar o robô.

**Voltar (a qualquer momento):**
1. `python ferramentas/virada_servidor_central.py --desligar --para TODOS --confirmo` (pelo canal do Google; funciona com o servidor fora do ar).
2. Conferir com `--onde` que todos estão em `google`.
3. Só depois, para trazer de volta o que foi gravado no servidor: `copiar_central_para_servidor.py --servidor http://IP:8770 --para-google --confirmo-escrever-no-google` (reescreve as abas internas do Google em pedaços e confere). Sem este passo, o Google fica com os dados de antes da virada.

**Cuidados:**
- Só o admin (João, no PC dele) manda ligar/desligar. O PC só liga se o servidor responde e já tem a Central copiada.
- O token não é senha para guardar: sai da chave do Google de cada PC (e do servidor).
- O banco do servidor tem dados de hóspedes: fica em `C:\ServidorCentral` (fora do projeto e do git). Cópia de segurança diária (sem Docker): tarefa `ServidorCentral_Backup`, criada por `Automacoes\agendar_backup_servidor_central.ps1` (sem administrador), roda `ferramentas\backup_servidor_central.py` todo dia às 03:00 (ou ao ligar, se o PC estava desligado): copia para `C:\ServidorCentral\copias\central-AAAA-MM-DD.sqlite` com o servidor ligado, abre a cópia e confere (integridade, abas, linhas), guarda 14 dias e anota só contagens em `copias\backup.log`. **Limite:** as cópias ficam no mesmo disco do banco; protegem de apagão do banco e de erro de gravação, não de o disco do notebook morrer. Para voltar a partir de uma cópia: pare a tarefa `ServidorCentral`, troque `central.sqlite` pela cópia e religue. Com Docker, o equivalente é `python -m servidor_central.backup`.
- Servidor fora do ar com os PCs ligados nele: o Painel mostra erro e tenta de novo; envios param até voltar. Por isso o primeiro passo da volta é o `--desligar`.

## Para colocar no ar no Servidor RA com Docker (opcional, depois)
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
