"""Servidor central (API) do Painel Fiscal (24/11/2026, início da API).

Um PC (o "Servidor RA") guarda os dados no `Armazem` e atende os outros pela rede do escritório. Os PCs deixam de ler e
gravar a planilha do Google e passam a pedir aqui, com os mesmos métodos do `BackendGoogle`.

Rotas:
  GET  /v1/saude    -> {"ok": true, "abas": N, "esperando": N, "servidor_id": "..."}   (sem token: o Docker e o monitoramento veem que está de pé)
  GET  /v1/saude?desafio=XYZ  -> o mesmo + "prova": HMAC(token, XYZ)   (o PC confere que o endereço é o servidor de verdade, sem mandar o token)
  POST /v1/chamar   -> {"metodo": "ler_abas", "args": [...], "kwargs": {...}, "id_pedido": "..."}  (com o cabeçalho X-Token;
                       `id_pedido` só nas gravações: repetir o mesmo pedido, depois de uma troca de endereço, não grava em dobro)

Segurança: sem o token certo nada é lido nem gravado. O token vem da variável CENTRAL_TOKEN (nunca do código, nunca do
repositório); sem ele o servidor nem sobe. Só os métodos da lista METODOS podem ser chamados (os 11 do backend mais `versoes_das_abas` e `esperar_mudanca`).
"""
import hashlib
import hmac
import json
import os
import re
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

from servidor_central.armazem import Armazem, ErroArmazem

METODOS_DO_BACKEND = frozenset({"listar_abas", "ler_abas", "escrever", "criar_aba_status", "criar_aba_log", "inserir_no_topo",
                                "substituir_aba", "garantir_colunas", "anexar_linhas", "apagar_linhas", "apagar_aba"})
METODOS_EXTRAS = frozenset({"versoes_das_abas", "esperar_mudanca"})   # só o servidor tem: o Google não "avisa" quando uma aba muda
METODOS = METODOS_DO_BACKEND | METODOS_EXTRAS
METODOS_QUE_ESCREVEM = METODOS_DO_BACKEND - {"listar_abas", "ler_abas"}   # estes aceitam `id_pedido`: repetir o mesmo pedido não grava em dobro
_ID_VALIDO = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_DESAFIO_VALIDO = re.compile(r"^[A-Za-z0-9_-]{8,128}$")
LIMITE_CORPO = 32 * 1024 * 1024   # as partes de anexo das NFs vão em abas: pedido grande é normal, infinito não
PORTA = 8770


def prova_do_desafio(token, desafio):
    """A resposta que só quem tem o token sabe dar a um desafio (o cliente calcula a mesma e compara). `token`: texto ou bytes."""
    chave = token if isinstance(token, bytes) else str(token).encode("utf-8")
    return hmac.new(chave, b"prova-do-servidor-v1|" + desafio.encode("utf-8"), hashlib.sha256).hexdigest()


def criar_handler(armazem, token):
    token = (token or "").encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *args):   # o log de cada pedido não diz nada que o Painel já não registre
            pass

        def _responder(self, corpo, codigo=200):
            dados = json.dumps(corpo, ensure_ascii=False).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(dados)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(dados)

        def _token_ok(self):
            enviado = (self.headers.get("X-Token") or "").encode("utf-8")
            return bool(token) and hmac.compare_digest(enviado, token)

        def do_GET(self):
            partes = urlsplit(self.path)
            if partes.path == "/v1/saude":
                resposta = {"ok": True, "abas": sum(len(armazem.listar_abas(p)) for p in armazem.planilhas()),
                            "esperando": armazem.esperando, "servidor_id": armazem.servidor_id()}
                desafio = (parse_qs(partes.query).get("desafio") or [""])[0]
                if desafio:
                    if not _DESAFIO_VALIDO.match(desafio):
                        return self._responder({"ok": False, "erro": "desafio inválido"}, 400)
                    # Prova que este servidor conhece a senha SEM mandá-la: quem não tem a chave do Google não sabe calcular isto.
                    # É assim que um PC confirma que o endereço novo é o servidor de verdade, antes de mandar qualquer dado.
                    resposta["prova"] = prova_do_desafio(token, desafio)
                return self._responder(resposta)
            self._responder({"ok": False, "erro": "rota desconhecida"}, 404)

        def do_POST(self):
            tamanho = int(self.headers.get("Content-Length") or 0)
            if tamanho > LIMITE_CORPO:
                self.close_connection = True   # não lê o corpo todo: só recusa
                return self._responder({"ok": False, "erro": "pedido grande demais"}, 413)
            corpo = self.rfile.read(tamanho) if tamanho else b""
            if not self._token_ok():
                return self._responder({"ok": False, "erro": "token inválido"}, 403)
            if self.path != "/v1/chamar":
                return self._responder({"ok": False, "erro": "rota desconhecida"}, 404)
            try:
                pedido = json.loads(corpo.decode("utf-8"))
                metodo, args, kwargs = pedido["metodo"], pedido.get("args", []), pedido.get("kwargs", {})
            except (ValueError, KeyError, TypeError):
                return self._responder({"ok": False, "erro": "pedido mal formado"}, 400)
            if metodo not in METODOS:
                return self._responder({"ok": False, "erro": f"método desconhecido: {metodo}"}, 404)
            id_pedido = pedido.get("id_pedido")
            if id_pedido is not None and (not isinstance(id_pedido, str) or not _ID_VALIDO.match(id_pedido)):
                return self._responder({"ok": False, "erro": "id_pedido inválido"}, 400)
            try:
                if id_pedido and metodo in METODOS_QUE_ESCREVEM:
                    resultado = armazem.executar_uma_vez(id_pedido, lambda: getattr(armazem, metodo)(*args, **kwargs))
                else:
                    resultado = getattr(armazem, metodo)(*args, **kwargs)
            except ErroArmazem as e:   # aba que não existe etc.: o cliente refaz como o erro do Google
                return self._responder({"ok": False, "tipo": "ErroArmazem", "erro": str(e)}, 409)
            except TypeError as e:     # argumento errado
                return self._responder({"ok": False, "tipo": "TypeError", "erro": str(e)}, 400)
            self._responder({"ok": True, "resultado": resultado})

    return Handler


def servir(armazem, token, porta=PORTA, endereco="0.0.0.0"):   # nosec B104: é o servidor da rede do escritório; o token protege
    servidor = ThreadingHTTPServer((endereco, porta), criar_handler(armazem, token))
    servidor.daemon_threads = True
    return servidor


def main():
    token = os.environ.get("CENTRAL_TOKEN", "")
    if len(token) < 24:
        sys.exit("CENTRAL_TOKEN ausente ou curto demais (mínimo 24 caracteres). Defina a variável antes de subir o servidor.")
    banco = os.environ.get("CENTRAL_BANCO", "central.sqlite")
    porta = int(os.environ.get("CENTRAL_PORTA", PORTA))
    servidor = servir(Armazem(banco), token, porta)
    print(f"Servidor central no ar na porta {porta} (banco: {banco})", flush=True)
    servidor.serve_forever()


if __name__ == "__main__":
    main()
