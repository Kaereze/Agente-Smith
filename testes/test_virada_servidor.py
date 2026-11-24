"""API central, etapa 5: ligar/desligar o servidor por comando, token derivado da chave, caminho de volta. Só dados inventados."""
import datetime
import json
import types

import pytest

from central import backend_roteado as rot
from central import migrar_para_servidor as mig
from central import virada
from central.sheets import ErroPlanilha
from painel import estado_sistema, rotas_api
from rede import rede_pcs
from servidor_central.armazem import Armazem

P = "central-teste"


@pytest.fixture()
def arquivo_local(tmp_path, monkeypatch):
    caminho = tmp_path / "central_api.json"
    monkeypatch.setattr(rot, "_caminho", lambda: caminho)
    monkeypatch.delenv("CENTRAL_TOKEN", raising=False)
    return caminho


def _servidor_pronto():
    a = Armazem()
    for aba in virada.ABAS_ESSENCIAIS:
        a.criar_aba_log(P, aba, ["x"])
    return a


CFG = {"planilha_central_id": P}


# ---------------------------------------------------------------- endereço
@pytest.mark.parametrize("texto,esperado", [
    ("http://10.145.150.247:8770", "http://10.145.150.247:8770"),
    ("http://10.145.150.247:8770/", "http://10.145.150.247:8770"),
    ("http://192.168.0.5:8770", "http://192.168.0.5:8770"),
    ("http://127.0.0.1:8770", "http://127.0.0.1:8770"),
    ("http://DESKTOP-7M6539V:8770", "http://desktop-7m6539v:8770"),   # o nome do PC sai em minúsculas: a rede não diferencia
])
def test_endereco_da_rede_do_escritorio_vale(texto, esperado):
    assert virada.url_valida(texto) == (esperado, "")


@pytest.mark.parametrize("texto", [
    "https://10.0.0.5:8770",           # só http (a rede é interna)
    "http://8.8.8.8:8770",              # IP da internet: nunca
    "http://servidor.exemplo.com:8770",  # nome da internet (tem ponto)
    "http://10.0.0.5",                  # sem porta
    "http://10.0.0.5:8770/v1/chamar",   # com caminho
    "http://fulano@10.0.0.5:8770",      # com usuário
    "10.0.0.5:8770", "", "ftp://10.0.0.5:8770", "http://:8770",
])
def test_endereco_fora_da_rede_ou_mal_formado_e_recusado(texto):
    url, motivo = virada.url_valida(texto)
    assert url == "" and motivo


# ---------------------------------------------------------------- conferir e ligar
def test_servidor_com_a_central_copiada_esta_pronto():
    ok, texto = virada.conferir_servidor("http://10.0.0.5:8770", CFG, api=_servidor_pronto())
    assert ok and "pronto" in texto


def test_servidor_vazio_nao_esta_pronto_e_diz_o_que_falta():
    ok, texto = virada.conferir_servidor("http://10.0.0.5:8770", CFG, api=Armazem())
    assert not ok and "não foi copiada" in texto and "Envios_NF" in texto


def test_servidor_que_nao_responde_nao_esta_pronto():
    class Fora:
        def listar_abas(self, _):
            raise ErroPlanilha("servidor central não respondeu")
    ok, texto = virada.conferir_servidor("http://10.0.0.5:8770", CFG, api=Fora())
    assert not ok and "não respondeu" in texto


def test_ligar_so_grava_o_arquivo_depois_de_conferir(arquivo_local):
    ok, texto = virada.ligar("http://10.0.0.5:8770", CFG, api=_servidor_pronto())
    assert ok and "reiniciando" in texto
    assert json.loads(arquivo_local.read_text(encoding="utf-8")) == {"ligada": True, "url": "http://10.0.0.5:8770"}


def test_ligar_com_servidor_vazio_ou_endereco_ruim_deixa_o_pc_como_estava(arquivo_local):
    ok, texto = virada.ligar("http://10.0.0.5:8770", CFG, api=Armazem())
    assert not ok and texto.startswith("não liguei") and not arquivo_local.exists()
    ok, texto = virada.ligar("http://8.8.8.8:8770", CFG, api=_servidor_pronto())
    assert not ok and "internet" in texto and not arquivo_local.exists()


