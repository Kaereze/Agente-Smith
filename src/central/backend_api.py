"""Cliente do servidor central (24/11/2026, início da API): os mesmos métodos do `BackendGoogle`, mas pedindo ao servidor.

Quem usa o backend (Painel, conferente, robô) não percebe a diferença: troca-se só o objeto criado. Os erros também
chegam no mesmo formato: aba que não existe numa gravação levanta `ErroPlanilha`, como no Google.
"""
import json
import urllib.error
import urllib.request

from central.sheets import ErroPlanilha

TEMPO_PADRAO = 20   # segundos; a rede do escritório responde em milésimos, isto só segura pedido pendurado


class ErroServidorCentral(ErroPlanilha):
    """O servidor central não respondeu, recusou o token ou devolveu erro."""


class BackendAPI:
    def __init__(self, url, token, tempo=TEMPO_PADRAO):
        self._url = url.rstrip("/")
        self._token = token
        self._tempo = tempo

    def _chamar(self, metodo, *args, **kwargs):
        corpo = json.dumps({"metodo": metodo, "args": list(args), "kwargs": kwargs}, ensure_ascii=False).encode("utf-8")
        pedido = urllib.request.Request(self._url + "/v1/chamar", data=corpo, method="POST",
                                        headers={"Content-Type": "application/json; charset=utf-8", "X-Token": self._token})
        try:
            with urllib.request.urlopen(pedido, timeout=self._tempo) as r:   # nosec B310: o endereço vem da configuração (http da rede do escritório)
                resposta = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                resposta = json.loads(e.read().decode("utf-8"))
            except ValueError:
                raise ErroServidorCentral(f"servidor central respondeu HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise ErroServidorCentral(f"servidor central não respondeu ({e})") from e
        if not resposta.get("ok"):
            raise ErroServidorCentral(str(resposta.get("erro") or "erro desconhecido"))
        return resposta.get("resultado")

    def listar_abas(self, planilha_id):
        return self._chamar("listar_abas", planilha_id)

    def ler_abas(self, planilha_id, nomes, faixas=None):
        lidas, erros = self._chamar("ler_abas", planilha_id, list(nomes), faixas or {})
        return lidas, erros

    def escrever(self, planilha_id, atualizacoes):
        if atualizacoes:
            self._chamar("escrever", planilha_id, [list(a) for a in atualizacoes])

    def criar_aba_status(self, planilha_id, nome, linhas):
        self._chamar("criar_aba_status", planilha_id, nome, linhas)

    def criar_aba_log(self, planilha_id, nome, cabecalho):
        self._chamar("criar_aba_log", planilha_id, nome, cabecalho)

    def inserir_no_topo(self, planilha_id, aba, linhas):
        self._chamar("inserir_no_topo", planilha_id, aba, linhas)

    def substituir_aba(self, planilha_id, aba, linhas):
        self._chamar("substituir_aba", planilha_id, aba, linhas)

    def garantir_colunas(self, planilha_id, aba, cabecalho):
        self._chamar("garantir_colunas", planilha_id, aba, cabecalho)

    def anexar_linhas(self, planilha_id, aba, linhas):
        self._chamar("anexar_linhas", planilha_id, aba, linhas)

    def apagar_linhas(self, planilha_id, aba, inicio, fim, novas=None):
        self._chamar("apagar_linhas", planilha_id, aba, inicio, fim, novas)

    def apagar_aba(self, planilha_id, aba):
        self._chamar("apagar_aba", planilha_id, aba)
