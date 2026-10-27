"""Diagnóstico e alerta de Outlook parado (26/10/2026). Dados inventados."""
import datetime

import avisos_windows as aw
import saude

SEG = datetime.datetime(2026, 10, 26, 9, 50)          # segunda 09:50


class Ns:
    def __init__(self, offline):
        self.Offline = offline


def test_motivo_do_outlook():
    assert saude.motivo_outlook(Ns(True), janelas=[]) == "offline"
    assert saude.motivo_outlook(Ns(False), janelas=["Inserir Senha de Rede"]) == "senha"
    assert saude.motivo_outlook(Ns(False), janelas=["Aviso de Segurança da Internet"]) == "certificado"
    assert saude.motivo_outlook(Ns(False), janelas=["Email da Internet - notafiscal@redeandradebahia.com.br"]) == "senha"
    assert saude.motivo_outlook(Ns(False), janelas=["Internet Email - a@b.com"]) == "senha"
    assert saude.motivo_outlook(Ns(False), janelas=["Lembrete"]) == ""


def test_coluna_leva_o_motivo():
    assert saude.ler_coluna(saude.coluna(15, recebido="2026-10-24T18:07:42", motivo="offline"))["mot"] == "offline"
    assert "mot" not in saude.ler_coluna(saude.coluna(0))


def pc(nome, saida=0, rec="2026-10-26T09:40:00", mot="", online=True):
    return {"pc": "PC-" + nome, "agente": nome, "online": online, "outlook": "aberto", "versao": "v1",
            "saude": saude.ler_coluna(saude.coluna(saida, recebido=rec, motivo=mot))}


def test_aviso_do_painel_diz_o_motivo_e_o_que_fazer():
    textos = [p["texto"] for p in saude.problemas([pc("Cristian", 15, "2026-10-24T18:07:42", "offline"), pc("Clara")], agora=SEG)]
    assert any("Outlook de Cristian parado em \u201cTrabalhar Offline\u201d: 15 e-mail(s)" in t and "Trabalhar Offline (para apagar)" in t
               for t in textos)
    assert not any("Nenhum e-mail novo chega ao Outlook de Cristian" in t for t in textos)   # um aviso só
    textos = [p["texto"] for p in saude.problemas([pc("Bernardo", 1), pc("Clara")], agora=SEG)]
    assert any(t.startswith("Caixa de Saída do Outlook de Bernardo travada: 1") and "F9" in t for t in textos)


def test_sem_receber_ha_3_horas_tambem_avisa():
    textos = [p["texto"] for p in saude.problemas([pc("Cristian", 0, "2026-10-26T06:00:00"), pc("Clara")], agora=SEG)]
    assert any("Nenhum e-mail novo chega ao Outlook de Cristian desde 26/10 06:00" in t for t in textos)


def test_alerta_no_principal_repete_de_30_em_30_e_avisa_quando_volta():
    a = aw.Avisos()
    pcs = [pc("Cristian", 15, "2026-10-24T18:07:42", "offline"), pc("João")]
    r = a.outlook(pcs, "PC-João", principal=True, agora=SEG)
    assert r == [("Outlook de Cristian parado desde 24/10 18:07", "Em \u201cTrabalhar Offline\u201d · 15 e-mail(s) presos na Caixa de Saída")]
    assert a.outlook(pcs, "PC-João", True, agora=SEG + datetime.timedelta(minutes=10)) == []      # não repete antes de 30 min
    assert len(a.outlook(pcs, "PC-João", True, agora=SEG + datetime.timedelta(minutes=31))) == 1  # repete
    ok = [pc("Cristian"), pc("João")]
    assert a.outlook(ok, "PC-João", True, agora=SEG + datetime.timedelta(minutes=40)) == [
        ("Outlook voltou", "O Outlook de Cristian voltou a enviar e receber.")]
    assert a.outlook(ok, "PC-João", True, agora=SEG + datetime.timedelta(minutes=80)) == []


def test_no_pc_dono_fala_com_ele_e_nos_outros_nao_aparece():
    pcs = [pc("Cristian", 15, "2026-10-24T18:07:42", "offline"), pc("Clara")]
    titulo, texto = aw.Avisos().outlook(pcs, "PC-Cristian", principal=False, agora=SEG)[0]
    assert titulo == "Seu Outlook parou de enviar e receber" and texto.startswith("Está em \u201cTrabalhar Offline\u201d. Enviar/Receber")
    assert aw.Avisos().outlook(pcs, "PC-Clara", principal=False, agora=SEG) == []


def test_fora_do_horario_so_fica_no_painel_e_avisa_quando_comeca():
    a = aw.Avisos()
    pcs = [pc("Cristian", 15, "2026-10-24T18:07:42", "offline"), pc("João")]
    domingo = datetime.datetime(2026, 10, 25, 10, 0)
    assert a.outlook(pcs, "PC-João", True, agora=domingo) == []
    assert a.outlook(pcs, "PC-João", True, agora=datetime.datetime(2026, 10, 24, 12, 30)) == []   # sábado depois das 12h
    assert len(a.outlook(pcs, "PC-João", True, agora=SEG.replace(hour=8, minute=1))) == 1
