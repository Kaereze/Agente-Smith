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
