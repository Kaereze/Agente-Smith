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


@pytest.mark.parametrize("largura,altura", [(1920, 1080), (1440, 900), (1100, 800)])
def test_menu_do_filtro_de_hoteis_abre_inteiro_colado_ao_botao_e_nao_e_cortado(painel_demo, navegador, largura, altura):
    """João (09/11/2026): o menu "Meus hotéis" saía cortado pela coluna da lista (o vidro dela prendia o position: fixed e o overflow
    escondia o resto; em 1440 px o menu nem aparecia no lugar). O menu fica fora da coluna: dentro da janela, colado ao botão, clicável."""
    contexto = navegador.new_context(viewport={"width": largura, "height": altura})
    pg = contexto.new_page()
    try:
        abrir(pg, painel_demo, "correio")
        pg.wait_for_selector("[data-fh-abrir]", timeout=10000)
        pg.locator("[data-fh-abrir]").first.click()
        pg.wait_for_selector(".fh-menu", timeout=5000)
        pg.wait_for_timeout(400)
        r = pg.evaluate("""() => { const m = document.querySelector('.fh-menu').getBoundingClientRect(), b = document.querySelector('[data-fh-abrir]').getBoundingClientRect();
          const cx = Math.round(m.left + m.width / 2), cy = Math.round(m.top + m.height / 2), topo = document.elementFromPoint(cx, cy);
          return {m: [m.left, m.top, m.right, m.bottom], b: [b.left, b.bottom], dentro: !!(topo && topo.closest('.fh-menu')), w: innerWidth, h: innerHeight}; }""")
        esq, topo, dir_, base = r["m"]
        assert esq >= 0 and topo >= 0 and dir_ <= r["w"] and base <= r["h"], r                 # inteiro dentro da janela
        assert abs(esq - r["b"][0]) <= 2 and abs(topo - (r["b"][1] + 6)) <= 2, r               # colado ao botão, não deslocado
        assert r["dentro"], "algo cobre o menu (a coluna cortando ou outra peça por cima)"
        pg.locator('.fh-menu [data-fh-h]').first.check()                                       # os cliques do menu solto seguem valendo
        pg.wait_for_timeout(400)
        assert pg.locator(".fh-menu").count() == 1 and pg.locator(".fh-menu [data-fh-h]:checked").count() == 1
        pg.mouse.click(5, altura - 5)                                                          # clique fora fecha e não deixa sobra
        pg.wait_for_timeout(400)
        assert pg.locator(".fh-menu").count() == 0
    finally:
        contexto.close()


@pytest.mark.parametrize("largura", [1100, 1000])
def test_leitor_de_email_ocupa_o_resto_da_largura_quando_a_pasta_lateral_some(painel_demo, navegador, largura):
    """Até 1180 px a pasta lateral some e a mesa tem 2 painéis; antes uma regra de 3 colunas vencia e o leitor ficava com 320 px e um vazio à direita."""
    contexto = navegador.new_context(viewport={"width": largura, "height": 800})
    pg = contexto.new_page()
    try:
        abrir(pg, painel_demo, "correio")
        r = pg.evaluate("""() => { const q = document.querySelector('.cx-quadro').getBoundingClientRect(), d = document.querySelector('.cx-direita').getBoundingClientRect(),
          m = document.querySelector('#cx-mesa').getBoundingClientRect(); return {q: [q.left, q.right], d: [d.left, d.right], m: [m.left, m.right]}; }""")
        assert r["d"][1] >= r["m"][1] - 2, r                      # o leitor vai até a borda direita da mesa
        assert r["d"][0] >= r["q"][1] - 1 and r["d"][0] - r["q"][1] <= 20, r   # e começa logo depois da lista
    finally:
        contexto.close()


@pytest.mark.parametrize("tela", ["correio", "fila"])
@pytest.mark.parametrize("largura,altura", [(1440, 900), (1100, 800)])
def test_lista_de_agentes_abre_inteira_por_cima_de_tudo(painel_demo, navegador, tela, largura, altura):
    """João (09/11/2026): a lista "Caixa de: agente" aparecia cortada pelos cartões (o topo de vidro ficava por baixo do conteúdo)."""
    contexto = navegador.new_context(viewport={"width": largura, "height": altura})
    pg = contexto.new_page()
    try:
        abrir(pg, painel_demo, tela)
        pg.locator("#sc-botao:visible").first.click()
        pg.wait_for_timeout(500)
        r = pg.evaluate("""() => { const l = document.querySelector('#sc-lista').getBoundingClientRect(), pontos = [];
          for (const fx of [0.1, 0.5, 0.9]) for (const fy of [0.05, 0.5, 0.97]) {
            const t = document.elementFromPoint(l.left + l.width * fx, l.top + l.height * fy); pontos.push(!!(t && t.closest('#sc-lista'))); }
          return {l: [l.left, l.top, l.right, l.bottom], w: innerWidth, h: innerHeight, pontos}; }""")
        assert all(r["pontos"]), r                                                    # nada cobre nenhum canto nem o meio da lista
        assert r["l"][0] >= 0 and r["l"][2] <= r["w"] and r["l"][3] <= r["h"], r      # e ela cabe na janela
    finally:
        contexto.close()


