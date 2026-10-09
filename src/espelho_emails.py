"""Espelho do Outlook de cada PC: Caixa de Entrada e Itens Enviados das caixas dos hotéis.

Pedido do usuário (08/10/2026): o Painel é uma ponte entre os 4 computadores e NÃO guarda histórico — quem guarda
é o Outlook. Cada PC só tem no Outlook as caixas dos hotéis dele; o robô (conferente) de cada PC reflete as caixas
em abas de passagem da Central, reescritas a cada volta (só quando muda). Nada se acumula.

- Caixa de Entrada: o que segue SEM RESPOSTA até 14 dias (de 7 a 14 dias vira "Urgência" no Painel). Passou de
  14 dias, sai do espelho (o Outlook não é mexido).
- Itens Enviados: últimas 24 h.
- Resolvido = respondido (saiu e-mail de uma caixa deste PC pra quem escreveu, depois que ele escreveu) OU
  excluído (saiu da Caixa de Entrada). Resolvido some do espelho.
- Fica de fora: o próprio robô (as "Solicitação NF - ..." com Código de envio) e remetente automático
  (no-reply, Booking, Decolar, lista com List-Unsubscribe).
- Duas abas: Correio_<PC> (o resumo, leve: o Painel lê a cada 15 s) e CorreioTexto_<PC> (o texto inteiro; o
  normal é o Painel pedir o texto ao vivo pro PC dono pela rede — esta aba é a reserva com o PC dono desligado).
- Linhas "resposta": último envio de cada caixa deste PC pra cada endereço (14 dias). O Painel junta as dos
  4 PCs: e-mail respondido pela caixa de OUTRO PC também some.
- Lido / não lido / excluído pelo Painel ficam na aba Eventos_Correio (valem pra equipe toda; não mexem no
  Outlook, a não ser Excluir, que vira um pedido pro PC dono). Faxina: 3 dias.
"""
import datetime
import hashlib
import json
import re
import socket
import time

from arquivos import salvar_json
from config import PASTA_ESTADO
from controle_nf import reclama_falta_nota
from log_util import configurar_logging
from tratamento import normalizar

logger = configurar_logging("espelho_emails")

PREFIXO_ABA = "Correio_"
PREFIXO_TEXTOS = "CorreioTexto_"
CABECALHO = ["ID", "Pasta", "Caixa", "Hotel", "De", "Nome", "Para", "Assunto", "Quando", "Anexos", "Prévia",
             "PC", "Atualizado", "Quartos", "Falta nota", "Classes", "Versão texto", "Análise"]
CAB_TEXTOS = ["ID", "Texto", "Citado"]
ABA_EVENTOS = "Eventos_Correio"
CAB_EVENTOS = ["Quando", "ID", "Ação", "Agente", "PC"]
EVENTOS = ("LIDO", "NAO_LIDO", "EXCLUIR")
ENTRADA, ENVIADO, RESPOSTA = "entrada", "enviado", "resposta"
JANELA_DIAS = 14                  # sem resposta há mais que isso: sai do espelho
RECENTE_HORAS = 24                # Itens Enviados: só as últimas 24 h
URGENCIA_DIAS = 7                 # sem resposta há mais que isso: aba Urgência
MAX_PDF_BYTES = 3 * 1024 * 1024   # voucher/recibo de reserva é pequeno; PDF grande não é lido
MAX_PDFS = 4
CAMINHO_ESTADO = PASTA_ESTADO / "espelho_emails.json"
VERSAO_ESTADO = 2
MAX_TEXTO = 15000                 # célula do Sheets aceita 50 mil
MAX_CITADO = 8000
MAX_TEXTO_ENVIADO = 4000
MAX_PREVIA = 220
MAX_RESPOSTAS = 45000             # célula das respostas (limite do Sheets: 50 mil)
REVARRER_HORAS = 24               # releitura completa 1x por dia
FOLGA_MINUTOS = 10
CADASTRO_SEGUNDOS = 30 * 60       # Cadastro_Hoteis muda pouco: relido a cada 30 min (cota)
REMETENTES_AUTOMATICOS = ("no-reply", "noreply", "naoresponda", "nao-responda", "nao_responda", "donotreply",
                          "mailer-daemon", "postmaster", "notifica", "newsletter", "marketing", "bounce")
