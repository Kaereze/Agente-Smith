"""Caixa de entrada da tela nova (React, 27/11/2026): abre o Painel de verdade num navegador, no modo demonstração, e usa a
caixa como a equipe usa: ler o e-mail inteiro, responder, a ficha do hóspede no formulário, o menu do botão direito,
excluir com Desfazer e a pesquisa nos 4 PCs.

Dados 100% fictícios (demo.py) e o "enviar" da demonstração não manda nada (o Outlook é de mentira). Usa o Edge do Windows
pelo Playwright; sem Playwright, sem Edge ou sem a tela montada (app_ui/v2) os testes são pulados em vez de falhar.
"""
import threading
from http.server import ThreadingHTTPServer

import pytest

sync_api = pytest.importorskip("playwright.sync_api", reason="pip install -r requirements-dev.txt")

import app_servidor  # noqa: E402
from painel import demo  # noqa: E402
from config import carregar_config  # noqa: E402

pytestmark = pytest.mark.skipif(not (app_servidor.PASTA_UI / "v2" / "index.html").is_file(), reason="tela nova ainda não montada (cd app_react; npm run build)")


@pytest.fixture(scope="module")
def painel_demo(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("react_correio")
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
        estado.versao_tela += 1
        reserva = ThreadingHTTPServer(("127.0.0.1", 0), lambda *a, **k: None)
        porta = reserva.server_address[1]
        reserva.server_close()
        mp.setattr(app_servidor, "PORTA", porta)
        estado.uso_ref = [-1e9]
        servidor = ThreadingHTTPServer(("127.0.0.1", porta), app_servidor.criar_handler(estado, cfg, "token-de-teste", estado.uso_ref))
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
def pagina(navegador, painel_demo):
    contexto = navegador.new_context(viewport={"width": 1440, "height": 900}, reduced_motion="reduce")
    pg = contexto.new_page()
    pg.erros = []
    pg.on("pageerror", lambda e: pg.erros.append(f"JS: {e}"))
    pg.goto(f"{painel_demo}/v2/#correio")
    pg.wait_for_selector(".em", timeout=15000)
    yield pg
    assert not pg.erros, pg.erros
    contexto.close()


NORMAL = ".em:not(.cinza):not(:has-text('Formulário'))"


def test_abre_o_email_inteiro_e_responde_sem_sair_da_tela(pagina):
    pagina.locator(NORMAL).first.click()
    pagina.wait_for_selector(".c-texto")
    assert pagina.locator(".c-texto").first.inner_text().strip()                         # o texto inteiro, pedido ao "PC dono"
    pagina.locator(".c-acoes button:has-text('Responder')").click()
    pagina.wait_for_selector(".esc-enviar:not([disabled])")
    para = pagina.locator(".esc-linha input").first.input_value()
    assert "@" in para and pagina.locator(".esc-linha input").nth(2).input_value().upper().startswith("RE:")
    assert pagina.locator(".esc-citacao").count() == 1                                    # o original citado embaixo
    pagina.locator(".esc-enviar").click()
    pagina.wait_for_selector(".aviso-curto:has-text('Pedido de envio entregue')")
    assert pagina.locator(".escrever").count() == 0 and pagina.locator(".em.cinza").count() >= 1   # respondido: a linha fica cinza


def test_formulario_abre_a_ficha_do_hospede_com_copiar_e_a_emissao(pagina):
    pagina.locator(".em:has-text('Formulário')").first.click()
    pagina.wait_for_selector(".hp-cab h2")
    assert pagina.locator(".hp-cab h2").inner_text().strip() not in ("", "Formulário")
    assert pagina.locator(".hp-cp").count() >= 5                                          # cada campo com Copiar
    pagina.locator(".hp-acoes button:has-text('Copiar tudo')").click()
    texto = pagina.locator(".janela textarea").input_value().split("\n")
    assert texto[0].startswith("DATA DE CHECK-IN : ") and texto[3] == "VALOR DA DIÁRIA :"   # nada inventado
    pagina.locator(".janela button:has-text('Fechar')").click()
    pagina.locator(".hp-faixa button:has-text('Voltar')").click()
    pagina.wait_for_selector(".linhas")


def test_excluir_some_na_hora_e_desfazer_volta(pagina):
    antes = pagina.locator(".em").count()
    pagina.locator(NORMAL).nth(1).click()
    pagina.keyboard.press("Delete")
    if pagina.locator(".janela").count():                                                  # quem não é administrador confirma
        pagina.locator(".janela button:has-text('Excluir')").click()
    pagina.wait_for_selector(".aviso-desfazer")
    assert pagina.locator(".em").count() == antes - 1
    pagina.locator(".aviso-desfazer button").click()
    pagina.wait_for_timeout(300)
    assert pagina.locator(".em").count() == antes and pagina.locator(".aviso-desfazer").count() == 0


def test_menu_do_botao_direito_marca_urgente_para_a_equipe(pagina):
    linha = pagina.locator(".em:not(.urg):not(.cinza)").first
    linha.click(button="right")
    itens = pagina.locator(".menu-email button").all_inner_texts()
    assert "Marcar como urgente" in itens and itens[-1] == "Excluir"                       # o perigoso fica por último
    pagina.locator(".menu-email button:has-text('Marcar como urgente')").click()
    pagina.wait_for_selector(".aviso-curto:has-text('urgente')")


def test_pesquisa_procura_nos_4_pcs_e_limpar_volta_a_caixa(pagina):
    pagina.fill("#busca-topo", "nota")
    pagina.wait_for_selector(".busca-info:has-text('e-mails com')", timeout=10000)
    assert pagina.locator(".em").count() > 0 and pagina.locator(".busca-pcs > span").count() >= 1
    pagina.locator(".busca-bts button:has-text('Limpar')").click()
    pagina.wait_for_selector(".abas-lista")
