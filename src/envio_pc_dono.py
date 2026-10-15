"""Envio pelo PC dono da caixa do hotel (usuário, 15/10/2026: "por que está sendo utilizado meu e-mail do Ondina?
preciso que mande uma requisição para o PC dono daquele hotel e ele mesmo envia").

Cada caixa de hotel está no Outlook de um PC só (aba PCs_Painel). O robô (PC principal) manda pelo próprio Outlook
quando a caixa do hotel está nele, como sempre. Senão, pede pela rede (rede_local, pedido assinado) ao PC que tem a
caixa: esse PC manda o e-mail da própria caixa do hotel para ela mesma e confere em Itens Enviados. A conta_remetente
(Ondina) não manda mais e-mail de hotel de outro PC; só sai por ela o que não é caixa de nenhum PC (e-mail de teste).

PC dono desligado ou sem a versão nova: o e-mail não sai (NaoEnviado), as linhas continuam sem TRUE e vão de novo
na próxima volta do robô (10 min); passou de 2 h, o alarme de pedido parado avisa no Painel.
"""
import re
import socket
import urllib.error

import rede_local
from log_util import configurar_logging

logger = configurar_logging(__name__)

ABA_PCS = "PCs_Painel"
DISPID_SEND_USING_ACCOUNT = 64209   # MailItem.SendUsingAccount (mesmo truque do outlook.py)
PASTA_CAIXA_SAIDA, PASTA_ENVIADOS = 4, 5
MAX_ITENS_PROCURADOS = 200
TEMPO_ENVIO = 60
TEMPO_CONFERIR = 30
CODIGO = re.compile(r"NF-[0-9A-F]{10}")


class NaoEnviado(Exception):
    """Certeza de que o e-mail NÃO saiu (PC dono desligado, sem a versão nova, sem a caixa): vai de novo na próxima."""


def _caixa(texto):
    return str(texto or "").strip().lower()