def test_desligar_volta_para_o_google_e_guarda_o_endereco(arquivo_local):
    virada.ligar("http://10.0.0.5:8770", CFG, api=_servidor_pronto())
    ok, texto = virada.desligar()
    assert ok and "Google" in texto
    assert json.loads(arquivo_local.read_text(encoding="utf-8")) == {"ligada": False, "url": "http://10.0.0.5:8770"}
    assert rot.configuracao_local() is None
    assert virada.desligar() == (True, "já estava no Google")     # repetir não faz mal


# ---------------------------------------------------------------- token derivado da chave
def test_token_derivado_e_estavel_proprio_do_servidor_e_nao_vale_como_segredo_da_rede(monkeypatch):
    from rede import rede_local
    monkeypatch.setattr(rede_local, "segredo_da_chave", lambda caminho: b"segredo-da-chave-inventado")
    monkeypatch.setattr(rot, "caminho_chave_google", lambda cfg: "chave.json")
    t = rot.token_derivado(CFG)
    assert t == rot.token_derivado(CFG) and len(t) == 64
    assert t != b"segredo-da-chave-inventado".hex()                         # não é o segredo da rede


def test_sem_chave_no_pc_nao_ha_token(monkeypatch):
    from rede import rede_local
    monkeypatch.setattr(rede_local, "segredo_da_chave", lambda caminho: b"")
    monkeypatch.setattr(rot, "caminho_chave_google", lambda cfg: "chave.json")
    assert rot.token_derivado(CFG) == ""
    ok, texto = virada.conferir_servidor("http://10.0.0.5:8770", CFG)
    assert not ok and "chave do Google" in texto


def test_arquivo_ligado_sem_token_usa_o_derivado_da_chave(arquivo_local, monkeypatch):
    arquivo_local.write_text(json.dumps({"ligada": True, "url": "http://10.0.0.5:8770"}), encoding="utf-8")
    monkeypatch.setattr(rot, "token_derivado", lambda cfg: "derivado-123")
    assert rot.configuracao_local(CFG) == {"url": "http://10.0.0.5:8770", "token": "derivado-123"}
    assert rot.configuracao_local() is None                                  # sem cfg não há como derivar: continua no Google


# ---------------------------------------------------------------- o canal fica no Google
def test_comandos_pc_continua_no_google_para_o_canal_de_volta_nunca_depender_do_servidor():
    assert rot.fica_no_google(rede_pcs.ABA_COMANDOS)
    google, api = Armazem(), Armazem()
    b = rot.BackendRoteado(google, api, P)
    b.criar_aba_log(P, rede_pcs.ABA_COMANDOS, rede_pcs.CAB_COMANDOS)
    b.anexar_linhas(P, rede_pcs.ABA_COMANDOS, [["agora", "CMD-1", "TODOS", "desligar_servidor", "João", ""]])
    assert rede_pcs.ABA_COMANDOS in google.listar_abas(P) and rede_pcs.ABA_COMANDOS not in api.listar_abas(P)


def test_a_copia_para_o_servidor_nao_leva_o_canal_de_comandos():
    origem = Armazem()
    origem.substituir_aba(P, rede_pcs.ABA_COMANDOS, [["x"]])
    origem.substituir_aba(P, "Envios_NF", [["x"]])
    assert mig.abas_a_copiar(origem, P)[0] == ["Envios_NF"]


# ---------------------------------------------------------------- comandos
def test_o_comando_com_endereco_e_reconhecido_pela_primeira_palavra():
    assert rede_pcs.comando_base("ligar_servidor http://10.0.0.5:8770") == "ligar_servidor"
    assert rede_pcs.comando_base("  atualizar ") == "atualizar" and rede_pcs.comando_base("") == ""
    agora = datetime.datetime(2026, 11, 24, 12, 0, 0)
    linhas = [rede_pcs.CAB_COMANDOS,
              [agora.isoformat(), "CMD-1", "TODOS", "ligar_servidor http://10.0.0.5:8770", "João", ""],
              [agora.isoformat(), "CMD-2", "TODOS", "apagar_tudo", "João", ""],
              [agora.isoformat(), "CMD-3", "DESKTOP-A", "desligar_servidor", "João", ""]]
    assert rede_pcs.pendentes(linhas, "DESKTOP-A", agora) == [("CMD-1", "ligar_servidor http://10.0.0.5:8770", "João"),
                                                              ("CMD-3", "desligar_servidor", "João")]