DOMINIOS_AUTOMATICOS = ("booking.com", "decolar.com", "expedia", "airbnb", "hotels.com", "trivago", "omnibees",
                        "hbook", "cloudbeds", "facebookmail", "google.com", "microsoft.com", "linkedin")
PR_CABECALHOS = "http://schemas.microsoft.com/mapi/proptag/0x007D001F"
_HISTORICO = re.compile(   # "Em qui., 8 de out. ... <x@y>\nescreveu:" (o Gmail quebra a linha antes do "escreveu:")
    r"^\s*(?:De:|From:|-{2,}\s*(?:Mensagem original|Original Message)|_{5,}|"
    r"Em [^\n]{5,160}(?:\n[^\n]{0,80})?escreveu:|On [^\n]{5,160}(?:\n[^\n]{0,80})?wrote:)",
    re.IGNORECASE | re.MULTILINE)


def nome_aba(pc=None):
    return PREFIXO_ABA + (pc or socket.gethostname())


def nome_aba_textos(pc=None):
    return PREFIXO_TEXTOS + (pc or socket.gethostname())


def id_do_email(entry_id):
    return hashlib.sha1(entry_id.encode("utf-8", "replace")).hexdigest()[:12]


def dividir_historico(texto):
    """-> (o que a pessoa escreveu, as mensagens antigas coladas embaixo)."""
    texto = (texto or "").replace("\r\n", "\n").replace("\r", "\n")
    m = _HISTORICO.search(texto)
    if m and m.start() > 0:
        proprio, citado = texto[:m.start()], texto[m.start():]
    else:
        proprio, citado = texto, ""
    limpa = lambda s, n: re.sub(r"\n{3,}", "\n\n", s).strip()[:n]
    return limpa(proprio, MAX_TEXTO), limpa(citado, MAX_CITADO)


def sem_historico(texto):
    """Corta as mensagens antigas coladas embaixo (De:/From:/Em ... escreveu:)."""
    return dividir_historico(texto)[0]


def previa(texto):
    return re.sub(r"\s+", " ", texto or "").strip()[:MAX_PREVIA]


def e_automatico(endereco, cabecalhos=""):
    endereco = (endereco or "").lower()
    usuario, _, dominio = endereco.partition("@")
    if not dominio:
        return True
    if any(p in usuario for p in REMETENTES_AUTOMATICOS) or any(d in dominio for d in DOMINIOS_AUTOMATICOS):
        return True
    return "list-unsubscribe:" in (cabecalhos or "").lower()


def e_do_robo(de, corpo, rede, remetente_antigo=""):
    """E-mail que o próprio robô manda (Solicitação NF com Código de envio) ou o robô antigo do Gmail."""
    de = (de or "").lower()
    return bool(remetente_antigo and de == remetente_antigo.lower()) or (de in rede and "Código de envio: NF-" in (corpo or ""))


# ---------- classificação por regras (o agente de IA do usuário entra aqui depois) ----------
_CORRIGIR = re.compile(   # qualquer pedido de refazer a NF vai pra Urgência (usuário, 08/10/2026)
    r"\b(?:errad[oa]s?|incorret[oa]s?|equivocad|retific|corrig|corre[cç][aã]o|cancel|substitu|refaz|refeita|reemit|estorn)"
    r"|valor\s+(?:a\s+mais|a\s+menos|errado|divergente|diferente)|\bdiverg|emitir\s+(?:novamente|de\s+novo|outra)"
    r"|\bnova\s+nota\b|\bnota\s+nova\b|\boutra\s+nota\b|n[aã]o\s+(?:confere|bate|corresponde|est[aá]\s+certo)", re.I)
_COBRANCA = re.compile(r"\bn[aã]o\s+(?:recebi|recebemos|chegou|veio)|\bcad[eê]\b|\bainda\s+(?:aguardo|n[aã]o)|"
                       r"\breiter|\bnovamente\b|\burgente\b|\bprazo\b", re.I)
_COMPLEMENTAR = re.compile(r"\b(?:falt\w*|outr[ao]s?|mais|restantes?|adiciona\w*|demais)\b[^.\n]{0,40}"
                           r"\b(?:di[aá]rias?|consumos?|noites?|pernoites?|frigobar|pagamentos?)\b", re.I)
