"""Abrir e-mail com o PC dono sem responder (07/11/2026): depois da 1ª falha, vai direto para a cópia da planilha por 45 s,
em vez de esperar 6 s a cada e-mail (medido: 10 s em média no PC de casa)."""
import types

import estado_correio
import rede_local


def _estado(monkeypatch, respostas):
    chamadas = []
    est = types.SimpleNamespace(segredo=b"x", _anotar_rede=lambda r: None, _enderecos_rede=lambda: {"PC-B": "10.0.0.2:8766"},
                                _email=lambda i: {"pc": "PC-B", "versao_texto": "v1"},
                                _texto_da_planilha=lambda pc, i: {"texto": "da planilha", "pc": pc})
    def perguntar(segredo, destinos, caminho, corpo, tempo=0):
        chamadas.append(caminho)
        return {"PC-B": respostas.pop(0)}
    monkeypatch.setattr(rede_local, "perguntar_a_todos", perguntar)
    monkeypatch.setattr(estado_correio.socket, "gethostname", lambda: "PC-A")
    est.texto_email = types.MethodType(estado_correio.CorreioMixin.texto_email, est)
    return est, chamadas


def test_depois_de_uma_falha_nao_pergunta_de_novo_e_usa_a_copia(monkeypatch):
    est, chamadas = _estado(monkeypatch, [{"erro": "sem resposta"}, {"texto": "ao vivo"}])
    r1 = est.texto_email("id1")
    r2 = est.texto_email("id2")
    assert r1["origem"].startswith("cópia") and r2["origem"].startswith("cópia")
    assert len(chamadas) == 1          # a 2ª abertura nem tentou a rede


def test_passado_o_tempo_pergunta_de_novo_e_volta_ao_vivo(monkeypatch):
    est, chamadas = _estado(monkeypatch, [{"erro": "sem resposta"}, {"texto": "ao vivo"}])
    est.texto_email("id1")
    est._texto_falhou = {"PC-B": -1e9}   # a falha ficou velha
    r = est.texto_email("id2")
    assert r["origem"] == "ao vivo" and len(chamadas) == 2 and est._texto_falhou == {}
