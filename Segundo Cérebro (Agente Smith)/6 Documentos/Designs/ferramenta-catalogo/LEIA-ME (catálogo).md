---
tipo: guia
pasta: "6 Documentos"
pai: "[[Designs]]"
tags: [cerebro/documentos, cerebro/design]
---
# Como refazer o Catálogo de peças

O [[Catalogo de pecas do Painel.html|Catálogo de peças]] é montado a partir do **próprio Painel**: a ferramenta abre o
Painel no **modo demonstração** (dados inventados), passa por cada tela e copia o HTML de cada peça; depois junta com o
CSS de verdade do Painel (`app_ui/index.html` e `app_ui/pecas/`). Quando o Painel mudar, é só refazer.

**Nunca** rode contra o Painel de verdade. A ferramenta confere e para sozinha se o Painel aberto não for o modo
demonstração.

## Passo a passo (no PC de casa, ou num PC com o Painel fechado)

1. Abra o modo demonstração: `PAINEL_DEMO_EM_CASA.bat` (fica na porta 8765).
2. Num terminal, nesta pasta (`Segundo Cérebro/6 Documentos/Designs/ferramenta-catalogo`):
   ```
   node copiar_pecas.js "%TEMP%\catalogo"
   python gerar_catalogo.py "C:\Users\<usuário>\Desktop\NOTAS\Solicitacoes NF" "%TEMP%\catalogo"
   ```
   O primeiro leva uns 3 minutos e mostra `ok` para cada peça (e `FALTOU` se alguma peça mudou de nome).
   O segundo grava `Catalogo de pecas do Painel.html` na pasta `Designs`, por cima do antigo.
3. Abra a página no navegador e confira. Peça nova no Painel? Acrescente um `pegar(...)` em `copiar_pecas.js` e o
   texto dela no dicionário `T` de `gerar_catalogo.py`.

Precisa do Node (vem com o Claude Code) e do Python (o mesmo do robô). Não usa internet, Google nem Outlook.

## O que cada arquivo faz

| Arquivo | O que faz |
|---|---|
| `copiar_pecas.js` | Abre o Edge escondido no modo demonstração e copia cada peça (com os pais, para o CSS valer igual) para `catalogo_pecas.json` |
| `gerar_catalogo.py` | Lê o CSS do Painel, deixa no tema escuro, troca e-mails/telefones/CPF/CNPJ por exemplos e monta a página |
| `modelo_catalogo.html` | O molde da página: índice, busca, caixinhas isoladas (cada peça com o CSS real), estados dos botões e o código embaixo |
| `animacoes_fonte.html` | A página das 22 animações, que vai embutida no fim do catálogo |

Feito em 22/10/2026. Fica dentro do cofre (e não em `ferramentas/`) para não reiniciar os PCs quando muda: o atualizador
só deixa de reiniciar quando a mudança é só no cofre.

Voltar: [[Designs]]
