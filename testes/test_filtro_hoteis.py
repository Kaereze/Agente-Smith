"""Filtro de vários hotéis com prioridade pela quantidade de e-mails (03/11/2026, prévia aprovada pelo João): regras de pecas/filtro_hoteis.js e a ligação com as telas."""
import json
import shutil
import subprocess
from pathlib import Path

import pytest
from tela_texto import pagina

UI = Path(__file__).resolve().parent.parent / "app_ui"
PECA = (UI / "pecas" / "filtro_hoteis.js").read_text(encoding="utf-8")
CORREIO = (UI / "correio.js").read_text(encoding="utf-8")
HTML = pagina(UI)
CSS = (UI / "pecas" / "filtro_hoteis.css").read_text(encoding="utf-8")

# o arquivo mexe em document/localStorage ao carregar: no Node entram só os mínimos para ele subir
PREPARO = ("globalThis.document = { addEventListener() {}, getElementById() { return null; }, querySelector() { return null; } };"
           "globalThis.localStorage = { getItem() { return null; }, setItem() {} }; globalThis.window = { innerWidth: 1500 };"
           "globalThis.requestAnimationFrame = f => f();")


def _node(expr):
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    saida = subprocess.run(["node", "-e", PREPARO + PECA + "\nconsole.log(JSON.stringify(" + expr + "));"], capture_output=True, text=True,
                           encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    return json.loads(saida.stdout)


def test_prioridade_vem_da_quantidade_de_emails():
    r = _node("[0, 1, 3, 4, 9, 10, 40].map(fhNivel)")
    assert r == ["vazia", "baixa", "baixa", "media", "media", "alta", "alta"]


def test_contar_separa_hoteis_juntos_e_passa_so_os_marcados():
    r = _node("""(() => {
      const n = fhContar([{ hotel: 'LUXOR' }, { hotel: 'LUXOR / BAHIA' }, { hotel: 'BAHIA' }, { hotel: '' }]);
      const antes = fhPassa('LUXOR');                              // sem hotel marcado, passa tudo
      FH.sel = new Set(['BAHIA']);
      return [n, antes, fhPassa('BAHIA'), fhPassa('LUXOR / BAHIA'), fhPassa('LUXOR'), fhPassa('')];
    })()""")
    assert r[0] == {"LUXOR": 2, "BAHIA": 2} and r[1] is True and r[2:] == [True, True, False, False]


def test_lista_agrupa_por_nivel_e_a_data_alterna_dentro_de_cada_nivel():
    r = _node("""(() => {
      FH.contagem = { A: 12, B: 5, C: 1, D: 0 };
      const l = [{ h: 'C', q: '2026-11-01' }, { h: 'A', q: '2026-11-03' }, { h: 'B', q: '2026-11-02' }, { h: 'A', q: '2026-11-01' }, { h: 'D', q: '2026-10-30' }, { h: 'B', q: '2026-11-04' }];
      FH.ordem = 'antigo'; const antigo = fhAgrupar(fhPorData(l, x => x.q), x => x.h).map(x => x.h + x.q.slice(8));
      FH.ordem = 'novo'; const novo = fhAgrupar(fhPorData(l, x => x.q), x => x.h).map(x => x.h + x.q.slice(8));
      return [antigo, novo, fhContarNiveis(l, x => x.h)];
    })()""")
    assert r[0] == ["A01", "A03", "B02", "B04", "C01", "D30"]                      # alta, média, baixa, sem e-mail; o mais antigo primeiro em cada nível
    assert r[1] == ["A03", "A01", "B04", "B02", "C01", "D30"]                      # o botão inverte só a data
    assert r[2] == {"alta": 2, "media": 2, "baixa": 1, "vazia": 1}


def test_item_com_dois_hoteis_vale_pelo_melhor_nivel():
    r = _node("(() => { FH.contagem = { A: 12, C: 1 }; return [fhNivelDe('C / A'), fhNivelDe('C'), fhNivelDe('Z')]; })()")
    assert r == ["alta", "baixa", "vazia"]


def test_meus_hoteis_so_marca_os_que_existem_e_os_botoes_de_nivel_funcionam():
    r = _node("""(() => {
      FH.hoteis = () => ['A', 'B', 'C']; FH.contagem = { A: 12, B: 11, C: 2 }; FH.meus = new Set(['A', 'Z']);
      fhMudou = () => {};
      fhAcao('meus'); const meus = [...FH.sel];
      fhAcao('altas'); const altas = [...FH.sel].sort();
      fhAcao('todos'); const todos = FH.sel.size;
      fhAcao('limpar'); const nenhum = FH.sel.size;
      return [meus, altas, todos, nenhum, fhHoteisDoNivel('baixa')];
    })()""")
    assert r == [["A"], ["A", "B"], 3, 0, ["C"]]                                 # "Z" não está no cadastro: fica de fora


def test_o_html_do_filtro_mostra_o_primeiro_hotel_e_quantos_mais():
    r = _node("""(() => { FH.hoteis = () => ['A', 'B', 'C']; FH.sel = new Set(['B', 'C']); FH.aberto = false;
      const fechado = fhHtml(); FH.aberto = true; const aberto = fhHtml(); return [fechado, aberto]; })()""")
    fechado, aberto = r
    assert "<b>B</b>" in fechado and "+1" in fechado and 'data-fh-acao="limpar"' in fechado and "fh-menu" not in fechado
    assert 'data-fh-acao="meus"' in aberto and 'data-fh-acao="salvar"' in aberto and 'type="checkbox"' in aberto and "2 selecionados" in aberto


def test_as_telas_usam_o_filtro_de_varios_hoteis_e_o_botao_de_ordem():
    assert "fhPassa(e.hotel)" in CORREIO and 'if (cx.caixa === "entrada") return fhPorData(lista, e => e.quando)' in CORREIO
    assert "fhHtml() + (cx.caixa === \"entrada\" ? fhBotaoOrdem()" in CORREIO and "ol-quebra" in CORREIO
    # sem "Prioridades (da seleção)" no menu, sem blocos "Prioridade alta" na lista e sem o menu "Filtro: Todos" (João, 07/11/2026)
    assert "data-fh-nivel" not in CORREIO and "Prioridades (da seleção)" not in CORREIO and "fhAgrupar(lista, e =>" not in CORREIO
    assert "filtroDaListaHtml" not in CORREIO and "FILTROS_LISTA" not in CORREIO
    assert "cx.hotel" not in CORREIO and "pecaFiltro({ id: \"cx-hotel\"" not in CORREIO                    # o filtro de um hotel só saiu
    assert 'id: "nf-hotel"' not in HTML and "fhPassa(it.hoteis)" in HTML and "fhAgrupar(lista, it => it.hoteis)" in HTML
    assert '<script src="/pecas/filtro_hoteis.js"></script>' in HTML and '<link rel="stylesheet" href="/pecas/filtro_hoteis.css">' in HTML
    assert ".fh-ordem{display:inline-flex!important" in CSS and "position:fixed" in CSS                      # o botão fica à vista e o menu não é cortado


def test_a_lista_fica_so_neste_pc_e_nao_vai_ao_google():
    assert "localStorage.setItem(\"painel.meusHoteis\"" in PECA and "api(" not in PECA and "fetch(" not in PECA
