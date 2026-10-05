import datetime

import canceladas as cn
import painel_metricas as pm

D = datetime.date


def test_status_pelo_prefixo_com_erros_de_digitacao():
    assert cn.status_do_nome("(CANCELADA) NF 1 - ANA") == (cn.CANCELADA, "NF 1 - ANA")
    assert cn.status_do_nome("( CANCELADA) NF 356 - X")[0] == cn.CANCELADA
    assert cn.status_do_nome("(CACELADA) NF 9 - X")[0] == cn.CANCELADA
    for p in ("SUBSTITUIDA", "SUBSITUÍDA", "SUBISTITUIDA", "SUSBTITUIDA", "SUBISTUIDA", "SUSTITUIDA", "SUBSTITUIDA NF 166"):
        assert cn.status_do_nome(f"({p}) NF 2 - X")[0] == cn.SUBSTITUIDA, p
    assert cn.status_do_nome("(DIGITALIZADO) NF 3 - X")[0] is None
    assert cn.status_do_nome("NF 4 - X")[0] is None


def test_hotel_pela_razao_social():
    hoteis = ["PAMPULHA", "CRICIÚMA", "ROYAL CRICIÚMA", "SÃO FRANCISCO", "L GINN", "GV"]
    assert cn.hotel_pela_razao("REDE ANDRADE PAMPULHA HOTEL LTDA", hoteis) == "PAMPULHA"
    assert cn.hotel_pela_razao("RA SAO FRANCISCO HOTEL LTDA", hoteis) == "SÃO FRANCISCO"
    assert cn.hotel_pela_razao("RA ROYAL CRICIUMA HOTEL LTDA", hoteis) == "ROYAL CRICIÚMA"   # o mais específico
    assert cn.hotel_pela_razao("RA GV CENTER HOTEL LTDA", hoteis) == "GV"
    assert cn.hotel_pela_razao("REDE ANDRADE LG INN HOTEL LTDA", hoteis, {"Lg Inn": "L GINN"}) == "L GINN"
    assert cn.hotel_pela_razao("RF HOTEIS LTDA", hoteis) is None


def _arq(tipo, cnpj="", razao="", hospede="ANA PAULA SOUZA", data=D(2026, 9, 10)):
    return {"tipo": tipo, "cnpj": cnpj, "razao": razao, "hospede": hospede, "data": data, "nf": "1"}


def test_hotel_pelo_cnpj_votos_pedido_e_configuracao():
    hoteis = ["PAMPULHA", "CECOMTUR", "BRAZ"]
    pedidos = [{"hotel": "CECOMTUR", "data": "2026-09-05", "nome": f"HOSPEDE{i} SILVA TESTE", "nomes": []} for i in range(3)]
    pedidos.append({"hotel": "BRAZ", "data": "2026-09-01", "nome": "JOANA DARC LIMA", "nomes": []})
    arqs = [_arq(cn.CANCELADA, "11", "REDE ANDRADE PAMPULHA HOTEL LTDA"),
            _arq(cn.SUBSTITUIDA, "11", ""),                                         # mesmo CNPJ, PDF sem razão
            *[_arq(cn.SUBSTITUIDA, "22", "RF HOTEIS LTDA", f"HOSPEDE{i} SILVA") for i in range(3)],   # 3 votos
            _arq(cn.CANCELADA, "", "", "JOANA DARC"),                               # PDF escaneado: pelo pedido
            _arq(cn.CANCELADA, "33", "X ADMINISTRADORA LTDA", "NINGUEM CONHECIDO")]
    cn.atribuir_hoteis(arqs, hoteis, pedidos)
    assert [a["hotel"] for a in arqs] == ["PAMPULHA", "PAMPULHA", "CECOMTUR", "CECOMTUR", "CECOMTUR", "BRAZ", None]
    cn.atribuir_hoteis(arqs, hoteis, pedidos, cnpj_hoteis={"33": "BRAZ"})
    assert arqs[-1]["hotel"] == "BRAZ"


def test_varrer_pega_so_renomeados_e_usa_o_cache(tmp_path):
    (tmp_path / "2026").mkdir()
    (tmp_path / "2026" / "(CANCELADA) NF 10 - ANA LIMA - 123.pdf").write_bytes(b"nao e pdf")
    (tmp_path / "(SUBSTITUIDA) NF 11 - BIA - 9.xml").write_text("x")
    (tmp_path / "NF 12 - CAIO - 1.pdf").write_bytes(b"x")
    cache = {str(tmp_path / "sumiu.pdf"): [1, "", ""]}
    achados = cn.varrer([str(tmp_path)], cache)
    assert sorted((a["tipo"], a["nf"], a["hospede"]) for a in achados) == [
        (cn.CANCELADA, "10", "ANA LIMA"), (cn.SUBSTITUIDA, "11", "BIA")]
    assert len(cache) == 2 and str(tmp_path / "sumiu.pdf") not in cache


def test_metricas_usam_os_renomeados_e_nao_o_mail_analytics():
    canc = [{"data": D(2026, 9, 2), "hotel": "BRAZ", "tipo": cn.CANCELADA},
            {"data": D(2026, 9, 3), "hotel": "BRAZ", "tipo": cn.SUBSTITUIDA},
            {"data": D(2026, 9, 3), "hotel": None, "tipo": cn.SUBSTITUIDA},
            {"data": D(2026, 8, 30), "hotel": "BRAZ", "tipo": cn.CANCELADA}]
    mail = [{"operador": "Clara", "data": D(2026, 9, 2), "hotel": "BRAZ", "recebidos": 5, "enviados": 4,
             "ligacoes": 0, "cancelamentos": 99, "nfs": 10}]
    v = pm.visao_geral(mail, [], D(2026, 9, 1), D(2026, 9, 30), D(2026, 9, 30), {}, canc)
    assert (v["kpis"]["cancelamentos"], v["kpis"]["canceladas"], v["kpis"]["substituidas"]) == (3, 1, 2)
    dia3 = next(p for p in v["serie"] if p["data"] == "2026-09-03")
    assert dia3["cancelamentos"] == 2

    class Cad:
        def nomes(self): return ["BRAZ"]
        def dados(self, h): return {"agente": "Clara"}
    braz = pm.tabela_hoteis(mail, [], D(2026, 9, 1), D(2026, 9, 30), D(2026, 9, 30), Cad(), (), canc)[0]
    assert (braz["canceladas"], braz["substituidas"], braz["taxa_cancelamento"]) == (1, 1, 20)


def test_arquivo_so_na_nuvem_nao_e_aberto(tmp_path, monkeypatch):
    (tmp_path / "(CANCELADA) NF 10 - ANA LIMA - 1.pdf").write_bytes(b"x")
    abertos = []
    monkeypatch.setattr(cn, "so_na_nuvem", lambda c: True)
    monkeypatch.setattr(cn, "ler_prestador", lambda c: abertos.append(c) or ("", ""))
    cache = {}
    achados = cn.varrer([str(tmp_path)], cache)
    assert len(achados) == 1 and abertos == [] and cache == {}   # sem cache: lê quando baixar
