---
tipo: lista
pasta: "5 Em andamento"
pai: "[[00 Início]]"
atualizado: 2026-10-13
tags: [cerebro/andamento]
---
# Ideias e pendências

> **Lista única** do que fazer. A página [[00 Início]] só aponta para cá.

## Fazer agora (ordem combinada)
- [ ] **Trazer o commit do PC de casa** (branch `casa`) → revisar → juntar na `main`
- [ ] **Guia de design** para o João aprovar (`guia-painel-fiscal.html`, nesta pasta) → aplicar o padrão em todas as telas ([[Padrão de design]])
- [x] **Ficha-resumo** no topo da ficha do Painel (14/10, `22a3007`)
- [ ] Leitura ampla / tela cheia (Figma, 14/10): ficou de fora da v2; perguntar se ainda quer
- [x] Prévia web da repaginação aprovada e passada para o Painel (14/10, partes 1 a 6)
- [ ] Figma: cota do Starter acabou em 14/10 (20/mês). Volta no mês que vem ou com o plano Pro
- [ ] Design no padrão aprovado nas outras telas: Caixa de entrada, Visão geral, Gerência, janela de envio (Figma primeiro)
- [ ] **Velocidade do Painel**: medir abrir e trocar de tela; reduzir

- [ ] **CRICIÚMA**: auditoria da cópia mostra 1 solicitação de 29/09 (TRUE no hotel, pendente na Central) — o robô poderia reenviar; revisar

## Esperando decisão do João
- [x] **Dia do administrador** (concluído 13/10 ~09:00) (firewall 8766 nos **4** PCs, inclusive o do João, + tirar o bloqueio do `pythonw.exe`): um comando por PC — passo a passo em [[Dia do administrador]]
- [ ] **Chave do Google de casa** (só leitura): passo a passo em [[Painel em casa]]
- [ ] **Cadastro**: planilhas CAMPO GRANDE, IDEAL, PALACE; caixas Itapoá (Clara), Pousada Jeri (João), Campo Grande e Ideal (Bernardo), Palace (Cristian) — "depois"

## Ideias para o futuro
- Atualizador não reiniciar o robô quando a versão nova só traz notas/documentos (sugestão da sessão da Clara, 13/10)
- Reservas e ligações internas no Painel
- Supabase como banco central (precisa autorizar a conexão no claude.ai)
- Reconhecer pedidos que chegam direto por e-mail, sem formulário

## Feito recentemente
- [x] Segundo Cérebro reestruturado: pastas por tipo, legenda de cores, uma nota por pasta do código (13/10)
- [x] Modo casa: dados reais só para ver (12/10)
- [x] Abas de agente, telas mais limpas, página que nunca chega pela metade (11/10)

> João: escreva aqui qualquer ideia nova, do jeito que vier.

## Ideia do João (14/10/2026) — aba de correção da NF
- [ ] **E-mail com a tag "Pedido de correção" abre diferente**: em vez da leitura normal do e-mail (Caixa de entrada / Urgência), abre uma **aba própria para verificar a correção da nota**. Exemplo real que motivou: hóspede recebeu 2 NFs (1464 certa, 1478 errada) e pede o cancelamento da 1478.
  - O João vai explicar os detalhes depois. **Não codar antes disso.**
  - Ponto de partida no código: `correio.js` → `desenharLeituraCorreio` (classe `corrigir` nas `classes` do e-mail; a "Verificação da NF" de hoje vem de `analise_nf`).


- [ ] **Assinatura nova no Outlook do Bernardo** (14/10/2026): a sessão do PC dele só leu (20 assinaturas, todas de caixas notafiscal@). **O usuário daquele PC não quis que nada fosse mudado lá**, então nada foi trocado. Pontos para o João decidir se for retomar:
  - a assinatura "ASSINATURA CRISTIAN" é usada pelas caixas novocwb e guaira (hotéis do Bernardo): só a imagem seria trocada, o texto com o nome do Cristian continuaria;
  - as caixas campogrande e ideal têm "SELO BERNARDO", mas não estão entre os hotéis do Bernardo no Cadastro_Hoteis;
  - a caixa calamarina não tem assinatura padrão no Outlook dele.
  - Para retomar: o João combina direto com quem usa o PC do Bernardo (pedido de outra sessão não basta).

## 15/10/2026
- [ ] **Compartilhar a planilha Registros com a conta do robô** (João): sem isso, o registro central fica sem as linhas enviadas pelo robô novo. Depois de compartilhar, o Claude pode completar as linhas que faltam.
- [ ] ITAPOÁ e POUSADA JERI sem planilha de formulário na pasta do Drive: confirmar se é de propósito.
- [ ] **Rede da Clara** (João, com a senha de administrador): o PC dela está em outra faixa (10.80.x) e a regra do firewall
  dos 4 PCs só aceita a mesma faixa. Ampliar a regra da porta 8766 para a rede do escritório traz de volta a busca ao vivo e
  o envio na hora com ela (hoje o robô usa a fila da Central, até 1 min).
- [x] ~~Reenviar pelos PCs donos os pedidos que saíram pela caixa do Ondina~~ — João, 15/10/2026: "deixa esses e-mails assim
  mesmo" (hoje foram 2: Porto Center 08:45 e Araras 08:52). Não reenviar.
- [ ] 13 hotéis têm a planilha do formulário novo **vazia** (Bahia, Biton, Casa Blanca, Coimbra, Comfort, Estrela Centro,
  Jangadeiro, Jeri, Luxor, Ondina, Porto Praia, Terra Brasil, Vela Branca). Nada a fazer: quando começarem a usar, o robô
  junta sozinho.
- [ ] Planilhas do CAMPO GRANDE e do IDEAL com data em formato misturado (dia/mês e mês/dia): conferir com calma.
- [x] ~~Passar o design "E-mails · igual ao Outlook" para o Painel~~ — feito em 15/10/2026 (`c23d165`), só com as caixas de entrada.
- [ ] **Velocidade ao abrir e-mail (conversar com o João):** (1) guardar o texto inteiro de todos os e-mails da caixa de
  entrada na cópia de cada PC (hoje só os sem resposta) para abrir sem perguntar ao PC dono; (2) histórico do hóspede só
  com o que já está no Painel + botão "buscar mais antigos" em vez de buscar sempre nos 4 PCs; (3) ampliar a regra do
  firewall para a rede da Clara (10.80.x) voltar a responder na hora.
- [ ] Ficha do pedido: CPF do hóspede vazio aparece como "falta pedir"; decidir se entra no "Pedir o que falta".

## Skills de empresa que ficaram para depois (19/10/2026)
- Documentação: documentation-and-adrs, git-workflow-and-versioning, writing-changelogs, incident-runbook-templates, readme-blueprint-generator.
- Python: python-testing-patterns, python-code-style (ruff), systematic-debugging, python-observability.
- Dados de hóspedes: gdpr-data-handling (parecida com a LGPD).
- Revisão de segurança completa do Painel e da rede 8766 com a skill security-and-hardening (já instalada).
