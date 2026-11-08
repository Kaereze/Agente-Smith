"""Teste de tela (auditoria 27/10/2026): abre o Painel de verdade num navegador, no modo demonstração, e confere cada tela.

Faz sozinho o que fazíamos à mão: abrir cada aba, ver se tem erro de JavaScript, rolagem pro lado ou texto espremido numa
coluna estreita (foi o que aconteceu com o bloco "NF enviada": 32 px de largura por colidir com a classe `.av`).

Usa o Edge do Windows pelo Playwright (não baixa navegador; o GitHub Actions do Windows já tem). Sem Playwright ou sem Edge
(pacote do pendrive, PC sem o modo de desenvolvimento) os testes são pulados em vez de falhar. Dados 100% fictícios (demo.py);
o servidor sobe dentro do teste numa porta livre, sem mexer no Painel que estiver aberto e sem gravar em estado/.
"""
import threading
from http.server import ThreadingHTTPServer

import pytest

sync_api = pytest.importorskip("playwright.sync_api", reason="pip install -r requirements-dev.txt")

import app_servidor  # noqa: E402
from painel import demo  # noqa: E402
from config import carregar_config  # noqa: E402

TELAS = ["visao", "fila", "correio", "gerencia", "maquinas"]


@pytest.fixture(scope="module")
def painel_demo(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("telas")
    mp = pytest.MonkeyPatch()
    for nome, arq in (("CAMINHO_CACHE", "cache.pkl"), ("CAMINHO_PREFS", "app.json"), ("CAMINHO_CANCELADAS", "canceladas.json")):
        mp.setattr(app_servidor, nome, tmp / arq)
    servidor = None
    try:
        cfg = demo.configurar_cfg(carregar_config(exigir_chave=False))
        backend = demo.BackendDemo()
        estado = app_servidor.Estado(backend, cfg)
        demo.preparar(estado, backend)
        estado.demo, estado.so_ver = True, False
        estado.atualizar()
        estado.atualizar_notas_emails()
        estado.atualizar_fi()
        estado.atualizar_canceladas()
        estado.versao_tela += 1
        servidor = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: None)   # só para reservar a porta livre
        porta = servidor.server_address[1]
        servidor.server_close()
        mp.setattr(app_servidor, "PORTA", porta)   # o Host aceito pelo servidor nasce dessa constante
        ultimo_uso = [-1e9]
        estado.uso_ref = ultimo_uso
        servidor = ThreadingHTTPServer(("127.0.0.1", porta),
                                       app_servidor.criar_handler(estado, cfg, "token-de-teste", ultimo_uso))
        threading.Thread(target=servidor.serve_forever, daemon=True).start()
        yield f"http://127.0.0.1:{porta}"
    finally:
        if servidor:
            servidor.shutdown()
            servidor.server_close()
        mp.undo()


@pytest.fixture(scope="module")
def navegador():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="msedge")
        except Exception as e:   # sem Edge instalado
            pytest.skip(f"Edge não encontrado para o teste de tela: {str(e)[:80]}")
        yield b
        b.close()


@pytest.fixture
def pagina(navegador):
    contexto = navegador.new_context(viewport={"width": 1440, "height": 900})
    pg = contexto.new_page()
    pg.erros = []
    pg.on("pageerror", lambda e: pg.erros.append(f"JS: {e}"))
    pg.on("console", lambda m: pg.erros.append(f"console: {m.text}")
          if m.type == "error" and "Failed to load resource" not in m.text else None)
    yield pg
    contexto.close()


ESPREMIDOS = """() => {
  const ruins = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (!r.width || !r.height) continue;
    if (el.closest('.so-leitor')) continue;   // texto só para leitor de tela: 1 px de propósito
    const cs = getComputedStyle(el);
    if (cs.visibility === 'hidden' || cs.display === 'none' || cs.position === 'fixed' && r.width === 0) continue;
    const proprio = [...el.childNodes].filter(n => n.nodeType === 3).map(n => n.textContent.trim()).join(' ');
    if (proprio.length >= 25 && r.width < 80) ruins.push(`${el.tagName}.${el.className}: "${proprio.slice(0, 40)}" (${Math.round(r.width)} px)`);
  }
  return ruins;
}"""


def abrir(pagina, base, tela):
    pagina.goto(f"{base}/#{tela}")
    pagina.wait_for_selector(f"#v-{tela}:not(.oculta)", timeout=10000)
    pagina.wait_for_timeout(1500)   # as primeiras leituras (estado e e-mails) chegam e a tela desenha


def confere_a_tela(pagina):
    assert pagina.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1"), "a página rola para o lado"
    assert pagina.evaluate(ESPREMIDOS) == [], "texto espremido numa coluna estreita"
    assert pagina.erros == []


