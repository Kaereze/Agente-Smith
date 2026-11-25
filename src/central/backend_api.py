"""Cliente do servidor central (24/11/2026, início da API): os mesmos métodos do `BackendGoogle`, mas pedindo ao servidor.

Quem usa o backend (Painel, conferente, robô) não percebe a diferença: troca-se só o objeto criado. Os erros também
chegam no mesmo formato: aba que não existe numa gravação levanta `ErroPlanilha`, como no Google.

Troca de endereço (25/11/2026): o IP do servidor pode mudar. Quando o servidor não responde e este cliente tem uma `descoberta`
(central/descoberta.py), ele procura o endereço novo (o `estado/central_api.json` e a aba `Servidor_Endereco` do Google), CONFERE que
é o servidor de verdade (prova da senha + identificador do banco) e repete o pedido. Cada gravação leva um `id_pedido`: se a resposta
se perdeu no meio da troca e o pedido é repetido, o servidor não grava em dobro. Se não acha o servidor, o erro sobe como sempre
(quem pediu tenta de novo na volta seguinte); nada é escondido numa fila.
"""
import json
import threading
import time
import urllib.error
import urllib.request
import uuid

from central.descoberta import verificar_servidor
from central.sheets import ErroPlanilha

TEMPO_PADRAO = 20   # segundos; a rede do escritório responde em milésimos, isto só segura pedido pendurado
# Só estas aceitam `id_pedido` (as que gravam). Têm que ser as mesmas do servidor (servidor_central/servidor.py: METODOS_QUE_ESCREVEM).
METODOS_QUE_ESCREVEM = frozenset({"escrever", "criar_aba_status", "criar_aba_log", "inserir_no_topo", "substituir_aba",
                                  "garantir_colunas", "anexar_linhas", "apagar_linhas", "apagar_aba"})
JANELA_DA_BUSCA = 25          # segundos procurando o endereço novo antes de desistir deste pedido
PAUSA_ENTRE_TENTATIVAS = 3    # segundos entre uma conferência e outra dentro da janela
INTERVALO_ENTRE_LEITURAS_DO_GOOGLE = 30   # no máximo uma leitura da aba do Google a cada tanto (a cota é de todos os PCs)
PAUSA_APOS_BUSCA_SEM_RESULTADO = 60       # depois de uma busca sem resultado, os pedidos seguintes falham logo, sem esperar de novo
TENTATIVAS_POR_PEDIDO = 3


class ErroServidorCentral(ErroPlanilha):
    """O servidor central não respondeu, recusou o token ou devolveu erro."""


class _SemConexao(Exception):
    """Não deu nem para falar com o endereço (nada respondeu). Diferente de o servidor responder com erro."""


