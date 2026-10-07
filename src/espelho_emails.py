"""Espelho dos e-mails de hóspedes ainda sem resposta, das caixas dos hotéis deste PC.

Pedido do usuário (07/10/2026): uma aba "E-mails" no Painel com o que os hóspedes escrevem direto
(o formulário do QR code só traz o que é pré-programado). Cada PC só lê o próprio Outlook, então o
robô (conferente) de cada PC reflete os PENDENTES numa aba de passagem da Central, Emails_<PC>,
reescrita a cada volta — não é histórico: respondeu, o e-mail some na volta seguinte.

- Entra: e-mail de fora da rede (hóspede/cliente) recebido desde DESDE nas caixas do Cadastro_Hoteis.
- Fica de fora: as próprias caixas da rede, remetentes automáticos (no-reply, Booking, Decolar...)
  e e-mail de lista (cabeçalho List-Unsubscribe).
- Respondido: saiu e-mail de qualquer caixa deste PC pra aquele endereço depois que ele chegou.
"""
import datetime
import hashlib
import json
import re
import socket

from arquivos import salvar_json
from config import PASTA_ESTADO
from controle_nf import reclama_falta_nota
from log_util import configurar_logging
from tratamento import normalizar

logger = configurar_logging("espelho_emails")

DESDE = datetime.date(2026, 9, 1)
PREFIXO_ABA = "Emails_"
CABECALHO = ["ID", "Caixa", "Hotel", "De", "Nome", "Assunto", "Recebido", "Anexos", "Texto", "PC", "Atualizado",
             "Quartos", "Falta nota"]
MAX_PDF_BYTES = 3 * 1024 * 1024   # voucher/recibo de reserva é pequeno; PDF grande não é lido
MAX_PDFS = 4
CAMINHO_ESTADO = PASTA_ESTADO / "espelho_emails.json"
MAX_TEXTO = 20000                 # célula do Sheets aceita 50 mil; o e-mail do hóspede raramente passa de 2 mil
REVARRER_HORAS = 24               # releitura completa 1x por dia (pega e-mail apagado/movido)
FOLGA_MINUTOS = 10
REMETENTES_AUTOMATICOS = ("no-reply", "noreply", "naoresponda", "nao-responda", "nao_responda", "donotreply",
                          "mailer-daemon", "postmaster", "notifica", "newsletter", "marketing", "bounce")
DOMINIOS_AUTOMATICOS = ("booking.com", "decolar.com", "expedia", "airbnb", "hotels.com", "trivago", "omnibees",
                        "hbook", "cloudbeds", "facebookmail", "google.com", "microsoft.com", "linkedin")
PR_CABECALHOS = "http://schemas.microsoft.com/mapi/proptag/0x007D001F"
_HISTORICO = re.compile(
    r"^\s*(?:De:|From:|-{2,}\s*(?:Mensagem original|Original Message)|_{5,}|Em .{5,120}escreveu:|On .{5,120}wrote:)",
    re.IGNORECASE | re.MULTILINE)


def nome_aba(pc=None):
    return PREFIXO_ABA + (pc or socket.gethostname())


def id_do_email(entry_id):
    return hashlib.sha1(entry_id.encode("utf-8", "replace")).hexdigest()[:12]


def sem_historico(texto):
    """Corta as mensagens antigas coladas embaixo (De:/From:/Em ... escreveu:)."""
    texto = (texto or "").replace("\r\n", "\n").replace("\r", "\n")
    m = _HISTORICO.search(texto)
    texto = texto[:m.start()] if m and m.start() > 0 else texto
    return re.sub(r"\n{3,}", "\n\n", texto).strip()[:MAX_TEXTO]


def e_automatico(endereco, cabecalhos=""):
    endereco = (endereco or "").lower()
    usuario, _, dominio = endereco.partition("@")
    if not dominio:
        return True
    if any(p in usuario for p in REMETENTES_AUTOMATICOS) or any(d in dominio for d in DOMINIOS_AUTOMATICOS):
        return True
    return "list-unsubscribe:" in (cabecalhos or "").lower()


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


