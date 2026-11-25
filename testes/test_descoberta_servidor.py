"""Troca de IP do servidor central (25/11/2026): o PC acha o endereço novo sozinho, só aceita o servidor de verdade e nunca grava em dobro."""
import datetime
import json
import socket
import threading
import urllib.error
import urllib.request

import pytest

from central import backend_roteado, descoberta, virada
from central.backend_api import BackendAPI, ErroServidorCentral, _SemConexao
from servidor_central import servidor
from servidor_central.armazem import Armazem, ErroArmazem

P = "planilha-teste"
TOKEN = "t" * 32
OUTRO_TOKEN = "x" * 32


class Servidor:
    """Um servidor de verdade nesta máquina (porta livre qualquer)."""

    def __init__(self, token=TOKEN, armazem=None):
        self.armazem = armazem or Armazem()
        self.srv = servidor.servir(self.armazem, token, porta=0, endereco="127.0.0.1")
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.srv.server_address[1]}"

    def parar(self):
        self.srv.shutdown()
        self.srv.server_close()


@pytest.fixture()
def no_ar():
    abertos = []

    def abrir(**kw):
        s = Servidor(**kw)
        abertos.append(s)
        return s
    yield abrir
    for s in abertos:
        s.parar()


def endereco_morto():
    """Um endereço onde ninguém atende (a porta é de um servidor que foi embora). Usa 0.0.0.0 de propósito: no Windows, conectar numa
    porta fechada de 127.0.0.1 demora 2 s para ser recusado (e os testes fazem isso dezenas de vezes); no 0.0.0.0 falha na hora."""
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return f"http://0.0.0.0:{s.getsockname()[1]}"


class Relogio:
    """Tempo de mentira: `dormir` só avança o relógio, então a janela de busca de 25 s passa na hora."""

    def __init__(self):
        self.t, self.dormiu = 1000.0, 0

    def __call__(self):
        return self.t

    def dormir(self, segundos):
        self.t += segundos
        self.dormiu += 1


class DescobertaFalsa:
    def __init__(self, local="", publicado=None):
        self.local, self.publicado, self.guardados, self.leituras_do_google = local, publicado, [], 0

    def endereco_local(self):
        return self.local

    def endereco_publicado(self):
        self.leituras_do_google += 1
        if isinstance(self.publicado, Exception):
            raise self.publicado
        return self.publicado

    def guardar_endereco(self, url):
        self.guardados.append(url)


def cliente(url, descobrir, relogio=None, **kw):
    relogio = relogio or Relogio()
    return BackendAPI(url, kw.pop("token", TOKEN), descoberta=descobrir, relogio=relogio, dormir=relogio.dormir, **kw), relogio


# ---------------------------------------------------------------- o servidor sabe quem é e não grava em dobro
def test_servidor_id_e_do_banco_e_nao_muda_ao_reabrir(tmp_path):
    banco = str(tmp_path / "central.sqlite")
    a = Armazem(banco)
    primeiro = a.servidor_id()
    a.fechar()
    b = Armazem(banco)
    assert b.servidor_id() == primeiro and len(primeiro) == 32
    assert Armazem().servidor_id() != primeiro   # outro banco, outra identidade
    copia = str(tmp_path / "copia.sqlite")
    b.copiar_para(copia)
    assert Armazem(copia).servidor_id() == primeiro   # a cópia de segurança leva a identidade junto


def test_executar_uma_vez_grava_uma_vez_so_e_erro_nao_fica_guardado():
    a = Armazem()
    a.criar_aba_log(P, "Aba", ["id"])
    gravar = lambda: a.anexar_linhas(P, "Aba", [["x"]])   # noqa: E731
    a.executar_uma_vez("pedido-0001", gravar)
    a.executar_uma_vez("pedido-0001", gravar)   # o PC repetiu: a resposta tinha se perdido
    a.executar_uma_vez("pedido-0002", gravar)
    assert a.ler_abas(P, ["Aba"])[0]["Aba"] == [["id"], ["x"], ["x"]]
    with pytest.raises(ErroArmazem):
        a.executar_uma_vez("pedido-0003", lambda: a.anexar_linhas(P, "NaoExiste", [["y"]]))
    a.criar_aba_log(P, "NaoExiste", ["id"])
    a.executar_uma_vez("pedido-0003", lambda: a.anexar_linhas(P, "NaoExiste", [["y"]]))   # o erro não foi lembrado: agora grava
    assert a.ler_abas(P, ["NaoExiste"])[0]["NaoExiste"] == [["id"], ["y"]]


