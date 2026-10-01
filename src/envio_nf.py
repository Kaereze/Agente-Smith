"""Envio da NF ao hóspede pelo Painel, saindo da caixa do próprio hotel.

Se a caixa do hotel está no Outlook deste PC, envia na hora. Se está em outro PC, o pedido vai pra
fila compartilhada (aba Envios_NF da Central) e o Painel daquele PC envia. Cada Painel publica na aba
PCs_Painel quais caixas tem, pra quem pede saber se existe um PC ligado capaz de enviar.

Envios_NF é append-only, como a aba Tratamento: PEDIDO, ASSUMIDO, ENVIADO, FALHOU. Anexo vindo do
Dropbox viaja como caminho relativo (cada PC lê do seu Dropbox); arquivo do computador viaja em partes
na aba Envios_NF_Anexos e é apagado depois do envio.
"""
import base64
import datetime
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

from controle_nf import _tokens, ler_assunto_nf
from log_util import configurar_logging

logger = configurar_logging("envio_nf")

ABA_FILA = "Envios_NF"
CAB_FILA = ["Quando", "ID", "Evento", "PC", "Quem", "Dados (JSON)"]
ABA_ANEXOS = "Envios_NF_Anexos"
CAB_ANEXOS = ["ID", "Parte", "Total", "Nome", "Base64"]
ABA_PCS = "PCs_Painel"
CAB_PCS = ["PC", "Agente", "Contas", "Visto em"]

PEDIDO, ASSUMIDO, ENVIADO, FALHOU = "PEDIDO", "ASSUMIDO", "ENVIADO", "FALHOU"
TAMANHO_PARTE = 45_000            # limite de célula do Sheets é 50 mil caracteres
MAX_ANEXO_BYTES = 8 * 1024 * 1024
PC_ONLINE_SEGUNDOS = 180
SEM_RESPOSTA_SEGUNDOS = 90
DISPID_SEND_USING_ACCOUNT = 64209

CORPO_PADRAO = ("Olá, {nome}!\n\nSegue em anexo a nota fiscal referente à sua hospedagem no {hotel}.\n\n"
                "Qualquer dúvida, estamos à disposição.\n\nAtenciosamente,\n{hotel}")


def agora():
    return datetime.datetime.now()


def _iso(d):
    return d.isoformat(timespec="seconds")


# ---------- assunto, destinatários, sugestões ----------
def assunto_sugerido(nome_arquivo, numero_nf, nome):
    """Usa o nome do arquivo quando ele já está no padrão "NF 1212 - NOME"; senão monta com o número."""
    base = os.path.splitext(os.path.basename(nome_arquivo or ""))[0]
    if ler_assunto_nf(base):
        return re.sub(r"\s+", " ", base).strip()
    return f"NF {numero_nf} - {nome.upper()}" if numero_nf else f"NF - {nome.upper()}"


def destinatarios(sol):
    vistos = []
    for e in [sol.get("email", "")] + list(sol.get("emails", [])):
        e = (e or "").strip().lower()
        if "@" in e and e not in vistos:
            vistos.append(e)
    return vistos


def raiz_dropbox(cfg):
    """Pasta raiz do Dropbox neste PC (onde fica 'REDE ANDRADE Dropbox')."""
    padrao = Path.home() / "REDE ANDRADE Dropbox"
    if padrao.exists():
        return padrao
    for pasta in (cfg.get("dropbox_notas") or {}).get("pastas", []):
        partes = Path(pasta).parts
        for i, p in enumerate(partes):
            if "dropbox" in p.lower():
                return Path(*partes[: i + 1])
    return None


PALAVRAS_COMUNS = {"dos", "das", "des", "del", "ltda", "eireli", "epp", "s/a", "sa", "me", "cia", "filho", "junior",
                   "neto", "comercio", "servicos", "industria", "empresa", "hotel"}


def _palavras(nome):
    return _tokens(nome) - PALAVRAS_COMUNS


def _primeira_palavra(nome):
    from tratamento import normalizar
    p = normalizar(nome).split()
    return p[0] if p else ""


