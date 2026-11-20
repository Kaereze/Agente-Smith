"""Conexão com o Supabase (20/11/2026): montagem dos pedidos, repetição em erro passageiro e a chave que nunca vaza.
Nenhum teste fala com a internet: a sessão é falsa."""
import datetime
import json

import pytest
import requests

from central import supabase
from central.supabase import Banco, ErroBanco

CHAVE_JWT = "eyJhbGciOiJIUzI1NiJ9.chave-falsa-de-teste.assinatura"
CHAVE_NOVA = "sb_publishable_chave_falsa_de_teste_123456"
URL = "https://abcdefghijkl.supabase.co"


class Resposta:
    def __init__(self, codigo=200, corpo=None, texto=""):
        self.status_code, self._corpo, self.text = codigo, corpo if corpo is not None else [], texto

    def json(self):
        return self._corpo


class Sessao:
    def __init__(self, *respostas):
        self.respostas, self.pedidos = list(respostas), []

    def request(self, metodo, url, **kw):
        self.pedidos.append((metodo, url, kw))
        r = self.respostas.pop(0) if self.respostas else Resposta()
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture(autouse=True)
def sem_espera(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)


def banco(*respostas, chave=CHAVE_JWT):
    s = Sessao(*respostas)
    return Banco(URL, chave, sessao=s, tentativa_segundos=5, limite_segundos=60), s


def test_ler_monta_o_pedido_com_filtro_colunas_ordem_e_limite():
    b, s = banco(Resposta(corpo=[{"pc": "A"}]))
    assert b.ler("painel_sinal", {"pc": "eq.A"}, colunas="pc,quando", limite=5, ordem="quando.desc") == [{"pc": "A"}]
    metodo, url, kw = s.pedidos[0]
    assert (metodo, url) == ("GET", f"{URL}/rest/v1/painel_sinal")
    assert kw["params"] == {"select": "pc,quando", "limit": 5, "pc": "eq.A", "order": "quando.desc"}
    assert kw["timeout"] == 5


def test_gravar_com_conflito_faz_upsert_e_sem_linha_nao_chama():
    b, s = banco()
    b.gravar("painel_teste", [])
    assert s.pedidos == []
    b.gravar("painel_teste", [{"id": "x", "valor": "ação"}], conflito="id")
    _, _, kw = s.pedidos[0]
    assert kw["params"] == {"on_conflict": "id"}
    assert "merge-duplicates" in kw["headers"]["Prefer"]
    assert json.loads(kw["data"].decode("utf-8")) == [{"id": "x", "valor": "ação"}]


def test_apagar_sem_filtro_e_recusado():
    b, s = banco()
    with pytest.raises(ValueError):
        b.apagar("painel_teste", {})
    assert s.pedidos == []


def test_chave_antiga_vai_tambem_como_bearer_e_a_nova_so_no_apikey():
    _, s_antiga = banco(chave=CHAVE_JWT)
    b1 = Banco(URL, CHAVE_JWT, sessao=s_antiga)
    b1.ler("t")
    b2 = Banco(URL, CHAVE_NOVA, sessao=Sessao())
    b2.ler("t")
    assert s_antiga.pedidos[0][2]["headers"]["Authorization"] == f"Bearer {CHAVE_JWT}"
    assert "Authorization" not in b2._sessao.pedidos[0][2]["headers"]
    assert b2._sessao.pedidos[0][2]["headers"]["apikey"] == CHAVE_NOVA


def test_erro_passageiro_tenta_de_novo_e_acerta():
    b, s = banco(Resposta(503, texto="indisponível"), requests.Timeout("lento"), Resposta(corpo=[{"ok": 1}]))
    assert b.ler("t") == [{"ok": 1}]
    assert len(s.pedidos) == 3


def test_erro_de_chave_nao_repete_e_nao_vaza_a_chave():
    b, s = banco(Resposta(401, texto='{"message":"Invalid API key"}'))
    with pytest.raises(ErroBanco) as e:
        b.ler("t")
    assert e.value.codigo == 401 and len(s.pedidos) == 1
    assert CHAVE_JWT not in str(e.value)


def test_sem_internet_vira_erro_do_banco_sem_o_texto_da_excecao_original():
    b, _ = banco(*[requests.ConnectionError(f"falhou com apikey={CHAVE_JWT}")] * 3)
    with pytest.raises(ErroBanco) as e:
        b.ler("t")
    assert e.value.codigo == 0 and CHAVE_JWT not in str(e.value)


def test_sinal_de_vida_grava_uma_linha_por_pc_com_hora_em_utc():
    b, s = banco()
    b.sinal_de_vida("DESKTOP-X", "2026.11.20", agora=datetime.datetime(2026, 11, 20, 15, 30, 5, tzinfo=datetime.timezone.utc))
    _, url, kw = s.pedidos[0]
    assert url.endswith("/painel_sinal") and kw["params"] == {"on_conflict": "pc"}
    assert json.loads(kw["data"].decode("utf-8")) == [{"pc": "DESKTOP-X", "quando": "2026-11-20T15:30:05Z", "versao": "2026.11.20"}]


def test_carregar_le_o_arquivo_e_confere_o_endereco(tmp_path):
    ok = tmp_path / "chave-supabase.json"
    ok.write_text(json.dumps({"url": URL + "/", "chave": CHAVE_NOVA}), encoding="utf-8")
    assert supabase.carregar(ok) == (URL, CHAVE_NOVA, "", "")
    for dados in ({"url": "http://abcdefghijkl.supabase.co", "chave": CHAVE_NOVA},   # sem https
                  {"url": "https://exemplo.com", "chave": CHAVE_NOVA},               # não é Supabase
                  {"url": URL, "chave": "curta"}):
        ruim = tmp_path / "ruim.json"
        ruim.write_text(json.dumps(dados), encoding="utf-8")
        with pytest.raises(ErroBanco):
            supabase.carregar(ruim)