def _enderecos(item):
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


def resolver_pendentes(pendentes, enviados):
    """Tira os e-mails respondidos. enviados: {endereço: último envio (datetime)}."""
    def respondido(e):
        try:
            return bool(enviados.get(e["de"])) and enviados[e["de"]] > datetime.datetime.fromisoformat(e["recebido"])
        except ValueError:
            return False
    return {i: e for i, e in pendentes.items() if not respondido(e)}


def linhas_da_aba(pendentes, pc, agora=None):
    agora = (agora or datetime.datetime.now()).isoformat(timespec="seconds")
    corpo = sorted(pendentes.values(), key=lambda e: e["recebido"], reverse=True)
    return [CABECALHO] + [[e["id"], e["caixa"], e["hotel"], e["de"], e["nome"], e["assunto"], e["recebido"],
                          ", ".join(e["anexos"]), e["texto"], pc, agora, texto_quartos(e),
                          reclama_falta_nota(e["texto"])] for e in corpo]


def ler_aba(linhas):
    """Linhas de uma aba Emails_<PC> -> [dict]"""
    chaves = ["id", "caixa", "hotel", "de", "nome", "assunto", "recebido", "anexos", "texto", "pc", "atualizado",
              "quartos", "falta_nota"]
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
        saida.append(e)
    return saida


