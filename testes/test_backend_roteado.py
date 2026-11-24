"""Roteador do backend: Google ou servidor central, aba por aba (API central, etapa 3). Só dados inventados."""
import inspect
import json

import pytest

from central import backend_roteado as rot
from central import sheets
from central.sheets import ErroPlanilha
from servidor_central.armazem import Armazem

CENTRAL = "central-teste"
HOTEL = "planilha-de-hotel"
FORM = "Solicitação Nota Fiscal (HOTEL A) (respostas)"


def _lados(**kw):
    google, api = Armazem(), Armazem()
    google.substituir_aba(CENTRAL, FORM, [["Carimbo", "Enviado"], ["01/01", "FALSE"]])
    google.substituir_aba(CENTRAL, "Cadastro_Hoteis", [["hotel", "caixa"], ["Hotel A", "a@exemplo.com"]])
    api.substituir_aba(CENTRAL, "Envios_NF", [["id", "estado"], ["ENV-1", "aguardando"]])
    api.substituir_aba(CENTRAL, "Status", [["Robô ligado", "TRUE"]])
    return google, api, rot.BackendRoteado(google, api, CENTRAL, **kw)


def test_o_roteador_tem_os_mesmos_metodos_e_argumentos_do_backend_google():
    publicos = [n for n, f in inspect.getmembers(sheets.BackendGoogle, inspect.isfunction) if not n.startswith("_")]
    for nome in publicos:
        assert list(inspect.signature(getattr(rot.BackendRoteado, nome)).parameters) == \
            list(inspect.signature(getattr(sheets.BackendGoogle, nome)).parameters), nome


def test_o_que_fica_no_google_e_o_que_vai_para_o_servidor():
    assert rot.fica_no_google(FORM) and rot.fica_no_google("Cadastro_Hoteis")
    assert not rot.fica_no_google("Envios_NF") and not rot.fica_no_google("Status") and not rot.fica_no_google("Correio_DESKTOP-A")


def test_leitura_mistura_as_duas_origens_e_devolve_cada_aba_no_seu_lugar():
    _, _, b = _lados()
    lidas, erros = b.ler_abas(CENTRAL, ["Envios_NF", FORM, "Status", "Cadastro_Hoteis", "Sumiu"], {FORM: "A2"})
    assert lidas["Envios_NF"] == [["id", "estado"], ["ENV-1", "aguardando"]]
    assert lidas[FORM] == [["01/01", "FALSE"]] and lidas["Cadastro_Hoteis"][1] == ["Hotel A", "a@exemplo.com"]
    assert "Sumiu" in erros
    assert list(lidas) == ["Envios_NF", FORM, "Status", "Cadastro_Hoteis"]   # na ordem pedida


def test_listar_abas_junta_as_do_google_que_ficam_la_com_as_do_servidor():
    google, api, b = _lados()
    google.substituir_aba(CENTRAL, "Aba_velha_do_Google", [["x"]])   # interna: no Google ela já não vale mais
    assert sorted(b.listar_abas(CENTRAL)) == sorted([FORM, "Cadastro_Hoteis", "Envios_NF", "Status"])


def test_gravacao_vai_para_o_lado_certo():
    google, api, b = _lados()
    b.anexar_linhas(CENTRAL, "Envios_NF", [["ENV-2", "enviado"]])
    b.escrever(CENTRAL, [("'Status'!B1", False), (f"'{FORM}'!B2", "TRUE")])
    b.criar_aba_log(CENTRAL, "Eventos_Correio", ["id"])
    b.garantir_colunas(CENTRAL, "Envios_NF", ["id", "estado", "pc"])
    assert api.ler_abas(CENTRAL, ["Envios_NF"])[0]["Envios_NF"] == [["id", "estado", "pc"], ["ENV-1", "aguardando"], ["ENV-2", "enviado"]]
    assert api.ler_abas(CENTRAL, ["Status"])[0]["Status"] == [["Robô ligado", "FALSE"]]
    assert google.ler_abas(CENTRAL, [FORM])[0][FORM][1] == ["01/01", "TRUE"]            # a marca do robô foi para o Google
    assert "Eventos_Correio" in api.listar_abas(CENTRAL) and "Eventos_Correio" not in google.listar_abas(CENTRAL)
    assert "Envios_NF" not in google.listar_abas(CENTRAL)


def test_outra_planilha_sempre_vai_para_o_google():
    google, api, b = _lados()
    google.substituir_aba(HOTEL, "Envios_NF", [["do hotel"]])   # mesmo nome de aba, planilha de hotel: é do Google
    assert b.ler_abas(HOTEL, ["Envios_NF"])[0]["Envios_NF"] == [["do hotel"]]
    b.anexar_linhas(HOTEL, "Envios_NF", [["mais"]])
    assert google.ler_abas(HOTEL, ["Envios_NF"])[0]["Envios_NF"] == [["do hotel"], ["mais"]]
    assert api.listar_abas(HOTEL) == []


def test_endereco_que_nao_se_entende_vai_para_o_google_e_nao_some():
    google, _, b = _lados()
    with pytest.raises(Exception):
        b.escrever(CENTRAL, [("endereco-sem-aspas", "x")])   # o Armazem do teste recusa, e o erro aparece (não é engolido)


