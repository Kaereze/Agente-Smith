"""PC só com o Painel (29/10/2026, o da Ingrid): sem Outlook, sem caixas; o pedido de envio vai para o PC dono da caixa."""
import types
from pathlib import Path

import app_servidor
import config
import envio_nf as en
from test_envio_nf import CAIXA, SOL, Relogio, _ler, _prep, _servico

RAIZ = Path(__file__).resolve().parents[1]
ANEXO = [{"tipo": "arquivo", "nome": "n.pdf", "conteudo": b"x"}]


def test_sem_outlook_so_vale_para_o_papel_so_painel():
    assert config.sem_outlook({"papel": "so_painel"})
    assert not config.sem_outlook({"papel": "conferente"}) and not config.sem_outlook({"papel": "principal"}) and not config.sem_outlook({})
    assert not config.e_principal({"papel": "so_painel"})                     # nunca copia nem envia pelo robô


def test_pc_sem_caixa_pede_e_o_pc_dono_envia(cfg, planilha):
    _prep(planilha)
    enviados_dono, enviados_ingrid, trabalhos = [], [], []
    dono = _servico(planilha, cfg, "PC-CLARA", [CAIXA], enviados_dono, Relogio())
    dono.tick(_ler(planilha), "Clara")
    ingrid = _servico(planilha, cfg, "PC-INGRID", [], enviados_ingrid, Relogio())
    ingrid.ler_contas = lambda: []
    ingrid.segundo_plano = trabalhos.append
    ingrid.tick(_ler(planilha), "Ingrid")
    r = ingrid.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, ANEXO, "Ingrid")
    assert r["ok"] and r["destino"] == "PC-CLARA"
    trabalhos[0]()                                                            # grava o pedido na fila da Central
    assert not enviados_ingrid                                                # daqui nada sai: não há Outlook
    assert len(planilha.aba(en.ABA_FILA)) >= 2


def test_pc_sem_caixa_e_sem_dono_ligado_avisa_em_vez_de_enviar(cfg, planilha):
    _prep(planilha)
    enviados = []
    ingrid = _servico(planilha, cfg, "PC-INGRID", [], enviados, Relogio())
    ingrid.tick(_ler(planilha), "Ingrid")
    r = ingrid.pedir(SOL, "hospede@x.com", "NF 9 - FH", "caixa.sem.dono@x.com", ANEXO, "Ingrid")
    assert not r["ok"] and "Nenhum PC" in r["motivo"] and not enviados


def test_pesquisa_pela_rede_nao_mexe_no_outlook_de_quem_nao_tem():
    est = types.SimpleNamespace(cfg={"papel": "so_painel"})
    r = app_servidor.Estado.rede_buscar(est, {"q": "hospede"})
    assert r["resultados"] == [] and r["completo"] and r["fonte"] == "sem_outlook"


def test_o_servidor_nao_vigia_nem_indexa_outlook_no_pc_so_painel():
    fonte = "".join(p.read_text(encoding="utf-8") for p in [RAIZ / "src" / "app_servidor.py", *sorted((RAIZ / "src").glob("estado_*.py"))])
    assert "if not sem_outlook(cfg):" in fonte and "estado.vigiar_caixa_de_saida()" in fonte
    assert 'outlook = "sem Outlook" if sem_outlook(self.cfg)' in fonte           # os outros PCs não o veem como "Outlook fechado"
    assert "estado_outlook = None if sem_outlook(self.cfg)" in fonte             # nem aparece "robô parou de ler e-mails" na atividade
    assert "self.envio_nf.ler_contas = lambda: []" in fonte


def test_tela_pc_so_painel_fica_fora_do_filtro_de_agentes_e_abre_em_todos():
    html = (RAIZ / "app_ui" / "index.html").read_text(encoding="utf-8")
    assert '(st.pcs || []).filter(p => p.papel !== "so_painel").map(p => p.agente)' in html
    # sem ela na lista, escopoAtual() devolve "todos" para quem não tem hotel (antes: abria em "Ingrid" e tudo ficava vazio)
    assert 'agentesEquipe().includes(e) ? e : "todos"' in html
