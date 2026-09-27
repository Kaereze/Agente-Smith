"""Outlook: envio pela conta certa e confirmação em Itens Enviados."""
import time

from log_util import configurar_logging

logger = configurar_logging(__name__)

PASTA_CAIXA_SAIDA = 4    # olFolderOutbox
PASTA_ENVIADOS = 5       # olFolderSentMail
DISPID_SEND_USING_ACCOUNT = 64209  # jeito conhecido de trocar a conta remetente pelo pywin32
MAX_ITENS_PROCURADOS = 200


class ErroOutlook(Exception):
    """Outlook não ficou pronto ou a conta remetente não existe."""


class OutlookNF:
    def __init__(self, cfg, esperar=time.sleep):
        self._cfg = cfg
        self._esperar = esperar
        self.outlook = None
        self.namespace = None
        self.conta = None
        self.contas = {}   # {e-mail: conta do Outlook} — pra enviar da própria conta do hotel

    # -- conexão -------------------------------------------------------------
    def conectar(self):
        """Tenta até N vezes. Se o Outlook estiver fechado, o próprio Windows abre."""
        import pythoncom
        import win32com.client

        opcoes = self._cfg["outlook"]
        tentativas = int(opcoes["tentativas_conexao"])
        espera = int(opcoes["espera_entre_tentativas_segundos"])
        ultimo_erro = None
        for tentativa in range(1, tentativas + 1):
            try:
                pythoncom.CoInitialize()
                self.outlook = win32com.client.Dispatch("Outlook.Application")
                self.namespace = self.outlook.GetNamespace("MAPI")
                if self.namespace.Folders.Count == 0:
                    raise ErroOutlook("Outlook abriu mas o perfil ainda não carregou nenhuma conta")
                self.conta = self._achar_conta()
                self.contas = {str(getattr(c, "SmtpAddress", "") or "").strip().lower(): c
                               for c in self.namespace.Accounts}
                logger.info(f"📬 Outlook pronto (remetente: {self._cfg.get('conta_remetente') or 'conta padrão'}).")
                return
            except Exception as e:
                ultimo_erro = e
                if tentativa < tentativas:
                    logger.warning(f"⚠️ Outlook não está pronto (tentativa {tentativa}/{tentativas}): {e} — "
                                   f"esperando {espera}s.")
                    self._esperar(espera)
        raise ErroOutlook(f"Outlook não ficou pronto depois de {tentativas} tentativas: {ultimo_erro}")

    def _achar_conta(self):
        desejada = str(self._cfg.get("conta_remetente", "")).strip().lower()
        if not desejada:
            return None
        encontradas = []
        for conta in self.namespace.Accounts:
            endereco = str(getattr(conta, "SmtpAddress", "") or "").strip().lower()
            encontradas.append(endereco)
            if endereco == desejada:
                return conta
        raise ErroOutlook(f"A conta remetente '{desejada}' não está neste Outlook. Contas encontradas: {encontradas}")

    # -- envio ---------------------------------------------------------------
    def conta_para(self, destinatario):
        """Se a caixa do destinatário (o hotel) está neste Outlook, o e-mail sai DELA pra ela mesma — assim o…"""
        return self.contas.get(str(destinatario or "").strip().lower()) or self.conta

    def enviar(self, email):
        """Entrega o e-mail pro Outlook enviar. Erro sobe pra quem chamou."""
        mail = self.outlook.CreateItem(0)  # olMailItem
        mail.To = email.destinatario
        mail.Subject = email.assunto
        mail.HTMLBody = email.html
        conta = self.conta_para(email.destinatario)
        if conta is not None:
            logger.info(f"   ↳ saindo da conta {conta.SmtpAddress}"
                        + (" (a própria caixa do hotel)" if conta is not self.conta else ""))
            mail._oleobj_.Invoke(*(DISPID_SEND_USING_ACCOUNT, 0, 8, 0, conta))
        mail.Send()
        try:
            self.namespace.SendAndReceive(False)  # empurra a Caixa de Saída na hora
        except Exception:
            pass

    # -- confirmação ---------------------------------------------------------
    def _pastas(self, tipo, destinatario=None):
        """Pasta da conta que enviou (a do hotel, se estiver aqui) e, por garantia, a da conta_remetente."""
        # As contas do Outlook (CDispatch) não servem de chave de dict — tira repetida pelo e-mail (achado…
        pastas, vistas = [], set()
        for conta in (self.conta_para(destinatario), self.conta):
            smtp = str(getattr(conta, "SmtpAddress", "") or "").lower() if conta is not None else ""
            if conta is None or smtp in vistas:
                continue
            vistas.add(smtp)
            try:
                pastas.append(conta.DeliveryStore.GetDefaultFolder(tipo))
            except Exception:
                pass
        return pastas or [self.namespace.GetDefaultFolder(tipo)]

    @staticmethod
    def _tem_codigo(item, codigo):
        try:
            return codigo in (item.Body or "") or codigo in (item.HTMLBody or "")
        except Exception:
            return False

    def esta_nos_enviados(self, codigo, desde=None, destinatario=None):
        """True se um e-mail com esse código está em Itens Enviados"""
        for pasta in self._pastas(PASTA_ENVIADOS, destinatario):
            itens = pasta.Items
            itens.Sort("[SentOn]", True)  # mais recente primeiro
            for i, item in enumerate(itens):
                if i >= MAX_ITENS_PROCURADOS:
                    break
                if self._tem_codigo(item, codigo):
                    return True
        return False

    def esta_na_caixa_saida(self, codigo, destinatario=None):
        for pasta in self._pastas(PASTA_CAIXA_SAIDA, destinatario):
            for i, item in enumerate(pasta.Items):
                if i >= MAX_ITENS_PROCURADOS:
                    break
                if self._tem_codigo(item, codigo):
                    return True
        return False