def test_gravacao_e_registro_do_pedido_sao_uma_transacao_so():
    a = Armazem()
    a.criar_aba_log(P, "Aba", ["id"])

    def grava_e_falha():
        a.anexar_linhas(P, "Aba", [["fantasma"]])
        raise RuntimeError("caiu no meio")
    with pytest.raises(RuntimeError):
        a.executar_uma_vez("pedido-0004", grava_e_falha)
    assert a.ler_abas(P, ["Aba"])[0]["Aba"] == [["id"]]   # nada ficou pela metade
    a.executar_uma_vez("pedido-0004", lambda: a.anexar_linhas(P, "Aba", [["certo"]]))
    assert a.ler_abas(P, ["Aba"])[0]["Aba"] == [["id"], ["certo"]]
    assert a.versoes_das_abas(P, ["Aba"])["Aba"] >= 2   # a versão sobe uma vez por gravação confirmada, mesmo aninhada


def test_saude_diz_quem_e_e_prova_que_conhece_a_senha_sem_mandar_a_senha(no_ar):
    s = no_ar()
    simples = json.loads(urllib.request.urlopen(s.url + "/v1/saude", timeout=5).read())
    assert simples["ok"] and simples["servidor_id"] == s.armazem.servidor_id() and "prova" not in simples
    desafio = "desafio-de-teste-123"
    com_prova = json.loads(urllib.request.urlopen(f"{s.url}/v1/saude?desafio={desafio}", timeout=5).read())
    assert com_prova["prova"] == descoberta.prova_do_desafio(TOKEN, desafio) == servidor.prova_do_desafio(TOKEN, desafio)
    assert TOKEN not in json.dumps(com_prova)
    with pytest.raises(urllib.error.HTTPError) as erro:
        urllib.request.urlopen(f"{s.url}/v1/saude?desafio=curto", timeout=5)
    assert erro.value.code == 400


def test_o_mesmo_id_de_pedido_pela_rede_nao_grava_em_dobro(no_ar):
    s = no_ar()
    BackendAPI(s.url, TOKEN).criar_aba_log(P, "Aba", ["id"])

    def post(extra):
        corpo = {"metodo": "anexar_linhas", "args": [P, "Aba", [["x"]]], "kwargs": {}, **extra}
        req = urllib.request.Request(s.url + "/v1/chamar", data=json.dumps(corpo).encode(), method="POST", headers={"X-Token": TOKEN})
        try:
            return urllib.request.urlopen(req, timeout=5).status
        except urllib.error.HTTPError as e:
            return e.code
    assert post({"id_pedido": "mesmo-pedido-01"}) == 200 and post({"id_pedido": "mesmo-pedido-01"}) == 200
    assert len(s.armazem.ler_abas(P, ["Aba"])[0]["Aba"]) == 2          # cabeçalho + 1 linha
    assert post({}) == 200 and post({}) == 200                         # sem id (cliente antigo): comporta-se como sempre
    assert len(s.armazem.ler_abas(P, ["Aba"])[0]["Aba"]) == 4
    assert post({"id_pedido": "curto"}) == 400                         # id fora do formato


# ---------------------------------------------------------------- conferir o servidor
def test_verificar_servidor_aceita_o_certo_e_recusa_impostor_e_outro_banco(no_ar):
    a, impostor, outro_banco = no_ar(), no_ar(token=OUTRO_TOKEN), no_ar()
    assert descoberta.verificar_servidor(a.url, TOKEN) == (True, "ok")
    assert descoberta.verificar_servidor(a.url, TOKEN, a.armazem.servidor_id())[0]
    ok, motivo = descoberta.verificar_servidor(impostor.url, TOKEN)
    assert not ok and "senha" in motivo                                          # não sabe a senha: não vale
    ok, motivo = descoberta.verificar_servidor(outro_banco.url, TOKEN, a.armazem.servidor_id())
    assert not ok and "outro servidor" in motivo                                 # sabe a senha, mas é outro banco
    assert descoberta.verificar_servidor(outro_banco.url, TOKEN)[0]              # sem identificador guardado, só a prova vale
    assert not descoberta.verificar_servidor(endereco_morto(), TOKEN)[0]
    assert descoberta.identificador_do_servidor(a.url) == a.armazem.servidor_id() and descoberta.identificador_do_servidor(endereco_morto()) == ""


