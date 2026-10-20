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
| 15/10/2026 | 26 pedidos do formulário (Boa Viagem 11, São Francisco 15, de 06/10 a 15/10) **nunca enviados** | Os dois hotéis passaram a usar o formulário novo, que grava em outra planilha ("Solicitação Nota Fiscal (X) (respostas)", outras colunas). A cópia lia só a planilha mais recente pela data do Drive, e o Forms não muda essa data | `sincronizar.juntar_planilhas` junta todas as planilhas do hotel; e-mail e nome da linha pela 1ª coluna preenchida (`sheets._achar_colunas`/`_coluna_da_linha`). Os 26 saíram às 11:24 de 15/10, cada um da caixa do próprio hotel (`9621bef`) |
| 15/10/2026 | CAMPO GRANDE e IDEAL "com robô antigo ativo" até 10/12/2026 (pedido novo esperava 75 min) | Carimbo lido no formato errado (10/12 virou dezembro) | `robo_antigo.registrar_atividade` e o `mesclar` ignoram data no futuro |
| 15/10/2026 | E-mails do robô de hotéis de **outros PCs saíam pela caixa do Ondina** (Araras e Porto Center hoje; uns 25 hotéis desde setembro) | Caixa do hotel fora do Outlook do PC principal = `conta_remetente` (Ondina) | `envio_pc_dono`: o robô pede ao PC dono (rede 8766; plano B pela fila Envios_NF) e ele manda da caixa do hotel (`ff77295`, `68b0539`) |
| 15/10/2026 | O pedido pela rede **não chega no PC da Clara** | O PC dela está em outra faixa (10.80.150.107; os outros em 10.145.150.x) e a regra do firewall (`liberar_rede.ps1`) só aceita a mesma faixa (`LocalSubnet`) | Plano B pela fila da Central (`68b0539`). Para a busca ao vivo e o envio na hora voltarem com ela: ampliar a regra (precisa de administrador) |
| 20/10/2026 | 14.017 "Logging error" na saída da cópia; `saida_console_sincronizar.txt` com 30 MB | Robô, conferente e Painel escreviam no mesmo `logs/solicitacoes_nf.log`; ao girar (5 MB) o Windows não deixa renomear arquivo aberto por outro processo (`PermissionError` WinError 32) | Um arquivo por programa (`log_util.arquivo_do_programa`: robô = `solicitacoes_nf.log`, `conferente.log`, `painel.log`); a saída da cópia gira em 5 MB |

## Cuidados aprendidos
- Scripts de alteração: escrever o arquivo `.py` pelo editor, não por heredoc (barras invertidas quebram).
- No Windows, `git` avisa LF→CRLF: é normal.
- O segredo do webapp do Mail Analytics já apareceu sem querer no terminal uma vez: **nunca** usar nem repetir.
- **14/10/2026 · Painel com menos e-mails que o Outlook (Clara 192 × 91)**: o espelho escondia respondidos, formulário e avisos. Regra nova: espelho literal (`resolver` não tira respondido; `correio.juntar` marca `respondido`/`pendente`). Para conferir: `Automacoes/diagnostico_espelho.py`.
- **14/10/2026 · Filtro de Hotel da Caixa de entrada não abria**: a lista dos filtros (`#pop`) ficava dentro da tela de Notas fiscais, que fica escondida na Caixa de entrada. Movida para fora das telas (`ee1e820`).
- **15/10/2026 · Script de alteração caiu no repositório em produção** (a troca do caminho para a cópia de teste falhou e o robô roda direto desta pasta): revertido antes da volta seguinte. Regra: script de alteração recebe a pasta por parâmetro, roda primeiro na cópia (`scratchpad/copia_teste`) e só vai para o repositório logo depois de uma volta do robô, com os testes rodando em seguida.
