---
tipo: guia
pasta: "2 Como trabalhar"
pai: "[[00 Início]]"
prioridade: P1
atualizado: 2026-10-28
tags: [cerebro/trabalho, armadilhas]
---
# Armadilhas conhecidas (já aconteceram; não repita)

> Cada linha: o que acontece, por quê e como evitar. Receitas em [[Manual do Claude (receitas)]]. Falhas grandes em [[Incidentes]].

## Git e entrega
| Armadilha | Por quê | Como evitar |
|---|---|---|
| Commit de código na pasta do projeto reinicia o Painel do João | Essa pasta é onde ele roda; ele pede reinício sozinho | Trabalhe numa cópia (R1). Só documentação fica na pasta |
| `git add -A` leva lixo | O Obsidian muda o fim de linha de notas e cria canvas vazio ("Sem título 1") | `git status` primeiro; `git add` só dos seus arquivos |
| Pasta com arquivo alterado à mão trava a atualização automática **daquele PC** | O atualizador exige árvore limpa ("há arquivos alterados à mão") | Deixe `git status --porcelain --untracked-files=no` vazio |
| Mover etiqueta, `push --force` ou reescrever histórico | Os PCs usam `fetch --tags` e `merge --ff-only`: param de atualizar | Nunca ([[ADR-01 PCs só atualizam com versão etiquetada]]) |
| Várias versões no mesmo dia | Cada etiqueta reinicia o Painel dos 4 PCs | Entregar em lote, fora do pico |
| Esquecer a branch de um PC | As 3 branches (Bernardo, Christian, clara) precisam ficar iguais à `main` | R4, passo 6 |

## Dados e LGPD
| Armadilha | Por quê | Como evitar |
|---|---|---|
| Copiar CPF, nome ou e-mail real para teste, diário ou cofre | Já aconteceu em 27/10 ([[2026-10-27 Dado real de hóspede num commit]]) | Só dado inventado (CPF `111.444.777-35`, "MARCOS EXEMPLO"); a prova com dado real fica só na conversa |
| Salvar saída de rotas do Painel real | Tem dado de hóspede | R3: só leitura, nada salvo |
| Abrir e-mail não lido pelo Painel em teste | Marca lido no Outlook real | Só e-mails já lidos, ou o modo demonstração |

## Windows e ferramentas
| Armadilha | Por quê | Como evitar |
|---|---|---|
| Nome de arquivo com `:` ou `/` | No Windows `:` cria "fluxo alternativo" (arquivo vazio com o resto escondido) e `/` cria pasta | Nunca em título de nota; troque por espaço ou "ou" |
| Aspas e acentos em script longo no shell | O shell do Windows (bash) quebra o texto | Grave o script num arquivo (ferramenta de escrita) e rode; se o arquivo já existe, **leia antes de regravar** |
| `print` de ✓ ou acento no console | O console do Windows usa cp1252 | `PYTHONIOENCODING=utf-8` |
| Caminho com acento (`Usuário`) em OpenCV | `cv2.imread` falha | `cv2.imdecode(np.fromfile(...))` |
| `&&` no PowerShell 5.1 | Não existe | Use `;` ou rode no bash |
| Parar processo pelo nome `python` | Derruba o Painel real | Filtre pela linha de comando da cópia de teste |
| Navegador sem janela (headless) | O evento `focus` não dispara | Em teste, dispare `click` |
| Classe de CSS genérica (`.av`, `.ok`, `.er`) | Colide com as do Painel (o bloco "NF enviada" ficou espremido) | Prefixo próprio por peça (`cp-`, `cg-`, `bh-`); há `testes/test_css_colisao.py` |

## Outlook e e-mail
| Armadilha | Por quê | Como evitar |
|---|---|---|
| Outlook "escondido" (`-Embedding`) | O robô por COM abre um Outlook sem janela que não envia nem recebe | `outlook_vivo.garantir()` antes de usar o COM |
| EntryID muda depois de mover o e-mail | O Outlook gera outro id | Não guarde o id para depois do `Move` |
| Janela "Email da Internet" pedindo senha com a senha certa | Servidor recusou (`-ERR [SYS/TEMP]`): [[2026-10-27 Três caixas recusadas pelo servidor de e-mail]] | Esperar, não apertar F9 em série, chamar quem cuida do e-mail |
| Tag "NF enviada" como prova | Às vezes está errada | Conferir em Itens Enviados; resposta do hóspede com a nota anexada não conta |
| Passar de 3 s numa ação | Abre a tela de carregamento e **trava a tela** | Normal; destrava ao terminar (90 s de segurança) |

## Bloqueio automático do Claude Code
Ele barra comandos que apagam ou restauram arquivos, forçam envio ou usam dado marcado como sensível. **Não contorne.** Explique o que queria fazer e por quê, e deixe o João decidir (como no caso do `git restore` de 28/10).
