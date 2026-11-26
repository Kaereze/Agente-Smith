"""Servidor central (API): o armazém, o servidor e o cliente falam como o BackendGoogle (24/11/2026)."""
import inspect
import json
import threading
import urllib.request

import pytest

from central import sheets
from central.backend_api import BackendAPI, ErroServidorCentral
from servidor_central import servidor
from servidor_central.armazem import Armazem, ErroArmazem

P = "planilha-teste"
TOKEN = "t" * 32


def test_o_cliente_tem_os_mesmos_metodos_e_argumentos_do_backend_google():
    """Se alguém mudar um método do Google e esquecer o servidor, o teste avisa antes de os PCs quebrarem."""
    publicos = [n for n, f in inspect.getmembers(sheets.BackendGoogle, inspect.isfunction) if not n.startswith("_")]
    for nome in publicos:
        assert hasattr(BackendAPI, nome), f"BackendAPI não tem {nome}"
        assert hasattr(Armazem, nome), f"Armazem não tem {nome}"
        google = list(inspect.signature(getattr(sheets.BackendGoogle, nome)).parameters)
        assert list(inspect.signature(getattr(BackendAPI, nome)).parameters) == google, nome
        assert list(inspect.signature(getattr(Armazem, nome)).parameters) == google, nome
    assert set(publicos) == servidor.METODOS_DO_BACKEND   # o servidor tem esses mais os extras (versões e espera)
    assert servidor.METODOS == servidor.METODOS_DO_BACKEND | servidor.METODOS_EXTRAS


# ---------------------------------------------------------------- armazém
def _com_aba(*linhas, nome="Aba"):
    a = Armazem()
    a.criar_aba_log(P, nome, ["id", "nome", "valor"])
    a.anexar_linhas(P, nome, [list(l) for l in linhas])
    return a


def test_ler_devolve_o_cabecalho_e_corta_celula_vazia_do_fim():
    a = _com_aba(["1", "ana", ""], ["2", "", "x"])
    lidas, erros = a.ler_abas(P, ["Aba"])
    assert lidas["Aba"] == [["id", "nome", "valor"], ["1", "ana"], ["2", "", "x"]] and erros == {}


def test_aba_que_nao_existe_vai_para_os_erros_sem_derrubar_as_outras():
    a = _com_aba(["1"])
    lidas, erros = a.ler_abas(P, ["Aba", "Sumiu"])
    assert "Aba" in lidas and "Sumiu" in erros and "Sumiu" not in lidas


def test_faixa_le_so_da_linha_pedida_e_ate_a_coluna_pedida():
    a = _com_aba(["1", "a", "b"], ["2", "c", "d"], ["3", "e", "f"])
    lidas, _ = a.ler_abas(P, ["Aba"], {"Aba": "A3:B"})
    assert lidas["Aba"] == [["2", "c"], ["3", "e"]]


def test_escrever_celula_com_booleano_vira_TRUE_como_na_planilha():
    a = Armazem()
    a.criar_aba_status(P, "Status", [["Robô ligado", True], ["Comando", ""]])
    a.escrever(P, [("'Status'!B1", False), ("'Status'!B2", "ENVIAR")])
    assert a.ler_abas(P, ["Status"])[0]["Status"] == [["Robô ligado", "FALSE"], ["Comando", "ENVIAR"]]


def test_apostrofo_do_comeco_some_como_no_google_ao_escrever_e_criar_status():
    """O PC grava a versão como "'031bbb2" (para o Google não converter). O Google tira o apóstrofo; o servidor também tem
    de tirar, senão o Painel compara "'031bbb2" com "031bbb2" e acusa todo PC de desatualizado."""
    a = Armazem()
    a.criar_aba_status(P, "Status", [["Versão", "'031bbb2"], ["Hora", "'26/11/2026 09:30:00"]])
    a.escrever(P, [("'Status'!C1", "'031bbb2"), ("'Status'!D1", "D'Ávila"), ("'Status'!E1", "''dois")])
    assert a.ler_abas(P, ["Status"])[0]["Status"] == [["Versão", "031bbb2", "031bbb2", "D'Ávila", "'dois"],
                                                      ["Hora", "26/11/2026 09:30:00"]]


