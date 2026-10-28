---
tipo: regra
pasta: "1 Regras"
pai: "[[00 Início]]"
prioridade: P1
tags: [cerebro/regras]
---
# Preferências do João (resumo para qualquer PC)

> Estas regras também ficam na memória do Claude **deste** PC; aqui elas viajam pelo GitHub, para valerem em casa e em qualquer outro PC. Ver a hierarquia completa em [[Hierarquia de prioridades]].

## Como trabalhar com ele
- **Responder em português simples.**
- **Desenho primeiro, código depois.** Telas novas: página que roda ao vivo (artifact) e salva em `6 Documentos/Designs`; só mexe no Painel depois do OK. Dúvida? Pergunta, dizendo se é possível.
- **Nunca mexer em produção sem ele confirmar**, mesmo se pedir de passagem: Mail Analytics intocado, os 4 PCs, Outlook real, planilhas.
- **Paleta das telas novas = a da Auditoria** (cinzas, azul, âmbar, vermelho). **Sem verde** e sem tom verde nos fundos.

## Dados e segurança
- **Testes, documentos, diário e exemplos usam só dados inventados**: nunca CPF, CNPJ, nome ou e-mail real de hóspede. Provou algo com dado real? Só na conversa; ao salvar, troque por inventado (ex.: CPF 111.444.777-35, "MARCOS EXEMPLO").
- **Nunca** senha, token, chave do Google ou segredo do Mail Analytics no cofre ou no GitHub ([[Credenciais]]).

## E-mail e Outlook
- **O Painel nunca tira nem apaga e-mail da entrada sozinho.** Mover para "NF enviada" é sempre um clique da pessoa, com "Desfazer" de 10 s. Hóspede pode pedir outra nota depois de receber a primeira.
- A tag "NF enviada" não é prova: conferir o envio nos Itens Enviados.
- Envio sempre pela caixa do hotel, no Outlook do PC dono.

## Entrega
- Só chega aos PCs a **versão com etiqueta** (ex.: `2026.10.27.14`) ou pelo "Atualizar todos os PCs". Commit sem etiqueta fica só no GitHub.
- **Nunca mover nem apagar etiqueta já publicada, nunca forçar envio (`push --force`)**: os PCs atualizam com `fetch --tags` e `merge --ff-only` e parariam. Ver [[Como entregar]].
- Cada etapa termina com testes passando, CHANGELOG, diário do dia e o cofre atualizado.

## Ícones, não emojis (28/10/2026)
Quando o João pede **ícones**, são os ícones de linha do próprio Painel (os do menu: caixa de entrada, nota, enviar, olho…), nunca emojis. Um engano com emojis foi corrigido no mesmo dia. O padrão do Painel segue **sem emojis** ([[Padrão de design]]).
