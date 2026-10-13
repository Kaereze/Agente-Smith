"""Confirma NFs já emitidas para todas as solicitações da Central e publica na aba Tratamento.

Fontes:
  - Itens Enviados das contas do Outlook deste PC (cada PC confere as caixas que tem);
  - pastas de notas do Dropbox (compartilhadas entre os PCs).

As regras são as do conferente (controle_nf.Registro): "NF 123 - NOME" no assunto/arquivo e o
conteúdo da nota batendo com a solicitação. Só NF confirmada vira evento; as ilegíveis ficam de fora.

    python src\\confirmar_nfs.py                 prévia, não grava
    python src\\confirmar_nfs.py --gravar
    python src\\confirmar_nfs.py --sem-email | --sem-dropbox
    python src\\confirmar_nfs.py --desde=2026-01-01 --rever --sem-ocr     conferência do ano (rápida)

--rever confere de novo e-mails/notas já vistos (ex.: os recusados antes da regra de 05/10/2026);
--sem-ocr não lê PDF escaneado (o OCR leva segundos por nota).
"""
import datetime
import hashlib
import json
import os
import re
import socket
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_utf8 import garantir_utf8

garantir_utf8()

import app_dados as dados
from arquivos import salvar_json, so_na_nuvem
from config import PASTA_ESTADO, caminho_chave_google, carregar_config
from controle_nf import Registro, _tokens, ler_assunto_nf, provas_da_solicitacao
from log_util import configurar_logging
import outlook_vivo
from sheets import ler_hoteis

logger = configurar_logging("confirmar_nfs")

CAMINHO_VISTOS = PASTA_ESTADO / "confirmar_nfs.json"
CAMINHO_STATUS = PASTA_ESTADO / "confirmar_status.json"   # última volta (o Painel publica pros outros PCs)
RECEBIDOS_DIAS = 2
MAX_ATIVIDADES_POR_TIPO = 25   # acima disso vira uma linha de resumo (ex.: conferência do ano)
# Sobe quando a regra muda e e-mails já vistos precisam ser lidos de novo: na 1ª volta depois de atualizar,
# cada PC relê os enviados sozinho. 2 = tratativas e NF anexada em assunto fora do padrão (07/10/2026).
VERSAO_REGRAS = 4   # 3/4: registra os e-mails com NF já enviados, até pra outro endereço (envio pendente x enviada)
CAMINHO_TEXTOS = PASTA_ESTADO / "cache_textos_nf.json"
AGENTE = "Robô"
PREFIXO_NOTA_UNICA = "Hóspede aceita nota única:"
MAX_ITENS_POR_CONTA = 3000


