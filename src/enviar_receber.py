"""Botão "Enviar/Receber todas" (27/10/2026, desenho aprovado: opção C, anel no botão).

O Painel pede aos 4 PCs, pela rede deles (pedido assinado, sem gastar cota do Google), que rodem o Enviar/Receber do
próprio Outlook (o F9). Cada PC responde quando terminou; o Painel guarda quanto cada um demorou e usa a mediana como
estimativa. O F9 também manda o que estiver preso na Caixa de Saída. O espelho dos e-mails se atualiza sozinho: a vigia do
conferente vê o e-mail novo em ~10 s e avisa os Painéis.
"""
import json
import statistics
import threading
import time
import uuid
from pathlib import Path

from log_util import configurar_logging

logger = configurar_logging("enviar_receber")

MAX_ESPERA_PC = 25         # um PC que passa disso responde "continua" e o Painel segue
TEMPO_REDE = 40            # espera pela resposta de outro PC
INTERVALO_MIN = 10         # entre um pedido e o seguinte (evita apertar 3 vezes sem querer)
ESTIMATIVA_PADRAO = 8.0    # segundos, até ter histórico
HISTORICO = 8              # últimos tempos guardados por PC


# ---------- neste PC ----------
def _presos(ns):
    """E-mails na Caixa de Saída (padrão + a de cada conta). Só conta."""
    total, vistos = 0, set()
    pastas = [ns.GetDefaultFolder(4)]
    try:
        pastas += [c.DeliveryStore.GetDefaultFolder(4) for c in ns.Accounts]
    except Exception:
        pass
    for pasta in pastas:
        try:
            if pasta.EntryID in vistos:
                continue
            vistos.add(pasta.EntryID)
            total += pasta.Items.Count
        except Exception:
            continue
    return total


def rodar_aqui(ns, max_seg=MAX_ESPERA_PC, dormir=time.sleep, relogio=time.monotonic):
    """Roda o Enviar/Receber deste Outlook e espera acabar (Caixa de Saída vazia ou parada por 4 s).
    -> {"ok": True, "segundos", "saiu", "presos"} | {"erro": texto}"""
    try:
        if ns.Offline:
            return {"erro": "Outlook em “Trabalhar Offline”"}
    except Exception:
        pass
    inicio = relogio()
    try:
        antes = _presos(ns)
        ns.SendAndReceive(False)
    except Exception as e:
        return {"erro": f"o Outlook não aceitou o Enviar/Receber ({str(e)[:80]})"}
    dormir(1)
    ultimo, parado = None, 0
    while relogio() - inicio < max_seg:
        try:
            agora = _presos(ns)
        except Exception:
            break
        if agora == 0 and relogio() - inicio >= 2:
            break
        parado = parado + 1 if agora == ultimo else 0
        if parado >= 4:
            break
        ultimo = agora
        dormir(1)
    try:
        depois = _presos(ns)
    except Exception:
        depois = ultimo or 0
    return {"ok": True, "segundos": round(relogio() - inicio, 1), "saiu": max(0, antes - depois), "presos": depois}


# ---------- o pedido aos 4 PCs ----------
def _mediana(tempos):
    return float(statistics.median(tempos)) if tempos else ESTIMATIVA_PADRAO