@pytest.mark.parametrize("tela", TELAS)
def test_cada_tela_abre_sem_erro_sem_rolagem_lateral_e_sem_texto_espremido(painel_demo, pagina, tela):
    abrir(pagina, painel_demo, tela)
    confere_a_tela(pagina)


def test_e_mail_aberto_mostra_a_ficha_de_etapas_e_nao_as_caixas_antigas(painel_demo, pagina):
    abrir(pagina, painel_demo, "correio")
    # um e-mail que tenha o pedido do formulário ligado (o 1º da lista pode ser só texto, sem formulário)
    id_com_pedido = pagina.evaluate("itensDaTela('').find(e => e.solicitacao)?.id")
    assert id_com_pedido, "a demonstração precisa ter e-mail com pedido de formulário"
    pagina.locator(f'.cx-l[data-id="{id_com_pedido}"]').click()
    pagina.wait_for_selector(".c-top", timeout=10000)
    # os 3 estados da NF enviada (dados inventados): tudo confere, não consegui ler, pede nova nota
    casos = {
        "ok": {"nfs": [{"nf": "1552", "pdf": "NF 1552.pdf"}], "sugere_concluir": True, "cobre": True, "linhas": []},
        "ler": {"nfs": [{"nf": "1552"}], "avisos_envio": ["1552"], "cobre": None, "linhas": []},
        "nova": {"nfs": [{"nf": "1552"}], "pede_nova": True, "cobre": False, "motivos": ["pede estacionamento"], "linhas": []},
    }
    for nome, cobre in casos.items():
        pagina.evaluate("c => { const e = (cx.dados.emails || []).find(x => x.id === cx.sel); cx.cobre = {[e.id]: c}; desenharLeituraCorreio(); }", cobre)
        pagina.wait_for_selector(".c-lista .c-item", timeout=5000)
        topo = pagina.locator(".c-top").first
        largura = topo.evaluate("el => el.getBoundingClientRect().width")
        pai = topo.evaluate("el => el.parentElement.getBoundingClientRect().width")
        assert largura > pai * 0.9, f"ficha {nome} espremida: {largura:.0f} px de {pai:.0f}"
        # desde 29/10 (João) o reconhecimento automático de NF está desligado: só 2 etapas e nada de Concluir, mesmo com a NF "achada"
        assert pagina.locator(".c-etapas .c-et").count() == 2 and pagina.locator(".c-lista .c-item").count() >= 6
        assert "Concluir" not in pagina.locator(".c-top").inner_text()
    # as caixas e o histórico antigos saíram da leitura
    for antigo in (".cx-cobre", ".cx-aviso-nf", ".cx-hist", ".ol-resumo"):
        assert pagina.locator(antigo).count() == 0, f"sobrou {antigo}"
    confere_a_tela(pagina)


def test_janela_do_robo_abre_sem_erro(painel_demo, pagina):
    abrir(pagina, painel_demo, "visao")
    pagina.evaluate("rbAbrir('agora')")
    pagina.wait_for_timeout(1200)
    confere_a_tela(pagina)


@pytest.mark.parametrize("largura", [1440, 1100])
def test_cabecalho_da_lista_de_emails_nao_corta_nenhuma_letra(painel_demo, navegador, largura):
    """João (07/11/2026): o filtro de hotel e a data apareciam cortados. Nada do cabeçalho da lista passa da coluna, nem com vários hotéis marcados."""
    contexto = navegador.new_context(viewport={"width": largura, "height": 900})
    pg = contexto.new_page()
    try:
        abrir(pg, painel_demo, "correio")
        pg.wait_for_selector(".ol-lcab .ol-ord", timeout=10000)
        for marcar in ("", "FH.sel = new Set(['BOA VIAGEM', 'ESTRELA CENTRO', 'PORTO SEGURO', 'MINI HOTEL']); desenharCorreio()"):
            if marcar:
                pg.evaluate(marcar)
                pg.wait_for_timeout(400)
            cortados = pg.evaluate("""() => { const col = document.querySelector('.ol-lcab').getBoundingClientRect();
              return [...document.querySelectorAll('.ol-lcab *')].filter(el => { const r = el.getBoundingClientRect();
                return r.width && (r.right > col.right + 1 || r.left < col.left - 1 || (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).display !== 'inline')); })
                .map(el => el.tagName + '.' + el.className + ' ' + (el.textContent || '').trim().slice(0, 30)); }""")
            assert cortados == [], (marcar, cortados)
    finally:
        contexto.close()


