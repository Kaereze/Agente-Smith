---
tipo: historico
pasta: "4 Histórico"
pai: "[[00 Início]]"
tags: [cerebro/historico]
---
# Problemas resolvidos (para não repetir)

| Data | Sintoma | Causa | Correção |
|---|---|---|---|
| 11/10/2026 | Cópia dos hotéis parada desde 08/10 21:36 | Função chamada com um argumento a mais em `sincronizar.py` | Argumento removido + teste novo; 95 formulários recuperados |
| 11/10/2026 | "Atualizar todos os PCs" não reiniciava os outros PCs | PowerShell aberto de dentro da tarefa do Windows não rodava | Reinício pela tarefa "SolicitacoesNF_Reiniciar" + log + nova tentativa após 5 min |
| 11/10/2026 | Caixa da CECOMTUR nunca espelhada | O leitor do cadastro pulava a 1ª linha achando que era cabeçalho | Lê todas as linhas |
| 11/10/2026 | E-mails não lidos viraram lidos no Outlook | Cliques de teste abriram e-mails não lidos depois que o "marcar lido" entrou no ar | Revertidos; capturas nunca abrem não lidos; data de início `LIDO_OUTLOOK_DESDE` |
| 11/10/2026 | Modo Professor desligou sozinho | Script de captura clicou no botão | Religado; scripts não mexem mais nele |
| 11/10/2026 | Cartões grandes voltavam por cima das abas | Código antigo redesenhava os cartões quando chegava e-mail | Troca por `desenharAbasNotas()` |
| 11/10/2026 | Código aparecendo como texto embaixo da tela | Página lida pela metade enquanto o arquivo era regravado (atualização/edição) | Servidor só entrega a página inteira; a página recarrega sozinha se vier quebrada |
| 11/10/2026 | Hora "Enviado em" sem segundos não ligava o pedido | Comparação exigia segundos | Compara até o minuto |

| 13/10/2026 | PC do Cristian sem receber e-mail desde 09/10 (13+ solicitações não apareciam), mas o Painel dizia "Outlook aberto" | O Outlook fechou em 10/10; o robô, pelo COM, abriu um Outlook **sem janela** ("-Embedding"); contas POP3 não fazem Enviar/Receber assim. A checagem só via se o OUTLOOK.EXE existia | Outlook aberto com janela + F9 (44 e-mails baixados). Código: `outlook_vivo.py` (guardião a cada 60 s, porta única `aplicativo()`), estado "sem janela" na saúde e alarme "nenhum e-mail novo chega" |

| 13/10/2026 | Busca ao vivo entre os PCs nunca funcionou | Nenhum PC tinha a regra da porta 8766, os Wi-Fi estão como rede Pública e havia bloqueio do `pythonw.exe` (alguém clicou "Cancelar" no aviso do firewall; bloqueio vence permissão) | `liberar_rede.ps1` tira os bloqueios do Python e cria a regra só para a rede local; aplicado nos 4 PCs com a senha de administrador |
| 13/10/2026 | `git pull` do Bernardo: "Cannot fast-forward to multiple branches" | `FETCH_HEAD` com a lista de branches duplicada (provável autofetch do VS Code em paralelo) | O atualizador agora faz `fetch` + `merge --ff-only origin/<ramo>` (não depende do FETCH_HEAD); antes falhou às 08:55 de 13/10 |

| 13/10/2026 | E-mail enviado pelo Painel saía com **duas assinaturas** | O Reply()/Forward() do Outlook já vem com a assinatura padrão da caixa (marca `_MailAutoSig`); o Painel somava a dele | `envio_nf.tirar_assinatura_automatica` tira o bloco e a imagem escondida; fica só a do Painel. E-mails do Painel levam a marca invisível `PainelFiscal` (Itens enviados mostra "pelo Painel"/"pelo Outlook") |

## Cuidados aprendidos
- Scripts de alteração: escrever o arquivo `.py` pelo editor, não por heredoc (barras invertidas quebram).
- No Windows, `git` avisa LF→CRLF: é normal.
- O segredo do webapp do Mail Analytics já apareceu sem querer no terminal uma vez: **nunca** usar nem repetir.
- **14/10/2026 · Painel com menos e-mails que o Outlook (Clara 192 × 91)**: o espelho escondia respondidos, formulário e avisos. Regra nova: espelho literal (`resolver` não tira respondido; `correio.juntar` marca `respondido`/`pendente`). Para conferir: `Automacoes/diagnostico_espelho.py`.
- **14/10/2026 · Filtro de Hotel da Caixa de entrada não abria**: a lista dos filtros (`#pop`) ficava dentro da tela de Notas fiscais, que fica escondida na Caixa de entrada. Movida para fora das telas (`ee1e820`).