# ---------- Ficha do hóspede (João, 09/11/2026) ----------
def _emissao(pagina, campos, nome=""):
    return pagina.evaluate("([campos, nome]) => textoEmissao({campos, nome})", [campos, nome])


def test_texto_da_emissao_tem_o_formato_do_joao_e_nao_inventa_nada(painel_demo, pagina):
    abrir(pagina, painel_demo, "correio")
    campos = [["Check-in da Hospedagem", "28/10/2026"], ["Check-out da Hospedagem", "02/11/2026"], ["Nome do Titular da Reserva", "Marina Albuquerque Costa"],
              ["Nome Tomador", "Outra Pessoa"], ["Informações necessárias na Nota Fiscal", "Nota da hospedagem. Estada 2202."]]
    assert _emissao(pagina, campos).split("\n") == [
        "DATA DE CHECK-IN : 28/10/2026", "DATA DE CHECK-OUT : 02/11/2026", "QUANTIDADE DE DIÁRIAS : 5", "VALOR DA DIÁRIA :", "",
        "VALOR TOTAL :", "Marina Albuquerque Costa - ESTADA 2202"]


def test_texto_da_emissao_estada_so_se_o_hospede_escreveu_o_numero(painel_demo, pagina):
    abrir(pagina, painel_demo, "correio")
    base = [["Nome do Titular da Reserva", "Ana Souza"], ["Check-in da Hospedagem", "01/11/2026"], ["Check-out da Hospedagem", "03/11/2026"]]

    def ultima(campos):
        return _emissao(pagina, campos).split("\n")[-1]
    assert ultima(base) == "Ana Souza"                                                                     # nada escrito: só o nome
    assert ultima(base + [["Informações necessárias na Nota Fiscal", "Preciso da nota da estada"]]) == "Ana Souza"   # "estada" sem número: não inventa
    assert ultima(base + [["Informações necessárias na Nota Fiscal", "estada nº 3317, obrigada"]]) == "Ana Souza - ESTADA 3317"
    assert ultima(base + [["Número da estada", "4410"]]) == "Ana Souza - ESTADA 4410"


def test_texto_da_emissao_diaria_sempre_vazia_e_total_so_se_o_hospede_informou(painel_demo, pagina):
    abrir(pagina, painel_demo, "correio")
    base = [["Nome Tomador", "Empresa X Ltda"], ["Check-in da Hospedagem", "2026-10-28"], ["Check-out da Hospedagem", "2026-10-30"]]
    sem = _emissao(pagina, base).split("\n")
    assert sem[2] == "QUANTIDADE DE DIÁRIAS : 2" and sem[3] == "VALOR DA DIÁRIA :" and sem[5] == "VALOR TOTAL :"
    assert sem[0] == "DATA DE CHECK-IN : 28/10/2026" and sem[-1] == "Empresa X Ltda"                    # data ISO vira dia/mês/ano; sem titular, o tomador
    com = _emissao(pagina, base + [["Valor da Nota", "R$ 1.840,00"]]).split("\n")
    assert com[3] == "VALOR DA DIÁRIA :" and com[5] == "VALOR TOTAL : R$ 1.840,00"


def test_texto_da_emissao_sem_datas_ou_datas_ilegiveis_deixa_em_branco(painel_demo, pagina):
    abrir(pagina, painel_demo, "correio")
    linhas = _emissao(pagina, [["Nome Tomador", "Fulano"]]).split("\n")
    assert linhas[:3] == ["DATA DE CHECK-IN : ", "DATA DE CHECK-OUT : ", "QUANTIDADE DE DIÁRIAS : "]
    errado = _emissao(pagina, [["Check-in da Hospedagem", "05/11/2026"], ["Check-out da Hospedagem", "03/11/2026"], ["Nome Tomador", "Fulano"]]).split("\n")
    assert errado[2] == "QUANTIDADE DE DIÁRIAS : "                                                       # check-out antes do check-in: nada de número
    ilegivel = _emissao(pagina, [["Check-in da Hospedagem", "semana que vem"], ["Check-out da Hospedagem", "domingo"], ["Nome Tomador", "Fulano"]]).split("\n")
    assert ilegivel[0] == "DATA DE CHECK-IN : semana que vem" and ilegivel[2] == "QUANTIDADE DE DIÁRIAS : "


def _ids(pagina):
    return pagina.evaluate("""() => { const t = cx.dados.emails.filter(e => e.pasta !== 'enviado');
      return {form: t.find(e => (e.classes || []).includes('formulario'))?.id, normal: t.find(e => !(e.classes || []).includes('formulario'))?.id}; }""")


