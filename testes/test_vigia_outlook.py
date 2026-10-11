import datetime
import types

import vigia_outlook as v


class Caixa:
    """Conta do Outlook falsa: pastas 5 (enviados) e 6 (entrada) com e-mails; Restrict devolve todos."""
    def __init__(self):
        self.pastas = {5: [], 6: []}
        self.SmtpAddress = "nf@hotel.com"
        self.DeliveryStore = types.SimpleNamespace(GetDefaultFolder=lambda n: types.SimpleNamespace(
            Items=types.SimpleNamespace(Restrict=lambda filtro, n=n: list(self.pastas[n]))))

    def chega(self, pasta, entry, classe=43):
        self.pastas[pasta].append(types.SimpleNamespace(EntryID=entry, Class=classe))


def test_so_avisa_o_que_e_novo_e_nao_conta_duas_vezes():
    relogio = [datetime.datetime(2026, 10, 7, 12, 0)]
    caixa = Caixa()
    ns = types.SimpleNamespace(Accounts=[caixa])
    vig = v.Vigia(relogio=lambda: relogio[0])
    caixa.chega(5, "velho")
    assert vig.novidades(ns) == {"enviado": 0, "recebido": 0, "saiu": 0}   # 1ª olhada só memoriza
    caixa.chega(5, "E1")
    caixa.chega(6, "R1")
    caixa.chega(6, "convite", classe=26)                        # não é e-mail: ignora
    relogio[0] += datetime.timedelta(seconds=20)
    assert vig.novidades(ns) == {"enviado": 1, "recebido": 1, "saiu": 0}
    relogio[0] += datetime.timedelta(seconds=20)
    assert vig.novidades(ns) == {"enviado": 0, "recebido": 0, "saiu": 0}   # os mesmos e-mails não avisam de novo


def test_pasta_que_falha_nao_derruba_o_vigia():
    ruim = types.SimpleNamespace(SmtpAddress="x@y", DeliveryStore=types.SimpleNamespace(
        GetDefaultFolder=lambda n: (_ for _ in ()).throw(RuntimeError("sem acesso"))))
    caixa = Caixa()
    ns = types.SimpleNamespace(Accounts=[ruim, caixa])
    vig = v.Vigia()
    vig.novidades(ns)
    caixa.chega(6, "R1")
    assert vig.novidades(ns)["recebido"] == 1
