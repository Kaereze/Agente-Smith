"""Fluidez do Painel (09/11/2026): o que a tela pede o tempo todo precisa responder rápido e sem refazer trabalho à toa."""
import copy
import hashlib
import json

import app_servidor


def _assinatura_antiga(corpo):
    """A versão de 21/10/2026: percorria a estrutura inteira em Python e serializava de novo. Fica aqui como referência do que a nova deve dizer."""
    def limpar(x):
        if isinstance(x, dict):
            return {k: limpar(v) for k, v in x.items() if k not in app_servidor.VOLATEIS_TELA}
        if isinstance(x, list):
            return [limpar(v) for v in x]
        return x
    return hashlib.sha1(json.dumps(limpar(corpo), ensure_ascii=False, default=str).encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


BASE = {
    "agente": "João", "pc": "DESKTOP-X", "atualizado_em": "2026-11-09T10:00:00-03:00",
    "pcs": [{"pc": "A", "agente": "Clara", "visto": "2026-11-09 10:00:00", "online": True}, {"pc": "B", "agente": "Bernardo", "visto": "", "online": False}],
    "fila": [{"chave": "k1", "dias": 3, "nome": "Ana Souza", "campos": [["Nome Tomador", "Ana"], ["CEP", "40170-110"]], "prazo": {"vence": "2026-11-10", "dias": 1.5}},
             {"chave": "k2", "dias": 0, "nome": "Bia", "obs": 'disse "dias": 9 e \\"visto\\": 1', "campos": []}],
    "emails": [{"id": "e1", "assunto": 'Prazo "dias": 3?', "atualizado": "x", "visto": None, "dias": -2}],
}


def _com(mudanca):
    c = copy.deepcopy(BASE)
    mudanca(c)
    return c


def test_assinatura_nova_diz_igual_exatamente_quando_a_antiga_dizia():
    mudancas = {
        "nada mudou": lambda c: None,
        "so a hora da leitura": lambda c: c.update(atualizado_em="2026-11-09T10:00:15-03:00"),
        "so o visto de um PC": lambda c: c["pcs"][0].update(visto="2026-11-09 10:01:00"),
        "so os dias de espera (em qualquer fundura)": lambda c: (c["fila"][0].update(dias=4), c["fila"][0]["prazo"].update(dias=0.5), c["emails"][0].update(dias=7)),
        "um nome mudou": lambda c: c["fila"][0].update(nome="Ana Souza Lima"),
        "um campo do formulario mudou": lambda c: c["fila"][0]["campos"][1].__setitem__(1, "40170-111"),
        "entrou um pedido": lambda c: c["fila"].append({"chave": "k3", "dias": 1, "nome": "Caio"}),
        "saiu um e-mail": lambda c: c["emails"].clear(),
        "PC ficou online": lambda c: c["pcs"][1].update(online=True),
        "texto que so parece ter um campo volatil mudou": lambda c: c["fila"][1].update(obs='disse "dias": 8 e \\"visto\\": 1'),
        "assunto com aspas mudou": lambda c: c["emails"][0].update(assunto='Prazo "dias": 4?'),
    }
    antes_antiga, antes_nova = _assinatura_antiga(BASE), app_servidor.assinatura_tela(BASE)
    for nome, mudanca in mudancas.items():
        depois = _com(mudanca)
        igual_antiga = _assinatura_antiga(depois) == antes_antiga
        igual_nova = app_servidor.assinatura_tela(depois) == antes_nova
        assert igual_nova == igual_antiga, f"'{nome}': a antiga diz igual={igual_antiga}, a nova diz igual={igual_nova}"


def test_assinatura_nova_nao_se_deixa_enganar_por_campo_volatil_digitado_pelo_hospede():
    # o hóspede escreveu um texto parecido com o campo "dias" do JSON: isso é dado de verdade e precisa contar
    a = _com(lambda c: c["fila"][1].update(obs='ok", "dias": 3, "x": "y'))
    b = _com(lambda c: c["fila"][1].update(obs='ok", "dias": 4, "x": "y'))
    assert app_servidor.assinatura_tela(a) != app_servidor.assinatura_tela(b)


# ---------- status do envio: nada de ir ao Google a cada consulta da tela ----------
import threading
import time
import types

from painel import estado_envio
from emails import envio_nf


class _Backend:
    """Google de mentira: conta as leituras e pode demorar ou falhar."""
    def __init__(self, demora=0.0, falha=False):
        self.leituras, self.demora, self.falha = 0, demora, falha

    def ler_abas(self, planilha, nomes, faixas=None):
        self.leituras += 1
        time.sleep(self.demora)
        if self.falha:
            raise OSError("sem rede")
        return {envio_nf.ABA_FILA: [envio_nf.CAB_FILA]}, {}


def _estado_de_mentira(backend):
    classe = next(c for c in vars(estado_envio).values() if isinstance(c, type) and hasattr(c, "situacao_envio"))
    e = types.SimpleNamespace(backend=backend, central="planilha", _fila_status=None, _lendo_fila_status=threading.Lock(),
                              FILA_STATUS_SEGUNDOS=3.0, envio_nf=types.SimpleNamespace(locais={}, fila={"x": 1}, situacao=lambda i, f: {"estado": "aguardando", "fila": f}))
    e._fila_para_status = types.MethodType(classe._fila_para_status, e)
    e.situacao_envio = types.MethodType(classe.situacao_envio, e)
    return e


def test_consultas_seguidas_do_status_leem_o_google_uma_vez_so():
    b = _Backend()
    e = _estado_de_mentira(b)
    for _ in range(25):
        e.situacao_envio("ENV-1")
    assert b.leituras == 1


def test_consultas_ao_mesmo_tempo_nao_viram_varias_leituras_iguais():
    b = _Backend(demora=0.3)
    e = _estado_de_mentira(b)
    respostas = []
    fios = [threading.Thread(target=lambda: respostas.append(e.situacao_envio("ENV-1"))) for _ in range(8)]
    for f in fios:
        f.start()
    for f in fios:
        f.join()
    assert b.leituras == 1 and len(respostas) == 8                    # um lê; os outros seguem com o que o Painel já tem, sem esperar o Google


def test_se_o_google_falha_o_status_sai_da_fila_que_o_painel_ja_tem():
    e = _estado_de_mentira(_Backend(falha=True))
    r = e.situacao_envio("ENV-1")
    assert r["estado"] == "aguardando" and r["fila"] is None          # None: o envio_nf usa a fila da última volta; nada de erro na tela
