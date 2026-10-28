---
tipo: plano
pasta: "5 Em andamento"
pai: "[[00 Início]]"
atualizado: 2026-10-28
tags: [cerebro/andamento, plano]
---
# Plano até dezembro de 2026

> Proposta do Claude (28/10/2026), vinda da **Auditoria do Painel** (nota 6,8 de 10) e da revisão de segurança e LGPD. O João muda a ordem e aprova cada fase: nada daqui começa sem o OK dele ([[Hierarquia de prioridades]]). Páginas: [[Designs]] ("Auditoria do Painel").
> **Regra do plano:** uma fase de cada vez, cada entrega medida antes e depois, em lotes, fora do horário de pico ([[ADR-01 PCs só atualizam com versão etiquetada]]).

## Onde estamos
Dados chegam certos e rápidos, a entrega é cuidadosa (625 testes, atualização só por etiqueta). O que falta é a **estrutura**: segurança entre os PCs, dados guardados por tempo demais, login, banco de dados e o código concentrado em dois arquivos.

## Fase 1 — Fundação (começa assim que o João der o OK)
| # | O quê | Por quê | Risco |
|---|---|---|---|
| 1 | **Código único em cada pedido entre PCs** e validade de 30 s (hoje 120 s, repetível) | Fecha o achado mais grave da revisão | Baixo |
| 2 | Teto de tamanho e tempo-limite na rede entre PCs | Qualquer máquina da rede pode sobrecarregar o Painel | Baixo |
| 3 | Enxugar `nf_achadas.json` (guardar só documento, valores, datas, serviços) | Tem texto inteiro de nota com CPF/CNPJ | Baixo |
| 4 | Registrar no log a duração de cada volta de atualização | Achar a causa das voltas de ~100 s ([[2026-10-28 Painel lento por reinícios depois das entregas]]) | Baixo |
| 5 | Trocar `pickle` por JSON no cache do Painel; fixar o GitHub Actions por código e ligar o Dependabot | Segurança de baixo custo | Baixo |

## Fase 2 — Segurança de verdade
- Segredo próprio da rede entre PCs (separado da chave do Google), um por PC, com troca simples.
- **Cifrar o conteúdo entre os PCs** (texto de e-mail e CPF hoje passam abertos na rede).
- Token do Painel só para a janela (antes: **verificar se os 4 PCs têm mais de um usuário do Windows**).

## Fase 3 — Login, perfis e continuidade
- Entrar com usuário do Windows ou PIN; perfis **gerente** (vê tudo, relatórios) e **operador** (as caixas dele); registro de quem **viu** os dados.
- **PC reserva:** um segundo PC assume se o principal ficar 15 min sem sinal.

## Fase 4 — Banco de dados (Supabase)
A Planilha Central usa quase toda a cota do Google. Caminho: Supabase (Postgres), com acesso por perfil no próprio banco e backup, migrando aos poucos com a planilha funcionando junto.
**Depende do João:** criar a conta (região São Paulo, e-mail da empresa) e escolher o caminho A ou B para os formulários. O conector do Supabase já está instalado, mas ainda não autorizado.

## Fase 5 — Módulos financeiros e relatórios
Contas a pagar, faturamento, caixa, cancelamentos e substituições; relatórios que se exportam em PDF e Excel; relatório automático da semana. (Pedido de 20/10/2026: usuários gerente e operador.)

## Em paralelo (organização)
- Separar `app_servidor.py` (2.480 linhas) e `index.html` (3.483) em módulos por assunto, sem mudar nada visível.
- Testes de tela rodando no GitHub (hoje conferimos à mão em todo lançamento).
- Esta nota e a Auditoria atualizadas a cada fase.

## O que depende de gente de fora ou de decisão
| Item | Quem |
|---|---|
| Confirmar **BitLocker** ligado nos 4 PCs | TI |
| Regras do **Firewall** nos 4 PCs (a porta 8766 escuta em todas as placas) | TI |
| Olhar as 3 contas de e-mail recusadas pelo servidor | Quem administra o e-mail da rede |
| Prazo de guarda por tipo de dado e responsável pela LGPD | João (e o jurídico) |
| Conta do Supabase e caminho A ou B | João |
| Proteção de branch, verificação em duas etapas e varredura de segredos no GitHub | João (só o dono vê) |
| Mascarar CPF na tela | João (estacionado) |

Outras ideias soltas: [[Ideias e pendências]].