def test_resumo_de_ontem_novo_abre_mostra_dica_e_troca_para_tabela_sem_cortar_nada(painel_demo, pagina):
    """João (07/11/2026): o resumo ganhou gráficos que se mexem. Sem erro, com dica ao passar o mouse e a opção de ver em tabela."""
    abrir(pagina, painel_demo, "visao")
    pagina.wait_for_selector(".rs-corpo .rs-kpi", timeout=10000)
    assert pagina.locator(".rs-kpi").count() == 5 and pagina.locator(".rs-hit").count() >= 8
    caixa = pagina.locator(".rs-hit").nth(4).bounding_box()
    pagina.mouse.move(caixa["x"] + caixa["width"] / 2, caixa["y"] + 30)
    pagina.wait_for_selector("#rs-dica.on", timeout=3000)
    assert "Pedidos" in pagina.locator("#rs-dica").inner_text()
    pagina.locator("[data-rs-tabela]").click()
    pagina.wait_for_selector(".rs-tabela-on", timeout=3000)
    assert pagina.locator(".rs-so-tabela").is_visible() and not pagina.locator(".rs-so-graficos").is_visible()
    pagina.locator("[data-rs-tabela]").click()
    pagina.wait_for_selector(".rs-so-graficos", state="visible", timeout=3000)
    pagina.locator("[data-rd=hoje]").click()
    pagina.wait_for_selector(".rd-cab h1:has-text('Resumo de hoje')", timeout=3000)
    confere_a_tela(pagina)


def test_pc_sem_caixas_nao_aparece_na_lista_de_pastas_do_email(painel_demo, pagina):
    """João (07/11/2026): o PC de casa ("0 caixas") aparecia na lista de pastas. PC sem caixa de hotel não entra."""
    abrir(pagina, painel_demo, "correio")
    pagina.wait_for_selector(".ol-pc2", timeout=10000)
    pagina.evaluate("st.pcs = [...st.pcs, { pc: 'PC-DE-CASA', agente: 'João', online: true, contas_lista: [] }]; desenharCorreio()")
    pagina.wait_for_timeout(400)
    nomes = pagina.evaluate("[...document.querySelectorAll('.ol-pc2')].map(e => e.textContent)")
    assert nomes and not any("PC-DE-CASA" in n or "0 caixas" in n for n in nomes), nomes


def test_filtros_rapidos_da_lista_de_email_filtram_contam_e_nao_cortam(painel_demo, pagina):
    """João (07/11/2026): "Sem resposta" e "Pedido de correção" voltaram como dois botões na lista, no lugar do menu Filtro."""
    abrir(pagina, painel_demo, "correio")
    pagina.wait_for_selector(".ol-rapido", timeout=10000)
    assert pagina.locator(".ol-rapido").count() == 2
    total = pagina.evaluate("itensDaTela('').length")
    n_sem = int(pagina.locator('[data-cx-rapido="semresp"] em').inner_text().replace(".", ""))
    pagina.locator('[data-cx-rapido="semresp"]').click()
    pagina.wait_for_timeout(300)
    assert pagina.evaluate("itensDaTela('').length") == n_sem <= total
    assert pagina.locator('[data-cx-rapido="semresp"]').get_attribute("aria-pressed") == "true"
    assert pagina.locator('[data-cx-filtro="todas"]').get_attribute("aria-pressed") == "false"
    pagina.locator('[data-cx-rapido="semresp"]').click()   # clicar de novo tira o filtro
    pagina.wait_for_timeout(300)
    assert pagina.evaluate("itensDaTela('').length") == total
    cortados = pagina.evaluate("""() => { const col = document.querySelector('.ol-lcab').getBoundingClientRect();
      return [...document.querySelectorAll('.ol-lcab *')].filter(el => { const r = el.getBoundingClientRect();
        return r.width && (r.right > col.right + 1 || r.left < col.left - 1 || (el.scrollWidth > el.clientWidth + 1 && getComputedStyle(el).display !== 'inline')); })
        .map(el => el.tagName + '.' + el.className + ' ' + (el.textContent || '').trim().slice(0, 30)); }""")
    assert cortados == [], cortados
    confere_a_tela(pagina)


