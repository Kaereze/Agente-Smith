"""Busca ao vivo no Outlook DESTE PC (pedido do usuário, 08/10/2026): o Painel não guarda histórico; quando alguém
pesquisa um hóspede, CPF, sobrenome ou frase, cada PC procura no próprio Outlook e devolve o que achou.

Usa o mesmo índice da barra de pesquisa do Outlook (Windows Search, "ci_phrasematch"): rápido mesmo com anos de
e-mail. Sem índice (Outlook sem pesquisa instantânea), cai pro LIKE, mais lento — por isso tem limite de tempo.
Só lê: nada é marcado, movido ou apagado.
"""
import heapq
import re
import time

import espelho_emails as ee
from log_util import configurar_logging

logger = configurar_logging("busca_outlook")

PASTAS = ((6, "entrada"), (5, "enviado"), (3, "excluido"))   # Caixa de Entrada, Itens Enviados, Itens Excluídos
LIMITE_POR_PC = 50
TEMPO_MAXIMO = 10.0
CAMPOS = ("urn:schemas:httpmail:subject", "urn:schemas:httpmail:textdescription", "urn:schemas:httpmail:fromemail",
          "urn:schemas:httpmail:fromname", "urn:schemas:httpmail:displayto")
CAMPOS_CURTOS = CAMPOS[0:1] + CAMPOS[2:]   # sem o corpo: o LIKE no corpo é lento


def limpar_termo(termo):
    return re.sub(r"\s+", " ", str(termo or "")).strip()[:80]


def filtros(termo):
    """-> (com índice, sem índice). "ci_startswith" usa o índice do Outlook e acha palavra pela metade ("Pereg"
    acha "Perego") em centésimos de segundo; o LIKE (Outlook sem índice) varre e-mail por e-mail — por isso só
    no assunto e no remetente. Aspas simples dobradas: o termo nunca quebra o filtro."""
    q = termo.replace("'", "''").replace('"', "")
    indice = " OR ".join(f"\"{c}\" ci_startswith '{q}'" for c in CAMPOS)
    sem_indice = " OR ".join(f"\"{c}\" LIKE '%{q}%'" for c in CAMPOS_CURTOS)
    return f"@SQL={indice}", f"@SQL={sem_indice}"


def resumo_do_item(item, pasta, caixa, hotel, pc, corpo=None):
    corpo = str(item.Body or "") if corpo is None else corpo
    proprio = ee.dividir_historico(corpo)[0]
    if pasta == "enviado":
        de, nome, para = caixa, "", ", ".join(sorted(ee.enderecos(item)))
        quando = ee._data(item.SentOn)
    else:
        de, nome, para = ee.remetente(item), str(item.SenderName or ""), caixa
        quando = ee._data(item.ReceivedTime)
    return {"id": ee.id_do_email(item.EntryID), "entry": item.EntryID, "pasta": pasta, "caixa": caixa, "hotel": hotel,
            "de": de, "nome": nome, "para": para, "assunto": str(item.Subject or ""),
            "quando": quando.isoformat(timespec="seconds") if quando else "", "previa": ee.previa(proprio),
            "anexos": ee.anexos_do_item(item), "pc": pc}


def buscar(namespace, caixas, termo, pc, limite=LIMITE_POR_PC, tempo_maximo=TEMPO_MAXIMO, relogio=time.monotonic,
           pastas=PASTAS):
    """caixas: {caixa: hotel} (só as caixas dos hotéis). -> {"resultados": [...], "completo": bool}
    1º passo leve (só data e EntryID de cada achado, em todas as pastas); o texto só dos `limite` mais recentes.
    pastas: só estas ((5, "enviado"),) na consulta rápida do envio do hóspede (22/10/2026)."""
    termo = limpar_termo(termo)
    if len(termo) < 3:
        return {"resultados": [], "completo": True}
    com_indice, sem_indice = filtros(termo)
    inicio, candidatos, completo = relogio(), [], True
    melhores = []   # as datas dos `limite` mais recentes até aqui (heap: a mais velha no topo)
    for conta in namespace.Accounts:
        caixa = str(conta.SmtpAddress or "").strip().lower()
        if caixa not in caixas:
            continue
        for numero, pasta in pastas:
            if relogio() - inicio > tempo_maximo:
                completo = False
                break
            try:
                itens_pasta = conta.DeliveryStore.GetDefaultFolder(numero).Items
                try:
                    itens = itens_pasta.Restrict(com_indice)
                except Exception:
                    itens = itens_pasta.Restrict(sem_indice)
                itens.Sort("[ReceivedTime]", True)
            except Exception as e:
                logger.debug(f"busca em {caixa}/{pasta}: {e}")
                continue
            for item in itens:   # do mais novo pro mais velho
                try:
                    if getattr(item, "Class", 43) != 43:
                        continue
                    quando = ee._data(item.ReceivedTime)
                    quando = quando.isoformat() if quando else ""
                except Exception as e:
                    logger.debug(f"item ilegível na busca: {e}")
                    continue
                if len(melhores) >= limite and quando <= melhores[0]:
                    completo = False   # o resto desta pasta é mais velho que os `limite` já achados
                    break
                candidatos.append((quando, item, pasta, caixa))
                heapq.heappush(melhores, quando)
                if len(melhores) > limite:
                    heapq.heappop(melhores)
    candidatos.sort(key=lambda c: c[0], reverse=True)
    achados = []
    for _quando, item, pasta, caixa in candidatos[:limite]:
        try:
            achados.append(resumo_do_item(item, pasta, caixa, caixas[caixa], pc))
        except Exception as e:
            logger.debug(f"item ilegível na busca: {e}")
    return {"resultados": achados, "completo": completo and len(candidatos) <= limite}