class Espelho:
    """Mantém os pendentes deste PC (em estado/espelho_emails.json) e publica na Central."""

    def __init__(self, backend, cfg, relogio=datetime.datetime.now):
        self.backend, self.cfg, self.relogio = backend, cfg, relogio
        self.central = cfg["planilha_central_id"]
        try:
            self.estado = json.load(open(CAMINHO_ESTADO, encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            self.estado = {}
        self.pendentes = self.estado.get("pendentes", {})

    def _caixas(self):
        """{caixa: 'HOTEL A / HOTEL B'} do Cadastro_Hoteis + todas as caixas da rede (pra ignorar)."""
        aba = self.cfg["aba_cadastro_hoteis"]
        linhas = self.backend.ler_abas(self.central, [aba])[0].get(aba, [])
        por_caixa = {}
        for l in linhas[1:]:
            if len(l) > 1 and "@" in str(l[1]):
                por_caixa.setdefault(str(l[1]).strip().lower(), []).append(str(l[0]).strip())
        return {c: " / ".join(dict.fromkeys(h)) for c, h in por_caixa.items()}

    def volta(self, namespace):
        agora = self.relogio()
        caixas = self._caixas()
        rede = set(caixas) | {str(self.cfg.get("conta_remetente", "")).lower(),
                              str((self.cfg.get("robo_antigo") or {}).get("remetente", "")).lower()}
        ultima = self.estado.get("ultima_volta")
        completa = (not ultima or agora - datetime.datetime.fromisoformat(self.estado.get("ultima_completa", ultima))
                    > datetime.timedelta(hours=REVARRER_HORAS))
        completa = completa or "vouchers" not in self.estado   # 1ª volta com a leitura de voucher: relê tudo
        desde = datetime.datetime.combine(DESDE, datetime.time()) if completa else \
            datetime.datetime.fromisoformat(ultima) - datetime.timedelta(minutes=FOLGA_MINUTOS)
        if completa:
            self.pendentes = {}
        enviados = dict(self.estado.get("enviados", {}))   # {endereço: iso do último envio}
        vouchers = dict(self.estado.get("vouchers", {}))   # {id: [quartos, nomes]} — PDF lido uma vez só
        for conta in namespace.Accounts:
            caixa = str(conta.SmtpAddress or "").strip().lower()
            if caixa not in caixas:
                continue
            try:
                loja = conta.DeliveryStore
                recebidos = loja.GetDefaultFolder(6).Items.Restrict(f"[ReceivedTime] >= '{desde:%d/%m/%Y %H:%M}'")
                saidos = loja.GetDefaultFolder(5).Items.Restrict(f"[SentOn] >= '{desde:%d/%m/%Y %H:%M}'")
            except Exception as e:
                logger.warning(f"⚠️ Não abri as pastas de {caixa}: {e}")
                continue
            for item in saidos:
                try:
                    quando = _data(item.SentOn)
                    for e in _enderecos(item):
                        if quando and quando.isoformat() > enviados.get(e, ""):
                            enviados[e] = quando.isoformat(timespec="seconds")
                except Exception:
                    continue
            for item in recebidos:
                try:
                    if getattr(item, "Class", 43) != 43:
                        continue
                    de = remetente(item)
                    if de in rede:
                        continue
                    try:
                        cabecalhos = item.PropertyAccessor.GetProperty(PR_CABECALHOS)
                    except Exception:
                        cabecalhos = ""
                    if e_automatico(de, cabecalhos):
                        continue
                    i = id_do_email(item.EntryID)
                    if i in self.pendentes:
                        continue
                    # voucher com 2+ quartos = nota dividida (lido 1 vez por e-mail; a releitura diária usa a memória)
                    if i not in vouchers:
                        n, nomes = quartos_dos_anexos(item) if item.Attachments.Count else (0, [])
                        vouchers[i] = [n, nomes]
                        if n >= 2:
                            try:
                                marcar_dividida_no_outlook(item)
                            except Exception as e:
                                logger.debug(f"categoria no Outlook: {e}")
                            logger.info(f"🔀 Nota dividida pelo voucher: {n} quartos ({'; '.join(nomes)}) · "
                                        f"{str(item.Subject or '')[:60]} ({caixa})")
                    recebido = _data(item.ReceivedTime)
                    anexos = [a.FileName for a in item.Attachments
                              if not str(a.FileName).lower().startswith("image0")]
                    self.pendentes[i] = {
                        "id": i, "entry_id": item.EntryID, "caixa": caixa, "hotel": caixas.get(caixa, ""),
                        "de": de, "nome": str(item.SenderName or ""), "assunto": str(item.Subject or ""),
                        "recebido": recebido.isoformat(timespec="seconds") if recebido else "",
                        "anexos": anexos, "texto": sem_historico(item.Body), "quartos": vouchers[i]}
                except Exception as e:
                    logger.debug(f"e-mail ilegível em {caixa}: {e}")
        enviados_dt = {e: datetime.datetime.fromisoformat(q) for e, q in enviados.items()}
        self.pendentes = resolver_pendentes(self.pendentes, enviados_dt)
        self.estado = {"ultima_volta": agora.isoformat(timespec="seconds"),
                       "ultima_completa": agora.isoformat(timespec="seconds") if completa
                       else self.estado.get("ultima_completa", agora.isoformat(timespec="seconds")),
                       "pendentes": self.pendentes, "enviados": enviados,
                       "vouchers": {i: v for i, v in vouchers.items() if i in self.pendentes or v[0] >= 2}}
        salvar_json(CAMINHO_ESTADO, self.estado, indent=None)
        self.publicar()
        return len(self.pendentes)

    def publicar(self):
        pc = socket.gethostname()
        linhas = linhas_da_aba(self.pendentes, pc, self.relogio())
        assinatura = hashlib.sha1(json.dumps([l[:9] + l[11:] for l in linhas], ensure_ascii=False).encode()).hexdigest()
        if assinatura == self.estado.get("publicado"):
            return   # nada mudou: poupa a cota da planilha
        aba = nome_aba(pc)
        try:
            self.backend.substituir_aba(self.central, aba, linhas)
        except Exception as e:
            logger.warning(f"⚠️ Não consegui publicar o espelho de e-mails ({e})")
            return
        self.estado["publicado"] = assinatura
        salvar_json(CAMINHO_ESTADO, self.estado, indent=None)


def entry_do_email(id_email):
    """EntryID (só existe neste PC) do e-mail espelhado — pra responder pelo próprio Outlook."""
    try:
        estado = json.load(open(CAMINHO_ESTADO, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return ""
    return estado.get("pendentes", {}).get(id_email, {}).get("entry_id", "")


def chave_de_busca(e):
    return normalizar(" ".join([e.get("nome", ""), e.get("de", ""), e.get("assunto", ""), e.get("hotel", "")]))
