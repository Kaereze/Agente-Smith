---
tipo: guia
pasta: "0 Comece aqui"
pai: "[[00 Início]]"
prioridade: P1
tags: [cerebro/inicio]
---
# Como usar este cérebro

## Para o João
- Abra o Obsidian → **Abrir pasta como cofre** → `Desktop\NOTAS\Solicitacoes NF\Segundo Cérebro (Agente Smith)` (fica dentro do projeto, no GitHub).
- Comece por [[00 Início]]. Os nomes entre colchetes são links: clique para abrir.
- Pode escrever à vontade: ideias novas em [[Ideias e pendências]], decisões em [[Decisões]]. O Claude lê tudo.
- O **gráfico** (ícone de rede na lateral do Obsidian) mostra como as notas se ligam.

## Para o Claude (regras de manutenção)
1. **Começo de conversa:** `git pull`; ler [[00 Início]] → [[Hierarquia de prioridades]] → [[O que não mexer]] → [[Onde mexer]]. Só abrir o código no arquivo que [[Onde mexer]] apontar; se ele estiver errado ou incompleto, **corrigir a nota** na mesma entrega.
2. **Fim de cada etapa** (depois do commit e do "Atualizar todos os PCs"):
   - acrescentar no diário do dia (`4 Histórico/Diário/AAAA-MM-DD.md`): o que foi feito, versão (commit) e o que ficou pendente;
   - atualizar "Onde paramos" e "Próximos passos" em [[00 Início]];
   - decisão nova do João → [[Decisões]] (data + o que + por quê);
   - erro resolvido → [[Problemas resolvidos]] (sintoma, causa, correção);
   - regra nova → [[O que não mexer]].
3. Escrever em português simples, curto, sem jargão. Datas sempre absolutas (12/10/2026, nunca "ontem").
4. **Nunca** guardar aqui senhas, tokens, a chave do Google ou o segredo do Mail Analytics. O cofre vai para o GitHub: só o **mapa** de [[Credenciais]] (o que é e onde fica).
5. Conversa que **muda o rumo** do projeto → [[Marcos do projeto]] (data, frase do João, o que mudou).
6. Arquivo ou função nova/renomeada → atualizar [[Onde mexer]] e [[Pastas e arquivos]].
7. Não apagar o que o João escreveu; se algo mudou, marcar como ~~antigo~~ e escrever o novo embaixo.

## Acréscimo de 28/10/2026 (para a sessão chegar "fria" e já saber o que fazer)
8. **Receitas:** para entregar, testar, desenhar ou diagnosticar, siga o [[Manual do Claude (receitas)]]; antes de qualquer comando novo, leia [[Armadilhas conhecidas]].
9. **A lista de fim de etapa é a R6 do manual.** "Onde paramos" em [[00 Início]] **sempre** com a data de hoje (ficou 5 dias parada antes de 28/10).
10. **O que o Claude aprender vai para o cofre, não só para a memória dele** (a memória fica num PC só): preferência do João → [[Preferências do João]]; decisão → nota em `Decisões (uma por nota)`; falha → [[Incidentes]]; truque ou erro de ferramenta → [[Armadilhas conhecidas]].
11. Ao criar uma nota: **sem `:` `/` `"` `?` `*` no nome do arquivo** (o Windows trata de forma diferente).