def _c(admin):
    chamadas = []
    estado = types.SimpleNamespace(pedir_comando=lambda para, comando, por: chamadas.append((para, comando)) or {"ok": True})
    return types.SimpleNamespace(estado=estado, e_admin=lambda: admin, agente=lambda: "Fulano", pc="PC-X"), chamadas


def test_so_o_admin_liga_ou_desliga_o_servidor_mas_qualquer_um_pede_atualizar():
    c, chamadas = _c(admin=False)
    r = rotas_api._comando(c, {"para": "TODOS", "comando": "ligar_servidor http://10.0.0.5:8770"})
    assert r[1] == 403 and r[0]["ok"] is False and chamadas == []
    assert rotas_api._comando(c, {"para": "TODOS", "comando": "desligar_servidor"})[1] == 403
    assert rotas_api._comando(c, {"para": "TODOS", "comando": "atualizar"}) == {"ok": True}
    c2, chamadas2 = _c(admin=True)
    assert rotas_api._comando(c2, {"para": "TODOS", "comando": "desligar_servidor"}) == {"ok": True} and chamadas2


def _estado_de_mentira():
    classe = next(c for c in vars(estado_sistema).values() if isinstance(c, type) and hasattr(c, "_virada"))
    respostas = []
    e = types.SimpleNamespace(cfg=CFG, central=P, comandos_em_execucao=set(),
                              backend=types.SimpleNamespace(anexar_linhas=lambda planilha, aba, linhas: respostas.append((aba, linhas))),
                              _agente=lambda: "Servidor RA")
    for nome in ("_virada", "_executar_comando", "pedir_comando"):
        setattr(e, nome, types.MethodType(getattr(classe, nome), e))
    return e, respostas


def test_comando_ligar_executa_responde_no_canal_e_pede_reinicio(arquivo_local, monkeypatch):
    e, respostas = _estado_de_mentira()
    reinicios = []
    monkeypatch.setattr(estado_sistema.atualizador, "so_reiniciar", lambda: reinicios.append(1))
    monkeypatch.setattr(estado_sistema.threading, "Timer", lambda s, f: types.SimpleNamespace(start=f))   # sem esperar os 8 s
    monkeypatch.setattr(estado_sistema.atividade, "registrar", lambda *a, **k: None)
    monkeypatch.setattr(virada, "conferir_servidor", lambda url, cfg, api=None: (True, "servidor pronto (31 abas)"))
    e._executar_comando("CMD-1", "ligar_servidor http://10.0.0.5:8770", "João")
    assert json.loads(arquivo_local.read_text(encoding="utf-8"))["ligada"] is True and reinicios == [1]
    aba, linhas = respostas[0]
    assert aba == rede_pcs.ABA_COMANDOS and "ligado no servidor central" in linhas[0][5]


def test_comando_ligar_recusado_responde_o_motivo_e_nao_reinicia(arquivo_local, monkeypatch):
    e, respostas = _estado_de_mentira()
    reinicios = []
    monkeypatch.setattr(estado_sistema.atualizador, "so_reiniciar", lambda: reinicios.append(1))
    monkeypatch.setattr(estado_sistema.threading, "Timer", lambda s, f: types.SimpleNamespace(start=f))
    monkeypatch.setattr(estado_sistema.atividade, "registrar", lambda *a, **k: None)
    monkeypatch.setattr(virada, "conferir_servidor", lambda url, cfg, api=None: (False, "o servidor não respondeu (recusou)"))
    e._executar_comando("CMD-2", "ligar_servidor http://10.0.0.5:8770", "João")
    assert not arquivo_local.exists() and reinicios == [] and "não liguei" in respostas[0][1][0][5]


def test_pedir_comando_de_ligar_com_endereco_ruim_nem_chega_na_fila():
    e, _ = _estado_de_mentira()
    e.envio_nf = types.SimpleNamespace(pcs_linhas=[[]])
    with pytest.raises(ValueError):
        e.pedir_comando("TODOS", "ligar_servidor http://8.8.8.8:8770", "João")
    with pytest.raises(ValueError):
        e.pedir_comando("TODOS", "apagar_tudo", "João")