LIMITE_ANEXO = 15 * 1024 * 1024   # anexo maior que isso: abrir no Outlook (não passa pela rede)


def tipo_do_anexo(nome):
    import mimetypes
    return mimetypes.guess_type(str(nome))[0] or "application/octet-stream"


def ler_anexo(namespace, entry, caixas, nome):
    """Bytes de 1 anexo de um e-mail das caixas dos hotéis (só lê; usuário, 14/10/2026: ver a foto/PDF que o hóspede
    mandou dentro do Painel). -> {"nome", "tipo", "tamanho", "b64"}"""
    import base64
    import os
    import tempfile
    item = namespace.GetItemFromID(entry)
    _caixa_e_pasta(namespace, item, caixas)   # PermissionError se não for caixa de hotel
    for i in range(1, item.Attachments.Count + 1):
        a = item.Attachments.Item(i)
        if str(a.FileName) != str(nome):
            continue
        if (a.Size or 0) > LIMITE_ANEXO:
            raise ValueError(f"anexo grande demais ({(a.Size or 0) / 1048576:.0f} MB): abra no Outlook")
        pasta = tempfile.mkdtemp(prefix="painel_anexo_")
        caminho = os.path.join(pasta, "anexo" + os.path.splitext(str(nome))[1][:10])
        try:
            a.SaveAsFile(caminho)
            dados = open(caminho, "rb").read()
        finally:
            try:
                os.remove(caminho)
                os.rmdir(pasta)
            except OSError:
                pass
        return {"nome": str(nome), "tipo": tipo_do_anexo(nome), "tamanho": len(dados), "b64": base64.b64encode(dados).decode()}
    raise KeyError(f"o anexo {nome} não está mais nesse e-mail")


def _caixa_e_pasta(namespace, item, caixas):
    pasta_id, loja_id = item.Parent.EntryID, item.Parent.Store.StoreID
    caixa, pasta = "", "entrada"
    for conta in namespace.Accounts:
        try:
            loja = conta.DeliveryStore
            if loja.StoreID != loja_id:
                continue
            caixa = str(conta.SmtpAddress or "").strip().lower()
            pasta = next((nome for numero, nome in PASTAS if loja.GetDefaultFolder(numero).EntryID == pasta_id), "entrada")
            break
        except Exception:
            continue
    if caixa not in caixas:   # só e-mail das caixas dos hotéis sai pela rede (nunca uma caixa pessoal)
        raise PermissionError("esse e-mail não é de uma caixa de hotel")
    return caixa, pasta


def abrir(namespace, entry, caixas, pc):
    """Texto inteiro de 1 e-mail (só lê). -> dict com texto e citado."""
    item = namespace.GetItemFromID(entry)
    pasta_id, loja_id = item.Parent.EntryID, item.Parent.Store.StoreID
    caixa, pasta = "", "entrada"
    for conta in namespace.Accounts:
        try:
            loja = conta.DeliveryStore
            if loja.StoreID != loja_id:
                continue
            caixa = str(conta.SmtpAddress or "").strip().lower()
            pasta = next((nome for numero, nome in PASTAS if loja.GetDefaultFolder(numero).EntryID == pasta_id), "entrada")
            break
        except Exception:
            continue
    if caixa not in caixas:   # só e-mail das caixas dos hotéis sai pela rede (nunca uma caixa pessoal)
        raise PermissionError("esse e-mail não é de uma caixa de hotel")
    resumo = resumo_do_item(item, pasta, caixa, caixas.get(caixa, ""), pc)
    resumo["texto"], resumo["citado"] = ee.dividir_historico(str(item.Body or ""))
    return resumo
