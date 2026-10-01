"""Confirma NFs já emitidas para todas as solicitações da Central e publica na aba Tratamento.

Fontes:
  - Itens Enviados das contas do Outlook deste PC (cada PC confere as caixas que tem);
  - pastas de notas do Dropbox (compartilhadas entre os PCs).

As regras são as do conferente (controle_nf.Registro): "NF 123 - NOME" no assunto/arquivo e o
conteúdo da nota batendo com a solicitação. Só NF confirmada vira evento; as ilegíveis ficam de fora.

    python src\\confirmar_nfs.py                 prévia, não grava
    python src\\confirmar_nfs.py --gravar
    python src\\confirmar_nfs.py --sem-email | --sem-dropbox
"""
import datetime
import json
import os
import socket
import sys
import types

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_utf8 import garantir_utf8

garantir_utf8()

import app_dados as dados
from arquivos import salvar_json
from config import PASTA_ESTADO, caminho_chave_google, carregar_config
from controle_nf import Registro, _tokens, ler_assunto_nf, provas_da_solicitacao
from log_util import configurar_logging
from sheets import ler_hoteis

logger = configurar_logging("confirmar_nfs")

CAMINHO_VISTOS = PASTA_ESTADO / "confirmar_nfs.json"
CAMINHO_TEXTOS = PASTA_ESTADO / "cache_textos_nf.json"
AGENTE = "Robô"
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
            "partes": max(s["partes"], 2 if est.get("dividida") else 1),
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


def _novas_nfs(reg, antes):
    """[(chave, numero, prova)] confirmadas nesta rodada."""
    saida = []
    for k, s in reg.solicitacoes.items():
        for numero, d in s["nfs"].items():
            if (k, numero) not in antes and not d.get("conferir"):
                saida.append((k, numero, d.get("prova", "")))
    return saida


def _itens_de_nf(pasta, limite):
    """Só os itens do período com "NF" no assunto; o filtro roda dentro do Outlook, não item a item."""
    itens = pasta.Items.Restrict(f"[SentOn] >= '{limite:%d/%m/%Y %H:%M}'")
    return itens.Restrict("@SQL=\"urn:schemas:httpmail:subject\" LIKE '%NF%'")


def varrer_emails(namespace, indice, cfg, limite, vistos, textos):
    from conferente import _anexos, _data_outlook, _enderecos, texto_da_nota
    extensoes = cfg["conferencia"]["extensoes_anexo_nf"]
    lidos = 0
    for conta in namespace.Accounts:
        smtp = (conta.SmtpAddress or "").strip().lower()
        try:
            itens = _itens_de_nf(conta.DeliveryStore.GetDefaultFolder(5), limite)   # olFolderSentMail
        except Exception as e:
            logger.warning(f"⚠️ Não abri Itens Enviados de {smtp}: {e}")
            continue
        da_conta = 0
        for i, item in enumerate(itens):
            if i >= MAX_ITENS_POR_CONTA:
                break
            try:
                if getattr(item, "Class", 43) != 43:
                    continue
                entry = item.EntryID
                if entry in vistos:
                    continue
                vistos.add(entry)
                nf = ler_assunto_nf(item.Subject or "")
                if not nf:
                    continue
                da_conta += 1
                destinatarios = _enderecos(item)
                candidatas = indice.para_email(destinatarios, smtp, nf[1])
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
            if candidatas:   # só lê o PDF se o nome do arquivo casa com alguém aberto
                lidos += 1
                chave = f"{e.path}|{marca}"
                indice.sub(candidatas).aplicar_nota_dropbox(
                    e.path, nf, modificado, lambda c=e.path, k=chave: textos.ler(k, lambda: texto_de_arquivo_dropbox(c)), fonte)
            vistos[e.path] = marca
        logger.info(f"   📂 {fonte}: conferida ({lidos} nota(s) lidas até aqui)")
    return lidos


def confirmar(backend, cfg, namespace=None, usar_dropbox=True, gravar=False, agora=None):
    agora = agora or datetime.datetime.now()
    dias = int(cfg["conferencia"]["dias_maximos"])
    desde = (agora.date() - datetime.timedelta(days=dias)).isoformat()
    limite = datetime.datetime.fromisoformat(desde) - datetime.timedelta(days=1)

    hoteis, _ = ler_hoteis(backend, dict(cfg, somente_hoteis=[]))
    lidas, _ = backend.ler_abas(cfg["planilha_central_id"], [h.aba for h in hoteis] + [dados.ABA_TRATAMENTO])
    solicitacoes = []
    for h in hoteis:
        for s in dados.ler_solicitacoes(h.aba, h.nome, lidas.get(h.aba, []), cfg):
            s["email_hotel"] = h.email_hotel
            solicitacoes.append(s)
    estados = dados.dobrar_eventos(lidas.get(dados.ABA_TRATAMENTO, [[]]))
    reg = registro_da_central(solicitacoes, estados, desde)
    antes = {(k, n) for k, s in reg.solicitacoes.items() for n in s["nfs"]}
    logger.info(f"🔎 {len(reg.solicitacoes)} solicitação(ões) sem NF confirmada desde {desde}")

    try:
        guardado = json.load(open(CAMINHO_VISTOS, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        guardado = {}
    vistos_email, vistos_dropbox = set(guardado.get("emails", [])), guardado.get("dropbox", {})
    textos = CacheTextos()

    try:
        indice = Indice(reg)
        lidos_email = varrer_emails(namespace, indice, cfg, limite, vistos_email, textos) if namespace is not None else 0
        lidos_dropbox = varrer_dropbox(indice, cfg, limite, vistos_dropbox, textos) if usar_dropbox else 0
    finally:   # o cache vale mesmo na prévia e mesmo se parar no meio: a próxima rodada não relê
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
    if gravar:
        if linhas:
            backend.anexar_linhas(cfg["planilha_central_id"], dados.ABA_TRATAMENTO, linhas)
        salvar_json(CAMINHO_VISTOS, {"emails": sorted(vistos_email),
                                     "dropbox": {p: m for p, m in vistos_dropbox.items() if m >= corte}})
    return [(por_chave[k], numero, prova) for k, numero, prova in achadas]


def rodar(namespace, cfg, usar_dropbox):
    """Chamado pelo conferente."""
    from sheets import BackendGoogle
    backend = BackendGoogle(caminho_chave_google(cfg))
    return confirmar(backend, cfg, namespace, usar_dropbox=usar_dropbox, gravar=True)


if __name__ == "__main__":
    import win32com.client
    from sheets import BackendGoogle
    cfg = carregar_config()
    gravar = "--gravar" in sys.argv
    ns = None if "--sem-email" in sys.argv else win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    achadas = confirmar(BackendGoogle(caminho_chave_google(cfg)), cfg, ns,
                        usar_dropbox="--sem-dropbox" not in sys.argv, gravar=gravar)
    print(("\nGRAVADO" if gravar else "\nPRÉVIA — nada gravado") + f": {len(achadas)} NF(s) confirmada(s)")
    for s, numero, prova in achadas:
        print(f"  NF {numero:>6} | {s['hotel'][:18]:18} | {s['nome'][:32]:32} | {prova[:90]}")
