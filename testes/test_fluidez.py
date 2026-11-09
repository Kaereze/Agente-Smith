"""Fluidez do Painel (09/11/2026): o que a tela pede o tempo todo precisa responder rápido e sem refazer trabalho à toa."""
import copy
import hashlib
import json

import app_servidor


def _assinatura_antiga(corpo):
    """A versão de 21/10/2026: percorria a estrutura inteira em Python e serializava de novo. Fica aqui como referência do que a nova deve dizer."""
    def limpar(x):
        if isinstance(x, dict):
            return {k: limpar(v) for k, v in x.items() if k not in app_servidor.VOLATEIS_TELA}
        if isinstance(x, list):
            return [limpar(v) for v in x]
        return x
    return hashlib.sha1(json.dumps(limpar(corpo), ensure_ascii=False, default=str).encode("utf-8"), usedforsecurity=False).hexdigest()[:16]


BASE = {
    "agente": "João", "pc": "DESKTOP-X", "atualizado_em": "2026-11-09T10:00:00-03:00",
    "pcs": [{"pc": "A", "agente": "Clara", "visto": "2026-11-09 10:00:00", "online": True}, {"pc": "B", "agente": "Bernardo", "visto": "", "online": False}],
    "fila": [{"chave": "k1", "dias": 3, "nome": "Ana Souza", "campos": [["Nome Tomador", "Ana"], ["CEP", "40170-110"]], "prazo": {"vence": "2026-11-10", "dias": 1.5}},
             {"chave": "k2", "dias": 0, "nome": "Bia", "obs": 'disse "dias": 9 e \\"visto\\": 1', "campos": []}],
    "emails": [{"id": "e1", "assunto": 'Prazo "dias": 3?', "atualizado": "x", "visto": None, "dias": -2}],
}


def _com(mudanca):
    c = copy.deepcopy(BASE)
    mudanca(c)
    return c


def test_assinatura_nova_diz_igual_exatamente_quando_a_antiga_dizia():
    mudancas = {
        "nada mudou": lambda c: None,
        "so a hora da leitura": lambda c: c.update(atualizado_em="2026-11-09T10:00:15-03:00"),
        "so o visto de um PC": lambda c: c["pcs"][0].update(visto="2026-11-09 10:01:00"),
        "so os dias de espera (em qualquer fundura)": lambda c: (c["fila"][0].update(dias=4), c["fila"][0]["prazo"].update(dias=0.5), c["emails"][0].update(dias=7)),
        "um nome mudou": lambda c: c["fila"][0].update(nome="Ana Souza Lima"),
        "um campo do formulario mudou": lambda c: c["fila"][0]["campos"][1].__setitem__(1, "40170-111"),
        "entrou um pedido": lambda c: c["fila"].append({"chave": "k3", "dias": 1, "nome": "Caio"}),
        "saiu um e-mail": lambda c: c["emails"].clear(),
        "PC ficou online": lambda c: c["pcs"][1].update(online=True),
        "texto que so parece ter um campo volatil mudou": lambda c: c["fila"][1].update(obs='disse "dias": 8 e \\"visto\\": 1'),
        "assunto com aspas mudou": lambda c: c["emails"][0].update(assunto='Prazo "dias": 4?'),
    }
    antes_antiga, antes_nova = _assinatura_antiga(BASE), app_servidor.assinatura_tela(BASE)
    for nome, mudanca in mudancas.items():
        depois = _com(mudanca)
        igual_antiga = _assinatura_antiga(depois) == antes_antiga
        igual_nova = app_servidor.assinatura_tela(depois) == antes_nova
        assert igual_nova == igual_antiga, f"'{nome}': a antiga diz igual={igual_antiga}, a nova diz igual={igual_nova}"


def test_assinatura_nova_nao_se_deixa_enganar_por_campo_volatil_digitado_pelo_hospede():
    # o hóspede escreveu um texto parecido com o campo "dias" do JSON: isso é dado de verdade e precisa contar
    a = _com(lambda c: c["fila"][1].update(obs='ok", "dias": 3, "x": "y'))
    b = _com(lambda c: c["fila"][1].update(obs='ok", "dias": 4, "x": "y'))
    assert app_servidor.assinatura_tela(a) != app_servidor.assinatura_tela(b)


# ---------- status do envio: nada de ir ao Google a cada consulta da tela ----------
import threading
import time
import types

from painel import estado_envio
from emails import envio_nf


class _Backend:
    """Google de mentira: conta as leituras e pode demorar ou falhar."""
    def __init__(self, demora=0.0, falha=False):
        self.leituras, self.demora, self.falha = 0, demora, falha

    def ler_abas(self, planilha, nomes, faixas=None):
        self.leituras += 1
        time.sleep(self.demora)
        if self.falha:
            raise OSError("sem rede")
        return {envio_nf.ABA_FILA: [envio_nf.CAB_FILA]}, {}