# ---------------------------------------------------------------- o PC acha o endereço novo
def test_o_pc_acha_o_servidor_no_endereco_novo_e_repete_o_pedido(no_ar):
    novo = no_ar()
    d = DescobertaFalsa(publicado={"url": novo.url})
    c, _ = cliente(endereco_morto(), d, servidor_id=novo.armazem.servidor_id())
    c.criar_aba_log(P, "Aba", ["id"])                 # o endereço velho não existe mais: acha, confere e repete
    c.anexar_linhas(P, "Aba", [["a"]])
    assert c.url == novo.url and d.guardados == [novo.url]
    assert novo.armazem.ler_abas(P, ["Aba"])[0]["Aba"] == [["id"], ["a"]]
    assert d.leituras_do_google == 1                   # uma leitura do Google só; os pedidos seguintes já vão direto


def test_a_gravacao_repetida_depois_da_troca_nao_duplica(no_ar):
    """A resposta se perde no meio da troca (o servidor gravou, o PC não soube): o PC repete e o servidor não grava de novo."""
    s = no_ar()
    s.armazem.criar_aba_log(P, "Aba", ["id"])
    d = DescobertaFalsa(publicado={"url": s.url})
    c, _ = cliente(s.url, d)
    real, corpos = c._enviar, []
    perdeu = {"ja": False}

    def enviar_e_perder_a_resposta(corpo, tempo):
        corpos.append(corpo)
        resposta = real(corpo, tempo)                  # o servidor recebeu e gravou...
        if not perdeu["ja"]:
            perdeu["ja"] = True
            raise _SemConexao("a resposta se perdeu")  # ...mas o PC não ficou sabendo
        return resposta
    c._enviar = enviar_e_perder_a_resposta
    c.anexar_linhas(P, "Aba", [["so-uma-vez"]])
    assert len(corpos) == 2 and corpos[0] == corpos[1]          # o mesmo pedido, com o mesmo id
    assert s.armazem.ler_abas(P, ["Aba"])[0]["Aba"] == [["id"], ["so-uma-vez"]]


def test_arquivo_local_corrigido_por_outro_programa_do_pc_evita_ler_o_google(no_ar):
    novo = no_ar()
    d = DescobertaFalsa(local=novo.url, publicado=AssertionError("não era para ler o Google"))
    c, _ = cliente(endereco_morto(), d)
    assert c.listar_abas(P) == [] and c.url == novo.url and d.leituras_do_google == 0


def test_impostor_com_senha_errada_nao_recebe_dados_nem_vira_o_endereco(no_ar):
    impostor = no_ar(token=OUTRO_TOKEN)
    morto = endereco_morto()
    d = DescobertaFalsa(publicado={"url": impostor.url})
    c, relogio = cliente(morto, d)
    with pytest.raises(ErroServidorCentral):
        c.criar_aba_log(P, "Aba", ["id"])
    assert c.url == morto and d.guardados == []
    assert impostor.armazem.listar_abas(P) == []        # nem uma aba criada lá: nenhum dado foi mandado
    antes = relogio.dormiu
    with pytest.raises(ErroServidorCentral):            # depois de uma busca sem resultado, os pedidos seguintes falham logo
        c.listar_abas(P)
    assert relogio.dormiu == antes


def test_servidor_com_a_senha_certa_mas_outro_banco_so_vale_sem_identificador_guardado(no_ar):
    a, outro = no_ar(), no_ar()
    d = DescobertaFalsa(publicado={"url": outro.url})
    c, _ = cliente(endereco_morto(), d, servidor_id=a.armazem.servidor_id())
    with pytest.raises(ErroServidorCentral):
        c.listar_abas(P)
    assert d.guardados == []
    d2 = DescobertaFalsa(publicado={"url": outro.url})   # PC antigo, sem identificador guardado: só a prova da senha conta
    c2, _ = cliente(endereco_morto(), d2)
    assert c2.listar_abas(P) == [] and c2.url == outro.url


