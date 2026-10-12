# O que é o projeto

**Quem:** setor financeiro/fiscal da Rede Andrade (~73 hotéis). Equipe de 4 agentes: João, Clara, Cristian e Bernardo. Ver [[Pessoas e PCs]].

**Problema:** hóspedes e empresas pedem nota fiscal da estadia por um formulário (uma planilha por hotel) e por e-mail. Os pedidos se perdiam entre planilhas, e-mails e várias trocas de mensagem com o hóspede. O antigo Apps Script estourava a cota do Gmail.

**O que construímos (desde 23/09/2026):**
1. **Robô Solicitações NF**: copia os pedidos das planilhas dos hotéis para a Planilha Central e manda cada pedido por e-mail (pelo Outlook) para a caixa do hotel, onde o agente trata. Confere quando a NF foi emitida e enviada.
2. **Painel Fiscal** (aplicativo no PC de cada agente): um **espelho do Outlook** dos 4 PCs, com as solicitações, os e-mails dos hóspedes, a urgência, o envio de NF, o relatório da gerência e a saúde do sistema.

**Visão de futuro do João:** apresentar o Painel para uma empresa grande; depois reservas, ligações internas e um banco central (Supabase) como hub.

**Onde fica:**
- Código: `Desktop\NOTAS\Solicitacoes NF` · GitHub `Kaereze/Notas-Fiscais` (branches `main`, `Bernardo`, `Christian`, `clara`).
- Mail Analytics (outro sistema, em produção): `Desktop\Mail Analitycs`: **não mexer** (ver [[Regras fixas]]).

Ver também: [[Como funciona]] · [[Decisões]].
