"""Vigia do Outlook: a cada 20 s só OLHA as caixas deste PC (pedido do usuário, 07/10/2026).

Não grava nada, nem na planilha nem no Outlook. Se chegou ou saiu e-mail novo desde a última olhada, avisa
o conferente, e ele roda na hora a conferência completa (confirmar_nfs + espelho de e-mails), que relê a
Central e grava. Sem novidade, a conferência segue no ritmo normal (a cada 2 min).
"""
import datetime

from log_util import configurar_logging

logger = configurar_logging(__name__)

PASTAS = {5: "enviado", 6: "recebido"}   # olFolderSentMail, olFolderInbox
FOLGA_MINUTOS = 3          # olha um pouco antes da última vez (relógio do servidor, e-mail que demora a cair)
MAX_VISTOS = 5000


class Vigia:
    def __init__(self, relogio=datetime.datetime.now):
        self.relogio = relogio
        self.ultima = None
        self.vistos = {}   # EntryID -> quando foi visto (só pra não avisar duas vezes)

    def novidades(self, namespace):
        """-> {"enviado": n, "recebido": n} de e-mails novos desde a última olhada. A 1ª olhada só
        memoriza o que já está lá (o conferente acabou de ligar e vai conferir tudo de qualquer jeito)."""
        agora = self.relogio()
        primeira = self.ultima is None
        desde = (agora - datetime.timedelta(minutes=FOLGA_MINUTOS)) if primeira \
            else self.ultima - datetime.timedelta(minutes=FOLGA_MINUTOS)
        novos = {"enviado": 0, "recebido": 0}
        for conta in namespace.Accounts:
            for pasta, tipo in PASTAS.items():
                campo = "SentOn" if pasta == 5 else "ReceivedTime"
                try:
                    itens = conta.DeliveryStore.GetDefaultFolder(pasta).Items.Restrict(
                        f"[{campo}] >= '{desde:%d/%m/%Y %H:%M}'")
                except Exception as e:
                    logger.debug(f"vigia: pasta {pasta} de {getattr(conta, 'SmtpAddress', '?')}: {e}")
                    continue
                for item in itens:
                    try:
                        if getattr(item, "Class", 43) != 43:
                            continue
                        entry = item.EntryID
                    except Exception:
                        continue
                    if entry in self.vistos:
                        continue
                    self.vistos[entry] = agora
                    if not primeira:
                        novos[tipo] += 1
        self.ultima = agora
        if len(self.vistos) > MAX_VISTOS:   # esquece os mais antigos
            for entry, _ in sorted(self.vistos.items(), key=lambda x: x[1])[:len(self.vistos) - MAX_VISTOS]:
                del self.vistos[entry]
        return novos