def _estado_de_mentira(backend):
    classe = next(c for c in vars(estado_envio).values() if isinstance(c, type) and hasattr(c, "situacao_envio"))
    e = types.SimpleNamespace(backend=backend, central="planilha", _fila_status=None, _lendo_fila_status=threading.Lock(),
                              FILA_STATUS_SEGUNDOS=3.0, envio_nf=types.SimpleNamespace(locais={}, fila={"x": 1}, situacao=lambda i, f: {"estado": "aguardando", "fila": f}))
    e._fila_para_status = types.MethodType(classe._fila_para_status, e)
    e.situacao_envio = types.MethodType(classe.situacao_envio, e)
    return e


def test_consultas_seguidas_do_status_leem_o_google_uma_vez_so():
    b = _Backend()
    e = _estado_de_mentira(b)
    for _ in range(25):
        e.situacao_envio("ENV-1")
    assert b.leituras == 1


def test_consultas_ao_mesmo_tempo_nao_viram_varias_leituras_iguais():
    b = _Backend(demora=0.3)
    e = _estado_de_mentira(b)
    respostas = []
    fios = [threading.Thread(target=lambda: respostas.append(e.situacao_envio("ENV-1"))) for _ in range(8)]
    for f in fios:
        f.start()
    for f in fios:
        f.join()
    assert b.leituras == 1 and len(respostas) == 8                    # um lê; os outros seguem com o que o Painel já tem, sem esperar o Google


def test_se_o_google_falha_o_status_sai_da_fila_que_o_painel_ja_tem():
    e = _estado_de_mentira(_Backend(falha=True))
    r = e.situacao_envio("ENV-1")
    assert r["estado"] == "aguardando" and r["fila"] is None          # None: o envio_nf usa a fila da última volta; nada de erro na tela


# ---------- leitura dos hotéis: só reinterpreta a aba que mudou ----------
import copy as _copy

from painel import app_dados as _dados


def _leitura(cfg, planilha, aba="ESTRELA"):
    from test_app import ESTRELA
    return ESTRELA, planilha.aba(ESTRELA)


def test_aba_que_nao_mudou_nao_e_reinterpretada(cfg, planilha):
    aba, linhas = _leitura(cfg, planilha)
    leitor = _dados.LeituraDeHoteis()
    primeira = leitor.ler(aba, "ESTRELA CENTRO", _copy.deepcopy(linhas), cfg)
    segunda = leitor.ler(aba, "ESTRELA CENTRO", _copy.deepcopy(linhas), cfg)        # a mesma aba lida de novo: linhas iguais
    assert leitor.interpretadas == 1
    assert primeira == segunda == _dados.ler_solicitacoes(aba, "ESTRELA CENTRO", linhas, cfg)   # e o resultado é idêntico ao de interpretar de verdade


def test_mudou_uma_celula_ou_o_hotel_ou_a_configuracao_reinterpreta(cfg, planilha):
    aba, linhas = _leitura(cfg, planilha)
    leitor = _dados.LeituraDeHoteis()
    leitor.ler(aba, "ESTRELA CENTRO", _copy.deepcopy(linhas), cfg)
    alterada = _copy.deepcopy(linhas)
    alterada[1][-1] = "TRUE" if alterada[1][-1] != "TRUE" else ""                    # o robô marcou Enviado numa linha
    leitor.ler(aba, "ESTRELA CENTRO", alterada, cfg)
    assert leitor.interpretadas == 2
    leitor.ler(aba, "OUTRO NOME", alterada, cfg)                                    # hotel renomeado no cadastro
    assert leitor.interpretadas == 3
    outra = _copy.deepcopy(cfg)
    outra["formato_data_planilha"] = "brasileiro" if cfg.get("formato_data_planilha") != "brasileiro" else "americano"
    leitor.ler(aba, "OUTRO NOME", alterada, outra)                                  # configuração mudou
    assert leitor.interpretadas == 4


def test_quem_usa_os_pedidos_pode_acrescentar_campos_sem_sujar_o_que_esta_guardado(cfg, planilha):
    aba, linhas = _leitura(cfg, planilha)
    leitor = _dados.LeituraDeHoteis()
    a = leitor.ler(aba, "ESTRELA CENTRO", linhas, cfg)
    a[0]["marca_de_outra_etapa"] = True
    b = leitor.ler(aba, "ESTRELA CENTRO", linhas, cfg)
    assert "marca_de_outra_etapa" not in b[0]


def test_aba_descadastrada_e_esquecida(cfg, planilha):
    aba, linhas = _leitura(cfg, planilha)
    leitor = _dados.LeituraDeHoteis()
    leitor.ler(aba, "ESTRELA CENTRO", linhas, cfg)
    leitor.esquecer_menos({})
    leitor.ler(aba, "ESTRELA CENTRO", linhas, cfg)
    assert leitor.interpretadas == 2


# ---------- cache em disco: só a janela que a tela usa ----------
def test_cache_guarda_so_os_pedidos_da_janela_com_os_estados_deles():
    sols = [{"chave": "velho", "data": "2025-01-10"}, {"chave": "recente", "data": "2026-11-01"}, {"chave": "sem_data", "data": ""}, {"chave": "limite", "data": "2026-07-01"}]
    estados = {"velho": {"n": 1}, "recente": {"n": 2}, "sem_data": {"n": 3}, "limite": {"n": 4}, "orfao": {"n": 5}}
    ficam, est = _dados.podar_para_cache(sols, estados, "2026-07-01")
    assert [s["chave"] for s in ficam] == ["recente", "sem_data", "limite"]                      # o dia do corte entra; sem data não some
    assert set(est) == {"recente", "sem_data", "limite"}                                          # estado de pedido que saiu também sai


