"""Tela que não trava (usuário, 21/10/2026): a causa da "tela verde" foi a fila de 5 conexões do servidor; a página não
desiste mais de recarregar; a janela confere se a tela está viva."""
import socket
import sys
import threading
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))
HTML = (RAIZ / "app_ui" / "index.html").read_text(encoding="utf-8")


def test_servidor_aguenta_a_rajada_da_tela():
    """A tela abre ~10 arquivos e pedidos juntos: com o servidor ocupado, a fila de 5 recusava parte deles."""
    from http.server import BaseHTTPRequestHandler

    import app_servidor
    assert app_servidor.ServidorPainel.request_queue_size >= 64

    class Lento(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *a):
            pass

    srv = app_servidor.ServidorPainel(("127.0.0.1", 0), Lento)
    porta = srv.server_address[1]
    socks = []
    try:   # ninguém atende (servidor "ocupado"): 40 conexões têm de entrar na fila sem recusa
        for _ in range(40):
            s = socket.create_connection(("127.0.0.1", porta), timeout=2)
            socks.append(s)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        for s in socks:
            s.sendall(b"GET / HTTP/1.0\r\n\r\n")
        assert all(s.recv(64).startswith(b"HTTP/1.0 200") for s in socks)
    finally:
        for s in socks:
            s.close()
        srv.shutdown()
        srv.server_close()


def test_pagina_pela_metade_nao_desiste():
    guarda = HTML.split("Página que veio pela metade")[1].split("</script>")[0]
    assert "n < 3" not in guarda and "location.reload()" in guarda and "tela-parada" in guarda
    assert "window.__telaInteira = ok" in guarda and "typeof pecaFiltro" in guarda and "typeof etiquetasDoEmail" in guarda


def test_faixa_sem_dados_e_f5():
    assert 'id="aviso-parado"' in HTML and "Recarregar agora" in HTML
    assert "ultimoOk = Date.now();" in HTML and "avisoParado();" in HTML
    assert 'e.key === "F5"' in HTML and "window.__painelVivo" in HTML
    bloco = HTML.split("Tela que não trava (usuário, 21/10/2026, desenho Pr6)")[1].split("visibilitychange")[0]
    assert 'e.key === "r"' not in bloco and '"R"' not in bloco   # Ctrl+R é Responder (correio.js), não recarregar


def test_janela_recarrega_tela_parada(monkeypatch):
    import app_janela

    class Janela:
        def __init__(self, resposta):
            self.resposta, self.urls = resposta, []

        def evaluate_js(self, _):
            if self.resposta == "trava":
                time.sleep(10)
            if isinstance(self.resposta, Exception):
                raise self.resposta
            return self.resposta

        def load_url(self, url):
            self.urls.append(url)

    monkeypatch.setattr(app_janela, "RESPOSTA_SEGUNDOS", 0.2)
    monkeypatch.setattr(app_janela, "servidor_no_ar", lambda: True)
    monkeypatch.setattr(app_janela, "anotar", lambda msg: None)
    monkeypatch.setattr(app_janela.time, "sleep", lambda s: None)
    for resposta, recarrega in [(True, False), (False, True), ("trava", True), (RuntimeError("página de erro"), True)]:
        j = Janela(resposta)
        monkeypatch.setitem(app_janela.ESTADO, "janela", j)
        monkeypatch.setitem(app_janela.ESTADO, "presas", 0)
        app_janela.conferir_ao_mostrar()
        assert bool(j.urls) is recarrega, resposta
    # servidor reiniciando: não recarrega (daria página de erro); espera a próxima conferência
    j = Janela(False)
    monkeypatch.setitem(app_janela.ESTADO, "janela", j)
    monkeypatch.setattr(app_janela, "servidor_no_ar", lambda: False)
    app_janela.conferir_ao_mostrar()
    assert j.urls == []
