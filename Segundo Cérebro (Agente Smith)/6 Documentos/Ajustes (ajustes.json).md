---
tipo: guia
pasta: "6 Documentos"
pai: "[[00 Início]]"
prioridade: P1
tags: [cerebro/documentos, ajustes]
---
# Ajustes (ajustes.json): mudar tempos, limites, assinaturas e textos sem mexer no código

Pedido do João em 04/11/2026: poder trocar um valor **achando a chave num arquivo**, sem pedir alteração de código (e sem gastar o trabalho do Claude). Decisão registrada em [[ADR-12 Ajustes do Painel num ajustes.json so do PC do administrador]].

## Em 30 segundos
1. Dê dois cliques em **`Bat\ajustes.bat`**. Ele cria o `ajustes.json` na primeira vez e abre no Bloco de Notas.
2. Ache a linha (Ctrl+F), mude só o **número** ou o **texto** depois dos dois pontos e salve.
3. Feche o Bloco de Notas. O `.bat` confere o que você digitou e diz se algo está errado.
4. Para valer: menu do operador → **Fechar o Painel** e abra de novo.

## Regras do arquivo
- **Número vai sem aspas** (`"limite_segundos": 12`). **Texto vai entre aspas.** Decimal usa **ponto**, não vírgula (`4.5`).
- As linhas que começam com `_ajuda` são explicação; o Painel as ignora. Pode apagar ou deixar.
- Cada número tem **mínimo e máximo** (está escrito na explicação). Fora disso, o Painel **não aceita**: usa o valor de fábrica e mostra um **aviso na faixa de saúde** dizendo qual chave está errada.
- Chave com erro de digitação também vira aviso (não é ignorada em silêncio).
- Não precisa manter todas as chaves: o que faltar usa o valor de fábrica. O `ajustes.exemplo.json` (no GitHub) mostra todas, com o valor de fábrica.
- `Bat\ajustes.bat` nunca troca um valor seu. Quando uma versão nova trouxer chaves novas, ele só **acrescenta** as que faltam.

## Onde fica e por que não sobe
O `ajustes.json` fica **só no PC do administrador** (pasta do projeto, ao lado do `config.json`) e está no `.gitignore`: **nunca vai ao GitHub**. Decisão do João em 04/11/2026: "deixa somente nesse PC porque ele é o administrador de tudo".

Isso tem uma consequência importante: **o ajuste vale só neste PC**. Os outros PCs (Clara, Cristian, Bernardo, Ingrid, Afonso) continuam com os valores de fábrica, a menos que alguém crie um `ajustes.json` lá também. Quem precisa de um valor diferente para **todos** fala com o Claude: ele muda o valor de fábrica e publica por versão.

## O que dá para mudar (14 grupos, 177 ajustes)
| Grupo | O que controla | Exemplos de chave |
|---|---|---|
| `tela` | animação do K, tempos da tela, atualização automática | `k_volta_segundos`, `k_standby_segundos`, `caixas_atualiza_segundos` |
| `filtro` | prioridade dos hotéis | `prioridade_alta_a_partir_de` (10), `prioridade_media_a_partir_de` (4) |
| `recarregar` | botão ⟳ (Enviar/Receber) | `limite_segundos` (10), `intervalo_minutos` (3) |
| `google` | conversa com o Google e leituras das planilhas | `tentativa_segundos`, `chamada_limite_segundos`, `reler_hoteis_segundos` |
| `atualizacao` | atualização dos PCs e do Dropbox | `verificar_github_minutos`, `validade_comando_minutos` |
| `rede` | conversa entre PCs | `pc_online_segundos`, `resposta_maxima_segundos` |
| `envio` | envio de e-mails e NFs | `fila_espera_horas`, `anexo_maximo_mb`, `assunto_maximo_caracteres` |
| `email` | leitura das caixas, espelho, prazos, cores do e-mail | `urgencia_dias`, `lido_confirma_minutos`, `prazo_horas`, `cor_primaria` |
| `outlook` | vigia e conferência de cada PC | `vivo_intervalo_segundos`, `espera_abrir_segundos` |
| `notas` | NFs achadas nas pastas, leitura de PDF | `janela_dias`, `olhar_pastas_segundos` |
| `saude` | quando o Painel avisa que algo está parado | `saida_travada_minutos`, `sem_email_horas`, `copia_atrasada_minutos` |
| `limpeza` | quanto tempo o Painel guarda cada coisa | `registros_dias`, `resolvida_horas`, `backups_guardados` |
| `janela` | janela do aplicativo | `vigiar_segundos`, `resposta_segundos` |
| `assinaturas` | assinaturas dos operadores e mensagem padrão do e-mail | `textos`, `nomes`, `ordem`, `mensagem_padrao` |