class OutlookComPcDono:
    """O Outlook do robô (mesma cara do OutlookNF para o main.py): caixa do hotel neste Outlook, manda daqui;
    caixa em outro PC, pede ao PC dono. ler_pcs: função -> rede_pcs.ler_pcs da aba PCs_Painel (lida 1 vez por volta)."""

    def __init__(self, local, ler_pcs, segredo, este_pc=None, perguntar=rede_local.perguntar):
        self.local = local
        self._ler_pcs = ler_pcs
        self._segredo = segredo
        self._este_pc = (este_pc or socket.gethostname()).lower()
        self._perguntar = perguntar
        self._pcs = None
        self._fora = set()       # PC que não respondeu nesta volta: os outros e-mails dele nem tentam
        self._remotos = {}       # código -> PC que mandou nesta volta

    def __getattr__(self, nome):   # namespace, contas, conta...: os do Outlook deste PC
        return getattr(self.local, nome)

    def conectar(self):
        self.local.conectar()

    def _e_local(self, caixa):
        return caixa in (getattr(self.local, "contas", None) or {})

    def _dono(self, caixa):
        """O PC (dict de rede_pcs.ler_pcs) que tem a caixa no Outlook, fora este; None = nenhum PC tem."""
        if self._pcs is None:
            self._pcs = list(self._ler_pcs() or [])
        return next((p for p in self._pcs if str(p.get("pc", "")).lower() != self._este_pc
                     and caixa in p.get("contas_lista", [])), None)

    @staticmethod
    def _quem(p):
        return f"{p.get('pc')}" + (f", {p['agente']}" if p.get("agente") else "")

    def enviar(self, email):
        caixa = _caixa(email.destinatario)
        if self._e_local(caixa):
            return self.local.enviar(email)
        try:
            p = self._dono(caixa)
        except Exception as e:
            raise NaoEnviado(f"não consegui ler a aba {ABA_PCS} pra achar o PC dono da caixa {caixa} ({e})") from e
        if p is None:   # caixa de nenhum PC da equipe (e-mail de teste, por exemplo): como antes, pela conta_remetente
            logger.info(f"   ↳ {caixa} não está no Outlook de nenhum PC da equipe: sai pela conta_remetente")
            return self.local.enviar(email)
        if not p.get("online") or not p.get("rede") or p["pc"] in self._fora:
            raise NaoEnviado(f"o PC dono da caixa {caixa} ({self._quem(p)}) está desligado ou sem rede agora")
        if not self._segredo:
            raise NaoEnviado("sem a chave do Google neste PC: a conversa pela rede com o PC dono está desligada")
        try:
            r = self._perguntar(self._segredo, p["rede"], "enviar", {"codigo": email.codigo, "para": caixa,
                                "assunto": email.assunto, "html": email.html}, TEMPO_ENVIO)
        except urllib.error.HTTPError as e:   # o PC dono recusou antes de mandar (404 = ainda sem a versão nova)
            if e.code in (403, 404, 413):
                raise NaoEnviado(f"o PC dono ({self._quem(p)}) não mandou (HTTP {e.code}"
                                 + (": ainda sem a versão nova do Painel" if e.code == 404 else "") + ")") from e
            raise
        except urllib.error.URLError as e:    # o pedido nem chegou no PC dono
            self._fora.add(p["pc"])
            raise NaoEnviado(f"o PC dono da caixa {caixa} ({self._quem(p)}) não respondeu pela rede ({e.reason})") from e
        # Demorou a responder (TimeoutError) ou outro erro: pode ter saído. Fica no diário; a conferência resolve.
        if not r.get("enviado"):
            raise NaoEnviado(f"o PC dono ({self._quem(p)}) não mandou: {r.get('erro') or r}")
        self._remotos[email.codigo] = p
        logger.info(f"   ↳ pedido ao PC dono {self._quem(p)}: saiu da própria caixa do hotel"
                    + (" (já tinha saído, não mandou de novo)" if r.get("ja_estava") else ""))

    def _conferir(self, caixa, codigo):
        p = self._dono(caixa)
        if not p.get("online") or not p.get("rede") or not self._segredo:
            raise RuntimeError(f"o PC dono da caixa {caixa} ({self._quem(p)}) está desligado ou sem rede: confiro depois")
        return self._perguntar(self._segredo, p["rede"], "conferir_envio", {"codigo": codigo, "para": caixa},
                               TEMPO_CONFERIR)

    def _da_rede(self, caixa):
        return not self._e_local(caixa) and self._dono(caixa) is not None

    def esta_nos_enviados(self, codigo, desde=None, destinatario=None):
        caixa = _caixa(destinatario)
        if not self._da_rede(caixa):
            return self.local.esta_nos_enviados(codigo, desde, destinatario=destinatario)
        if codigo not in self._remotos and self.local.esta_nos_enviados(codigo, desde, destinatario=destinatario):
            return True   # antes de 15/10/2026 esse e-mail saía daqui, pela conta_remetente
        return bool(self._conferir(caixa, codigo).get("enviados"))

    def esta_na_caixa_saida(self, codigo, destinatario=None):
        caixa = _caixa(destinatario)
        if not self._da_rede(caixa):
            return self.local.esta_na_caixa_saida(codigo, destinatario=destinatario)
        if codigo not in self._remotos and self.local.esta_na_caixa_saida(codigo, destinatario=destinatario):
            return True
        return bool(self._conferir(caixa, codigo).get("saida"))


def com_pc_dono(local, backend, cfg):
    """O Outlook do robô no PC principal, já sabendo pedir ao PC dono (config "envio_pelo_pc_dono": false desliga)."""
    if cfg.get("envio_pelo_pc_dono", True) is False:
        return local
    import rede_pcs
    from config import caminho_chave_google

    def ler_pcs():
        dados, erros = backend.ler_abas(cfg["planilha_central_id"], [ABA_PCS])
        if ABA_PCS in erros:
            raise RuntimeError(erros[ABA_PCS])
        return rede_pcs.ler_pcs(dados.get(ABA_PCS, []))
    return OutlookComPcDono(local, ler_pcs, rede_local.segredo_da_chave(caminho_chave_google(cfg)))


