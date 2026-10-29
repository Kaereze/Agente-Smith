"""Fluidez (29/10/2026): o clique só lê da memória. Envio responde na hora, atividade sem Google no clique, mapa leve."""
import types
from pathlib import Path

import pytest

import app_servidor
import envio_nf as en
from test_envio_nf import CAIXA, SOL, Relogio, _ler, _prep, _servico

RAIZ = Path(__file__).resolve().parents[1]
ANEXO = [{"tipo": "arquivo", "nome": "n.pdf", "conteudo": b"x"}]


def _com_segundo_plano(planilha, cfg, pc="PC-JOAO", contas=(CAIXA,)):
    _prep(planilha)
    enviados, trabalhos = [], []
    serv = _servico(planilha, cfg, pc, list(contas), enviados, Relogio())
    serv.segundo_plano = trabalhos.append          # guarda o trabalho; o teste decide quando ele roda
    serv.tick(_ler(planilha), "João")
    return serv, enviados, trabalhos


def test_enviar_responde_antes_de_qualquer_ida_ao_google(cfg, planilha):
    serv, enviados, trabalhos = _com_segundo_plano(planilha, cfg)
    r = serv.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, ANEXO, "João")
    assert r["ok"] and r["destino"] == "PC-JOAO" and r["id"]
    assert len(planilha.aba(en.ABA_FILA)) == 1 and not enviados     # só o cabeçalho: nada foi ao Google, nada saiu
    assert serv.situacao(r["id"])["estado"] == "aguardando"          # a tela já acompanha o envio
    trabalhos[0]()                                                   # o trabalho por trás: grava o pedido e envia
    assert len(planilha.aba(en.ABA_FILA)) >= 2 and len(enviados) == 1
    assert serv.situacao(r["id"])["estado"] == "enviado"


def test_caixa_em_outro_pc_grava_o_pedido_por_tras_e_nao_envia_daqui(cfg, planilha):
    serv, enviados, trabalhos = _com_segundo_plano(planilha, cfg, contas=("nf@ondina.com",))
    outro = _servico(planilha, cfg, "PC-CRISTIAN", [CAIXA], [], Relogio())
    outro.tick(_ler(planilha), "Cristian")
    serv.tick(_ler(planilha), "João")
    r = serv.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, ANEXO, "João")
    assert r["ok"] and r["destino"] == "PC-CRISTIAN" and len(planilha.aba(en.ABA_FILA)) == 1
    trabalhos[0]()
    pedidos = [l for l in planilha.aba(en.ABA_FILA)[1:]]
    assert len(pedidos) == 1 and not enviados                        # o pedido está na fila para o PC dono; daqui nada sai


def test_pedido_que_nao_grava_vira_falhou_e_nada_e_enviado(cfg, planilha, monkeypatch):
    serv, enviados, trabalhos = _com_segundo_plano(planilha, cfg)
    r = serv.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, ANEXO, "João")

    def cair(*a, **k):
        raise RuntimeError("Google fora do ar")
    monkeypatch.setattr(planilha, "anexar_linhas", cair)
    trabalhos[0]()                                                   # não levanta erro: vira estado para a tela
    estado = serv.situacao(r["id"])
    assert estado["estado"] == "falhou" and "Aperte Enviar de novo" in estado["detalhe"]
    assert not enviados


def test_sem_segundo_plano_continua_como_sempre_o_erro_sobe(cfg, planilha, monkeypatch):
    _prep(planilha)
    serv = _servico(planilha, cfg, "PC-JOAO", [CAIXA], [], Relogio())   # segundo_plano vazio: testes e uso síncrono
    serv.tick(_ler(planilha), "João")

    def cair(*a, **k):
        raise RuntimeError("Google fora do ar")
    monkeypatch.setattr(planilha, "anexar_linhas", cair)
    with pytest.raises(RuntimeError):
        serv.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, ANEXO, "João")


def test_o_servidor_liga_o_segundo_plano_do_envio():
    fonte = (RAIZ / "src" / "app_servidor.py").read_text(encoding="utf-8")
    assert "self.envio_nf.segundo_plano = lambda trabalho: threading.Thread(target=trabalho" in fonte


class _BackendContador:
    def __init__(self):
        self.leituras = 0

    def ler_abas(self, central, abas, faixas=None):
        self.leituras += 1
        return {a: [] for a in abas}, {}


def _estado_falso():
    return types.SimpleNamespace(atividade_cache=([], -1e9), backend=_BackendContador(), central="c", versao="v", atualizacao={}, pcs=lambda: [])


def test_atividade_no_clique_nunca_vai_ao_google():
    est = _estado_falso()
    app_servidor.Estado.atividade_resumo(est)
    app_servidor.Estado.atividade_resumo(est)
    assert est.backend.leituras == 0


def test_atividade_o_laco_le_uma_vez_e_guarda_por_20_s():
    est = _estado_falso()
    app_servidor.Estado.atualizar_atividade(est)
    app_servidor.Estado.atualizar_atividade(est)
    assert est.backend.leituras == 1                                 # a segunda volta dentro de 20 s usa o guardado
    app_servidor.Estado.atualizar_atividade(est, forcar=True)
    assert est.backend.leituras == 2