A lista completa, com explicação de cada uma, está no próprio `ajustes.json` (e no `ajustes.exemplo.json`).

## Assinaturas e textos (os "nomes" do JSON)
- **Assinatura só de texto** (como a do Afonso): em `assinaturas.textos`, copie o bloco do Afonso e troque o código (minúsculas, sem espaço), o `nome` e as `linhas`. Para tirar alguém, ponha `null` no lugar do bloco.
- **Assinatura de imagem** continua sendo o PNG em `app_ui/assinaturas/<codigo>.png`. Aqui só se muda o **nome mostrado** (`assinaturas.nomes`) e a **ordem** na lista (`assinaturas.ordem`). A imagem em si é arquivo, não ajuste.
- **Mensagem padrão do e-mail de NF**: `assinaturas.mensagem_padrao`. Use `\n` para pular linha e termine em "Atenciosamente,".
- Vale para dicionários (assinaturas, nomes, prazos): o que você escreve **soma** ao de fábrica. Para tirar um item de fábrica, ponha `null`.

## O que NÃO é ajuste (e por quê)
Ficou de fora de propósito, porque trocar quebraria o sistema:
- Portas de rede (8765 e 8766): a tela, o firewall e os outros PCs dependem delas.
- Identificadores do Windows e do Outlook (números de pasta, códigos internos), versões de formato (`VERSAO_*`) e códigos de saída.
- Nomes das abas e colunas das planilhas: o Google e as cópias antigas dependem do nome exato.
- **Hotéis, agentes, apelidos, planilhas, e-mail de teste e modo (SIMULAÇÃO/TESTE/PRODUÇÃO)** já são chave e valor no **`config.json`** (com `_ajuda` em cada um). Esse arquivo vai ao GitHub e vale para todos os PCs. O papel de cada PC (`so_painel` etc.) fica no `config.local.json`.

Se quiser que outra coisa vire ajuste, peça ao Claude: ele acrescenta uma linha na tabela (`src/sistema/ajustes_tabela.py`), liga ao código e o teste confere o resto.

## Para o Claude (como funciona por dentro)
- `src/ajustes.py` lê e valida o arquivo uma vez por inicialização (cache). `valor("grupo.chave")` devolve o ajustado ou o de fábrica; **nunca levanta erro por valor ruim** (guarda em `erros()`, que vai para a faixa de saúde via `saude.ajustes_com_erro`).
- `src/sistema/ajustes_tabela.py` é a tabela: chave, valor de fábrica, mínimo, máximo, explicação, tipo (`decimal`, `cor`, `textos`, `selos_nomes`, `selos_textos`, `numeros`).
- Código Python: `NOME = ajustes.valor("grupo.chave")` no lugar do número fixo (as constantes continuam com o mesmo nome, então tudo que importava continua funcionando).
- Tela (JavaScript): `src/app_servidor.py` serve `/ajustes.js` (só os grupos `tela`, `filtro` e `recarregar`); as peças leem `globalThis.aj?.("chave") ?? padrão`. O teste confere que o padrão do JavaScript é igual ao da tabela.
- Chave nova: linha em `ajustes_tabela.py` → usar no código → `python Automacoes\gerar_ajustes_exemplo.py` → `testes/test_ajustes.py` falha se uma chave da tabela não for usada em lugar nenhum, se o código pedir chave que não existe ou se o exemplo estiver desatualizado.
- Cuidado: o `ajustes.json` do João **congela** os valores que ele tiver no arquivo. Se um dia o valor de fábrica mudar numa versão, quem tem aquela chave no arquivo não recebe a mudança (o `python src\ajustes.py` lista o que ele mudou em relação à fábrica).
- Nunca pôr segredo aqui: o `/ajustes.js` é servido a qualquer janela do Painel (só tempos e limites).

Voltar: [[00 Início]]
