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
