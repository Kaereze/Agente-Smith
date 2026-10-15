"""Hotel com duas planilhas (15/10/2026): o formulário novo grava em 'Solicitação Nota Fiscal (X) (respostas)', com
outras colunas, e a planilha antiga para. A cópia junta as duas numa aba só da Central, o robô envia o que está
pendente nas duas e o TRUE volta para a planilha de onde cada linha veio."""
import datetime
import json

import robo_antigo as ra
import sincronizar as sz
from modelos import Hotel
from sheets import interpretar_aba

CFG = {"colunas": {"enviado": "Enviado", "carimbo": "Carimbo de data/hora",
                   "email_hospede": ["Endereço de e-mail", "E-mail"],
                   "nome_hospede": ["Nome do Hóspede", "Nome Tomador", "Nome do Titular da Reserva"]},
       "formato_data_planilha": "americano"}
ANTIGA = [["Carimbo de data/hora", "Endereço de e-mail", "Nome do Hóspede", "E-mail", "Enviado"],
          ["30/10/2025 05:48:06", "ana@x.com", "Ana", "nf@empresa.com", "TRUE"],
          [],
          ["07/10/2026 10:52:27", "bia@x.com", "Bia", "", ""]]
NOVA = [["Carimbo de data/hora", "Termos de aceite", "Nome Tomador", "E-mail", "Valor da Nota Fiscal", "Enviado"],
        ["13/10/2026 10:33:26", "Aceito", "Caio", "caio@x.com", "350", ""],
        ["15/10/2026 09:59:22", "Aceito", "Duda", "duda@x.com", "", ""]]
A = {"id": "ANTIGA", "name": "Nota Fiscal (Boa Viagem) (respostas)"}
N = {"id": "NOVA", "name": "Solicitação Nota Fiscal (Boa Viagem) (respostas)"}


def _lidas(nova=NOVA):
    return [(N, "Respostas ao formulário 1", nova), (A, "Respostas ao formulário 1", ANTIGA)]   # a nova primeiro, de propósito


def test_junta_as_duas_com_o_cabecalho_da_antiga_e_as_colunas_novas_no_fim():
    origem, fontes = sz.juntar_planilhas(_lidas(), CFG)
    assert origem[0] == ANTIGA[0] + ["Termos de aceite", "Nome Tomador", "Valor da Nota Fiscal"]
    assert [l[0] for l in origem[1:]] == ["30/10/2025 05:48:06", "07/10/2026 10:52:27",
                                          "13/10/2026 10:33:26", "15/10/2026 09:59:22"]
    caio = origem[3]
    assert caio[3] == "caio@x.com" and caio[6] == "Caio" and caio[7] == "350" and caio[1] == "" and caio[4] == ""
    assert [[(a["id"], n) for a, _aba, n in f] for f in fontes] == [[("ANTIGA", 2)], [("ANTIGA", 4)], [("NOVA", 2)], [("NOVA", 3)]]


def test_pedidos_do_formulario_novo_ficam_pendentes_e_o_true_volta_pra_planilha_certa():
    lidas = _lidas()
    origem, fontes = sz.juntar_planilhas(lidas, CFG)
    novas, resumo = sz.mesclar(origem, [], CFG)
    assert resumo["pendentes"] == 3 and resumo["true_origem"] == 1
    central = [list(l) for l in novas]
    central[3][4] = "TRUE"   # o robô enviou o do Caio e marcou na Central
    novas, _ = sz.mesclar(origem, central, CFG)
    plano = {a["id"]: (letra, linhas) for a, _aba, letra, linhas in sz.linhas_para_marcar_no_hotel(lidas, fontes, novas, CFG)}
    assert plano == {"NOVA": ("F", [2]), "ANTIGA": ("E", [])}


def test_mesma_solicitacao_copiada_nas_duas_vira_uma_linha_e_marca_as_duas():
    nova = NOVA + [["07/10/2026 10:52:27", "Aceito", "Bia", "bia@x.com", "", ""]]
    lidas = _lidas(nova)
    origem, fontes = sz.juntar_planilhas(lidas, CFG)
    assert len(origem) == 5   # cabeçalho + Ana, Bia, Caio, Duda
    assert [(a["id"], n) for a, _aba, n in fontes[1]] == [("ANTIGA", 4), ("NOVA", 4)]
    novas, _ = sz.mesclar(origem, [], CFG, {("2026-10-07", "10:52:27", "bia@x.com")})   # Bia já enviada (lista do robô)
    plano = {a["id"]: linhas for a, _aba, _letra, linhas in sz.linhas_para_marcar_no_hotel(lidas, fontes, novas, CFG)}
    assert plano == {"ANTIGA": [4], "NOVA": [4]}


def test_hotel_com_uma_planilha_fica_igual_a_antes():
    origem, fontes = sz.juntar_planilhas([(A, "R", ANTIGA)], CFG)
    assert origem is ANTIGA
    assert [[n for _a, _aba, n in f] for f in fontes] == [[2], [4]]


def test_aba_juntada_le_email_e_nome_da_linha_do_formulario_novo():
    origem, _ = sz.juntar_planilhas(_lidas(), CFG)
    novas, _ = sz.mesclar(origem, [], CFG)
    cfg = {**CFG, "colunas_ocultas": ["Enviado", "Carimbo de data/hora", "Termos de aceite"]}
    hotel = Hotel("Solicitação Nota Fiscal (BOA VIAGEM) (respostas)", "BOA VIAGEM", "hotel@x", "P")
    pendentes, erro = interpretar_aba(hotel, [[str(c) for c in l] if i == 0 else
                                              ["TRUE" if v is True else "FALSE" if v is False else v for v in l]
                                              for i, l in enumerate(novas)], cfg)
    assert erro is None
    por_nome = {s.nome_titulo: s for s in pendentes}
    assert set(por_nome) == {"Bia", "Caio", "Duda"}
    assert por_nome["Bia"].email_hospede == "bia@x.com" and por_nome["Caio"].email_hospede == "caio@x.com"
    campos = dict(por_nome["Caio"].campos)
    assert campos == {"Nome Tomador": "Caio", "Valor da Nota Fiscal": "350"}   # e-mail vai como remetente, vazios somem


def test_linha_que_so_existe_na_central_e_remapeada_pelo_nome_quando_o_cabecalho_muda():
    central = [["Carimbo de data/hora", "Nome do Hóspede", "Endereço de e-mail", "Enviado"],
               ["01/01/2025 08:00:00", "Zeca", "zeca@x.com", "TRUE"]]   # outra ordem de colunas, linha que o hotel apagou
    origem, _ = sz.juntar_planilhas(_lidas(), CFG)
    novas, resumo = sz.mesclar(origem, central, CFG)
    assert resumo["so_na_central"] == 1
    zeca = novas[-1]
    assert zeca[1] == "zeca@x.com" and zeca[2] == "Zeca" and zeca[4] == "TRUE" and len(zeca) == len(novas[0])


def test_data_no_futuro_nao_conta_como_robo_antigo(tmp_path):
    arq = tmp_path / "robo_antigo.json"
    arq.write_text(json.dumps({"IDEAL": "2026-12-10T15:56:19", "BAHIA": "2026-10-14T08:53:45"}), encoding="utf-8")
    agora = datetime.datetime(2026, 10, 15, 11, 0)
    ra.registrar_atividade(arq, {"CAMPO GRANDE": datetime.datetime(2026, 12, 10, 9, 13)}, agora)
    assert json.loads(arq.read_text(encoding="utf-8")) == {"BAHIA": "2026-10-14T08:53:45"}
