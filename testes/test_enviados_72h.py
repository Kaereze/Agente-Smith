"""Itens Enviados 72 h e envio do hóspede à mão (usuário, 22/10/2026)."""
import app_servidor
import busca_outlook
import espelho_emails as ee


def _estado(monkeypatch, local, rapido, enderecos=None):
    e = object.__new__(app_servidor.Estado)
    e.segredo = None
    e._enderecos_rede = lambda: dict(enderecos or {})
    e._anotar_rede = lambda r: None
    e._pcs_por_nome = lambda: {}
    e._buscar_local = lambda termo, vivo=False: local
    chamadas = []

    def rede_buscar(corpo):
        chamadas.append(corpo)
        return rapido
    e.rede_buscar = rede_buscar
    return e, chamadas


def _r(id_, pasta, quando):
    return {"id": id_, "pasta": pasta, "quando": quando, "para": "hospede@x.com", "de": "nf@h.com"}


def test_enviado_fica_72h_e_o_estado_antigo_e_relido():
    assert ee.RECENTE_HORAS == 72 and ee.VERSAO_ESTADO >= 6


def test_pesquisa_do_endereco_sem_enviado_e_indice_incompleto_faz_consulta_rapida(monkeypatch):
    e, chamadas = _estado(monkeypatch, {"resultados": [_r("a", "entrada", "2026-10-01T10:00:00")], "completo": False, "fonte": "indice"},
                          {"resultados": [_r("env1", "enviado", "2026-09-20T10:00:00")]})
    r = e.buscar_outlook("hospede@x.com")
    assert [x["id"] for x in r["resultados"]] == ["a", "env1"] or [x["id"] for x in r["resultados"]] == ["env1", "a"]
    assert chamadas and chamadas[0]["so_enviados"] is True and chamadas[0]["tempo"] <= 1.5
    chamadas.clear()
    e.buscar_outlook("hospede@x.com")                       # mesmo endereço de novo em 60 s: não repete
    assert not chamadas


def test_indice_completo_ou_ja_tem_enviado_ou_nao_e_endereco_nao_consulta(monkeypatch):
    completo = {"resultados": [_r("a", "entrada", "2026-10-01T10:00:00")], "completo": True, "fonte": "indice"}
    e, chamadas = _estado(monkeypatch, completo, {"resultados": [_r("x", "enviado", "2026-09-01T10:00:00")]})
    e.buscar_outlook("hospede@x.com")
    assert not chamadas                                      # índice pronto e sem envio: não existe, não perde tempo
    com_env = {"resultados": [_r("env", "enviado", "2026-10-01T10:00:00")], "completo": False, "fonte": "indice"}
    e, chamadas = _estado(monkeypatch, com_env, {"resultados": []})
    e.buscar_outlook("hospede@x.com")
    assert not chamadas                                      # já tem enviado
    e, chamadas = _estado(monkeypatch, {"resultados": [], "completo": False, "fonte": "indice"}, {"resultados": []})
    e.buscar_outlook("marina exemplo")
    assert not chamadas                                      # não é endereço


def test_consulta_rapida_so_olha_itens_enviados():
    pastas = []

    class Conta:
        SmtpAddress = "nf@h.com"

        class DeliveryStore:
            @staticmethod
            def GetDefaultFolder(n):
                pastas.append(n)
                raise RuntimeError("sem pasta no teste")

    class Ns:
        Accounts = [Conta()]
    busca_outlook.buscar(Ns(), {"nf@h.com": "H"}, "hospede@x.com", "PC", pastas=((5, "enviado"),))
    assert pastas == [5]
    pastas.clear()
    busca_outlook.buscar(Ns(), {"nf@h.com": "H"}, "hospede@x.com", "PC")
    assert pastas == [6, 5, 3]