def _nota(t, alvos, primeiros=()):
    """3 = nome da nota (2+ palavras) inteiro dentro do nome pedido; 2 = 2+ palavras em comum;
    1 = a nota tem uma palavra só e ela é o primeiro nome de alguém do pedido; 0 = não bate.
    Uma palavra solta (ex.: "SANTOS") não basta: sobrenome comum casa com muita gente."""
    if not t:
        return 0
    if len(t) == 1:
        return 1 if next(iter(t)) in primeiros else 0
    if any(t <= a for a in alvos):
        return 3
    return 2 if any(len(t & a) >= 2 for a in alvos) else 0


_LISTAGEM = {"em": None, "chave": None, "itens": []}
LISTAGEM_SEGUNDOS = 300


def listar_notas_dropbox(cfg, forcar=False):
    """[(nome, caminho, mtime, (nº, nome na NF))] das pastas de notas — em cache: ler o Dropbox leva segundos."""
    pastas = tuple((cfg.get("dropbox_notas") or {}).get("pastas", []))
    velha = _LISTAGEM["em"] is None or (agora() - _LISTAGEM["em"]).total_seconds() > LISTAGEM_SEGUNDOS
    if forcar or velha or _LISTAGEM["chave"] != pastas:
        itens = []
        for pasta in pastas:
            try:
                entradas = list(os.scandir(pasta))
            except OSError:
                continue
            for e in entradas:
                if e.is_file() and e.name.lower().endswith((".pdf", ".xml")):
                    nf = ler_assunto_nf(os.path.splitext(e.name)[0])
                    if nf:
                        itens.append((e.name, e.path, e.stat().st_mtime, nf))
        _LISTAGEM.update(em=agora(), chave=pastas, itens=itens)
    return _LISTAGEM["itens"]


def sugestoes_dropbox(sol, cfg, limite=6):
    """NFs das pastas do Dropbox cujo nome bate com o hóspede/tomador: melhor encaixe e mais novas primeiro."""
    raiz = raiz_dropbox(cfg)
    nomes = [sol.get("nome", "")] + list(sol.get("nomes", []))
    alvos = [t for t in (_palavras(n) for n in nomes) if t]
    primeiros = {_primeira_palavra(n) for n in nomes} - {""}
    achadas = []
    for nome, caminho, mtime, nf in listar_notas_dropbox(cfg):
        nota = _nota(_palavras(nf[1]), alvos, primeiros)
        if nota:
            achadas.append({"nome": nome, "nf": nf[0], "modificado": mtime, "nota": nota, "forte": nota == 3,
                            "rel": os.path.relpath(caminho, raiz) if raiz else caminho})
    achadas.sort(key=lambda a: (-a["nota"], -a["modificado"]))
    for a in achadas:
        a["modificado"] = datetime.datetime.fromtimestamp(a["modificado"]).strftime("%d/%m/%Y %H:%M")
    return achadas[:limite]


# ---------- fila compartilhada ----------
def evento(quando, id_envio, ev, pc, quem, dados=None):
    return [_iso(quando), id_envio, ev, pc, quem, json.dumps(dados or {}, ensure_ascii=False)]


def dobrar_fila(linhas):
    """-> {id: {"pedido": dados, "pedido_em", "assumido_por", "resultado": ENVIADO|FALHOU|None, "detalhe", "pc"}}"""
    envios = {}
    for l in linhas[1:]:
        l = list(l) + [""] * (6 - len(l))
        quando, id_envio, ev, pc, quem, dados = (str(v) for v in l[:6])
        try:
            dados = json.loads(dados) if dados else {}
        except ValueError:
            dados = {}
        e = envios.setdefault(id_envio, {"pedido": None, "pedido_em": "", "quem": "", "assumido_por": "",
                                         "resultado": None, "detalhe": "", "pc": ""})
        if ev == PEDIDO and e["pedido"] is None:
            e.update(pedido=dados, pedido_em=quando, quem=quem)
        elif ev == ASSUMIDO and not e["assumido_por"]:
            e["assumido_por"] = pc          # o primeiro gravado vence, como no Assumir da fila
        elif ev in (ENVIADO, FALHOU) and e["resultado"] is None:
            e.update(resultado=ev, detalhe=dados.get("detalhe", ""), pc=pc)
    return envios


def pcs_online(linhas_pcs, agora_=None, segundos=PC_ONLINE_SEGUNDOS):
    """-> {conta: pc} das caixas de PCs com o Painel visto há pouco."""
    agora_ = agora_ or agora()
    contas = {}
    for l in linhas_pcs[1:]:
        l = list(l) + [""] * (4 - len(l))
        pc, _agente, lista, visto = (str(v) for v in l[:4])
        try:
            if agora_ - datetime.datetime.fromisoformat(visto) > datetime.timedelta(seconds=segundos):
                continue
        except ValueError:
            continue
        for c in lista.split(","):
            if c.strip():
                contas.setdefault(c.strip().lower(), pc)
    return contas