class BackendAPI:
    def __init__(self, url, token, tempo=TEMPO_PADRAO, *, descoberta=None, servidor_id="", relogio=time.monotonic, dormir=time.sleep):
        self._url = url.rstrip("/")
        self._token = token
        self._tempo = tempo
        self._descoberta = descoberta      # quem sabe achar o servidor de novo (None = não procura, só reclama)
        self._servidor_id = servidor_id    # o banco que este PC conhece; "" = só confere a prova da senha
        self._relogio, self._dormir = relogio, dormir
        self._trava_busca = threading.Lock()
        self._sem_busca_ate = 0.0
        self._proxima_leitura_do_google = 0.0

    @property
    def url(self):
        return self._url

    def _enviar(self, corpo, tempo):
        pedido = urllib.request.Request(self._url + "/v1/chamar", data=corpo, method="POST",
                                        headers={"Content-Type": "application/json; charset=utf-8", "X-Token": self._token})
        try:
            with urllib.request.urlopen(pedido, timeout=tempo) as r:   # nosec B310: o endereço vem da configuração (http da rede do escritório)
                return json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            try:
                return json.loads(e.read().decode("utf-8"))
            except ValueError:
                raise ErroServidorCentral(f"servidor central respondeu HTTP {e.code}") from e
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise _SemConexao(str(e)) from e

    def _chamar(self, metodo, *args, _tempo=None, **kwargs):
        pedido = {"metodo": metodo, "args": list(args), "kwargs": kwargs}
        if metodo in METODOS_QUE_ESCREVEM:
            pedido["id_pedido"] = uuid.uuid4().hex   # o mesmo em toda repetição deste pedido: o servidor não grava duas vezes
        corpo = json.dumps(pedido, ensure_ascii=False).encode("utf-8")
        for tentativa in range(TENTATIVAS_POR_PEDIDO):
            url_usada = self._url
            try:
                resposta = self._enviar(corpo, _tempo or self._tempo)
                break
            except _SemConexao as e:
                if tentativa + 1 >= TENTATIVAS_POR_PEDIDO or not self._achar_o_servidor(url_usada):
                    raise ErroServidorCentral(f"servidor central não respondeu ({e})") from e
        if not resposta.get("ok"):
            raise ErroServidorCentral(str(resposta.get("erro") or "erro desconhecido"))
        return resposta.get("resultado")

    # ---------------------------------------------------------------- troca de endereço
    def _achar_o_servidor(self, url_que_falhou):
        """O pedido não chegou. Dá para repetir agora? (o endereço mudou e já achamos o novo, ou o servidor só tinha caído e voltou)"""
        if self._descoberta is None:
            return False
        with self._trava_busca:                      # uma busca por vez neste programa; quem esperava só confere o resultado
            if self._url != url_que_falhou:
                return True                          # outra volta deste programa já achou o endereço novo
            if self._relogio() < self._sem_busca_ate:
                return False                         # buscamos há pouco e não achou: não prende cada pedido por 25 s de novo
            fim = self._relogio() + JANELA_DA_BUSCA
            while True:
                if self._tentar_enderecos():
                    return True
                if self._conferir(self._url):        # o servidor só estava fora do ar e voltou, no mesmo endereço
                    return True
                if self._relogio() >= fim:
                    break
                self._dormir(PAUSA_ENTRE_TENTATIVAS)
            self._sem_busca_ate = self._relogio() + PAUSA_APOS_BUSCA_SEM_RESULTADO
            return False

    def _tentar_enderecos(self):
        d = self._descoberta
        local = d.endereco_local()                   # de graça: outro programa deste PC pode já ter corrigido o arquivo
        if local and local != self._url and self._conferir(local):
            self._adotar(local)
            return True
        if self._relogio() >= self._proxima_leitura_do_google:
            self._proxima_leitura_do_google = self._relogio() + INTERVALO_ENTRE_LEITURAS_DO_GOOGLE
            try:
                publicado = d.endereco_publicado()   # uma leitura do Google
            except Exception:
                publicado = None
            if publicado and publicado["url"] != self._url and self._conferir(publicado["url"]):
                self._adotar(publicado["url"])
                return True
        return False

    def _conferir(self, url):
        return verificar_servidor(url, self._token, self._servidor_id)[0]

    def _adotar(self, url):
        self._url = url.rstrip("/")
        try:
            self._descoberta.guardar_endereco(self._url)   # os outros programas deste PC leem o arquivo e já enxergam
        except Exception:
            pass   # não conseguir gravar o arquivo não impede de usar o endereço novo agora

    # ---------------------------------------------------------------- os métodos (iguais aos do BackendGoogle)
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

    # ---- só do servidor (o Google não tem)
    def versoes_das_abas(self, planilha_id, nomes):
        return self._chamar("versoes_das_abas", planilha_id, list(nomes))

    def esperar_mudanca(self, planilha_id, aba, versao_vista, segundos=20):
        """Fica pendurado no servidor até a aba mudar (ou até `segundos`) e devolve a versão de agora."""
        return self._chamar("esperar_mudanca", planilha_id, aba, versao_vista, segundos, _tempo=segundos + 10)
