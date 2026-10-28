# Painel Fiscal — produto

> **Fonte da verdade: o Segundo Cérebro** (`Segundo Cérebro (Agente Smith)/`, cofre do Obsidian). Antes de qualquer trabalho de design ou código,
> leia `Segundo Cérebro (Agente Smith)/0 Comece aqui/00 Início.md` e siga a ordem de leitura de lá
> (Hierarquia de prioridades → O que não mexer → Credenciais → Onde mexer). Este arquivo só resume.

## O que é
Painel interno do setor fiscal da Rede Andrade (cerca de 73 hotéis). Quatro agentes (João, Clara, Cristian, Bernardo)
atendem pedidos de nota fiscal de hóspedes e empresas, que chegam pelo formulário de cada hotel e por e-mail.

## O problema que ele resolve
O hóspede liga e o agente que cuida dele está ocupado em outra ligação. O e-mail da empresa é POP/SMTP: cada mensagem
fica só no PC de quem cuida do hotel, sem nuvem. O Painel é um **espelho** do Outlook dos 4 PCs e das planilhas:
qualquer agente vê, do próprio PC, com quem está o pedido, em que situação e qual o próximo passo, sem interromper ninguém.

## Quem usa e como
- Os 4 agentes, o dia todo, muitas vezes **com o telefone no ouvido**: precisa ser rápido e fácil de ler.
- Pessoas que não são de TI. Português simples, sem jargão.
- Gerência: relatório do mês (números do Mail Analytics, só leitura).
- Futuro: outros setores (faturamento, contas a pagar, controladoria, comercial, reservas).

## Modo de uso (Impeccable)
**Operate**: é ferramenta de trabalho. Ler rápido e agir vence enfeite.

## Regras que nunca se quebram (resumo; o cofre manda)
- **P0:** nenhum dado de hóspede (nome, CPF/CNPJ, e-mail) ou credencial fora de onde já está. Prévias e ferramentas externas
  (Figma, 21st, páginas publicadas) **só com dados fictícios**. O Claude nunca envia e-mail a hóspede por conta própria.
- **P1:** Mail Analytics, planilhas dos hotéis, Dropbox e Outlook real: só leitura.
- **P2:** o Painel nunca inventa número; todo percentual diz contra o quê.
- Design: `DESIGN.md` e `Segundo Cérebro (Agente Smith)/1 Regras/Padrão de design.md`.