def test_gravacoes_cruas_guardam_o_apostrofo_como_no_google():
    """inserir_no_topo, anexar e substituir vão como RAW no Google, que guarda o texto tal qual; o servidor também."""
    a = Armazem()
    a.criar_aba_log(P, "Log", ["id"])
    a.inserir_no_topo(P, "Log", [["'cru"]])
    assert a.ler_abas(P, ["Log"])[0]["Log"] == [["id"], ["'cru"]]


def test_escrever_em_aba_com_apostrofo_no_nome():
    a = Armazem()
    a.criar_aba_status(P, "D'Ávila", [["x"]])
    a.escrever(P, [("'D''Ávila'!B1", "ok")])
    assert a.ler_abas(P, ["D'Ávila"])[0]["D'Ávila"] == [["x", "ok"]]


def test_escrever_em_aba_que_nao_existe_falha_e_nao_grava_nada():
    a = Armazem()
    a.criar_aba_status(P, "Status", [["a"]])
    with pytest.raises(ErroArmazem):
        a.escrever(P, [("'Status'!B1", "x"), ("'Falta'!A1", "y")])
    assert a.ler_abas(P, ["Status"])[0]["Status"] == [["a"]]   # a transação desfez a 1ª também


def test_inserir_no_topo_fica_logo_abaixo_do_cabecalho():
    a = _com_aba(["1"], ["2"])
    a.inserir_no_topo(P, "Aba", [["novo1"], ["novo2"]])
    assert a.ler_abas(P, ["Aba"])[0]["Aba"][1:] == [["novo1"], ["novo2"], ["1"], ["2"]]


def test_apagar_linhas_com_novas_no_lugar_e_o_fim_intacto():
    a = _com_aba(["1"], ["2"], ["3"], ["4"])          # linhas 2..5
    a.apagar_linhas(P, "Aba", 2, 4, [["resumo"]])       # apaga as linhas 2 e 3 (valores 1 e 2) e põe uma no lugar
    assert a.ler_abas(P, ["Aba"])[0]["Aba"][1:] == [["resumo"], ["3"], ["4"]]


def test_apagar_linhas_sem_novas_puxa_o_resto_para_cima():
    a = _com_aba(["1"], ["2"], ["3"])
    a.apagar_linhas(P, "Aba", 2, 3)
    assert a.ler_abas(P, ["Aba"])[0]["Aba"][1:] == [["2"], ["3"]]


def test_substituir_aba_cria_e_reescreve_inteira():
    a = Armazem()
    a.substituir_aba(P, "Espelho", [["a", "b"], ["c"]])
    a.substituir_aba(P, "Espelho", [["z"]])
    assert a.ler_abas(P, ["Espelho"])[0]["Espelho"] == [["z"]]


def test_garantir_colunas_aumenta_o_cabecalho_sem_perder_os_dados():
    a = _com_aba(["1", "ana"])
    a.garantir_colunas(P, "Aba", ["id", "nome", "valor", "extra"])
    assert a.ler_abas(P, ["Aba"])[0]["Aba"] == [["id", "nome", "valor", "extra"], ["1", "ana"]]


def test_apagar_aba_e_listar():
    a = _com_aba(["1"])
    assert a.listar_abas(P) == ["Aba"]
    a.apagar_aba(P, "Aba")
    assert a.listar_abas(P) == []


def test_criar_aba_que_ja_existe_falha():
    a = _com_aba()
    with pytest.raises(ErroArmazem):
        a.criar_aba_log(P, "Aba", ["x"])


def test_planilhas_diferentes_nao_se_misturam():
    a = Armazem()
    a.criar_aba_status("A", "Status", [["so da A"]])
    a.criar_aba_status("B", "Status", [["so da B"]])
    assert a.ler_abas("A", ["Status"])[0]["Status"] == [["so da A"]]
    assert a.ler_abas("B", ["Status"])[0]["Status"] == [["so da B"]]


def test_dois_pcs_anexando_ao_mesmo_tempo_nao_perdem_nem_misturam_linhas():
    a = _com_aba()

    def pc(i):
        for j in range(25):
            a.anexar_linhas(P, "Aba", [[f"pc{i}", str(j)]])
    fios = [threading.Thread(target=pc, args=(i,)) for i in range(8)]
    for f in fios:
        f.start()
    for f in fios:
        f.join()
    linhas = a.ler_abas(P, ["Aba"])[0]["Aba"][1:]
    assert len(linhas) == 200 and len({tuple(linha) for linha in linhas}) == 200