def test_barra_lateral_e_uma_capsula_flutuante_no_meio_da_altura_com_tudo_junto(painel_demo, pagina):
    """João (08/11/2026): barra de borda espelhada, centralizada na altura, com enviar, operador e o botão dos nomes juntos (sem linha antes deles)."""
    abrir(pagina, painel_demo, "visao")
    pagina.wait_for_selector(".capsula", timeout=10000)
    pagina.wait_for_timeout(900)
    cx = pagina.locator(".capsula").bounding_box()
    centro = cx["y"] + cx["height"] / 2
    assert abs(centro - 450) <= 3, f"cápsula fora do meio da altura: centro {centro:.0f} de 450"   # a janela do teste tem 900 px de altura
    assert 50 <= cx["width"] <= 64 and cx["x"] >= 8
    dentro = pagina.evaluate("""() => { const c = document.querySelector('.capsula').getBoundingClientRect();
      return ['.marca', '.navega', '#btn-enviar', '#op-btn', '#btn-recolher'].map(s => { const r = document.querySelector(s).getBoundingClientRect();
        return r.left >= c.left - 1 && r.right <= c.right + 1 && r.top >= c.top - 1 && r.bottom <= c.bottom + 1; }); }""")
    assert all(dentro), dentro
    # separador só entre os grupos (geral | e-mails | admin): nada entre as abas e o pé da barra
    assert pagina.evaluate("getComputedStyle(document.querySelector('.capsula .rodape')).borderTopWidth") == "0px"
    assert pagina.evaluate("[...document.querySelectorAll('.capsula .navega > div')].filter(d => getComputedStyle(d, '::before').content !== 'none' && getComputedStyle(d, '::before').width === '24px').length") >= 1
    # o nome aparece ao passar o mouse
    pagina.locator('.capsula .ln[aria-label="Visão geral"]').hover()
    pagina.wait_for_timeout(350)
    assert pagina.evaluate("getComputedStyle(document.querySelector('.capsula .ln[aria-label=\"Visão geral\"]'), '::after').opacity") == "1"
    confere_a_tela(pagina)


@pytest.mark.parametrize("largura,altura", [(1920, 1080), (1440, 900), (1000, 700)])
@pytest.mark.parametrize("tela", ["visao", "correio", "maquinas", "gerencia", "fila"])
def test_casco_centro_leve_cabe_na_janela_inteira_em_todo_tamanho(painel_demo, navegador, tela, largura, altura):
    """João (08/11/2026): a barra flutuante deixou canto vazio e rodapé cortado. O casco todo (barra, topo, conteúdo, rodapé) tem de caber."""
    contexto = navegador.new_context(viewport={"width": largura, "height": altura})
    pg = contexto.new_page()
    try:
        abrir(pg, painel_demo, tela)
        g = pg.evaluate("""() => { const r = s => document.querySelector(s)?.getBoundingClientRect(), c = r('.capsula'), rod = r('.rodape-status'), t = r('.topo'),
          v = [...document.querySelectorAll('.palco > .vista')].find(x => x.offsetParent)?.getBoundingClientRect();
          return { capsula: [c.left, c.right, c.top + c.height / 2], rodape: [rod.left, rod.right, rod.bottom], vista: [v.left, v.right, v.bottom], topo: t.height ? [t.left, t.right] : null,
                   rolagem: document.documentElement.scrollWidth > innerWidth + 1, vertical: document.documentElement.scrollHeight > innerHeight + 1 } }""")
        assert abs(g["capsula"][2] - altura / 2) <= 3, "a barra tem de ficar no meio da altura"
        assert g["capsula"][1] <= g["vista"][0] + 1, "o conteúdo não pode ficar por baixo da barra"
        assert g["topo"] is None or g["capsula"][1] <= g["topo"][0] + 1, "o topo não pode ficar por baixo da barra"
        assert 0 <= g["rodape"][0] and g["rodape"][1] <= largura and g["rodape"][2] <= altura, f"rodapé cortado: {g['rodape']}"
        assert g["vista"][1] <= largura and g["vista"][2] <= altura + 1, "o conteúdo passa da janela"
        assert not g["rolagem"] and not g["vertical"], "a página rola (a barra de rolagem é só de dentro das telas)"
        assert pg.erros == [] if hasattr(pg, "erros") else True
    finally:
        contexto.close()


def test_barra_com_os_nomes_abertos_cabe_inteira_na_janela_e_empurra_o_conteudo(painel_demo, pagina):
    """Com os nomes abertos a barra ficou cortada na esquerda (08/11/2026): a coluna dela tem de alargar junto."""
    abrir(pagina, painel_demo, "visao")
    pagina.locator("#btn-recolher").click()
    pagina.wait_for_timeout(900)
    g = pagina.evaluate("""() => { const c = document.querySelector('.capsula').getBoundingClientRect(), v = [...document.querySelectorAll('.palco > .vista')].find(x => x.offsetParent).getBoundingClientRect();
      return { esq: c.left, dir: c.right, centro: c.top + c.height / 2, vistaEsq: v.left, texto: document.querySelector('.capsula .ln').getBoundingClientRect().left } }""")
    assert g["esq"] >= 0 and g["texto"] >= g["esq"], f"barra cortada na esquerda: {g}"
    assert g["dir"] <= g["vistaEsq"] + 1, "os nomes abertos não podem cobrir o conteúdo"
    assert abs(g["centro"] - 450) <= 3
    confere_a_tela(pagina)