def test_formulario_abre_a_ficha_do_hospede_e_email_normal_segue_igual(painel_demo, pagina):
    abrir(pagina, painel_demo, "correio")
    ids = _ids(pagina)
    assert ids["form"] and ids["normal"], "a demonstração precisa ter um formulário e um e-mail normal"
    pagina.evaluate("id => abrirEmail(id)", ids["normal"])
    assert pagina.evaluate("pn.vista") == "correio"                                                       # e-mail normal: leitura de sempre
    pagina.locator(f'.cx-l[data-id="{ids["form"]}"]').click()
    pagina.wait_for_selector("#v-hospede:not(.oculta) .hp-janela")
    assert pagina.evaluate("pn.vista") == "hospede" and pagina.locator("#v-correio.oculta").count() == 1
    assert pagina.locator("#v-fila.oculta").count() == 1                                                  # nunca cai na aba reservada
    assert pagina.locator('.ln[data-vista="correio"][data-caixa="entrada"][aria-current="true"]').count() == 1   # a barra acende "Caixa de entrada"
    assert pagina.locator(".hp-campo").count() >= 8 and pagina.locator(".hp-cab h2").inner_text().strip()
    pagina.locator("[data-hp-voltar]").click()
    assert pagina.evaluate("pn.vista") == "correio"


def test_setas_na_lista_nao_pulam_para_a_ficha(painel_demo, pagina):
    abrir(pagina, painel_demo, "correio")
    ids = _ids(pagina)
    pagina.evaluate("id => abrirEmail(id, true)", ids["form"])
    assert pagina.evaluate("pn.vista") == "correio" and pagina.evaluate("cx.sel") == ids["form"]          # a seta mostra a leitura de sempre


def test_pedido_da_pesquisa_abre_a_ficha_e_nao_a_aba_notas(painel_demo, pagina):
    abrir(pagina, painel_demo, "correio")
    nome = pagina.evaluate("st.fila[0].nome.split(' ')[0]")
    pagina.fill("#busca", nome)
    pagina.wait_for_selector("[data-abrir-ficha]", timeout=8000)
    pagina.locator("[data-abrir-ficha]").first.click()
    pagina.wait_for_selector("#v-hospede:not(.oculta) .hp-janela")
    assert pagina.locator("#v-fila.oculta").count() == 1 and pagina.locator("#v-hospede .hp-campo").count() >= 8


def test_copiar_tudo_abre_janelinha_editavel_com_so_o_texto_da_emissao(painel_demo, navegador):
    contexto = navegador.new_context(viewport={"width": 1440, "height": 900}, permissions=["clipboard-read", "clipboard-write"])
    pg = contexto.new_page()
    try:
        abrir(pg, painel_demo, "correio")
        pg.evaluate("abrirHospede(st.fila.find(s => campoDoPedido(s, /check.?in/) && campoDoPedido(s, /check.?out/)).chave)")
        pg.wait_for_selector("#v-hospede:not(.oculta) [data-hp-emissao]")
        pg.locator("[data-hp-emissao]").click()
        pg.wait_for_selector(".hp-pop #hp-pop-txt")
        linhas = pg.input_value("#hp-pop-txt").split("\n")
        assert linhas[0].startswith("DATA DE CHECK-IN : ") and linhas[3] == "VALOR DA DIÁRIA :" and linhas[4] == "" and linhas[5].startswith("VALOR TOTAL :")
        assert pg.evaluate("navigator.clipboard.readText()").replace("\r", "") == "\n".join(linhas)          # já copia ao abrir
        pg.fill("#hp-pop-txt", "ALTEREI AQUI")                                                           # editável
        pg.keyboard.press("Escape")
        assert pg.locator(".hp-pop").count() == 1, "Esc não pode perder o que foi editado"
        pg.locator("#hp-pop-copiar").click()
        pg.wait_for_timeout(200)
        assert pg.evaluate("navigator.clipboard.readText()") == "ALTEREI AQUI"
        pg.locator(".hp-pop button:has-text('Fechar')").click()
        pg.wait_for_timeout(500)
        assert pg.locator(".hp-pop").count() == 0
    finally:
        contexto.close()


@pytest.mark.parametrize("largura", [1440, 1100, 420])
def test_ficha_do_hospede_cabe_na_janela_sem_rolar_para_o_lado(painel_demo, navegador, largura):
    contexto = navegador.new_context(viewport={"width": largura, "height": 900})
    pg = contexto.new_page()
    try:
        abrir(pg, painel_demo, "correio")
        pg.evaluate("abrirHospede(st.fila[0].chave)")
        pg.wait_for_selector("#v-hospede:not(.oculta) .hp-janela")
        pg.wait_for_timeout(300)
        assert pg.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
        assert pg.evaluate("(() => { const r = document.querySelector('#v-hospede .hp-janela').getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth + 1; })()")
        assert pg.evaluate(ESPREMIDOS) == []
    finally:
        contexto.close()