def test_laco_do_painel_atualiza_a_atividade_e_o_clique_nao_tem_ler_abas():
    fonte = (RAIZ / "src" / "app_servidor.py").read_text(encoding="utf-8")
    assert 'medir("painel.atividade"' in fonte and "estado.atualizar_atividade()" in fonte
    corpo = fonte[fonte.index("    def atividade_resumo(self):"):]
    corpo = corpo[:corpo.index("    def registrar_nf_enviada")]
    assert "ler_abas" not in corpo


def test_mapa_esconde_de_verdade_o_que_esta_apagado_e_o_que_anima_enquanto_move():
    html = (RAIZ / "app_ui" / "agentes" / "mapa.html").read_text(encoding="utf-8")
    assert ".edge.dim { display: none; }" in html                    # linha apagada não é pintada (11 -> 30 quadros por segundo)
    assert ".node.dim { opacity: .28; box-shadow: none; }" in html and ".node.dim .port { display: none; }" in html
    assert ".world.movendo .lbl, .world.movendo .pk { display: none; }" in html and 'world.classList.add("movendo")' in html


# ---------------------------------------------------------------- CPU do servidor (29/10/2026): lembrar o que é igual
def _normalizar_de_referencia(texto):
    import unicodedata
    nfkd = unicodedata.normalize("NFKD", str(texto or ""))
    return " ".join("".join(c for c in nfkd if not unicodedata.combining(c)).lower().split())


def test_normalizar_continua_dando_o_mesmo_resultado_e_fica_lembrado():
    import tratamento
    amostras = ["  Endereço de E-mail ", "CPF/CNPJ", None, 123, "", "Ação  Nº 5", "ÁGUA", "ﬁnal", "água", " \t "]
    for s in amostras:
        assert tratamento.normalizar(s) == _normalizar_de_referencia(s), repr(s)
    antes = tratamento._normalizado.cache_info().hits
    tratamento.normalizar("  Endereço de E-mail ")
    assert tratamento._normalizado.cache_info().hits > antes


def test_tipo_documento_continua_igual():
    from tratamento import tipo_documento
    casos = {"CPF": "cpf", "CNPJ": "cnpj", "CPF/CNPJ": "cpf_cnpj", "CPF ou CNPJ do Tomador": "cpf_cnpj", "CEP": "cep",
             "Recepção": None, "Nome": None, "Documento Tomador": None, "Código Postal (CEP)": "cep"}
    for cabecalho, esperado in casos.items():
        assert tipo_documento(cabecalho) == esperado, cabecalho
    assert tipo_documento("Documento Tomador", {"documento tomador": "cpf_cnpj"}) == "cpf_cnpj"   # a lista da configuração vence


def test_achar_coluna_com_cabecalhos_lembrados():
    import sheets
    cab = ["Carimbo de data/hora", "Endereço de e-mail", "Nome"]
    assert sheets._achar_coluna(cab, "ENDERECO DE E-MAIL") == 1
    assert sheets._achar_coluna(cab, ["x", "nome"]) == 2
    assert sheets._achar_coluna(cab, "nada") is None
    assert sheets._achar_coluna(tuple(cab), "nome") == 2


class _RespostaDrive:
    def __init__(self, status=200):
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self):
        return {"files": [{"id": "a", "name": "n"}]}


def _drive_falso(monkeypatch, respostas):
    import google.auth.transport.requests as transporte
    import google.oauth2.service_account as conta
    criadas = []

    class Sessao:
        def __init__(self, credenciais):
            criadas.append(credenciais)

        def get(self, url, **kw):
            return _RespostaDrive(respostas.pop(0) if respostas else 200)

    class Credenciais:
        @staticmethod
        def from_service_account_file(caminho, scopes=None):
            return object()
    monkeypatch.setattr(transporte, "AuthorizedSession", Sessao)
    monkeypatch.setattr(conta, "Credentials", Credenciais)
    return criadas


def test_sessao_do_drive_e_criada_uma_vez_so(monkeypatch):
    import sincronizar
    sincronizar._sessoes_drive.clear()
    criadas = _drive_falso(monkeypatch, [])
    for _ in range(3):
        assert sincronizar.listar_pasta("chave-a.json", "pasta") == [{"id": "a", "name": "n"}]
    assert len(criadas) == 1                         # antes eram 3: uma credencial nova (RSA + internet) a cada chamada
    sincronizar._sessoes_drive.clear()


def test_sessao_do_drive_recusada_pelo_google_e_refeita_uma_vez(monkeypatch):
    import sincronizar
    sincronizar._sessoes_drive.clear()
    criadas = _drive_falso(monkeypatch, [401, 200])
    assert sincronizar.listar_pasta("chave-b.json", "pasta")
    assert len(criadas) == 2
    sincronizar._sessoes_drive.clear()
