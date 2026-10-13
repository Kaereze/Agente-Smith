---
tipo: guia
pasta: "2 Como trabalhar"
pai: "[[00 Início]]"
tags: [cerebro/trabalho]
---
# Dia do administrador

> O que só dá para fazer com a **senha de administrador** em cada PC, para deixar tudo automático. Levantado em 13/10/2026.
> Ninguém do Claude digita a senha: a pessoa que tem a senha aprova na tela do Windows.

## 1. Firewall da rede entre os PCs (obrigatório nos 4 PCs)
**Para quê:** busca ao vivo no Outlook dos outros PCs e abrir o texto inteiro de um e-mail de outro PC (porta 8766).
**Por que não funciona hoje:**
- nenhum dos 4 PCs tem a regra da porta 8766;
- os Wi-Fi do escritório estão como **rede Pública**;
- no PC do João existe um **bloqueio do `pythonw.exe`** (o programa que roda o Painel), criado quando alguém clicou "Cancelar" no aviso do firewall. No Windows, bloqueio vence permissão.

**Levantamento de 13/10/2026 (só leitura, pelas sessões Remote Control):**

| PC | Bloqueios do pythonw (rede Pública) | Regra 8766 | Energia na tomada | Windows Update |
|---|---|---|---|---|
| João · DESKTOP-GA8IJAU | 2 | não existe | nunca suspende | — |
| Clara · DESKTOP-FA8HRTN | 2 (TCP e UDP) | não existe | nunca suspende (desktop) | sem reinício pendente |
| Cristian · DESKTOP-0EP6A0T | 2 | não existe | nunca suspende (desktop) | sem reinício pendente |
| Bernardo · DESKTOP-DF2300B | 2 | não existe | nunca suspende (desktop) | renomeação pendente: reiniciar no fim do dia |

O Painel já escuta a 8766 em todas as interfaces (conferido no PC do Bernardo); só o firewall barra. O Python fica em pastas diferentes por PC (`AppData\Local\Python\pythoncore-3.14-64` ou `AppData\Local\Programs\Python\Python314`): o script acha qualquer `python.exe`/`pythonw.exe`.

**Jeito mais fácil (13/10/2026):** em cada PC já fica aberta uma janela "Dia do administrador - aperte Enter" com o comando digitado (aberta por `Automacoes/preparar_dia_admin.ps1`, que não executa nada). Basta apertar **Enter** e digitar a senha quando o Windows pedir. Se a janela tiver sido fechada, rode de novo: `powershell -ExecutionPolicy Bypass -File .\Automacoes\preparar_dia_admin.ps1` na pasta do projeto.

**Como fazer (um comando por PC):**
1. Menu Iniciar → digite `PowerShell` → **Executar como administrador** → digite a senha.
2. Cole:
   ```
   powershell -NoProfile -ExecutionPolicy Bypass -File "$env:USERPROFILE\Desktop\NOTAS\Solicitacoes NF\Automacoes\liberar_rede.ps1"
   ```
3. Tem que aparecer: `OK: rede entre os PCs liberada (porta 8766, so a rede local) e nenhum bloqueio do Python.`

O script (`Automacoes/liberar_rede.ps1`) tira **só** os bloqueios de entrada do Python e cria a regra da porta 8766 **só para a rede local**, em qualquer perfil de rede (decisão do João). Pode rodar de novo sem problema.

## 2. Opcional (decisão do João)
- **Rede como Privada** em vez de Pública: não é preciso com a regra acima; muda a descoberta do PC na rede (decisão de segurança da TI).
- **Login automático depois de reiniciar** (Windows Update à noite): hoje o robô e o Painel só voltam quando alguém entra no Windows. Ligar o login automático deixa a senha guardada no PC (risco de segurança) — **não recomendado**. Alternativa sem administrador: deixar o Windows Update reiniciar fora do horário de trabalho e entrar no Windows ao chegar.

## 3. O que NÃO precisa de administrador (já automático)
- Tarefas do Windows (`SolicitacoesNF_*`): rodam como o próprio usuário, ao entrar no Windows.
- Atualização e reinício pelo "Atualizar todos os PCs".
- **Guardião do Outlook** (abre o Outlook com janela se fechar).
- Python e bibliotecas (instalados só para o usuário).
- Suspensão do PC na tomada: o próprio usuário ajusta (Configurações → Sistema → Energia → "Nunca" na tomada).

Ver: [[O que não mexer]] (firewall e rede são decisão do João) · [[Pessoas e PCs]].
