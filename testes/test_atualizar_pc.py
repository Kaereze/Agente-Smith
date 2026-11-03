"""Animação simples do "Atualizar PC" (29/10/2026): as regras de pecas/atualizar_pc.js e a ligação com a página das Máquinas."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest

UI = Path(__file__).resolve().parent.parent / "app_ui"
PECA = (UI / "pecas" / "atualizar_pc.js").read_text(encoding="utf-8")
PAINEL = (UI / "painel.js").read_text(encoding="utf-8")
HTML = (UI / "index.html").read_text(encoding="utf-8")


def _node(expr):
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    saida = subprocess.run(["node", "-e", PECA + "\nconsole.log(JSON.stringify(" + expr + "));"], capture_output=True, text=True,
                           encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


PCS = "[{pc:'PC-A',agente:'Clara',versao:'aaa1111'},{pc:'PC-B',agente:'Cristian',versao:'aaa1111'}]"


def test_um_pc_anda_e_vira_atualizado_quando_a_versao_muda():
    r = _node(f"""(() => {{
      const a = atzNovo('PC-A', {PCS}.slice(0, 1), 1000);
      const antes = atzSituacao(a, {{ pcs: [{{ pc: 'PC-A', versao: 'aaa1111' }}], eventos: [] }}, 5000);
      const depois = atzSituacao(a, {{ pcs: [{{ pc: 'PC-A', versao: 'bbb2222' }}], eventos: [] }}, 9000);
      return [antes, depois];
    }})()""")
    antes, depois = r
    assert antes["estado"] == "andando" and antes["botao"] == "Pedido enviado…" and "até 1 min" in antes["linha"]
    assert depois["estado"] == "ok" and depois["botao"] == "✓ Atualizado"


def test_o_aviso_atualizado_da_atividade_tambem_conta():
    r = _node("""(() => {
      const a = atzNovo('PC-A', [{ pc: 'PC-A', agente: 'Clara', versao: 'aaa1111' }], Date.parse('2026-10-29T15:00:00'));
      return [atzSituacao(a, { pcs: [{ pc: 'PC-A', versao: 'aaa1111' }], eventos: [{ pc: 'PC-A', tipo: 'ATUALIZADO', quando: '2026-10-29 14:50:00' }] }, Date.parse('2026-10-29T15:00:10')).estado,
              atzSituacao(a, { pcs: [{ pc: 'PC-A', versao: 'aaa1111' }], eventos: [{ pc: 'PC-A', tipo: 'ATUALIZADO', quando: '2026-10-29 15:00:30' }] }, Date.parse('2026-10-29T15:00:40')).estado];
    })()""")
    assert r == ["andando", "ok"]                                                       # aviso de antes do clique não vale; o de depois vale


def test_passou_de_1_minuto_sem_mudar_avisa_em_ambar_e_libera():
    r = _node(f"""(() => {{
      const a = atzNovo('PC-A', {PCS}.slice(0, 1), 0);
      const s = atzSituacao(a, {{ pcs: [{{ pc: 'PC-A', versao: 'aaa1111' }}], eventos: [] }}, 61000);
      return [s, atzTerminou(a, s, 61000), atzTerminou(a, s, 61000 + 3600)];
    }})()""")
    sit, antes_do_tempo, depois_do_tempo = r
    assert sit["estado"] == "sem" and sit["botao"] == "Sem mudança" and sit["linha"] == "Sem mudança em 1 min · veja o Log"
    assert antes_do_tempo is False and depois_do_tempo is True                                # o aviso fica à vista 3,5 s e o botão volta ao normal


def test_todos_conta_quantos_ja_atualizaram_e_diz_quem_faltou():
    r = _node(f"""(() => {{
      const a = atzNovo('TODOS', {PCS}, 0);
      const meio = atzSituacao(a, {{ pcs: [{{ pc: 'PC-A', versao: 'bbb2222' }}, {{ pc: 'PC-B', versao: 'aaa1111' }}], eventos: [] }}, 20000);
      const corte = atzSituacao(a, {{ pcs: [{{ pc: 'PC-A', versao: 'bbb2222' }}, {{ pc: 'PC-B', versao: 'aaa1111' }}], eventos: [] }}, 61000);
      const fim = atzSituacao(a, {{ pcs: [{{ pc: 'PC-A', versao: 'bbb2222' }}, {{ pc: 'PC-B', versao: 'bbb2222' }}], eventos: [] }}, 30000);
      return [meio, corte, fim];
    }})()""")
    meio, corte, fim = r
    assert meio["estado"] == "andando" and meio["linha"] == "1 de 2 atualizados · aguardando"
    assert corte["estado"] == "sem" and corte["linha"] == "1 de 2 atualizados · sem mudança: Cristian" and corte["faltam"] == ["Cristian"]
    assert fim["estado"] == "ok" and fim["linha"] == "2 de 2 atualizados"


def test_andamento_nao_acaba_sozinho():
    r = _node(f"(() => {{ const a = atzNovo('PC-A', {PCS}.slice(0, 1), 0); const s = atzSituacao(a, {{ pcs: [{{ pc: 'PC-A', versao: 'aaa1111' }}], eventos: [] }}, 10000); return [s.estado, atzTerminou(a, s, 999999)]; }})()")
    assert r == ["andando", False]


def test_a_pagina_guarda_o_andamento_e_so_aceita_um_clique_enquanto_anda():
    assert '<script src="/pecas/atualizar_pc.js"></script>' in HTML and (UI / "pecas" / "atualizar_pc.js").exists()
    assert "const atz = {};" in PAINEL and "botaoAtz(p.pc," in PAINEL and 'botaoAtz("TODOS",' in PAINEL
    assert 'atzSituacao(atz[para], at.dados).estado === "andando"' in PAINEL and "if (!r.ok) return toast(" in PAINEL      # falhou: botão livre
    assert "atz[para] = atzNovo(" in PAINEL and "acompanharAtz()" in PAINEL
    assert ".btn-atz.andando svg{animation:atz-gira" in HTML and "prefers-reduced-motion" in HTML and "var(--info)" in HTML
