# Hierarquia de prioridades

> Quando duas coisas brigam, **vence a de nível mais alto**. Ninguém (nem o Claude) desce um nível P0 ou P1 sem pedido explícito do João, confirmado por escrito e registrado em [[Decisões]].

| Nível | O que protege | Exemplos do que vale | Pode flexibilizar? |
|---|---|---|---|
| **P0 · Segurança e privacidade** | Credenciais e dados de hóspedes (LGPD) | Nenhuma chave/senha no GitHub, no cofre ou na conversa · CPF/CNPJ só onde já está · nunca mandar e-mail a hóspede por conta própria | **Nunca** |
| **P1 · Não quebrar produção** | Mail Analytics, os 4 PCs da equipe, Outlook e planilhas | Mail Analytics intocado · planilhas dos hotéis e Dropbox só leitura · testes antes de subir · branches iguais à main · não abrir e-mail não lido em teste | Só com pedido explícito do João |
| **P2 · Fidelidade dos dados** | Que o Painel mostre a verdade | Painel = espelho do Outlook · nunca inventar número · nunca somar duas fontes do mesmo dado · todo % diz contra o quê | Só com pedido explícito |
| **P3 · Recursos compartilhados** | Cota do Google e leveza dos PCs | 60 leituras/min somando os 4 PCs · nada acumula sem prazo (faxina) · modo casa lê devagar | Com cuidado, medindo |
| **P4 · Decisões do João** | O rumo do produto | O que está em [[Decisões]]; a mais recente vence a mais antiga · perguntar antes de mudança grande de design/organização | O João decide |
| **P5 · Experiência de uso** | Clareza para a equipe e para quem não é de TI | [[Padrão de design]] fixo · português simples · carregamento visível · plano B quando falha | O João decide |
| **P6 · Velocidade e acabamento** | Rapidez e polimento | Abrir rápido, trocar de tela rápido, animação discreta | Livre, dentro de P0–P5 |

## Fontes da verdade (quem manda no dado)
1. **Outlook** de cada PC → o que está na caixa agora (Notas fiscais, Caixa de entrada, lido/excluído).
2. **Planilhas dos hotéis** → o que o hóspede pediu (a Central é cópia).
3. **Planilha Central** → o que a equipe compartilha (espelhos, fila, comandos, saúde).
4. **Mail Analytics** → números oficiais por agente/dia. Quando a linha dele existe, ele vence a contagem do Painel (fim de semana).
5. **Cache local** (`estado/`) → só para abrir rápido; nunca é a verdade.

## Casos de conflito (já resolvidos)
- "Deixar mais rápido" × "ler menos do Google" → **P3 vence**: rápido usando cache, não lendo mais.
- "Testar clicando na tela" × "não marcar lido no Outlook" → **P1 vence**: teste só abre e-mail já lido.
- "Corrigir dado na planilha do Mail Analytics" → **P1 vence**: só ler; o Painel conta por trás e mostra.
- "Guardar a credencial no cofre para não perder" → **P0 vence**: o cofre guarda **onde** ela está ([[Credenciais]]), nunca o valor.

## Escalabilidade (quando crescer)
- **Novo agente / PC:** `config.json` (`agentes`), `Cadastro_Hoteis` (hotel, e-mail, agente), nova branch com o nome dele, regra de divisão da cota (`src/cota_google.py`), [[Pessoas e PCs]].
- **Novo hotel:** linha no `Cadastro_Hoteis` + planilha do hotel na pasta do Drive; o Painel avisa "cadastro incompleto" se faltar.
- **Banco central (Supabase, futuro):** substitui a Planilha Central como hub, mas a hierarquia continua igual: P0 e P1 primeiro, e o Outlook segue como fonte da verdade da caixa.
- **Mais PCs = mais leituras:** antes de qualquer leitura nova, refazer a conta da cota (P3).
