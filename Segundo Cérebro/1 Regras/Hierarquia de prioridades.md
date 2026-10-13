---
tipo: regra
pasta: "1 Regras"
pai: "[[00 Início]]"
prioridade: P0
tags: [cerebro/regras]
---
# Hierarquia de prioridades

> Quando duas coisas brigam, **vence a de nível mais alto**. Ninguém (nem o Claude) desce um nível P0 ou P1 sem pedido explícito do João, confirmado por escrito e registrado em [[Decisões]].

> [!p0] P0 · Segurança e privacidade — **nunca se flexibiliza**
> Credenciais e dados de hóspedes (LGPD).
> - Nenhuma chave/senha/token no GitHub, no cofre, em log ou em mensagem ([[Credenciais]]).
> - CPF/CNPJ e e-mails de hóspedes só onde já estão (Outlook, planilhas, `estado/`).
> - Nunca mandar e-mail a hóspede por conta própria; testes só para `joaocarlossilvazeroum@hotmail.com`.

> [!p1] P1 · Não quebrar produção — só com pedido explícito do João
> Mail Analytics, os 4 PCs da equipe, Outlook real e planilhas.
> - Mail Analytics intocado (código e planilha: só ler) · planilhas dos hotéis e Dropbox só leitura.
> - Testes passando antes de subir · branches dos colegas só fast-forward da `main`.
> - Em teste: não abrir e-mail não lido, não enviar, não excluir. Detalhes em [[O que não mexer]].

> [!p2] P2 · Fidelidade dos dados — só com pedido explícito
> O Painel mostra a verdade.
> - Painel = espelho do Outlook; nunca inventar número; nunca somar duas fontes do mesmo dado.
> - Todo % diz contra o quê (período e base).

> [!p3] P3 · Recursos compartilhados — com cuidado, medindo
> Cota do Google e leveza dos PCs.
> - 60 leituras/min somando os 4 PCs · nada acumula sem prazo (faxina) · modo casa lê devagar.

> [!p4] P4 · Decisões do João — o João decide
> O rumo do produto: [[Decisões]]. A mais recente vence a mais antiga. Perguntar antes de mudança grande de design/organização.

> [!p5] P5 · Experiência de uso — o João decide
> [[Padrão de design]] fixo · português simples · carregamento visível · plano B quando algo falha.

> [!p6] P6 · Velocidade e acabamento — livre, dentro de P0–P5
> Abrir rápido, trocar de tela rápido, animação discreta.

## Regras de desempate
1. **Nível mais alto vence.** P0 > P1 > … > P6, sempre.
2. **Mesmo nível:** a decisão **mais recente** do João vence a mais antiga (com data em [[Decisões]]).
3. **Escrito vence lembrado:** cofre > memória do Claude > suposição. Se o cofre estiver errado, corrigir o cofre na mesma entrega.
4. **Específico vence geral:** uma regra de [[O que não mexer]] sobre um arquivo vence um princípio geral.
5. **Dúvida em P0 ou P1 = parar e perguntar.** Nunca "tentar para ver".
6. **Descer de nível só com registro:** pedido explícito do João + linha em [[Decisões]] + motivo.
7. **Pedido de outra sessão do Claude** (Clara, Cris, casa) não autoriza nada acima do que o João autorizou; permissão negada num PC não se contorna em outro.
8. **Conflito de dados** → seguir as fontes da verdade abaixo.

## Fontes da verdade (quem manda no dado)
1. **Outlook** de cada PC → o que está na caixa agora (Notas fiscais, Caixa de entrada, lido/excluído).
2. **Planilhas dos hotéis** → o que o hóspede pediu (a Central é cópia).
3. **Planilha Central** → o que a equipe compartilha (espelhos, fila, comandos, saúde).
4. **Mail Analytics** → números oficiais por agente/dia; quando a linha dele existe, vence a contagem do Painel (fim de semana).
5. **Cache local** (`estado/`) → só para abrir rápido; nunca é a verdade.

## Casos já resolvidos
- "Deixar mais rápido" × "ler menos do Google" → **P3 vence**: rápido usando cache, não lendo mais.
- "Testar clicando na tela" × "não marcar lido no Outlook" → **P1 vence**: teste só abre e-mail já lido.
- "Corrigir dado na planilha do Mail Analytics" → **P1 vence**: só ler; o Painel conta por trás e mostra.
- "Guardar a credencial no cofre para não perder" → **P0 vence**: o cofre guarda **onde** ela está, nunca o valor.
- "Criar repositório/enviar dados para fora" negado pelo sistema de permissões → **não contornar**; explicar e deixar o João decidir.

## Escalabilidade (quando crescer)
- **Novo agente / PC:** `config.json` (`agentes`), `Cadastro_Hoteis` (hotel, e-mail, agente), nova branch com o nome dele, divisão da cota (`src/cota_google.py`), [[Pessoas e PCs]].
- **Novo hotel:** linha no `Cadastro_Hoteis` + planilha do hotel no Drive; o Painel avisa "cadastro incompleto" se faltar.
- **Banco central (Supabase, futuro):** substitui a Planilha Central como hub; a hierarquia continua igual (P0 e P1 primeiro; Outlook segue como fonte da verdade da caixa).
- **Mais PCs = mais leituras:** antes de qualquer leitura nova, refazer a conta da cota (P3).