def test_salvar_cache_nao_grava_o_historico_inteiro(tmp_path, monkeypatch):
    import datetime as dt
    import pickle
    sols = [{"chave": f"antigo{i}", "data": "2024-03-01"} for i in range(500)] + [{"chave": f"novo{i}", "data": dt.date.today().isoformat()} for i in range(20)]
    estado = types.SimpleNamespace(atualizado_em="agora", relogio=lambda: 1e9, cache_salvo=0, lock=threading.Lock(), solicitacoes=sols,
                                   estados={s["chave"]: {} for s in sols}, status={}, fi={}, cadastro=None, abas_hotel={})
    monkeypatch.setattr(app_servidor, "CAMINHO_CACHE", tmp_path / "cache.pkl")
    app_servidor.Estado.salvar_cache(estado, forcar=True)
    gravado = pickle.loads((tmp_path / "cache.pkl").read_bytes())
    assert len(gravado["solicitacoes"]) == 20 and all(s["chave"].startswith("novo") for s in gravado["solicitacoes"])
    assert len(gravado["estados"]) == 20


# ---------- a tela é avisada assim que a Central é lida, não só no fim da volta inteira ----------
from pathlib import Path as _Path

from codigo_fonte import fonte_servidor

_RAIZ = _Path(__file__).resolve().parents[1]


def test_ciclo_publica_a_novidade_logo_depois_de_ler_a_central():
    fonte = fonte_servidor(_RAIZ)
    laco = fonte[fonte.index("def laco():"):fonte.index("esperar_proxima_volta(estado, ultimo_uso, em_uso, em_fundo)", fonte.index("def laco():"))]
    ordem = [laco.index(t) for t in ("estado.atualizar()", "estado.preparar_para_a_tela()", "estado.versao_tela += 1", "estado.salvar_cache()")]
    assert ordem == sorted(ordem), "publicar (e deixar a lista pronta) tem que vir ANTES de gravar o cache"
    for lenta in ("atualizar_notas_emails", "atualizar_fi", "atualizar_atividade"):
        assert f"estado.{lenta}()" not in laco, f"{lenta} não pode travar a volta principal"
    assert laco.count("estado.versao_tela += 1") == 2          # e de novo no fim da volta, como sempre


def test_lista_de_pedidos_fica_pronta_para_o_periodo_que_a_tela_pediu(monkeypatch):
    chamadas = []
    estado = types.SimpleNamespace(dias_pedidos_pela_tela=60, fila_da_tela=lambda d: chamadas.append(d))
    app_servidor.Estado.preparar_para_a_tela(estado)
    del estado.dias_pedidos_pela_tela
    app_servidor.Estado.preparar_para_a_tela(estado)
    assert chamadas == [60, 60]                                  # o pedido da tela; sem pedido ainda, o padrão dela (60)


def test_preparar_a_lista_nunca_derruba_o_ciclo():
    estado = types.SimpleNamespace(fila_da_tela=lambda d: 1 / 0)
    app_servidor.Estado.preparar_para_a_tela(estado)             # não levanta


# ---------- excluir / urgência / concluir não esperam o Google ----------
def test_evento_do_correio_vale_na_hora_e_grava_por_tras():
    import threading as _th
    from painel.estado_correio import CorreioMixin
    gravou, solta = _th.Event(), _th.Event()
    montou = []

    class E(types.SimpleNamespace):
        _evento_na_hora = CorreioMixin._evento_na_hora

        def _montar_correio(self):
            montou.append(list(self.eventos_pendentes))

        def _gravar_eventos_pendentes(self):   # a ida ao Google: lenta de propósito
            solta.wait(5)
            gravou.set()

    e = E(lock=_th.RLock(), eventos_pendentes=[])
    e._evento_na_hora(["linha"])
    assert montou == [["linha"]] and not gravou.is_set()          # a lista já refletiu, e a gravação ainda não terminou
    solta.set()
    assert gravou.wait(5)                                         # ... e ela acontece por trás


def test_excluir_urgencia_e_concluir_nao_gravam_na_central_no_clique():
    fonte = (_RAIZ / "src" / "painel" / "estado_correio.py").read_text(encoding="utf-8")
    for nome in ("def excluir_email", "def marcar_urgencia", "def concluir_conversa", "def mover_email_nf"):
        i = fonte.index(nome)
        corpo = fonte[i:fonte.index("\n    def ", i + 10)]
        assert "anexar_linhas" not in corpo and "_evento_na_hora" in corpo, nome


def test_etapas_lentas_rodam_cada_uma_na_sua_linha():
    fonte = fonte_servidor(_RAIZ)
    for etapa in ("atualizar_notas_emails", "atualizar_fi", "atualizar_atividade"):
        assert "etapa_lenta(" in fonte and f"estado.{etapa}, " in fonte, etapa
