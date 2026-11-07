# NFS-e Nacional: primeiro teste (produção restrita)

> Pacote novo de 07/11/2026. Fica **fora** do que o Painel roda hoje: nada aqui é importado por `src/` e a pasta só chega aos outros PCs quando a branch for juntada e etiquetada, com o OK do João.

## O que é

Um programa de linha de comando para provar, **no ambiente de teste do governo** (produção restrita), que:

1. o certificado A1 do hotel serve (vale, tem o CNPJ certo e a finalidade "Autenticação do Cliente");
2. o PC consegue conversar com o governo (conexão com certificado dos dois lados);
3. a assinatura do XML está certa e o governo aceita o algoritmo (SHA-256 ou SHA-1: pendência P-19);
4. uma nota de teste é criada, consultada e cancelada.

**Nada disso vale como nota de verdade.** Hotel piloto: Boa Viagem (Recife, código IBGE 2611606).

## Regras de segurança (não mude)

- **Senha do certificado nunca vai em chat, arquivo, commit nem linha de comando.** O programa lê a variável `NFSE_CERT_SENHA` ou pergunta no terminal (a senha não aparece enquanto você digita).
- **Certificado (`.pfx`/`.p12`) nunca entra no repositório.** O `.gitignore`, o teste `test_segredos.py` e o gancho de commit barram esses arquivos.
- **Só produção restrita.** `nfse/trava.py` recusa qualquer endereço que não seja `sefin.producaorestrita.nfse.gov.br` ou `adn.producaorestrita.nfse.gov.br`, recusa XML com `tpAmb` diferente de 2 e para se o governo responder que o ambiente é outro. Não existe opção para desligar a trava.
- **Emitir e cancelar exigem você digitar a frase de confirmação** (`EMITIR TESTE` / `CANCELAR TESTE`).
- **Envio (POST) nunca é repetido sozinho.** Se a rede cair no meio, o programa manda você **consultar** antes de qualquer outra coisa.
- **Dados de teste são inventados** (ADR-05). Tomador de teste: `MARCOS EXEMPLO`, CPF `111.444.777-35`.

## Antes de começar (uma vez, no PC da empresa)

```
cd C:\Users\Usuário\Desktop\NFS-EaUTOMATIC\painel-fiscal-nfse
git pull
python -m pip install -r requirements.txt
python -m pip install -r nfse\requirements-nfse.txt
python -m pytest testes -q
```

Guarde o `.pfx` **fora da pasta do repositório** (por exemplo `C:\NFSE_TESTE\BOA_VIAGEM.pfx`).

Para não digitar a senha toda vez, no PowerShell da sessão: `$env:NFSE_CERT_SENHA = Read-Host -MaskInput "Senha"` (some quando você fecha a janela; não grave em arquivo).

## Roteiro (nesta ordem; pare no primeiro erro)

| # | Comando | Mexe na internet? | O que prova |
|---|---|---|---|
| 1 | `python -m nfse.primeiro_teste certificado --pfx C:\NFSE_TESTE\BOA_VIAGEM.pfx --cnpj-hotel <CNPJ do Boa Viagem>` | Não | Validade, CNPJ do certificado igual ao do hotel, "Autenticação do Cliente", tamanho da chave |
| 2 | `python -m nfse.primeiro_teste assinatura --pfx ...` | Não | A conta de assinar (SHA-256 e SHA-1) fecha neste PC; gera `saida_nfse_teste\dps_exemplo_*.xml` |
| 3 | `python -m nfse.primeiro_teste conexao --pfx ...` | Sim, **só leitura** | Duas consultas: convênio do município no ADN e uma DPS que não existe no Sefin. **404 no Sefin = deu certo** (conexão e certificado aceitos) |
| 4 | `python -m nfse.primeiro_teste emitir --pfx ... --dados nfse\dados_teste.json --xsd <XSD do DPS> --algoritmo sha256` | Sim, **grava no teste** | Nota de teste criada, chave de acesso de 50 dígitos, qual algoritmo o governo aceita |
| 5 | `python -m nfse.primeiro_teste consultar --pfx ... --chave <50 dígitos>` (ou `--dps-id`) | Sim, leitura | A nota aparece pelo Id e pela chave |
| 6 | `python -m nfse.primeiro_teste cancelar --pfx ... --chave ... --motivo "..." --xsd <XSD do evento>` | Sim, **grava no teste** | Evento 101101 aceito |

