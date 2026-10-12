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

## Cuidados aprendidos
- Scripts de alteração: escrever o arquivo `.py` pelo editor, não por heredoc (barras invertidas quebram).
- No Windows, `git` avisa LF→CRLF: é normal.
- O segredo do webapp do Mail Analytics já apareceu sem querer no terminal uma vez: **nunca** usar nem repetir.