def test_servidor_que_so_caiu_e_voltou_no_mesmo_endereco_retoma_sem_trocar_nada(no_ar):
    s = no_ar()
    d = DescobertaFalsa()
    c, _ = cliente(s.url, d)
    real, falhas = c._enviar, {"n": 0}

    def cai_uma_vez(corpo, tempo):
        if not falhas["n"]:
            falhas["n"] = 1
            raise _SemConexao("conexão recusada")
        return real(corpo, tempo)
    c._enviar = cai_uma_vez
    assert c.listar_abas(P) == [] and c.url == s.url and d.guardados == []


def test_sem_descoberta_o_erro_sobe_como_sempre(no_ar):
    c = BackendAPI(endereco_morto(), TOKEN)
    with pytest.raises(ErroServidorCentral, match="não respondeu"):
        c.listar_abas(P)


def test_google_fora_do_ar_na_busca_nao_derruba_o_programa(no_ar):
    d = DescobertaFalsa(publicado=RuntimeError("Google fora do ar"))
    c, _ = cliente(endereco_morto(), d)
    with pytest.raises(ErroServidorCentral):
        c.listar_abas(P)


# ---------------------------------------------------------------- o que se publica e o que cada PC guarda
def test_ler_publicado_so_aceita_endereco_da_rede_do_escritorio():
    ok = descoberta.ler_publicado([descoberta.CABECALHO, ["http://10.145.150.247:8770", "abc", "DESKTOP-X", "2026-11-25T11:00:00"]])
    assert ok == {"url": "http://10.145.150.247:8770", "servidor_id": "abc", "pc": "DESKTOP-X", "atualizado_em": "2026-11-25T11:00:00"}
    assert descoberta.ler_publicado([descoberta.CABECALHO, ["http://8.8.8.8:8770", "abc"]]) is None     # internet: não
    assert descoberta.ler_publicado([descoberta.CABECALHO, ["lixo"]]) is None
    assert descoberta.ler_publicado([descoberta.CABECALHO]) is None and descoberta.ler_publicado(None) is None


def test_descoberta_pelo_google_le_a_aba_certa_e_ignora_aba_que_nao_existe():
    class Google:
        def __init__(self, lidas):
            self.lidas, self.pedidos = lidas, []

        def ler_abas(self, planilha_id, nomes, faixas=None):
            self.pedidos.append((planilha_id, list(nomes)))
            return self.lidas, {}
    g = Google({descoberta.ABA: [descoberta.CABECALHO, ["http://10.0.0.9:8770", "i", "pc", "agora"]]})
    assert descoberta.DescobertaPeloGoogle(g, P).endereco_publicado()["url"] == "http://10.0.0.9:8770"
    assert g.pedidos == [(P, [descoberta.ABA])]
    assert descoberta.DescobertaPeloGoogle(Google({}), P).endereco_publicado() is None   # a aba ainda não existe


def test_guardar_endereco_troca_so_o_endereco_e_nao_cria_arquivo(monkeypatch, tmp_path):
    arquivo = tmp_path / "central_api.json"
    monkeypatch.setattr(descoberta, "_caminho", lambda: arquivo)
    assert descoberta.guardar_endereco("http://10.0.0.1:8770") is False and not arquivo.exists()
    arquivo.write_text(json.dumps({"ligada": True, "url": "http://10.0.0.2:8770", "servidor_id": "abc", "token": "t"}), encoding="utf-8")
    assert descoberta.endereco_local() == "http://10.0.0.2:8770"
    assert descoberta.guardar_endereco("http://10.0.0.3:8770") is True
    assert json.loads(arquivo.read_text(encoding="utf-8")) == {"ligada": True, "url": "http://10.0.0.3:8770", "servidor_id": "abc", "token": "t"}