Antes do passo 4:
- copie `nfse\exemplo_dados_teste.json` para `nfse\dados_teste.json` (esse nome fica fora do GitHub), troque `prestador_cnpj` pelo CNPJ do Boa Viagem e mude `n_dps` a cada tentativa (o governo não aceita o mesmo Id duas vezes);
- baixe os **XSD oficiais** (DPS e pedido de evento) no portal do Emissor Nacional e guarde **fora** do repositório ou em `referencias/oficiais/` depois de conferir a licença. **Sem XSD o programa não emite** (regra RN-80: validar antes de assinar). Os nomes de tags do `nfse/dps.py` são rascunho (P-34); se o XSD recusar, o XSD manda.

Se o passo 4 falar de assinatura, rode de novo com `--algoritmo sha1` e **anote qual funcionou**: isso fecha a P-19.

## Tabela de erros

| Sinal | Quer dizer | O que fazer |
|---|---|---|
| Falha antes de qualquer HTTP (handshake/SSL) | O governo nem chegou a ver o pedido | Certificado sem "Autenticação do Cliente", cadeia ICP-Brasil não instalada, relógio do PC errado, proxy/antivírus da empresa mexendo no HTTPS |
| HTTP 403 | Certificado recusado | Vencido/revogado, CNPJ sem cadastro no Emissor Nacional, ou cadeia incompleta |
| HTTP 400 + lista `erros` | Dado ou XML recusado | Ler `codigo` e `descricao`; corrigir o **dado**; não repetir às cegas |
| HTTP 404 em consulta | Não existe | Resposta normal (ainda não foi emitido) |
| HTTP 500 | Erro do governo | **Não reenviar.** Consultar pelo Id da DPS |
| `AmbienteProibido` | A trava barrou | Não é defeito: algo tentou sair da produção restrita |
| Erros `E2210` a `E2214` (ADN) | Certificado inválido, revogado, cadeia, expirado, falha de LCR | Ver certificado e rede |
| `RECUSADO: CNPJ do certificado diferente` | Hotel errado | Usar o certificado do hotel que consta no DPS |

## Mapa dos arquivos

| Arquivo | Para quê |
|---|---|
| `trava.py` | Só produção restrita (endereço, `tpAmb`, resposta) |
| `certificado.py` | Abrir `.pfx`, CNPJ, validade, finalidade |
| `assinatura.py` | XMLDSIG enveloped, SHA-256/SHA-1, conferência |
| `dps.py` | Montar DPS e pedido de cancelamento (rascunho) e validar contra XSD |
| `cliente.py` | HTTP com certificado, repetição só em consulta, sem redirecionamento |
| `validacao.py` | CPF, CNPJ (inclui alfanumérico), dinheiro, datas, Id da DPS |
| `primeiro_teste.py` | O roteiro acima |
| `exemplo_dados_teste.json` | Dados inventados para o passo 4 |

## O que ainda não está fechado

- **P-19** algoritmo de assinatura aceito (SHA-256 ou SHA-1): fecha no passo 4.
- **P-34** leiaute do DPS e do evento: rascunho até o XSD oficial entrar no projeto.
- **P-21** código do motivo de cancelamento.
- Consumo e estacionamento dentro da nota (P-01/P-22/P-24/P-26): o programa **não decide**; a descrição vem pronta e é conferida por gente.
- Parâmetros municipais: o passo 3 consulta o convênio de Recife; o endereço `/parametrizacao/...` ainda não foi visto funcionando (o Swagger do ADN não traz o `host`).