def partes_do_anexo(id_envio, nome, conteudo):
    b64 = base64.b64encode(conteudo).decode()
    pedacos = [b64[i:i + TAMANHO_PARTE] for i in range(0, len(b64), TAMANHO_PARTE)] or [""]
    return [[id_envio, i + 1, len(pedacos), nome, p] for i, p in enumerate(pedacos)]


def juntar_anexo(linhas_anexos, id_envio):
    partes = sorted((int(l[1]), l) for l in linhas_anexos[1:] if l and str(l[0]) == id_envio and len(l) >= 5 and l[4])
    if not partes or len(partes) != int(partes[0][1][2]):
        return None, None
    return partes[0][1][3], base64.b64decode("".join(l[4] for _, l in partes))


# ---------- Outlook ----------
def contas_do_outlook():
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    ns = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    return [str(c.SmtpAddress or "").strip().lower() for c in ns.Accounts if c.SmtpAddress]


def enviar_pelo_outlook(conta_de, para, assunto, corpo, anexo):
    """Envia saindo da conta `conta_de` deste Outlook. Levanta erro com mensagem legível."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    outlook = win32com.client.Dispatch("Outlook.Application")
    ns = outlook.GetNamespace("MAPI")
    conta = next((c for c in ns.Accounts if str(c.SmtpAddress or "").strip().lower() == conta_de.lower()), None)
    if conta is None:
        raise RuntimeError(f"a caixa {conta_de} não está no Outlook deste PC")
    mail = outlook.CreateItem(0)
    mail.To = para
    mail.Subject = assunto
    mail.Body = corpo
    mail.Attachments.Add(str(anexo))
    mail._oleobj_.Invoke(*(DISPID_SEND_USING_ACCOUNT, 0, 8, 0, conta))
    mail.Send()
    try:
        ns.SendAndReceive(False)
    except Exception:
        pass


# ---------- pedido ----------
def novo_id():
    return "ENV-" + uuid.uuid4().hex[:10].upper()


def montar_pedido(sol, para, assunto, conta_de, anexo, corpo=None):
    """anexo: {"tipo": "dropbox", "rel": ...} | {"tipo": "planilha", "nome": ...}"""
    nf = ler_assunto_nf(assunto)
    return {"aba": sol["aba"], "carimbo": sol["carimbo"], "email": sol["email"], "hotel": sol["hotel"],
            "nome": sol["nome"], "para": para, "assunto": assunto, "conta_de": conta_de, "anexo": anexo,
            "nf": nf[0] if nf else "",
            "corpo": corpo or CORPO_PADRAO.format(nome=sol["nome"], hotel=sol["hotel"])}


def arquivo_do_pedido(pedido, cfg, linhas_anexos, id_envio):
    """Caminho local do anexo (cópia temporária quando vem da planilha)."""
    anexo = pedido["anexo"]
    if anexo["tipo"] == "local":
        return Path(anexo["caminho"])
    if anexo["tipo"] == "dropbox":
        raiz = raiz_dropbox(cfg)
        caminho = (raiz / anexo["rel"]) if raiz else Path(anexo["rel"])
        if not caminho.exists():
            raise RuntimeError(f"não achei a nota no Dropbox deste PC ({anexo['rel']}) — ele já sincronizou?")
        return caminho
    nome, conteudo = juntar_anexo(linhas_anexos, id_envio)
    if conteudo is None:
        raise RuntimeError("o anexo não chegou inteiro na planilha")
    pasta = Path(tempfile.mkdtemp(prefix="nf_envio_"))
    destino = pasta / os.path.basename(nome or "nota.pdf")
    destino.write_bytes(conteudo)
    return destino


class ServicoEnvio:
    """Roda dentro do Painel de cada PC (thread do laço de atualização)."""

    def __init__(self, backend, cfg, pc, ao_registrar_nf, enviar=None, ler_contas=None, relogio=agora):
        self.backend, self.cfg, self.pc = backend, cfg, pc
        self.central = cfg["planilha_central_id"]
        self.ao_registrar_nf = ao_registrar_nf        # (pedido, quem) -> grava NF/OBS na aba Tratamento
        # resolvidos na hora da chamada (os testes trocam as funções do módulo)
        self.enviar = enviar or (lambda *a: enviar_pelo_outlook(*a))
        self.ler_contas = ler_contas or (lambda: contas_do_outlook())
        self.relogio = relogio
        self.contas, self.contas_lidas_em = [], None
        self.fila, self.pcs_linhas, self.publicado_em = {}, [[]], None
        self.locais = {}                               # id -> resultado de envios feitos aqui (resposta imediata)
        import threading
        self.lock = threading.Lock()

    # chamado a cada volta do laço do Painel, com as abas já lidas no batch da Central
    def tick(self, lidas, agente):
        self.fila = dobrar_fila(lidas.get(ABA_FILA, [[]]))
        self.pcs_linhas = lidas.get(ABA_PCS, [[]])
        if self.contas_lidas_em is None or self.relogio() - self.contas_lidas_em > datetime.timedelta(minutes=10):
            try:
                self.contas = self.ler_contas()
            except Exception as e:
                logger.warning(f"⚠️ Não consegui ler as contas do Outlook ({e})")
            self.contas_lidas_em = self.relogio()
        if self.publicado_em is None or self.relogio() - self.publicado_em > datetime.timedelta(seconds=60):
            self._publicar(agente)
        self.executar_pendentes()
        try:
            listar_notas_dropbox(self.cfg)   # deixa a lista do Dropbox pronta pro "Enviar NF" abrir na hora
        except Exception:
            logger.debug("listagem do Dropbox falhou", exc_info=True)

    def _publicar(self, agente):
        linha = [self.pc, agente, ",".join(self.contas), _iso(self.relogio())]
        idx = next((i for i, l in enumerate(self.pcs_linhas[1:], start=2) if l and str(l[0]) == self.pc), None)
        from sheets import nome_intervalo
        if idx:
            self.backend.escrever(self.central, [(f"{nome_intervalo(ABA_PCS)}!{c}{idx}", v) for c, v in zip("ABCD", linha)])
        else:
            self.backend.anexar_linhas(self.central, ABA_PCS, [linha])
        self.publicado_em = self.relogio()

    def destino_para(self, conta_de):
        """-> (pc que envia | None, motivo)"""
        conta_de = (conta_de or "").lower()
        if conta_de in self.contas:
            return self.pc, ""
        pc = pcs_online(self.pcs_linhas, self.relogio()).get(conta_de)
        if pc:
            return pc, ""
        return None, (f"Nenhum PC ligado agora tem a caixa {conta_de} no Outlook (o Painel do PC dela precisa"
                      f" estar aberto/rodando).")

    def pedir(self, sol, para, assunto, conta_de, anexo_entrada, quem, corpo=None):
        """anexo_entrada: {"tipo": "dropbox", "rel"} | {"tipo": "arquivo", "nome", "conteudo": bytes}"""
        destino, motivo = self.destino_para(conta_de)
        if not destino:
            return {"ok": False, "motivo": motivo, "contas_locais": self.contas}
        id_envio = novo_id()
        if anexo_entrada["tipo"] == "arquivo":
            if len(anexo_entrada["conteudo"]) > MAX_ANEXO_BYTES:
                return {"ok": False, "motivo": "O anexo passa de 8 MB."}
            if destino == self.pc:
                pasta = Path(tempfile.mkdtemp(prefix="nf_envio_"))
                caminho = pasta / os.path.basename(anexo_entrada["nome"])
                caminho.write_bytes(anexo_entrada["conteudo"])
                anexo = {"tipo": "local", "caminho": str(caminho), "nome": anexo_entrada["nome"]}
            else:
                self.backend.anexar_linhas(self.central, ABA_ANEXOS,
                                           partes_do_anexo(id_envio, anexo_entrada["nome"], anexo_entrada["conteudo"]))
                anexo = {"tipo": "planilha", "nome": anexo_entrada["nome"]}
        else:
            anexo = {"tipo": "dropbox", "rel": anexo_entrada["rel"]}
        pedido = montar_pedido(sol, para, assunto, conta_de, anexo, corpo)
        pedido["pc_destino"] = destino
        self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, PEDIDO, self.pc, quem, pedido)])
        if destino == self.pc:
            import threading
            self.fila[id_envio] = {"pedido": pedido, "pedido_em": _iso(self.relogio()), "quem": quem,
                                   "assumido_por": "", "resultado": None, "detalhe": "", "pc": ""}
            threading.Thread(target=self._executar, args=(id_envio, self.fila[id_envio]), daemon=True).start()
        return {"ok": True, "id": id_envio, "destino": destino}

    def executar_pendentes(self):
        for id_envio, e in list(self.fila.items()):
            p = e["pedido"]
            if not p or e["resultado"] or p.get("pc_destino") != self.pc or id_envio in self.locais:
                continue
            if e["assumido_por"] and e["assumido_por"] != self.pc:
                continue
            if e["assumido_por"] == self.pc:
                continue   # já assumido por este PC numa volta anterior: não reenvia
            self._executar(id_envio, e)

    def _executar(self, id_envio, e):
        with self.lock:
            if id_envio in self.locais:
                return
            self.locais[id_envio] = {"estado": "enviando"}
        p = e["pedido"]
        self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, ASSUMIDO, self.pc, e["quem"])])
        try:
            anexos = self.backend.ler_abas(self.central, [ABA_ANEXOS])[0].get(ABA_ANEXOS, [[]]) if p["anexo"]["tipo"] == "planilha" else [[]]
            arquivo = arquivo_do_pedido(p, self.cfg, anexos, id_envio)
            self.enviar(p["conta_de"], p["para"], p["assunto"], p["corpo"], arquivo)
        except Exception as erro:
            detalhe = str(erro)[:300]
            logger.warning(f"⚠️ Envio {id_envio} falhou: {detalhe}")
            self.backend.anexar_linhas(self.central, ABA_FILA,
                                       [evento(self.relogio(), id_envio, FALHOU, self.pc, e["quem"], {"detalhe": detalhe})])
            self.locais[id_envio] = {"estado": "falhou", "detalhe": detalhe, "pc": self.pc}
            return
        self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, ENVIADO, self.pc, e["quem"])])
        self.locais[id_envio] = {"estado": "enviado", "pc": self.pc}
        logger.info(f"📧 {id_envio}: \"{p['assunto']}\" enviado de {p['conta_de']} para {p['para']}")
        try:
            self.ao_registrar_nf(p, e["quem"])
        except Exception:
            logger.exception("NF enviada, mas não consegui registrar na aba Tratamento")
        if p["anexo"]["tipo"] == "planilha":
            self._apagar_anexo(id_envio)

    def _apagar_anexo(self, id_envio):
        from sheets import nome_intervalo
        linhas = self.backend.ler_abas(self.central, [ABA_ANEXOS])[0].get(ABA_ANEXOS, [[]])
        alvos = [i for i, l in enumerate(linhas[1:], start=2) if l and str(l[0]) == id_envio]
        if alvos:
            self.backend.escrever(self.central, [(f"{nome_intervalo(ABA_ANEXOS)}!E{i}", "") for i in alvos])

    def situacao(self, id_envio, fila_fresca=None):
        """-> {"estado": aguardando|enviando|enviado|falhou|sem_resposta, "detalhe", "pc"}"""
        if id_envio in self.locais and self.locais[id_envio]["estado"] != "enviando":
            return self.locais[id_envio]
        e = (fila_fresca or self.fila).get(id_envio)
        if not e:
            return {"estado": "aguardando", "detalhe": ""}
        if e["resultado"] == ENVIADO:
            return {"estado": "enviado", "pc": e["pc"]}
        if e["resultado"] == FALHOU:
            return {"estado": "falhou", "detalhe": e["detalhe"], "pc": e["pc"], "contas_locais": self.contas}
        if e["assumido_por"]:
            return {"estado": "enviando", "pc": e["assumido_por"]}
        try:
            espera = (self.relogio() - datetime.datetime.fromisoformat(e["pedido_em"])).total_seconds()
        except ValueError:
            espera = 0
        if espera > SEM_RESPOSTA_SEGUNDOS:
            return {"estado": "sem_resposta", "contas_locais": self.contas,
                    "detalhe": f"O PC {e['pedido'].get('pc_destino')} não respondeu em {SEM_RESPOSTA_SEGUNDOS}s "
                               f"(desligado ou Painel fechado)."}
        return {"estado": "aguardando", "pc": e["pedido"].get("pc_destino", "")}
