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
