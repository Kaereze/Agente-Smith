import datetime

import avisos_windows as a

DIA = datetime.datetime(2026, 10, 7, 14, 0)


def pc(nome, agente, online=True, outlook="aberto", atrasada=False):
    return {"pc": nome, "agente": agente, "online": online, "outlook": outlook, "conferencia_atrasada": atrasada}


def test_principal_avisa_so_na_mudanca_de_qualquer_pc():
    av = a.Avisos()
    assert av.mudancas([pc("A", "João"), pc("B", "Clara")], "A", True, DIA) == []        # ao ligar só memoriza
    avisos = av.mudancas([pc("A", "João"), pc("B", "Clara", outlook="fechado")], "A", True, DIA)
    assert [t for t, _ in avisos] == ["Outlook fechado"] and "Clara" in avisos[0][1]
    assert av.mudancas([pc("A", "João"), pc("B", "Clara", outlook="fechado")], "A", True, DIA) == []   # não repete
    assert [t for t, _ in av.mudancas([pc("A", "João"), pc("B", "Clara")], "A", True, DIA)] == ["Voltou ao normal"]
    assert [t for t, _ in av.mudancas([pc("A", "João"), pc("B", "Clara", online=False)], "A", True, DIA)] == ["PC desligado"]
    assert av.mudancas([pc("A", "João"), pc("B", "Clara")], "A", True, DIA) == []        # ligou de manhã: sem aviso


def test_conferente_so_avisa_dele_mesmo_e_fora_do_horario_fica_quieto():
    av = a.Avisos()
    av.mudancas([pc("A", "João"), pc("B", "Clara")], "B", False, DIA)
    assert av.mudancas([pc("A", "João", outlook="fechado"), pc("B", "Clara")], "B", False, DIA) == []
    avisos = av.mudancas([pc("A", "João", outlook="fechado"), pc("B", "Clara", atrasada=True)], "B", False, DIA)
    assert [t for t, _ in avisos] == ["Conferência parada"] and "este PC" in avisos[0][1]
    noite = DIA.replace(hour=22)
    assert av.mudancas([pc("A", "João"), pc("B", "Clara", online=False)], "B", False, noite) == []
