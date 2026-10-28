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
import demo  # noqa: E402
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
    pagina.locator(".cx-l").first.click()
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
        assert pagina.locator(".c-etapas .c-et").count() == 4 and pagina.locator(".c-lista .c-item").count() == 8
        assert pagina.locator(".c-top .c-bt.p").inner_text() == "Concluir"   # NF já enviada: o botão principal é Concluir
    # as caixas e o histórico antigos saíram da leitura
    for antigo in (".cx-cobre", ".cx-aviso-nf", ".cx-hist", ".ol-resumo"):
        assert pagina.locator(antigo).count() == 0, f"sobrou {antigo}"
    confere_a_tela(pagina)


def test_janela_do_robo_abre_sem_erro(painel_demo, pagina):
    abrir(pagina, painel_demo, "visao")
    pagina.evaluate("rbAbrir('agora')")
    pagina.wait_for_timeout(1200)
    confere_a_tela(pagina)