_PEDIDO_NF = re.compile(r"\b(?:preciso|precisamos|solicit|gostaria|favor|poderia|podem|enviar|emitir|emiss[aã]o)"
                        r"[^.\n]{0,60}\b(?:nota|nf|nfs-?e|nfe)\b|\bnota\s+fiscal\b", re.I)
_DOCUMENTO = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b|raz[aã]o\s+social|"
                        r"\bcnpj\b|\bcpf\b|inscri[cç][aã]o\s+(?:estadual|municipal)", re.I)
CLASSES = {"corrigir": "Corrigir / cancelar NF", "complementar": "Nota complementar", "cobranca": "Cobrança",
           "dados_tomador": "Dados do tomador", "pedido_nf": "Pedido de NF"}


def classificar(assunto, texto, anexos=()):
    """Etiquetas do e-mail (ordem de prioridade). "corrigir" vai pra Urgência na hora; "faltou diária/consumo" é
    nota complementar (tratativa), não cancelamento — regra do usuário (08/10/2026)."""
    t = f"{assunto or ''}\n{texto or ''}"
    saida = []
    if _CORRIGIR.search(t):
        saida.append("corrigir")
    if _COMPLEMENTAR.search(t):
        saida.append("complementar")
    elif _COBRANCA.search(t):
        saida.append("cobranca")
    if _DOCUMENTO.search(texto or ""):
        saida.append("dados_tomador")
    if _PEDIDO_NF.search(t) or any(str(a).lower().endswith(".pdf") and "voucher" in str(a).lower() for a in anexos):
        saida.append("pedido_nf")
    return saida


def remetente(item):
    endereco = str(getattr(item, "SenderEmailAddress", "") or "").strip().lower()
    if "@" in endereco:
        return endereco
    try:
        return item.Sender.GetExchangeUser().PrimarySmtpAddress.lower()
    except Exception:
        return endereco


def _data(valor):
    try:
        return datetime.datetime(valor.year, valor.month, valor.day, valor.hour, valor.minute, valor.second)
    except Exception:
        return None


def enderecos(item):
    saida = set()
    try:
        for r in item.Recipients:
            e = (r.Address or "").strip().lower()
            if "@" not in e:
                try:
                    e = r.AddressEntry.GetExchangeUser().PrimarySmtpAddress.lower()
                except Exception:
                    continue
            saida.add(e)
    except Exception:
        pass
    return saida


def anexos_do_item(item):
    try:
        return [a.FileName for a in item.Attachments if not str(a.FileName).lower().startswith("image0")]
    except Exception:
        return []


def quartos_dos_anexos(item):
    """Lê os PDFs anexados (voucher/recibo de reserva) -> (quartos, [nomes]). Sem OCR: só o texto do PDF."""
    import os
    import tempfile
    from controle_nf import quartos_da_reserva
    melhor = (0, [])
    try:
        anexos = [item.Attachments.Item(i) for i in range(1, item.Attachments.Count + 1)]
    except Exception:
        return melhor
    pdfs = [a for a in anexos if str(a.FileName).lower().endswith(".pdf") and (a.Size or 0) <= MAX_PDF_BYTES]
    for a in pdfs[:MAX_PDFS]:
        pasta = tempfile.mkdtemp(prefix="voucher_")
        caminho = os.path.join(pasta, "anexo.pdf")
        try:
            a.SaveAsFile(caminho)
            from pypdf import PdfReader
            texto = "\n".join((p.extract_text() or "") for p in PdfReader(caminho).pages[:4])
            achado = quartos_da_reserva(texto)
            if achado[0] > melhor[0] or (achado[0] == melhor[0] and len(achado[1]) > len(melhor[1])):
                melhor = achado
        except Exception as e:
            logger.debug(f"anexo ilegível ({a.FileName}): {e}")
        finally:
            try:
                os.remove(caminho)
                os.rmdir(pasta)
            except OSError:
                pass
    return melhor