def test_ligar_guarda_quem_e_o_servidor_e_o_roteado_repassa_para_o_cliente(monkeypatch, tmp_path, no_ar):
    arquivo = tmp_path / "central_api.json"
    monkeypatch.setattr(backend_roteado, "_caminho", lambda: arquivo)
    monkeypatch.setattr(descoberta, "_caminho", lambda: arquivo)
    monkeypatch.setattr(backend_roteado, "token_derivado", lambda cfg: TOKEN)
    s = no_ar()
    for aba in virada.ABAS_ESSENCIAIS:
        s.armazem.criar_aba_log(P, aba, ["x"])
    cfg = {"planilha_central_id": P}
    ok, _ = virada.ligar(s.url, cfg)
    assert ok
    dados = json.loads(arquivo.read_text(encoding="utf-8"))
    assert dados["servidor_id"] == s.armazem.servidor_id() and dados["ligada"] is True
    config = backend_roteado.configuracao_local(cfg)
    assert config["servidor_id"] == s.armazem.servidor_id()
    api = backend_roteado._api(config, google=object(), cfg=cfg)
    assert api._servidor_id == s.armazem.servidor_id() and api._descoberta is not None
    virada.desligar()
    assert json.loads(arquivo.read_text(encoding="utf-8"))["servidor_id"] == s.armazem.servidor_id()   # desligado, ainda sabe quem era


def test_a_aba_do_endereco_fica_no_google_e_virada_url_valida_continua_igual():
    assert backend_roteado.fica_no_google(descoberta.ABA) and "Servidor_Endereco" in backend_roteado.ABAS_QUE_FICAM_NO_GOOGLE
    assert virada.url_valida is descoberta.url_valida
    assert virada.url_valida("http://DESKTOP-7M6539V:8770")[0] == "http://desktop-7m6539v:8770"


# ---------------------------------------------------------------- o notebook publica o próprio endereço
class GoogleQueGrava:
    def __init__(self):
        self.gravacoes = []

    def substituir_aba(self, planilha_id, aba, linhas):
        self.gravacoes.append((planilha_id, aba, linhas))


def test_publicador_grava_quando_o_ip_muda_e_renova_o_sinal_de_vida():
    from importlib import util
    from pathlib import Path
    spec = util.spec_from_file_location("publicador", Path(__file__).resolve().parent.parent / "ferramentas" / "publicar_endereco_servidor.py")
    pub = util.module_from_spec(spec)
    spec.loader.exec_module(pub)
    g, estado, saude = GoogleQueGrava(), {}, {"ok": True, "servidor_id": "banco-1"}
    t0 = datetime.datetime(2026, 11, 25, 12, 0, 0)

    def volta(quando, ip="10.145.150.247", saude=saude):
        return pub.uma_volta(estado, g, P, 8770, "DESKTOP-7M6539V", quando, ip=ip, saude=saude)
    assert "o endereço mudou" in volta(t0) and len(g.gravacoes) == 1
    assert g.gravacoes[0][:2] == (P, descoberta.ABA) and g.gravacoes[0][2][1][:3] == ["http://10.145.150.247:8770", "banco-1", "DESKTOP-7M6539V"]
    assert volta(t0 + datetime.timedelta(minutes=5)) == "" and len(g.gravacoes) == 1            # nada mudou: não grava
    assert "sinal de vida" in volta(t0 + datetime.timedelta(minutes=31)) and len(g.gravacoes) == 2
    assert "o endereço mudou" in volta(t0 + datetime.timedelta(minutes=32), ip="10.145.150.88")  # IP novo: grava na hora
    assert g.gravacoes[-1][2][1][0] == "http://10.145.150.88:8770" and len(g.gravacoes) == 3
    assert "não respondeu" in volta(t0 + datetime.timedelta(hours=2), saude=None) and len(g.gravacoes) == 3   # servidor fora: não aponta ninguém para o nada
    assert "sem rede" in volta(t0 + datetime.timedelta(hours=2), ip="") and len(g.gravacoes) == 3
    assert "sem rede" in volta(t0 + datetime.timedelta(hours=2), ip="8.8.8.8") and len(g.gravacoes) == 3   # IP da internet nunca vira endereço


def test_ip_da_lan_devolve_um_ip_ou_vazio_e_nunca_estoura():
    ip = descoberta.ip_da_lan()
    assert ip == "" or ip.count(".") == 3
    assert descoberta.endereco_da_lan(8770, ip="10.1.2.3") == "http://10.1.2.3:8770" and descoberta.endereco_da_lan(8770, ip="") == ""