# ---------- no PC dono: o que chega pela rede (app_servidor registra as ações) ----------
def _conta_do_hotel(ns, caixa, caixas_de_hotel):
    if caixa not in caixas_de_hotel:
        raise PermissionError(f"{caixa} não é caixa de hotel do cadastro")
    for conta in ns.Accounts:
        if _caixa(getattr(conta, "SmtpAddress", "")) == caixa:
            return conta
    raise PermissionError(f"a caixa {caixa} não está no Outlook deste PC")


def _pastas(ns, conta, tipo):
    """A pasta da caixa do hotel e a da caixa padrão deste Outlook (dependendo da conta, o Outlook guarda a cópia do
    enviado na caixa padrão: procurar só numa faria o robô achar que não saiu e mandar de novo)."""
    pastas, vistas = [], set()
    for pegar in (lambda: conta.DeliveryStore.GetDefaultFolder(tipo), lambda: ns.GetDefaultFolder(tipo)):
        try:
            pasta = pegar()
        except Exception:
            continue
        chave = str(getattr(pasta, "EntryID", "") or id(pasta))
        if chave not in vistas:
            vistas.add(chave)
            pastas.append(pasta)
    return pastas


def _tem(ns, conta, tipo, codigo):
    for pasta in _pastas(ns, conta, tipo):
        try:
            itens = pasta.Items
            if tipo == PASTA_ENVIADOS:
                itens.Sort("[SentOn]", True)
        except Exception:
            continue
        for i, item in enumerate(itens):
            if i >= MAX_ITENS_PROCURADOS:
                break
            try:
                if codigo in (item.Body or "") or codigo in (item.HTMLBody or ""):
                    return True
            except Exception:
                continue
    return False


def _pedido(corpo, caixas_de_hotel, ns):
    caixa, codigo = _caixa(corpo.get("para")), str(corpo.get("codigo") or "")
    if not CODIGO.fullmatch(codigo):
        raise PermissionError("pedido sem código de envio do robô")
    return caixa, codigo, _conta_do_hotel(ns, caixa, caixas_de_hotel)


def enviar_aqui(app, ns, corpo, caixas_de_hotel):
    """No PC dono: manda o e-mail do robô da caixa do hotel para ela mesma (nunca para fora). Pedido repetido
    (o código já está em Enviados ou na Caixa de Saída) não manda de novo."""
    caixa, codigo, conta = _pedido(corpo, caixas_de_hotel, ns)
    if not str(corpo.get("html") or "").strip():
        raise PermissionError("pedido sem o texto do e-mail")
    eu = socket.gethostname()
    if _tem(ns, conta, PASTA_ENVIADOS, codigo) or _tem(ns, conta, PASTA_CAIXA_SAIDA, codigo):
        return {"pc": eu, "conta": caixa, "enviado": True, "ja_estava": True}
    mail = app.CreateItem(0)   # olMailItem
    mail.To = caixa
    mail.Subject = str(corpo.get("assunto") or "")
    mail.HTMLBody = str(corpo["html"])
    mail._oleobj_.Invoke(*(DISPID_SEND_USING_ACCOUNT, 0, 8, 0, conta))
    mail.Send()
    try:
        ns.SendAndReceive(False)
    except Exception:
        pass
    logger.info(f"📤 {codigo}: saiu da caixa {caixa} a pedido do robô (PC principal)")
    return {"pc": eu, "conta": caixa, "enviado": True, "ja_estava": False}


def conferir_aqui(ns, corpo, caixas_de_hotel):
    """No PC dono: o e-mail do robô com esse código está em Itens Enviados / Caixa de Saída da caixa do hotel?"""
    caixa, codigo, conta = _pedido(corpo, caixas_de_hotel, ns)
    return {"pc": socket.gethostname(), "conta": caixa, "enviados": _tem(ns, conta, PASTA_ENVIADOS, codigo),
            "saida": _tem(ns, conta, PASTA_CAIXA_SAIDA, codigo)}