def test_modo_casa_ignora_toda_gravacao_nos_dois_lados():
    google, api, b = _lados(ignorar_gravacao=True)
    b.anexar_linhas(CENTRAL, "Envios_NF", [["ENV-9", "x"]])
    b.escrever(CENTRAL, [(f"'{FORM}'!B2", "TRUE")])
    b.substituir_aba(CENTRAL, "Nova", [["x"]])
    assert len(api.ler_abas(CENTRAL, ["Envios_NF"])[0]["Envios_NF"]) == 2 and "Nova" not in api.listar_abas(CENTRAL)
    assert google.ler_abas(CENTRAL, [FORM])[0][FORM][1] == ["01/01", "FALSE"]
    assert b.ler_abas(CENTRAL, ["Envios_NF"])[0]["Envios_NF"][1][0] == "ENV-1"   # ler continua funcionando


def test_somente_leitura_recusa_gravar_como_o_google_faria():
    _, _, b = _lados(somente_leitura=True)
    with pytest.raises(ErroPlanilha):
        b.anexar_linhas(CENTRAL, "Envios_NF", [["x"]])
    assert b.ler_abas(CENTRAL, ["Status"])[0]["Status"] == [["Robô ligado", "TRUE"]]


# ---------------------------------------------------------------- a escolha por PC (estado/central_api.json)
@pytest.fixture()
def arquivo_local(tmp_path, monkeypatch):
    caminho = tmp_path / "central_api.json"
    monkeypatch.setattr(rot, "_caminho", lambda: caminho)
    monkeypatch.delenv("CENTRAL_TOKEN", raising=False)
    return caminho


def test_sem_arquivo_ou_desligado_nao_muda_nada(arquivo_local):
    assert rot.configuracao_local() is None                       # arquivo não existe
    arquivo_local.write_text(json.dumps({"ligada": False, "url": "http://x:8770", "token": "t" * 32}), encoding="utf-8")
    assert rot.configuracao_local() is None                       # existe, mas desligado
    arquivo_local.write_text("{ isto nao e json", encoding="utf-8")
    assert rot.configuracao_local() is None                       # estragado: cai para o Google, nunca derruba o Painel


def test_ligado_sem_endereco_ou_sem_token_continua_no_google(arquivo_local):
    arquivo_local.write_text(json.dumps({"ligada": True, "url": "http://x:8770"}), encoding="utf-8")
    assert rot.configuracao_local() is None


def test_ligado_completo_devolve_endereco_e_token(arquivo_local):
    arquivo_local.write_text(json.dumps({"ligada": True, "url": "http://10.0.0.5:8770", "token": "abc"}), encoding="utf-8")
    assert rot.configuracao_local() == {"url": "http://10.0.0.5:8770", "token": "abc"}


def test_token_pode_vir_da_variavel_de_ambiente(arquivo_local, monkeypatch):
    arquivo_local.write_text(json.dumps({"ligada": True, "url": "http://10.0.0.5:8770"}), encoding="utf-8")
    monkeypatch.setenv("CENTRAL_TOKEN", "do-ambiente")
    assert rot.configuracao_local()["token"] == "do-ambiente"


class _GoogleFalso:
    def __init__(self, chave, somente_leitura=False):
        self.chave, self.somente_leitura = chave, somente_leitura


def test_fabrica_devolve_o_google_puro_quando_desligado(arquivo_local, monkeypatch):
    monkeypatch.setattr(rot, "BackendGoogle", _GoogleFalso)
    monkeypatch.setattr(rot, "caminho_chave_google", lambda cfg: "chave.json")
    b = rot.criar_backend({"planilha_central_id": CENTRAL})
    assert isinstance(b, _GoogleFalso) and b.chave == "chave.json"
    assert rot.criar_backend({"planilha_central_id": CENTRAL}, somente_leitura=True).somente_leitura is True


def test_fabrica_devolve_o_roteado_quando_ligado(arquivo_local, monkeypatch):
    arquivo_local.write_text(json.dumps({"ligada": True, "url": "http://10.0.0.5:8770", "token": "abc"}), encoding="utf-8")
    monkeypatch.setattr(rot, "BackendGoogle", _GoogleFalso)
    monkeypatch.setattr(rot, "BackendSoLeitura", _GoogleFalso)
    monkeypatch.setattr(rot, "caminho_chave_google", lambda cfg: "chave.json")
    b = rot.criar_backend({"planilha_central_id": CENTRAL})
    assert isinstance(b, rot.BackendRoteado) and b._central == CENTRAL and isinstance(b._google, _GoogleFalso)
    casa = rot.criar_backend_casa({"planilha_central_id": CENTRAL})
    assert casa._ignorar_gravacao is True


def test_o_arquivo_com_o_token_esta_no_catalogo_e_fora_do_github():
    from sistema import armazem
    assert "central_api.json" in armazem.DADOS
    import subprocess
    r = subprocess.run(["git", "check-ignore", "estado/central_api.json"], capture_output=True, text=True,
                       cwd=str(armazem.config.PASTA_PROJETO))
    assert r.returncode == 0   # o git ignora: o token nunca sobe


def test_os_programas_pedem_o_backend_pela_fabrica_e_nao_criam_o_do_google_direto():
    """Quem criar BackendGoogle(...) por conta própria passa por cima da escolha de cada PC (servidor ou Google)."""
    from pathlib import Path
    src = Path(__file__).resolve().parent.parent / "src"
    for nome in ("app_servidor.py", "main.py", "conferente.py", "confirmar_nfs.py", "identidade.py"):
        texto = (src / nome).read_text(encoding="utf-8")
        assert "BackendGoogle(" not in texto and "BackendSoLeitura(" not in texto, f"{nome} cria o backend direto: use criar_backend"