def textos_pdf_anexos(item, maximo=MAX_PDFS):
    """[(nome, texto)] dos PDFs anexados (pequenos). Só lê; o arquivo temporário é apagado em seguida."""
    import os
    import tempfile
    saida = []
    try:
        anexos = [item.Attachments.Item(i) for i in range(1, item.Attachments.Count + 1)]
    except Exception:
        return saida
    for a in [a for a in anexos if str(a.FileName).lower().endswith(".pdf") and (a.Size or 0) <= MAX_PDF_BYTES][:maximo]:
        pasta = tempfile.mkdtemp(prefix="nf_anexo_")
        caminho = os.path.join(pasta, "anexo.pdf")
        try:
            a.SaveAsFile(caminho)
            from pypdf import PdfReader
            texto = "\n".join((p.extract_text() or "") for p in PdfReader(caminho).pages[:3])
            if not texto.strip():   # PDF que é imagem (foto/scan da nota): leitor de texto do Windows
                import conferente
                texto = conferente._texto_ocr(caminho)
            saida.append((str(a.FileName), texto))
        except Exception as e:
            logger.debug(f"anexo ilegível ({a.FileName}): {e}")
        finally:
            try:
                os.remove(caminho)
                os.rmdir(pasta)
            except OSError:
                pass
    return saida


def marcar_dividida_no_outlook(item):
    """Etiqueta azul "Nota dividida" no próprio e-mail do hóspede (a mesma dos e-mails do robô)."""
    from controle_nf import CATEGORIA_DIVIDIDA
    atuais = [c.strip() for c in re.split(r"[;,]", item.Categories or "") if c.strip()]
    if CATEGORIA_DIVIDIDA not in atuais:
        item.Categories = ", ".join(atuais + [CATEGORIA_DIVIDIDA])
        item.Save()


def texto_quartos(e):
    n, nomes = e.get("quartos", [0, []]) if isinstance(e.get("quartos"), list) else (0, [])
    return f"{n}|{'; '.join(nomes)}" if n else ""


def resolver(itens, enviados, agora):
    """Tira o que foi respondido (some do Painel: o Outlook guarda), o que passou de 14 dias sem resposta e os
    enviados com mais de 24 h. enviados: {endereço: último envio (datetime)}."""
    saida = {}
    for i, e in itens.items():
        try:
            quando = datetime.datetime.fromisoformat(e["quando"])
        except (ValueError, KeyError):
            continue
        idade = agora - quando
        if e["pasta"] == ENVIADO:
            if idade <= datetime.timedelta(hours=RECENTE_HORAS):
                saida[i] = e
            continue
        resposta = enviados.get(e["de"])
        if resposta and resposta > quando:
            continue
        if idade <= datetime.timedelta(days=JANELA_DIAS):
            saida[i] = e
    return saida


def versao_textos(itens):
    return hashlib.sha1(json.dumps(sorted((i, e.get("texto", ""), e.get("citado", "")) for i, e in itens.items()),
                                   ensure_ascii=False).encode()).hexdigest()[:10]


def linhas_da_aba(itens, enviados, pc, agora=None, versao=""):
    agora = agora or datetime.datetime.now()
    carimbo = agora.isoformat(timespec="seconds")
    corpo = sorted(itens.values(), key=lambda e: e["quando"], reverse=True)
    linhas = [CABECALHO]
    for e in corpo:
        entrada = e["pasta"] == ENTRADA
        linhas.append([e["id"], e["pasta"], e["caixa"], e["hotel"], e["de"], e.get("nome", ""), e.get("para", ""),
                       e["assunto"], e["quando"], ", ".join(e.get("anexos", [])), previa(e.get("texto", "")),
                       pc, carimbo, texto_quartos(e) if entrada else "",
                       reclama_falta_nota(e.get("texto", "")) if entrada else "",
                       " ".join(e.get("classes", [])) if entrada else "", versao, e.get("analise", "") if entrada else ""])
    # respostas: TODAS numa célula só ("endereço=quando;..."), as mais novas primeiro — 400 linhas viravam 80 KB
    limite = agora - datetime.timedelta(days=JANELA_DIAS)
    pares, tamanho = [], 0
    for endereco, quando in sorted(enviados.items(), key=lambda x: x[1], reverse=True):
        par = f"{endereco}={quando.isoformat(timespec='seconds')}"
        if quando < limite or tamanho + len(par) > MAX_RESPOSTAS:
            break
        pares.append(par)
        tamanho += len(par) + 1
    if pares:
        linhas.append(["r:*", RESPOSTA, "", "", "", "", "", "", "", "", ";".join(pares), pc, carimbo, "", "", "", versao, ""])
    return linhas


