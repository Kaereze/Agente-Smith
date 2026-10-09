import cota_google
from cota_google import PERFIS, Cota


class Relogio:
    def __init__(self):
        self.t = 1000.0
        self.dormiu = []

    def __call__(self):
        return self.t

    def esperar(self, s):
        self.dormiu.append(s)
        self.t += s


def test_soma_das_fatias_dos_4_pcs_fica_abaixo_do_limite_do_google():
    leituras = lambda p: PERFIS[p][0]
    escritas = lambda p: PERFIS[p][1]
    # 3 PCs comuns (painel + conferente) + o principal (painel + conferente do principal + cópia dos hotéis)
    total_l = 3 * (leituras("painel") + leituras("conferente")) + leituras("painel") + leituras("conferente_principal") \
        + leituras("sincronizar")
    total_e = 3 * (escritas("painel") + escritas("conferente")) + escritas("painel") + escritas("conferente_principal") \
        + escritas("sincronizar")
    assert total_l < cota_google.LIMITE_GOOGLE and total_e < cota_google.LIMITE_GOOGLE


def test_segura_quando_a_fatia_do_minuto_acaba(tmp_path, monkeypatch):
    monkeypatch.setattr(cota_google, "PASTA_CONSUMO", tmp_path)
    r = Relogio()
    c = Cota("painel", relogio=r, esperar=r.esperar)
    for _ in range(PERFIS["painel"][0]):
        c.usar("leitura")
    assert r.dormiu == []
    c.usar("leitura")              # a 8ª do minuto espera a 1ª sair da janela
    assert 59 < sum(r.dormiu) <= 61
    assert c.consumo()["leituras"] == 1 and c.esperas == 1


def test_leitura_e_escrita_tem_fatias_separadas(tmp_path, monkeypatch):
    monkeypatch.setattr(cota_google, "PASTA_CONSUMO", tmp_path)
    r = Relogio()
    c = Cota("painel", relogio=r, esperar=r.esperar)
    for _ in range(PERFIS["painel"][0]):
        c.usar("leitura")
    c.usar("escrita")
    assert r.dormiu == []


def test_429_pausa_o_programa_inteiro(tmp_path, monkeypatch):
    monkeypatch.setattr(cota_google, "PASTA_CONSUMO", tmp_path)
    r = Relogio()
    c = Cota("painel", relogio=r, esperar=r.esperar)
    c.pausar(20)
    c.usar("escrita")
    assert sum(r.dormiu) >= 20


def test_consumo_do_pc_soma_os_programas(tmp_path, monkeypatch):
    monkeypatch.setattr(cota_google, "PASTA_CONSUMO", tmp_path)
    for perfil, n in (("painel", 3), ("conferente", 2)):
        c = Cota(perfil)
        for _ in range(n):
            c.usar("leitura")
        c.gravado_em = -1e9
        c._gravar_consumo()
    assert cota_google.consumo_deste_pc() == (5, 0)


def test_reconhece_erro_de_cota():
    assert cota_google.e_cota_estourada("APIError: [429]: Quota exceeded for quota metric 'Read requests'")
    assert not cota_google.e_cota_estourada("APIError: [400]: Unable to parse range")