def test_os_dados_sobrevivem_a_reiniciar_o_servidor(tmp_path):
    arquivo = str(tmp_path / "central.sqlite")
    a = Armazem(arquivo)
    a.criar_aba_log(P, "Aba", ["id"])
    a.anexar_linhas(P, "Aba", [["1"]])
    a.fechar()
    assert Armazem(arquivo).ler_abas(P, ["Aba"])[0]["Aba"] == [["id"], ["1"]]


# ---------------------------------------------------------------- servidor + cliente
@pytest.fixture()
def no_ar():
    srv = servidor.servir(Armazem(), TOKEN, porta=0, endereco="127.0.0.1")
    fio = threading.Thread(target=srv.serve_forever, daemon=True)
    fio.start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_do_cliente_ao_armazem_pela_rede(no_ar):
    b = BackendAPI(no_ar, TOKEN)
    b.criar_aba_log(P, "Envios", ["id", "estado"])
    b.anexar_linhas(P, "Envios", [["ENV-1", "aguardando"]])
    b.escrever(P, [("'Envios'!B2", "enviado")])
    lidas, erros = b.ler_abas(P, ["Envios", "Falta"])
    assert lidas["Envios"] == [["id", "estado"], ["ENV-1", "enviado"]] and "Falta" in erros
    assert b.listar_abas(P) == ["Envios"]
    b.apagar_linhas(P, "Envios", 2, 3)
    assert b.ler_abas(P, ["Envios"])[0]["Envios"] == [["id", "estado"]]


def test_texto_com_acento_e_emoji_vai_e_volta_igual(no_ar):
    b = BackendAPI(no_ar, TOKEN)
    b.substituir_aba(P, "Acentos", [["Solicitação Nota Fiscal (GOIÂNIA)", "✅ ñ"]])
    assert b.ler_abas(P, ["Acentos"])[0]["Acentos"] == [["Solicitação Nota Fiscal (GOIÂNIA)", "✅ ñ"]]


def test_token_errado_nao_le_nem_grava(no_ar):
    ruim = BackendAPI(no_ar, "x" * 32)
    with pytest.raises(ErroServidorCentral):
        ruim.substituir_aba(P, "Aba", [["invasor"]])
    assert BackendAPI(no_ar, TOKEN).listar_abas(P) == []


def test_erro_do_armazem_chega_como_erro_de_planilha(no_ar):
    with pytest.raises(sheets.ErroPlanilha):
        BackendAPI(no_ar, TOKEN).escrever(P, [("'Falta'!A1", "x")])


def test_servidor_fora_do_ar_vira_erro_claro():
    with pytest.raises(ErroServidorCentral):
        BackendAPI("http://127.0.0.1:1", TOKEN, tempo=1).listar_abas(P)


def test_so_os_metodos_da_lista_podem_ser_chamados(no_ar):
    with pytest.raises(ErroServidorCentral):
        BackendAPI(no_ar, TOKEN)._chamar("fechar")


def test_saude_nao_precisa_de_token(no_ar):
    with urllib.request.urlopen(no_ar + "/v1/saude", timeout=5) as r:
        assert json.loads(r.read())["ok"] is True


def test_sem_token_configurado_o_servidor_nem_sobe(monkeypatch):
    monkeypatch.delenv("CENTRAL_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        servidor.main()


# ---------------------------------------------------------------- cópia de segurança
def test_backup_guarda_os_dados_e_apaga_as_copias_antigas(tmp_path):
    import datetime
    from servidor_central.backup import fazer_backup
    banco = str(tmp_path / "central.sqlite")
    a = Armazem(banco)
    a.criar_aba_log(P, "Aba", ["id"])
    a.anexar_linhas(P, "Aba", [["1"]])
    a.fechar()
    pasta = tmp_path / "copias"
    pasta.mkdir()
    velha = pasta / "central-2026-01-01.sqlite"
    velha.write_bytes(b"x")
    copia = fazer_backup(banco, pasta, hoje=datetime.date(2026, 11, 24))
    assert not velha.exists()
    assert Armazem(str(copia)).ler_abas(P, ["Aba"])[0]["Aba"] == [["id"], ["1"]]