# ---------------------------------------------------------------- caminho de volta (servidor -> Google)
class GoogleFalso(Armazem):
    """Faz o papel do Google no teste e anota o tamanho de cada gravação (o Google recusa pedido enorme)."""

    def __init__(self):
        super().__init__()
        self.tamanhos = []

    def substituir_aba(self, planilha_id, aba, linhas):
        self.tamanhos.append(len(linhas))
        return super().substituir_aba(planilha_id, aba, linhas)

    def anexar_linhas(self, planilha_id, aba, linhas):
        self.tamanhos.append(len(linhas))
        return super().anexar_linhas(planilha_id, aba, linhas)


def test_caminho_de_volta_leva_as_abas_do_servidor_para_o_google_em_pedacos_e_confere():
    servidor = Armazem()
    servidor.substituir_aba(P, "Tratamento", [[f"linha {i}", "x"] for i in range(5000)])
    servidor.substituir_aba(P, "Envios_NF", [["id"], ["ENV-1", "enviado"]])
    servidor.substituir_aba(P, "Cadastro_Hoteis", [["fica no Google"]])           # nunca é levada
    servidor.substituir_aba(P, "Solicitação (X) (respostas)", [["fica no Google"]])
    google = GoogleFalso()
    saidas = []
    assert mig.caminho_de_volta(servidor, google, P, escrever=saidas.append) == 0
    assert sorted(google.listar_abas(P)) == ["Envios_NF", "Tratamento"]
    assert google.ler_abas(P, ["Tratamento"])[0]["Tratamento"] == servidor.ler_abas(P, ["Tratamento"])[0]["Tratamento"]
    assert max(google.tamanhos) <= mig.LINHAS_POR_ESCRITA and len(google.tamanhos) >= 4     # 5000 linhas = 3 gravações + a outra aba
    assert "2 aba(s) iguais" in saidas[-1]


def test_caminho_de_volta_so_roda_com_a_confirmacao_explicita(monkeypatch):
    args = types.SimpleNamespace(servidor="http://10.0.0.5:8770", confirmo_escrever_no_google=False, abas=None, arquivo=None)
    with pytest.raises(SystemExit) as erro:
        mig._caminho_de_volta(args, CFG, P)
    assert "confirmo-escrever-no-google" in str(erro.value)
    args.servidor = None
    with pytest.raises(SystemExit):
        mig._caminho_de_volta(args, CFG, P)


def test_a_copia_normal_para_o_servidor_continua_inteira_e_sem_pedacos():
    origem = Armazem()
    origem.substituir_aba(P, "Tratamento", [[str(i)] for i in range(3000)])
    destino = GoogleFalso()
    mig.copiar(origem, destino, P, ["Tratamento"])
    assert destino.tamanhos == [3000]


# ---------------------------------------------------------------- quem está onde (a virada não pode deixar PC para trás)
def test_onde_estao_mostra_quem_esta_no_servidor_quem_ficou_no_google_e_quem_esta_desligado():
    agora = datetime.datetime(2026, 11, 24, 12, 0, 0)
    recente, velho = (agora - datetime.timedelta(seconds=20)).isoformat(), (agora - datetime.timedelta(hours=2)).isoformat()
    cab = ["PC", "Agente", "Contas", "Visto em"]
    google = [cab, ["PC-JA-VIROU", "A", "", velho], ["PC-FICOU", "B", "", recente], ["PC-DESLIGADO", "C", "", velho], ["PC-DOIS", "D", "", recente]]
    servidor = [cab, ["PC-JA-VIROU", "A", "", recente], ["PC-DOIS", "D", "", recente]]
    onde = virada.onde_estao(google, servidor, agora)
    assert onde == {"PC-DESLIGADO": "desligado", "PC-DOIS": "os dois", "PC-FICOU": "google", "PC-JA-VIROU": "servidor"}
    assert virada.dividido(onde) is True


def test_virada_completa_nao_e_dividida_e_antes_da_virada_tambem_nao():
    agora = datetime.datetime(2026, 11, 24, 12, 0, 0)
    recente = (agora - datetime.timedelta(seconds=20)).isoformat()
    cab = ["PC", "Agente", "Contas", "Visto em"]
    todos_no_servidor = virada.onde_estao([cab], [cab, ["PC-A", "", "", recente], ["PC-B", "", "", recente]], agora)
    assert todos_no_servidor == {"PC-A": "servidor", "PC-B": "servidor"} and not virada.dividido(todos_no_servidor)
    todos_no_google = virada.onde_estao([cab, ["PC-A", "", "", recente], ["PC-B", "", "", recente]], [cab], agora)
    assert not virada.dividido(todos_no_google)