class CacheTextos:
    """Texto já extraído de cada nota (PDF/OCR é o passo caro). Chave: EntryID ou caminho|mtime."""

    def __init__(self):
        try:
            self.dados = json.load(open(CAMINHO_TEXTOS, encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            self.dados = {}
        self.mudou = False

    def ler(self, chave, extrair):
        if chave not in self.dados:
            self.dados[chave] = extrair() or ""
            self.mudou = True
        return self.dados[chave]

    def salvar(self, manter):
        if self.mudou:
            salvar_json(CAMINHO_TEXTOS, {k: v for k, v in self.dados.items() if k in manter}, indent=None)


def registro_da_central(solicitacoes, estados, desde):
    """Registro temporário com as solicitações abertas, no formato que o conferente entende."""
    reg = Registro()
    for s in solicitacoes:
        if not s["data"] or s["data"] < desde:
            continue
        est = estados.get(s["chave"], dados.estado_inicial())
        if dados.situacao(s, est) == dados.CONCLUIDA:
            continue
        reg.solicitacoes[s["chave"]] = {
            "codigo": "", "hotel": s["hotel"], "aba": s["aba"], "email_hotel": s.get("email_hotel", ""),
            "carimbo": s["carimbo"], "data_pedido": s["data"], "nome": s["nome"],
            "emails": list(dict.fromkeys([s["email"]] + s["emails"])) if s["email"] else s["emails"],
            "nomes": list(dict.fromkeys([s["nome"]] + s.get("nomes", []))),
            "partes": dados.partes_esperadas(s, est),
            "nfs": {n: {"data": "", "entry_id": "app"} for n in est["nfs"]}, "tratativas": {},
            **provas_da_solicitacao(types.SimpleNamespace(campos=s["campos"])),
        }
    return reg


class Indice:
    """Candidatas por e-mail, conta do hotel e palavras do nome. Sem isso cada nota seria
    comparada com milhares de solicitações abertas (e o texto da nota reprocessado a cada uma)."""

    def __init__(self, reg):
        self.reg = reg
        self.por_email, self.por_conta, self.por_palavra, self.nomes = {}, {}, {}, {}
        for ref, s in reg.solicitacoes.items():
            for e in s["emails"]:
                self.por_email.setdefault(e.lower(), set()).add(ref)
            self.por_conta.setdefault(s["email_hotel"].lower(), set()).add(ref)
            self.nomes[ref] = [_tokens(n) for n in s["nomes"]]
            for palavra in set().union(*self.nomes[ref]):
                self.por_palavra.setdefault(palavra, set()).add(ref)

    def por_nome(self, nome):
        alvo = _tokens(nome)
        if not alvo:
            return set()
        candidatas = set().union(*(self.por_palavra.get(p, set()) for p in alvo))
        return {r for r in candidatas if any(alvo <= t or len(alvo & t) >= 2 for t in self.nomes[r])}

    def para_email(self, destinatarios, conta, nome_nf):
        refs = set().union(*(self.por_email.get(d.lower(), set()) for d in destinatarios)) if destinatarios else set()
        return refs | (self.por_conta.get(conta, set()) & self.por_nome(nome_nf))

    def sub(self, refs):
        """Registro só com as candidatas; os dicts são os mesmos, então NF marcada aparece no reg completo."""
        r = Registro()
        r.solicitacoes = {k: self.reg.solicitacoes[k] for k in refs}
        return r


# Hóspede que pediu nota dividida mas aceita uma só (pedido do usuário, 05/10/2026). "uma nota" sozinho
# não serve: quase todo pedido diz "preciso de uma nota fiscal".
_NOTA_UNICA = re.compile(
    r"(?:s[oó]|somente|apenas)\s+(?:uma|1)\s+(?:[uú]nica\s+)?nota"
    r"|(?:uma|1)\s+[uú]nica\s+nota|nota\s+[uú]nica"
    r"|pode\s+ser\s+(?:s[oó]\s+)?(?:uma|1)\s+(?:s[oó]\s+)?nota"
    r"|(?:uma|1)\s+nota\s+s[oó]\b"
    r"|valor\s+(?:total|todo|integral|inteiro)\s+(?:em|numa|na)\s+(?:uma|1|[uú]nica|mesma)?\s*nota"
    r"|n[aã]o\s+(?:precisa|precisamos|preciso|é\s+necess[aá]rio)\s+(?:mais\s+)?(?:dividir|separar)"
    r"|(?:pode|podem)\s+(?:juntar|unir|ser\s+(?:tudo\s+)?junt[oa]s?)"
    r"|tudo\s+(?:em|numa)\s+(?:uma|1)\s+(?:s[oó]\s+)?nota", re.IGNORECASE)


def frase_de_nota_unica(texto):
    """Trecho em que o hóspede aceita uma nota só, ou None."""
    texto = re.sub(r"\s+", " ", texto or "")
    m = _NOTA_UNICA.search(texto)
    if not m:
        return None
    return texto[max(0, m.start() - 40):m.end() + 40].strip()


def _parciais(reg):
    """Divididas com alguma NF e ainda faltando nota: as que podem ter virado nota única."""
    saida = {}
    for k, s in reg.solicitacoes.items():
        validas = [n for n, d in s["nfs"].items() if not d.get("conferir")]
        if s.get("partes", 1) > 1 and 0 < len(validas) < s["partes"]:
            saida[k] = s
    return saida


def pedidos_de_nota_unica(namespace, parciais, campos_por_chave):
    """{chave: (frase, origem)} — procura no formulário e nos e-mails que o hóspede mandou pra caixa do
    hotel (só as caixas deste PC)."""
    achados = {}
    contas = {}
    if namespace is not None:
        for conta in namespace.Accounts:
            contas[(conta.SmtpAddress or "").strip().lower()] = conta
    for k, s in parciais.items():
        for rotulo, valor in campos_por_chave.get(k, []):
            if "dividid" in rotulo.lower():
                continue
            frase = frase_de_nota_unica(str(valor))
            if frase:
                achados[k] = (frase, "no formulário")
                break
        if k in achados or s.get("email_hotel", "").lower() not in contas:
            continue
        try:
            caixa = contas[s["email_hotel"].lower()].DeliveryStore.GetDefaultFolder(6)   # olFolderInbox
        except Exception as e:
            logger.debug(f"caixa de entrada de {s['email_hotel']}: {e}")
            continue
        desde = datetime.date.fromisoformat(s["data_pedido"]).strftime("%d/%m/%Y")
        for email in s.get("emails", []):
            try:
                itens = caixa.Items.Restrict(f"[ReceivedTime] >= '{desde} 00:00'").Restrict(
                    f"[SenderEmailAddress] = '{email.replace(chr(39), '')}'")
                for item in itens:
                    frase = frase_de_nota_unica(f"{item.Subject or ''} {(item.Body or '')[:4000]}")
                    if frase:
                        achados[k] = (frase, f"no e-mail do hóspede de {item.ReceivedTime:%d/%m/%Y}")
                        break
            except Exception as e:
                logger.debug(f"e-mails de {email}: {e}")
            if k in achados:
                break
    return achados


def _novas_nfs(reg, antes):
    """[(chave, numero, prova)] confirmadas nesta rodada."""
    saida = []
    for k, s in reg.solicitacoes.items():
        for numero, d in s["nfs"].items():
            if (k, numero) not in antes and not d.get("conferir"):
                saida.append((k, numero, d.get("prova", "")))
    return saida


def _novas_tratativas(reg, antes):
    """[(chave, entry_id, {data, assunto})] — e-mails sem NF mandados ao hóspede nesta rodada."""
    return [(k, entry, d) for k, s in reg.solicitacoes.items() for entry, d in s["tratativas"].items()
            if (k, entry) not in antes]


def marca_do_email(entry_id):
    """Marca curta e fixa do e-mail no texto da tratativa: a mesma mensagem nunca vira duas."""
    return "#" + hashlib.sha1(entry_id.encode("utf-8", "replace")).hexdigest()[:8]


def _itens_enviados(pasta, limite):
    """Todos os enviados do período (com ou sem "NF" no assunto: pergunta ao hóspede é tratativa)."""
    return pasta.Items.Restrict(f"[SentOn] >= '{limite:%d/%m/%Y %H:%M}'")


def numeros_de_nf_enviados(assunto, anexos, extensoes):
    """Nºs das NFs que um e-mail levou: "NF 590 - NOME" no assunto (com anexo de NF) e/ou PDF/XML "NF 590 - NOME"."""
    from controle_nf import tem_anexo_nf
    numeros = set()
    nf = ler_assunto_nf(assunto or "")
    if nf and tem_anexo_nf(anexos, extensoes):
        numeros.add(nf[0])
    for a in anexos:
        if str(a).lower().endswith((".pdf", ".xml")):
            n = ler_assunto_nf(os.path.splitext(str(a))[0])
            if n:
                numeros.add(n[0])
    return numeros


def varrer_emails(namespace, indice, cfg, limite, vistos, textos, max_itens=MAX_ITENS_POR_CONTA,
                  envios=None, por_email_todos=None, por_nf=None):
    """Itens Enviados das caixas deste PC: e-mail com NF anexada conclui o pedido; qualquer outro
    e-mail mandado ao endereço de um pedido aberto é tratativa (pedido do usuário, 06/10/2026)."""
    from conferente import _anexos, _data_outlook, _enderecos, texto_da_nota
    extensoes = cfg["conferencia"]["extensoes_anexo_nf"]
    lidos = 0
    for conta in namespace.Accounts:
        smtp = (conta.SmtpAddress or "").strip().lower()
        try:
            itens = _itens_enviados(conta.DeliveryStore.GetDefaultFolder(5), limite)   # olFolderSentMail
        except Exception as e:
            logger.warning(f"⚠️ Não abri Itens Enviados de {smtp}: {e}")
            continue
        da_conta = 0
        for i, item in enumerate(itens):
            if max_itens and i >= max_itens:
                break
            try:
                if getattr(item, "Class", 43) != 43:
                    continue
                entry = item.EntryID
                if entry in vistos:
                    continue
                vistos.add(entry)
                nf = ler_assunto_nf(item.Subject or "")
                destinatarios = _enderecos(item)
                if nf:
                    da_conta += 1
                if envios is not None:
                    # e-mail com NF pro endereço de um pedido, mesmo já marcado como emitido (Painel: "enviada")
                    numeros = numeros_de_nf_enviados(item.Subject, _anexos(item), extensoes)
                    if numeros:
                        quando = _data_outlook(item.SentOn)
                        refs = {k: d for d in destinatarios for k in (por_email_todos or {}).get(d.lower(), ())}
                        # mandada pra outro endereço (o hóspede pediu): vale a NF do pedido saindo da caixa do hotel
                        for n in numeros:
                            for k in (por_nf or {}).get((smtp, n), ()):
                                refs.setdefault(k, ", ".join(sorted(destinatarios)))
                        for k, para in refs.items():
                            envios.append((k, entry, para, quando, sorted(numeros, key=int)))
                candidatas = indice.para_email(destinatarios, smtp, nf[1] if nf else "")
                if not candidatas:
                    continue
                indice.sub(candidatas).aplicar_envio(
                    {"entry_id": entry, "conta": smtp, "destinatarios": destinatarios, "assunto": item.Subject or "",
                     "data": _data_outlook(item.SentOn), "anexos": _anexos(item)},
                    extensoes, ler_texto=lambda item=item, e=entry: textos.ler(e, lambda: texto_da_nota(item)))
            except Exception as e:
                logger.debug(f"item ilegível em {smtp}: {e}")
        if da_conta:
            logger.info(f"   📨 {smtp}: {da_conta} e-mail(s) de NF novo(s)")
        lidos += da_conta
    return lidos


def _remetente(item):
    endereco = str(getattr(item, "SenderEmailAddress", "") or "").strip().lower()
    if "@" in endereco:
        return endereco
    try:
        return item.Sender.GetExchangeUser().PrimarySmtpAddress.lower()
    except Exception:
        return endereco


def varrer_recebidos(namespace, indice, vistos, dias=RECEBIDOS_DIAS):
    """E-mails que hóspedes de pedidos abertos mandaram pras caixas deste PC (últimos `dias`).
    -> [(chave, conta, assunto, quando)] dos ainda não vistos."""
    from conferente import _data_outlook
    desde = datetime.datetime.now() - datetime.timedelta(days=dias)
    achados = []
    for conta in namespace.Accounts:
        smtp = (conta.SmtpAddress or "").strip().lower()
        try:
            itens = conta.DeliveryStore.GetDefaultFolder(6).Items.Restrict(f"[ReceivedTime] >= '{desde:%d/%m/%Y %H:%M}'")
        except Exception as e:
            logger.debug(f"caixa de entrada de {smtp}: {e}")
            continue
        for item in itens:
            try:
                if getattr(item, "Class", 43) != 43 or item.EntryID in vistos:
                    continue
                vistos.add(item.EntryID)
                refs = indice.por_email.get(_remetente(item), set())
                for ref in refs:
                    achados.append((ref, smtp, str(item.Subject or ""), _data_outlook(item.ReceivedTime)))
            except Exception as e:
                logger.debug(f"item ilegível na entrada de {smtp}: {e}")
    return achados


def _agente_deste_pc():
    try:
        import identidade
        return identidade.ler().get("agente") or ""
    except Exception:
        return ""


def _atividades(tipo, itens, montar, agente):
    """Uma linha por item; muitos de uma vez (conferência do ano) viram uma linha de resumo."""
    import atividade
    if len(itens) > MAX_ATIVIDADES_POR_TIPO:
        return [atividade.linha(tipo, detalhe=f"{len(itens)} de uma vez (conferência em lote)", agente=agente)]
    return [atividade.linha(tipo, *montar(i), agente=agente) for i in itens]


def varrer_dropbox(indice, cfg, limite, vistos, textos):
    from conferente import _nome_da_fonte, texto_de_arquivo_dropbox
    conf = cfg.get("dropbox_notas") or {}
    if not conf.get("ativo"):
        return 0
    lidos = 0
    for pasta in conf.get("pastas", []):
        fonte = _nome_da_fonte(pasta)
        try:
            entradas = list(os.scandir(pasta))
        except OSError as e:
            logger.warning(f"⚠️ Não abri a pasta do Dropbox {pasta}: {e}")
            continue
        for e in entradas:
            if not e.is_file() or not e.name.lower().endswith((".pdf", ".xml")):
                continue
            modificado = datetime.datetime.fromtimestamp(e.stat().st_mtime)
            marca = modificado.isoformat(timespec="seconds")
            if modificado < limite or vistos.get(e.path) == marca:
                continue
            nf = ler_assunto_nf(os.path.splitext(e.name)[0])
            candidatas = indice.por_nome(nf[1]) if nf else set()
            if candidatas and so_na_nuvem(e.path):
                # não baixa o PDF: casa pelo nome do arquivo na pasta do agente
                if indice.sub(candidatas).aplicar_nota_pelo_nome(e.path, nf, modificado, fonte):
                    lidos += 1
                vistos[e.path] = marca
                continue
            if candidatas:   # só lê o PDF se o nome do arquivo casa com alguém aberto
                lidos += 1
                chave = f"{e.path}|{marca}"
                indice.sub(candidatas).aplicar_nota_dropbox(
                    e.path, nf, modificado, lambda c=e.path, k=chave: textos.ler(k, lambda: texto_de_arquivo_dropbox(c)), fonte)
            vistos[e.path] = marca
        logger.info(f"   📂 {fonte}: conferida ({lidos} nota(s) lidas até aqui)")
    return lidos


# Leitura leve (08/10/2026): a conferência roda a cada 2 min em cada PC e relia ~11 MB (abas dos hotéis +
# Tratamento inteira). Agora as abas dos hotéis valem 5 min e a Tratamento vem só pelo fim (as linhas novas).
_CACHE_CENTRAL = {"hoteis_em": -1e9, "hoteis": {}, "trat": None, "trat_em": -1e9}
HOTEIS_CACHE_SEGUNDOS = 300
TRATAMENTO_INTEIRA_SEGUNDOS = 1800


def ler_central(backend, central, abas_hoteis, relogio=None):
    """-> {aba: linhas} com as abas dos hotéis pedidas + a Tratamento, gastando o mínimo de leitura/download."""
    import time
    agora = (relogio or time.monotonic)()
    c = _CACHE_CENTRAL
    ler_hoteis = agora - c["hoteis_em"] >= HOTEIS_CACHE_SEGUNDOS or set(abas_hoteis) - set(c["hoteis"])
    inteira = c["trat"] is None or agora - c["trat_em"] >= TRATAMENTO_INTEIRA_SEGUNDOS
    faixas = {} if inteira else {dados.ABA_TRATAMENTO: f"A{len(c['trat'])}:H"}
    lidas, _ = backend.ler_abas(central, (list(abas_hoteis) if ler_hoteis else []) + [dados.ABA_TRATAMENTO],
                                faixas=faixas)
    if ler_hoteis:
        c["hoteis"], c["hoteis_em"] = {a: lidas.get(a, []) for a in abas_hoteis}, agora
    trat = lidas.get(dados.ABA_TRATAMENTO)
    if trat is not None and not inteira:
        trat = dados.juntar_fim(c["trat"], trat)
    if trat is None and not inteira:   # mudou por baixo (faxina) ou o fim falhou: inteira
        trat = backend.ler_abas(central, [dados.ABA_TRATAMENTO])[0].get(dados.ABA_TRATAMENTO)
        inteira = True
    if trat is None:
        if c["trat"] is None:
            raise RuntimeError("não consegui ler a aba Tratamento")
        trat = c["trat"]
    elif inteira:
        c["trat_em"] = agora
    c["trat"] = trat
    return {**{a: c["hoteis"].get(a, []) for a in abas_hoteis}, dados.ABA_TRATAMENTO: trat}


def confirmar(backend, cfg, namespace=None, usar_dropbox=True, gravar=False, agora=None, desde=None, rever=False,
              ocr=True):
    agora = agora or datetime.datetime.now()
    dias = int(cfg["conferencia"]["dias_maximos"])
    desde = desde or (agora.date() - datetime.timedelta(days=dias)).isoformat()
    limite = datetime.datetime.fromisoformat(desde) - datetime.timedelta(days=1)

    hoteis, _ = ler_hoteis(backend, dict(cfg, somente_hoteis=[]))
    lidas = ler_central(backend, cfg["planilha_central_id"], [h.aba for h in hoteis])
    solicitacoes = []
    for h in hoteis:
        for s in dados.ler_solicitacoes(h.aba, h.nome, lidas.get(h.aba, []), cfg):
            s["email_hotel"] = h.email_hotel
            solicitacoes.append(s)
    estados = dados.dobrar_eventos(lidas.get(dados.ABA_TRATAMENTO, [[]]))
    reg = registro_da_central(solicitacoes, estados, desde)
    antes = {(k, n) for k, s in reg.solicitacoes.items() for n in s["nfs"]}
    antes_trat = {(k, e) for k, s in reg.solicitacoes.items() for e in s["tratativas"]}
    logger.info(f"🔎 {len(reg.solicitacoes)} solicitação(ões) sem NF confirmada desde {desde}")

    try:
        guardado = json.load(open(CAMINHO_VISTOS, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        guardado = {}
    vistos_email, vistos_dropbox = set(guardado.get("emails", [])), guardado.get("dropbox", {})
    vistos_recebidos = set(guardado.get("recebidos", []))
    if guardado.get("versao_regras", 1) < VERSAO_REGRAS:
        logger.info(f"🔁 Regras novas (v{VERSAO_REGRAS}): relendo os e-mails já vistos uma vez.")
        rever = True
    if rever:
        vistos_email, vistos_dropbox = set(), {}
    recebidos, envios = [], []
    textos = CacheTextos()
    import conferente
    ocr_original = conferente._texto_ocr
    if not ocr:
        conferente._texto_ocr = lambda caminho: ""

    try:
        indice = Indice(reg)
        por_email_todos = {}
        for s in solicitacoes:
            if s["data"] and s["data"] >= desde:
                for e in [s["email"]] + list(s.get("emails", [])):
                    if e:
                        por_email_todos.setdefault(e.lower(), set()).add(s["chave"])
        por_nf = {}   # (caixa do hotel, nº da NF) -> pedidos: o nº da NF é único em cada hotel
        for s in solicitacoes:
            if s["data"] and s["data"] >= desde and s.get("email_hotel"):
                for n in estados.get(s["chave"], {}).get("nfs", []):
                    por_nf.setdefault((s["email_hotel"].lower(), str(n)), set()).add(s["chave"])
        lidos_email = varrer_emails(namespace, indice, cfg, limite, vistos_email, textos,
                                    None if rever else MAX_ITENS_POR_CONTA, envios=envios,
                                    por_email_todos=por_email_todos, por_nf=por_nf) if namespace is not None else 0
        lidos_dropbox = varrer_dropbox(indice, cfg, limite, vistos_dropbox, textos) if usar_dropbox else 0
        if namespace is not None:
            recebidos = varrer_recebidos(namespace, indice, vistos_recebidos)
    finally:   # o cache vale mesmo na prévia e mesmo se parar no meio: a próxima rodada não relê
        conferente._texto_ocr = ocr_original
        corte = limite.isoformat(timespec="seconds")
        textos.salvar({k for k in textos.dados if "|" not in k or k.rsplit("|", 1)[1] >= corte} if usar_dropbox
                      else set(textos.dados))
    achadas = _novas_nfs(reg, antes)
    logger.info(f"📨 {lidos_email} e-mail(s) de NF e 📂 {lidos_dropbox} nota(s) do Dropbox conferidos · "
                f"{len(achadas)} NF(s) confirmada(s)")

    por_chave = {s["chave"]: s for s in solicitacoes}
    pc = socket.gethostname()
    linhas = []
    for k, numero, prova in achadas:
        s = por_chave[k]
        logger.info(f"✅ NF {numero} · {s['hotel']} · {s['nome']} — {prova}")
        linhas.append(dados.evento(dados.agora(), AGENTE, pc, s["aba"], s["carimbo"], s["email"], dados.NF, numero))
        linhas.append(dados.evento(dados.agora(), AGENTE, pc, s["aba"], s["carimbo"], s["email"], dados.OBS,
                                   f"NF {numero} confirmada automaticamente: {prova}"))
    unicas = pedidos_de_nota_unica(namespace, _parciais(reg), {k: por_chave[k]["campos"] for k in _parciais(reg)})
    for k, (frase, origem) in unicas.items():
        s = por_chave[k]
        logger.info(f"1️⃣ Nota única pedida · {s['hotel']} · {s['nome']} — “{frase}” ({origem})")
        linhas.append(dados.evento(dados.agora(), AGENTE, pc, s["aba"], s["carimbo"], s["email"], dados.DIVIDIDA, "nao"))
        linhas.append(dados.evento(dados.agora(), AGENTE, pc, s["aba"], s["carimbo"], s["email"], dados.OBS,
                                   f"{PREFIXO_NOTA_UNICA} “{frase}” ({origem})"))
    # Tratativas: e-mail sem NF ao hóspede (pergunta, pedido de dados...). A marca do e-mail no texto
    # impede repetir a mesma mensagem (ex.: numa conferência com --rever).
    ja_registradas = {k: " ".join(t["texto"] for t in estados.get(k, {}).get("tratativas", [])) for k in reg.solicitacoes}
    tratativas = []
    for k, entry, d in _novas_tratativas(reg, antes_trat):
        marca = marca_do_email(entry)
        if marca in ja_registradas.get(k, ""):
            continue
        s = por_chave[k]
        quando = d.get("data", "")[:16].replace("T", " ")
        linhas.append(dados.evento(dados.agora(), AGENTE, pc, s["aba"], s["carimbo"], s["email"], dados.TRATATIVA,
                                   f"E-mail ao hóspede em {quando}: {d.get('assunto', '')[:90]} [{marca}]"))
        tratativas.append((s, d))
    # E-mail com NF que saiu pro hóspede: o Painel separa "NF emitida · enviada" de "envio pendente"
    ja_obs = {k: " ".join(o["texto"] for o in estados.get(k, {}).get("obs", [])) for k in {x[0] for x in envios}}
    feitos = set()
    for k, entry, para, quando, numeros in envios:
        marca = marca_do_email(entry)
        if (k, entry) in feitos or marca in ja_obs.get(k, "") or k not in por_chave:
            continue
        feitos.add((k, entry))
        s = por_chave[k]
        quando_txt = quando.strftime("%d/%m/%Y %H:%M") if quando else ""
        linhas.append(dados.evento(dados.agora(), AGENTE, pc, s["aba"], s["carimbo"], s["email"], dados.OBS,
                                   f"E-mail com a NF {', '.join(numeros)} enviado para {para} em {quando_txt} [{marca}]"))
    if feitos:
        logger.info(f"📧 {len(feitos)} e-mail(s) com NF ao hóspede registrado(s) (envio conferido)")
    if unicas:
        achadas = achadas + [(k, "nota única", f"“{frase}” ({origem})") for k, (frase, origem) in unicas.items()]

    import atividade
    agente = _agente_deste_pc()
    atividades = []
    nfs_email = [(por_chave[k], n, p) for k, n, p in achadas if n != "nota única" and "e-mail" in p]
    nfs_dropbox = [(por_chave[k], n, p) for k, n, p in achadas if n != "nota única" and "e-mail" not in p]
    atividades += _atividades(atividade.NF_ENVIADA, nfs_email, lambda x: (x[0]["hotel"], x[0]["nome"], f"NF {x[1]} · {x[2]}"), agente)
    atividades += _atividades(atividade.NF_DROPBOX, nfs_dropbox, lambda x: (x[0]["hotel"], x[0]["nome"], f"NF {x[1]} · {x[2]}"), agente)
    atividades += _atividades(atividade.TRATATIVA, tratativas,
                              lambda x: (x[0]["hotel"], x[0]["nome"], f"e-mail sem nota: {x[1].get('assunto', '')}"), agente)
    atividades += _atividades(atividade.EMAIL_RECEBIDO, [(por_chave[r], c, a) for r, c, a, _ in recebidos if r in por_chave],
                              lambda x: (x[0]["hotel"], x[0]["nome"], f"de {x[0]['email']} para {x[1]}: {x[2]}"), agente)
    atividades += _atividades(atividade.NOTA_UNICA, [(por_chave[k], f) for k, (f, _) in unicas.items()],
                              lambda x: (x[0]["hotel"], x[0]["nome"], f"hóspede aceita nota única: “{x[1]}”"), agente)
    if gravar:
        if linhas:
            backend.anexar_linhas(cfg["planilha_central_id"], dados.ABA_TRATAMENTO, linhas)
        atividade.registrar(backend, cfg["planilha_central_id"], atividades)
        salvar_json(CAMINHO_VISTOS, {"versao_regras": VERSAO_REGRAS, "emails": sorted(vistos_email),
                                     "dropbox": {p: m for p, m in vistos_dropbox.items() if m >= corte},
                                     "recebidos": sorted(vistos_recebidos)[-20000:]})
        salvar_json(CAMINHO_STATUS, {"quando": agora.isoformat(timespec="seconds"),
                                     "contas": len(list(namespace.Accounts)) if namespace is not None else 0,
                                     "nfs": len(nfs_email) + len(nfs_dropbox), "tratativas": len(tratativas),
                                     "recebidos": len(recebidos)})
    return [(por_chave[k], numero, prova) for k, numero, prova in achadas]


def rodar(namespace, cfg, usar_dropbox):
    """Chamado pelo conferente."""
    from sheets import BackendGoogle
    backend = BackendGoogle(caminho_chave_google(cfg))
    return confirmar(backend, cfg, namespace, usar_dropbox=usar_dropbox, gravar=True)


if __name__ == "__main__":
    from sheets import BackendGoogle
    cfg = carregar_config()
    gravar = "--gravar" in sys.argv
    ns = None if "--sem-email" in sys.argv else outlook_vivo.aplicativo().GetNamespace("MAPI")
    desde = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--desde=")), None)
    achadas = confirmar(BackendGoogle(caminho_chave_google(cfg)), cfg, ns,
                        usar_dropbox="--sem-dropbox" not in sys.argv, gravar=gravar, desde=desde,
                        rever="--rever" in sys.argv, ocr="--sem-ocr" not in sys.argv)
    print(("\nGRAVADO" if gravar else "\nPRÉVIA — nada gravado") + f": {len(achadas)} NF(s) confirmada(s)")
    for s, numero, prova in achadas:
        print(f"  NF {numero:>6} | {s['hotel'][:18]:18} | {s['nome'][:32]:32} | {prova[:90]}")