def linhas_textos(itens):
    corpo = sorted(itens.values(), key=lambda e: e["quando"], reverse=True)
    return [CAB_TEXTOS] + [[e["id"], e.get("texto", ""), e.get("citado", "")] for e in corpo]


def ler_textos(linhas):
    """Aba CorreioTexto_<PC> -> {id: (texto, citado)}"""
    return {str(l[0]): (str(l[1]) if len(l) > 1 else "", str(l[2]) if len(l) > 2 else "")
            for l in (linhas or [])[1:] if l and str(l[0]).strip()}


def ler_aba(linhas):
    """Linhas de uma aba Correio_<PC> -> [dict] (entrada, enviado e resposta)."""
    chaves = ["id", "pasta", "caixa", "hotel", "de", "nome", "para", "assunto", "quando", "anexos", "previa",
              "pc", "atualizado", "quartos", "falta_nota", "classes", "versao_texto", "analise"]
    saida = []
    for l in (linhas or [])[1:]:
        if not l or not str(l[0]).strip():
            continue
        l = list(l) + [""] * (len(chaves) - len(l))
        e = dict(zip(chaves, (str(v) for v in l[:len(chaves)])))
        e["anexos"] = [a for a in e["anexos"].split(", ") if a]
        n, _, nomes = e["quartos"].partition("|")
        e["quartos"] = int(n) if n.strip().isdigit() else 0
        e["hospedes_quartos"] = [x for x in nomes.split("; ") if x]
        e["classes"] = [c for c in e["classes"].split() if c]
        e["falta_nota"] = e["falta_nota"].upper() == "TRUE"
        e["recebido"] = e["quando"]   # nome antigo (NF do Dropbox e conversa do hóspede usam)
        if e["pasta"] == RESPOSTA and e["id"] == "r:*":
            for par in e["previa"].split(";"):
                endereco, _, quando = par.partition("=")
                if endereco and quando:
                    saida.append({**e, "id": f"r:{endereco}", "de": endereco, "quando": quando, "previa": ""})
            continue
        saida.append(e)
    return saida


def dobrar_eventos(linhas):
    """Aba Eventos_Correio -> {id: {lido, lido_por, lido_em, excluido, excluido_por}} (vale o último de cada tipo)."""
    estado = {}
    for l in (linhas or [])[1:]:
        l = [str(v) for v in l] + [""] * 5
        quando, i, acao, agente, _pc = l[:5]
        if not i or acao not in EVENTOS:
            continue
        e = estado.setdefault(i, {"lido": False, "lido_por": "", "lido_em": "", "excluido": False, "excluido_por": ""})
        if acao == "LIDO":
            e.update(lido=True, lido_por=agente, lido_em=quando)
        elif acao == "NAO_LIDO":
            e.update(lido=False, lido_por="", lido_em="")
        elif acao == "EXCLUIR":
            e.update(excluido=True, excluido_por=agente)
    return estado


def evento(i, acao, agente, pc=None, quando=None):
    return [(quando or datetime.datetime.now()).isoformat(timespec="seconds"), i, acao, agente, pc or socket.gethostname()]