class EnviarReceber:
    """local() -> resposta deste PC · remoto(pc, endereco) -> resposta de outro (ou {"erro"}) ·
    pcs() -> [{"pc", "agente", "online", "rede"}] de todos, inclusive este · ao_terminar(pc) avisa a tela."""

    def __init__(self, este_pc, local, remoto, pcs, caminho_tempos, ao_terminar=None, relogio=time.monotonic):
        self.este_pc, self.local, self.remoto, self.pcs = este_pc, local, remoto, pcs
        self.caminho, self.ao_terminar, self.relogio = Path(caminho_tempos), ao_terminar, relogio
        self.lock = threading.Lock()
        self.job = None

    # histórico de tempos
    def _tempos(self):
        try:
            return json.loads(self.caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _guardar(self, pc, segundos):
        with self.lock:
            t = self._tempos()
            t[pc] = (t.get(pc, []) + [round(float(segundos), 1)])[-HISTORICO:]
            try:
                self.caminho.parent.mkdir(parents=True, exist_ok=True)
                self.caminho.write_text(json.dumps(t), encoding="utf-8")
            except OSError:
                logger.debug("tempos do Enviar/Receber", exc_info=True)

    # pedido
    def iniciar(self, quem=""):
        with self.lock:
            j = self.job
            if j and not j["fim"]:
                return self._ver(j)
            if j and self.relogio() - j["terminou"] < INTERVALO_MIN:
                return {"erro": f"Acabou de rodar. Espere uns {int(INTERVALO_MIN - (self.relogio() - j['terminou'])) + 1} s."}
            tempos = self._tempos()
            pcs = []
            for p in self.pcs():
                nome = p.get("agente") or p["pc"]
                x = {"pc": p["pc"], "agente": nome, "estado": "andando", "segundos": None, "res": "", "aviso": False,
                     "eta": _mediana(tempos.get(p["pc"], [])), "inicio": self.relogio()}
                if p["pc"] != self.este_pc and not p.get("online"):
                    x.update(estado="falha", res="desligado")
                elif p["pc"] != self.este_pc and not p.get("rede"):
                    x.update(estado="falha", res="sem rede")
                pcs.append(x)
            self.job = j = {"id": uuid.uuid4().hex[:10], "quem": quem, "inicio": self.relogio(), "fim": False, "terminou": 0.0, "pcs": pcs}
        for x in pcs:
            if x["estado"] == "andando":
                threading.Thread(target=self._um, args=(j, x, next(p for p in self.pcs() if p["pc"] == x["pc"])), daemon=True).start()
        self._conferir_fim(j)
        return self._ver(j)

    def _um(self, j, x, p):
        try:
            r = self.local() if p["pc"] == self.este_pc else self.remoto(p["pc"], p["rede"])
        except Exception as e:
            r = {"erro": f"falhou ({str(e)[:60]})"}
        r = r or {"erro": "sem resposta"}
        x["segundos"] = round(self.relogio() - x["inicio"], 1)
        if r.get("erro"):
            x.update(estado="falha", res=str(r["erro"])[:60])
        else:
            x["segundos"] = r.get("segundos") or x["segundos"]   # o tempo que o PC mediu (sem o da rede)
            presos = int(r.get("presos") or 0)
            x.update(estado="feito", aviso=bool(presos),
                     res=(f"{x['segundos']:.0f} s" + (f" · {r['saiu']} saíram" if r.get("saiu") else "")
                          + (f" · {presos} continuam presos" if presos else "")))
            self._guardar(p["pc"], r.get("segundos") or x["segundos"])
        try:
            if self.ao_terminar:
                self.ao_terminar(p["pc"])
        except Exception:
            logger.debug("aviso ao terminar", exc_info=True)
        self._conferir_fim(j)

    def _conferir_fim(self, j):
        with self.lock:
            if not j["fim"] and all(x["estado"] != "andando" for x in j["pcs"]):
                j["fim"], j["terminou"] = True, self.relogio()
                falhas = [f"{x['agente']}: {x['res']}" for x in j["pcs"] if x["estado"] == "falha"]
                logger.info(f"🔄 Enviar/Receber todas (pedido por {j['quem'] or '?'}): "
                            f"{len(j['pcs']) - len(falhas)} de {len(j['pcs'])} PCs" + (f" — {'; '.join(falhas)}" if falhas else ""))

    # o que a tela vê
    def _ver(self, j):
        agora = self.relogio()
        pcs, eta_total = [], 0.0
        for x in j["pcs"]:
            pronto = x["estado"] != "andando"
            decorrido = agora - x["inicio"]
            prog = 1.0 if pronto else min(0.95, decorrido / max(x["eta"], 1.0))
            falta = 0.0 if pronto else max(1.0, x["eta"] - decorrido)
            eta_total = max(eta_total, falta)
            pcs.append({"pc": x["pc"], "agente": x["agente"], "estado": x["estado"], "res": x["res"], "aviso": x["aviso"],
                        "progresso": round(prog, 3)})
        progresso = sum(p["progresso"] for p in pcs) / len(pcs) if pcs else 1.0
        return {"id": j["id"], "fim": j["fim"], "progresso": round(1.0 if j["fim"] else progresso, 3),
                "eta": 0 if j["fim"] else int(eta_total + .999), "decorrido": round(agora - j["inicio"], 1), "pcs": pcs,
                "feitos": sum(1 for p in pcs if p["estado"] != "andando"), "total": len(pcs),
                "falhas": [f"{p['agente']}: {p['res']}" for p in pcs if p["estado"] == "falha"],
                "avisos": [f"{p['agente']}: {p['res']}" for p in pcs if p["aviso"]]}

    def status(self, id_):
        j = self.job
        if not j or j["id"] != id_:
            return {"erro": "pedido não encontrado"}
        return self._ver(j)
