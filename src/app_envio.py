"""Botão "Enviar pendentes" do Painel, com o andamento ao vivo.

No PC principal o envio roda aqui mesmo (thread), e o log vem direto da memória. Nos outros PCs o
pedido vai pela aba Status (o conferente do principal executa) e o andamento é lido de lá.
"""
import datetime
import logging
import threading
import time

from log_util import configurar_logging

logger = configurar_logging("app_envio")

IGNORAR_LOGGERS = ("urllib3", "google", "gspread", "requests", "app")
MAX_LINHAS = 300


class _Captura(logging.Handler):
    def __init__(self, thread_id, destino):
        super().__init__(logging.INFO)
        self.thread_id, self.destino = thread_id, destino

    def emit(self, record):
        if record.thread != self.thread_id or record.name.startswith(IGNORAR_LOGGERS):
            return
        texto = record.getMessage()
        if not texto.strip() or set(texto) <= {"="}:
            return
        self.destino.append({"hora": datetime.datetime.fromtimestamp(record.created).strftime("%H:%M:%S"),
                             "nivel": record.levelname, "texto": texto})
        del self.destino[:-MAX_LINHAS]


class Envio:
    def __init__(self, ao_terminar=None):
        self.lock = threading.Lock()
        self.ao_terminar = ao_terminar
        self.estado = {"modo": "", "rodando": False, "linhas": [], "inicio": "", "fim": "", "codigo": None, "resumo": ""}

    def iniciar_local(self, quem):
        with self.lock:
            if self.estado["rodando"]:
                return False
            self.estado = {"modo": "local", "rodando": True, "linhas": [], "inicio": _agora(), "fim": "",
                           "codigo": None, "resumo": ""}
        threading.Thread(target=self._rodar, args=(quem,), daemon=True).start()
        return True

    def _rodar(self, quem):
        import main as robo_envio
        from historico import ORIGEM_PAINEL
        linhas = self.estado["linhas"]
        captura = _Captura(threading.get_ident(), linhas)
        raiz = logging.getLogger()
        raiz.addHandler(captura)
        codigo, resumo = 1, ""
        try:
            codigo = robo_envio.rodar(codigo_se_ocupado=robo_envio.OCUPADO, origem=ORIGEM_PAINEL, quem=f"{quem} (Painel)")
            if codigo == robo_envio.OCUPADO:
                resumo = "Já tinha um envio ou uma cópia rodando neste PC. Tente de novo em 1 minuto."
            else:
                resumo = next((l["texto"].lstrip("✅⚠️ ").strip() for l in reversed(linhas)
                               if l["texto"].startswith(("✅", "⚠️"))), "Envio terminado.")
        except Exception as e:
            logger.exception("envio pelo Painel falhou")
            resumo = f"O envio parou com erro: {e}"
        finally:
            raiz.removeHandler(captura)
            with self.lock:
                self.estado.update(rodando=False, fim=_agora(), codigo=codigo, resumo=resumo)
            if self.ao_terminar:
                try:
                    self.ao_terminar()
                except Exception:
                    logger.exception("atualização depois do envio falhou")

    def iniciar_remoto(self):
        with self.lock:
            self.estado = {"modo": "remoto", "rodando": True, "linhas": [], "inicio": _agora(), "fim": "",
                           "codigo": None, "resumo": "", "pedido_em": time.time()}

    def situacao(self, ler_status=None):
        """ler_status: função que devolve {rótulo: valor} da aba Status (só no modo remoto)."""
        with self.lock:
            e = dict(self.estado, linhas=list(self.estado["linhas"]))
        if e["modo"] != "remoto" or not e["rodando"] or ler_status is None:
            return e
        st = ler_status()
        comando = (st.get("Comando") or "").upper().replace(" ", "_")
        andamento = [l for l in (st.get("Andamento do envio (ao vivo)") or "").splitlines() if l.strip()]
        e["linhas"] = [{"hora": l[:8], "nivel": "INFO", "texto": l[10:] if l[2:3] == ":" else l} for l in andamento]
        esperando = time.time() - e.get("pedido_em", 0) < 15
        if comando not in ("ENVIAR", "EM_ANDAMENTO") and not esperando:
            resumo = st.get("Resposta do robô", "")
            with self.lock:
                self.estado.update(rodando=False, fim=_agora(), resumo=resumo, codigo=0 if resumo.startswith("✅") else 1)
            e.update(rodando=False, resumo=resumo)
        elif comando == "ENVIAR" and not e["linhas"]:
            e["linhas"] = [{"hora": "", "nivel": "INFO", "texto": "Pedido entregue ao PC principal — aguardando ele começar…"}]
        return e


def _agora():
    return datetime.datetime.now().isoformat(timespec="seconds")