class Espelho:
    """Mantém o espelho deste PC (em estado/espelho_emails.json) e publica na Central."""

    def __init__(self, backend, cfg, relogio=datetime.datetime.now):
        self.backend, self.cfg, self.relogio = backend, cfg, relogio
        self.central = cfg["planilha_central_id"]
        try:
            self.estado = json.load(open(CAMINHO_ESTADO, encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            self.estado = {}
        if self.estado.get("versao") != VERSAO_ESTADO:
            self.estado = {"vouchers": self.estado.get("vouchers", {})}   # formato antigo: relê tudo
        self.itens = self.estado.get("itens", {})
        self._cadastro = None

    def _caixas(self):
        """{caixa: 'HOTEL A / HOTEL B'} do Cadastro_Hoteis (guardado 30 min)."""
        if self._cadastro and time.monotonic() - self._cadastro[0] < CADASTRO_SEGUNDOS:
            return self._cadastro[1]
        aba = self.cfg["aba_cadastro_hoteis"]
        linhas = self.backend.ler_abas(self.central, [aba])[0].get(aba, [])
        por_caixa = {}
        for l in linhas[1:]:
            if len(l) > 1 and "@" in str(l[1]):
                por_caixa.setdefault(str(l[1]).strip().lower(), []).append(str(l[0]).strip())
        self._cadastro = (time.monotonic(), {c: " / ".join(dict.fromkeys(h)) for c, h in por_caixa.items()})
        return self._cadastro[1]

    def volta(self, namespace):
        agora = self.relogio()
        caixas = self._caixas()
        antigo = str((self.cfg.get("robo_antigo") or {}).get("remetente", "")).lower()
        rede = set(caixas) | {str(self.cfg.get("conta_remetente", "")).lower(), antigo}
        ultima = self.estado.get("ultima_volta")
        completa = (not ultima or agora - datetime.datetime.fromisoformat(self.estado.get("ultima_completa", ultima))
                    > datetime.timedelta(hours=REVARRER_HORAS))
        inicio = (agora - datetime.timedelta(days=JANELA_DIAS)) if completa else \
            datetime.datetime.fromisoformat(ultima) - datetime.timedelta(minutes=FOLGA_MINUTOS)
        if completa:
            self.itens = {}
        limite = agora - datetime.timedelta(days=JANELA_DIAS)
        enviados = {e: q for e, q in self.estado.get("enviados", {}).items() if q >= limite.isoformat()}
        vouchers = dict(self.estado.get("vouchers", {}))   # {id: [quartos, nomes]} — PDF lido uma vez só
        pastas_entrada = {}   # caixa -> EntryID da Caixa de Entrada (pra saber se o e-mail foi excluído/movido)
        for conta in namespace.Accounts:
            caixa = str(conta.SmtpAddress or "").strip().lower()
            if caixa not in caixas:
                continue
            try:
                loja = conta.DeliveryStore
                pasta_entrada = loja.GetDefaultFolder(6)
                pastas_entrada[caixa] = pasta_entrada.EntryID
                recebidos = pasta_entrada.Items.Restrict(f"[ReceivedTime] >= '{inicio:%d/%m/%Y %H:%M}'")
                saidos = loja.GetDefaultFolder(5).Items.Restrict(f"[SentOn] >= '{inicio:%d/%m/%Y %H:%M}'")
            except Exception as e:
                logger.warning(f"⚠️ Não abri as pastas de {caixa}: {e}")
                continue
            for item in saidos:
                try:
                    self._enviado(item, caixa, caixas, enviados, agora)
                except Exception as e:
                    logger.debug(f"enviado ilegível em {caixa}: {e}")
            for item in recebidos:
                try:
                    self._recebido(item, caixa, caixas, rede, antigo, vouchers)
                except Exception as e:
                    logger.debug(f"e-mail ilegível em {caixa}: {e}")
        if not completa:
            self._tirar_excluidos(namespace, pastas_entrada)
        nf_marcadas = self._marcar_nf_emitida(namespace)
        enviados_dt = {e: datetime.datetime.fromisoformat(q) for e, q in enviados.items()}
        self.itens = resolver(self.itens, enviados_dt, agora)
        self.estado = {"versao": VERSAO_ESTADO, "ultima_volta": agora.isoformat(timespec="seconds"),
                       "ultima_completa": agora.isoformat(timespec="seconds") if completa
                       else self.estado.get("ultima_completa", agora.isoformat(timespec="seconds")),
                       "itens": self.itens, "enviados": enviados,
                       "vouchers": {i: v for i, v in vouchers.items() if i in self.itens},
                       "publicado": self.estado.get("publicado", ""),
                       "publicado_textos": self.estado.get("publicado_textos", ""),
                       "nf_marcadas": {i: v for i, v in nf_marcadas.items() if i in self.itens}}
        salvar_json(CAMINHO_ESTADO, self.estado, indent=None)
        self.publicar(enviados_dt)
        return len(self.itens)

    def _enviado(self, item, caixa, caixas, enviados, agora):
        if getattr(item, "Class", 43) != 43:
            return
        quando = _data(item.SentOn)
        destinos = enderecos(item)
        for e in destinos:
            if quando and quando.isoformat() > enviados.get(e, ""):
                enviados[e] = quando.isoformat(timespec="seconds")
        i = id_do_email(item.EntryID)
        if not quando or i in self.itens or agora - quando > datetime.timedelta(hours=RECENTE_HORAS):
            return
        corpo = str(item.Body or "")
        if "Código de envio: NF-" in corpo and str(item.Subject or "").startswith("Solicitação NF"):
            return   # e-mail do robô pra caixa do hotel
        self.itens[i] = {"id": i, "entry_id": item.EntryID, "pasta": ENVIADO, "caixa": caixa,
                         "hotel": caixas.get(caixa, ""), "de": caixa, "nome": "", "para": ", ".join(sorted(destinos)),
                         "assunto": str(item.Subject or ""), "quando": quando.isoformat(timespec="seconds"),
                         "anexos": anexos_do_item(item), "texto": dividir_historico(corpo)[0][:MAX_TEXTO_ENVIADO],
                         "citado": ""}

    def _recebido(self, item, caixa, caixas, rede, antigo, vouchers):
        if getattr(item, "Class", 43) != 43:
            return
        i = id_do_email(item.EntryID)
        if i in self.itens:
            return
        de = remetente(item)
        corpo = str(item.Body or "")
        if e_do_robo(de, corpo, rede, antigo):
            return
        try:
            cabecalhos = item.PropertyAccessor.GetProperty(PR_CABECALHOS)
        except Exception:
            cabecalhos = ""
        if e_automatico(de, cabecalhos):
            return
        recebido = _data(item.ReceivedTime)
        if not recebido:
            return
        anexos = anexos_do_item(item)
        if i not in vouchers:   # voucher com 2+ quartos = nota dividida (lido 1 vez por e-mail)
            n, nomes = quartos_dos_anexos(item) if item.Attachments.Count else (0, [])
            vouchers[i] = [n, nomes]
            if n >= 2:
                try:
                    marcar_dividida_no_outlook(item)
                except Exception as e:
                    logger.debug(f"categoria no Outlook: {e}")
                logger.info(f"🔀 Nota dividida pelo voucher: {n} quartos ({'; '.join(nomes)}) · "
                            f"{str(item.Subject or '')[:60]} ({caixa})")
        proprio, citado = dividir_historico(corpo)
        classes = classificar(item.Subject, proprio, anexos)
        analise = self._analisar(item, caixas.get(caixa, ""), str(item.SenderName or ""), str(item.Subject or ""),
                                 proprio, recebido) if "corrigir" in classes else ""
        self.itens[i] = {"id": i, "entry_id": item.EntryID, "pasta": ENTRADA, "caixa": caixa,
                         "hotel": caixas.get(caixa, ""), "de": de, "nome": str(item.SenderName or ""),
                         "para": caixa, "assunto": str(item.Subject or ""),
                         "quando": recebido.isoformat(timespec="seconds"), "anexos": anexos,
                         "texto": proprio, "citado": citado, "quartos": vouchers[i],
                         "classes": classes, "analise": analise}

    def _analisar(self, item, hotel, nome, assunto, texto, recebido):
        """Pedido de correção: abre a NF (anexada ao e-mail ou no Dropbox) e cruza com o que o cliente escreveu."""
        try:
            import analise_nf
            import envio_nf
            e = {"nome": nome, "hotel": hotel, "assunto": assunto, "texto": texto,
                 "recebido": recebido.isoformat(timespec="seconds")}
            itens = envio_nf.listar_notas_dropbox(self.cfg)
            achadas = envio_nf.notas_do_email(e, self.cfg)
            return analise_nf.analisar(e, texto, itens, achadas, textos_pdf_anexos(item))["resumo"]
        except Exception as erro:
            logger.debug(f"análise da NF: {erro}")
            return ""

    def _marcar_nf_emitida(self, namespace):
        """A NF do hóspede apareceu no Dropbox: etiqueta "🧾 NF emitida" no e-mail dele, no Outlook deste PC
        (pela reserva ou pelo nome, conferido no PDF). Cada e-mail é conferido de novo só quando a pasta muda."""
        marcadas = dict(self.estado.get("nf_marcadas", {}))
        try:
            import envio_nf
            from controle_nf import CATEGORIA_NF_EMITIDA
            envio_nf.listar_notas_dropbox(self.cfg)
            listagem = str(envio_nf._LISTAGEM.get("em"))
        except Exception as erro:
            logger.debug(f"Dropbox indisponível pra etiqueta de NF: {erro}")
            return marcadas
        checadas = getattr(self, "_checadas", {})
        for i, e in self.itens.items():
            if e["pasta"] != ENTRADA or i in marcadas or checadas.get(i) == listagem:
                continue
            checadas[i] = listagem
            try:
                notas = envio_nf.notas_do_email({**e, "recebido": e["quando"]}, self.cfg)
                if not notas:
                    continue
                item = namespace.GetItemFromID(e["entry_id"])
                atuais = [c.strip() for c in re.split(r"[;,]", item.Categories or "") if c.strip()]
                if CATEGORIA_NF_EMITIDA not in atuais:
                    item.Categories = ", ".join(atuais + [CATEGORIA_NF_EMITIDA])
                    item.Save()
                marcadas[i] = [str(n.get("nf", "")) for n in notas]
                logger.info(f"🧾 NF {', '.join(marcadas[i])} no Dropbox → etiqueta no e-mail de {e.get('nome') or e['de']} "
                            f"({e['hotel']})")
            except Exception as erro:
                logger.debug(f"etiqueta de NF emitida ({e.get('de')}): {erro}")
        self._checadas = checadas
        return marcadas

    def _tirar_excluidos(self, namespace, pastas_entrada):
        """E-mail que saiu da Caixa de Entrada (excluído ou movido) sai do espelho: conta como resolvido."""
        for i, e in list(self.itens.items()):
            if e["pasta"] != ENTRADA or e["caixa"] not in pastas_entrada:
                continue
            try:
                item = namespace.GetItemFromID(e["entry_id"])
                if item.Parent.EntryID != pastas_entrada[e["caixa"]]:
                    del self.itens[i]
            except Exception:
                del self.itens[i]

    def publicar(self, enviados_dt=None):
        """Duas abas, cada uma só regravada quando muda: o resumo (leve) e os textos (pesada, muda menos)."""
        pc = socket.gethostname()
        if enviados_dt is None:
            enviados_dt = {e: datetime.datetime.fromisoformat(q) for e, q in self.estado.get("enviados", {}).items()}
        versao = versao_textos(self.itens)
        mudou = False
        if versao != self.estado.get("publicado_textos"):
            try:
                self.backend.substituir_aba(self.central, nome_aba_textos(pc), linhas_textos(self.itens))
                self.estado["publicado_textos"] = versao
                mudou = True
            except Exception as e:
                logger.warning(f"⚠️ Não consegui publicar os textos dos e-mails ({e})")
                versao = self.estado.get("publicado_textos", "")
        linhas = linhas_da_aba(self.itens, enviados_dt, pc, self.relogio(), versao)
        assinatura = hashlib.sha1(json.dumps([l[:12] + l[13:] for l in linhas], ensure_ascii=False).encode()).hexdigest()
        if assinatura != self.estado.get("publicado"):
            try:
                self.backend.substituir_aba(self.central, nome_aba(pc), linhas)
                self.estado["publicado"] = assinatura
                mudou = True
            except Exception as e:
                logger.warning(f"⚠️ Não consegui publicar o espelho de e-mails ({e})")
        if mudou:
            salvar_json(CAMINHO_ESTADO, self.estado, indent=None)


def item_local(id_email):
    """O e-mail espelhado neste PC (com entry_id, texto e citado) — só existe no PC dono da caixa."""
    try:
        estado = json.load(open(CAMINHO_ESTADO, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    return (estado.get("itens") or estado.get("pendentes") or {}).get(id_email, {})


def entry_do_email(id_email):
    """EntryID (só existe neste PC) do e-mail espelhado — pra responder, encaminhar ou excluir pelo próprio Outlook."""
    return item_local(id_email).get("entry_id", "")


def chave_de_busca(e):
    return normalizar(" ".join([e.get("nome", ""), e.get("de", ""), e.get("assunto", ""), e.get("hotel", ""),
                                e.get("previa", "")]))