def test_carregar_sem_arquivo_ou_com_arquivo_quebrado_explica_sem_mostrar_o_conteudo(tmp_path):
    with pytest.raises(ErroBanco, match="Não achei"):
        supabase.carregar(tmp_path / "nao-existe.json")
    quebrado = tmp_path / "q.json"
    quebrado.write_text("{chave: " + CHAVE_JWT, encoding="utf-8")
    with pytest.raises(ErroBanco) as e:
        supabase.carregar(quebrado)
    assert CHAVE_JWT not in str(e.value)


def test_o_caminho_padrao_fica_ao_lado_da_chave_do_google_e_a_config_pode_trocar():
    assert supabase.caminho_da_chave({}).endswith("chave-supabase.json")
    assert supabase.caminho_da_chave({"supabase": {"caminho_chave": "D:\\x\\k.json"}}) == "D:\\x\\k.json"


# ---- entrada de cada PC (Supabase Auth) e leitura em páginas ----
SENHA = "senha-secreta-de-teste"


def entrada(token="T1", renova="R1", expira=3600):
    return Resposta(corpo={"access_token": token, "refresh_token": renova, "expires_in": expira})


def banco_com_credencial(*respostas, agora=None):
    s, relogio = Sessao(*respostas), agora or [1000.0]
    return Banco(URL, CHAVE_NOVA, email="pc@exemplo.com", senha=SENHA, sessao=s, tentativa_segundos=5, limite_segundos=60,
                 relogio=lambda: relogio[0]), s, relogio


def test_carregar_aceita_email_e_senha_juntos_e_recusa_um_sem_o_outro(tmp_path):
    f = tmp_path / "k.json"
    f.write_text(json.dumps({"url": URL, "chave": CHAVE_NOVA, "email": "a@b.com", "senha": SENHA}), encoding="utf-8")
    assert supabase.carregar(f) == (URL, CHAVE_NOVA, "a@b.com", SENHA)
    f.write_text(json.dumps({"url": URL, "chave": CHAVE_NOVA, "email": "a@b.com"}), encoding="utf-8")
    with pytest.raises(ErroBanco, match="juntos"):
        supabase.carregar(f)


def test_com_credencial_entra_uma_vez_e_manda_o_token_do_pc_nas_chamadas():
    b, s, _ = banco_com_credencial(entrada(), Resposta(corpo=[]), Resposta(corpo=[]))
    b.ler("aba_linhas")
    b.ler("aba_linhas")
    entradas = [p for p in s.pedidos if "/auth/v1/token" in p[1]]
    assert len(entradas) == 1 and entradas[0][2]["params"] == {"grant_type": "password"}
    assert json.loads(entradas[0][2]["data"].decode("utf-8")) == {"email": "pc@exemplo.com", "password": SENHA}
    leituras = [p for p in s.pedidos if "/rest/v1/" in p[1]]
    assert all(p[2]["headers"]["Authorization"] == "Bearer T1" and p[2]["headers"]["apikey"] == CHAVE_NOVA for p in leituras)


def test_token_perto_de_vencer_e_renovado_com_o_refresh_token():
    b, s, relogio = banco_com_credencial(entrada("T1", "R1", 3600), Resposta(corpo=[]), entrada("T2", "R2", 3600), Resposta(corpo=[]))
    b.ler("t")
    relogio[0] += 3600 - 30   # falta menos de um minuto
    b.ler("t")
    segunda = [p for p in s.pedidos if "/auth/v1/token" in p[1]][1]
    assert segunda[2]["params"] == {"grant_type": "refresh_token"}
    assert [p for p in s.pedidos if "/rest/v1/" in p[1]][-1][2]["headers"]["Authorization"] == "Bearer T2"


def test_401_numa_chamada_entra_de_novo_uma_vez_e_acerta():
    b, s, _ = banco_com_credencial(entrada("T1"), Resposta(401, texto="JWT expired"), entrada("T2"), Resposta(corpo=[{"ok": 1}]))
    assert b.ler("t") == [{"ok": 1}]
    assert len([p for p in s.pedidos if "/rest/v1/" in p[1]]) == 2


def test_senha_errada_vira_erro_claro_sem_mostrar_a_senha_e_sem_insistir():
    b, s, _ = banco_com_credencial(Resposta(400, texto='{"error":"invalid_grant","email":"pc@exemplo.com"}'))
    with pytest.raises(ErroBanco) as e:
        b.ler("t")
    assert e.value.codigo == 401 and SENHA not in str(e.value) and "pc@exemplo.com" not in str(e.value)
    assert len(s.pedidos) == 1


def test_ler_tudo_junta_as_paginas_ate_vir_uma_incompleta():
    b, s = banco(Resposta(corpo=[{"id": 1}, {"id": 2}]), Resposta(corpo=[{"id": 3}]))
    assert b.ler_tudo("aba_linhas", {"aba": "eq.X"}, colunas="id", ordem="id.asc", pagina=2) == [{"id": 1}, {"id": 2}, {"id": 3}]
    assert [p[2]["params"].get("offset") for p in s.pedidos] == [None, 2]
    assert all(p[2]["params"]["limit"] == 2 and p[2]["params"]["order"] == "id.asc" for p in s.pedidos)
