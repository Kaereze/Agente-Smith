"""Escolhe de onde o Painel lê e grava a Central: do Google (como sempre) ou do servidor central (API central, etapa 3, 24/11/2026).

Todos os programas pedem o backend aqui (`criar_backend`). Sem o arquivo `estado/central_api.json` ligado, devolve o
`BackendGoogle` de sempre: nada muda. Com ele ligado, devolve um `BackendRoteado`, que manda cada pedido para um lado:

- **servidor central:** as abas internas do Painel da Planilha Central (envios, correio, PCs, comandos, status...);
- **Google:** as abas de formulário dos hotéis (`... (respostas)`, o Google Forms é quem as alimenta), o `Cadastro_Hoteis`
  (a equipe edita direto na planilha) e QUALQUER outra planilha (as dos hotéis, o Mail Analytics).

Cada PC liga ou desliga por conta própria, com o arquivo local `estado/central_api.json` (fora do GitHub, porque leva o token):

    {"ligada": true, "url": "http://IP-DO-SERVIDOR:8770"}

O token não precisa ir no arquivo: sai da chave do Google do próprio PC (`token_derivado`). Quem quiser pode pôr `"token"` ou a variável
CENTRAL_TOKEN. O comando `ligar_servidor` (central/virada.py) cria este arquivo, depois de conferir que o servidor está pronto.

Cuidado: um PC ligado no servidor passa a ver os dados DO SERVIDOR, não os do Google. Ligar só um PC dá um PC isolado dos outros
(serve de teste). A virada de todos os PCs de uma vez está no plano (etapa 5).
"""
import hashlib
import hmac
import json
import os
import re

from central.backend_api import BackendAPI
from central.descoberta import DescobertaPeloGoogle
from central.sheets import BackendGoogle, BackendSoLeitura, ErroPlanilha
from config import caminho_chave_google
from sistema import armazem

SUFIXO_FORMULARIO = "(respostas)"
# Cadastro_Hoteis: a equipe edita na própria planilha (sai daqui numa etapa futura).
# Comandos_PC: o canal que liga/desliga o servidor e manda atualizar os PCs. Se morasse no servidor e ele caísse, não haveria
# como mandar ninguém voltar para o Google nem atualizar (etapa 5, 24/11/2026).
# Servidor_Endereco: o endereço atual do servidor (central/descoberta.py). É por ela que os PCs acham o servidor depois de uma troca
# de IP, então não pode morar nele.
ABAS_QUE_FICAM_NO_GOOGLE = frozenset({"Cadastro_Hoteis", "Comandos_PC", "Servidor_Endereco"})
_ABA_DO_ENDERECO = re.compile(r"^'((?:[^']|'')*)'!")           # 'Aba'!K5


def fica_no_google(aba):
    """Aba de formulário de hotel ou uma das poucas que a equipe edita à mão: continua no Google."""
    nome = str(aba).strip()
    return nome.endswith(SUFIXO_FORMULARIO) or nome in ABAS_QUE_FICAM_NO_GOOGLE


def _caminho():
    return armazem.caminho("central_api.json")


def token_derivado(cfg):
    """O token do servidor central, calculado da chave do Google que todo PC da equipe já tem (o mesmo jeito do segredo da rede
    entre os PCs): ninguém precisa copiar senha de um PC para outro. Domínio próprio: não vale como o segredo da rede.
    -> texto hexadecimal, ou "" se este PC não tem a chave."""
    try:
        from rede import rede_local
        segredo = rede_local.segredo_da_chave(caminho_chave_google(cfg))
    except Exception:
        return ""
    return hmac.new(segredo, b"servidor-central-v1", hashlib.sha256).hexdigest() if segredo else ""


def configuracao_local(cfg=None):
    """O que este PC diz sobre o servidor central -> {"url", "token"} se estiver ligado e completo, senão None.
    Token: o do arquivo, senão o da variável CENTRAL_TOKEN, senão o derivado da chave do Google (se `cfg` foi dado)."""
    try:
        with open(_caminho(), encoding="utf-8") as f:
            dados = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(dados, dict) or not dados.get("ligada"):
        return None
    url, token = str(dados.get("url") or "").strip(), str(dados.get("token") or os.environ.get("CENTRAL_TOKEN", "")).strip()
    if url and not token and cfg:
        token = token_derivado(cfg)
    if not (url and token):
        return None
    configuracao = {"url": url, "token": token}
    if dados.get("servidor_id"):   # o banco que este PC conhece (gravado por ligar_servidor): só ele vale depois de uma troca de IP
        configuracao["servidor_id"] = str(dados["servidor_id"]).strip()
    return configuracao


class BackendRoteado:
    """Mesmos métodos do `BackendGoogle`; cada um decide, pela planilha e pela aba, quem atende."""

    def __init__(self, google, api, central_id, somente_leitura=False, ignorar_gravacao=False):
        self._google, self._api, self._central = google, api, central_id
        self._somente_leitura, self._ignorar_gravacao = somente_leitura, ignorar_gravacao

    # ---------------------------------------------------------------- decisão
    def _lado(self, planilha_id, aba):
        return self._api if planilha_id == self._central and not fica_no_google(aba) else self._google

    def _pode_gravar(self):
        """Modo casa: grava nada em silêncio (como o BackendSoLeitura). Só leitura: erro, como o Google daria."""
        if self._ignorar_gravacao:
            return False
        if self._somente_leitura:
            raise ErroPlanilha("este PC está em modo somente leitura: não grava na Central")
        return True

    # ---------------------------------------------------------------- só do servidor (o Google não "avisa" quando muda)
    def atende_pelo_servidor(self, planilha_id, aba):
        """Esta aba mora no servidor central? (então dá para esperar a mudança dela em vez de ficar perguntando)"""
        return self._lado(planilha_id, aba) is self._api

    def esperar_mudanca(self, planilha_id, aba, versao_vista, segundos=20):
        if not self.atende_pelo_servidor(planilha_id, aba):
            raise ErroPlanilha(f"a aba '{aba}' é do Google: não dá para esperar mudança nela")
        return self._api.esperar_mudanca(planilha_id, aba, versao_vista, segundos)

    # ---------------------------------------------------------------- leitura
    def listar_abas(self, planilha_id):
        if planilha_id != self._central:
            return self._google.listar_abas(planilha_id)
        do_google = [a for a in self._google.listar_abas(planilha_id) if fica_no_google(a)]
        return do_google + [a for a in self._api.listar_abas(planilha_id) if a not in do_google]

    def ler_abas(self, planilha_id, nomes, faixas=None):
        nomes = list(dict.fromkeys(nomes))
        faixas = faixas or {}
        lados = {}
        for nome in nomes:
            lados.setdefault(id(self._lado(planilha_id, nome)), (self._lado(planilha_id, nome), []))[1].append(nome)
        lidas, erros = {}, {}
        for lado, dele in lados.values():
            l, e = lado.ler_abas(planilha_id, dele, {n: f for n, f in faixas.items() if n in dele})
            lidas.update(l)
            erros.update(e)
        return {n: lidas[n] for n in nomes if n in lidas}, erros

    # ---------------------------------------------------------------- escrita
    def escrever(self, planilha_id, atualizacoes):
        if not atualizacoes or not self._pode_gravar():
            return
        por_lado = {}
        for endereco, valor in atualizacoes:
            m = _ABA_DO_ENDERECO.match(str(endereco))
            lado = self._lado(planilha_id, m.group(1).replace("''", "'")) if m else self._google
            por_lado.setdefault(id(lado), (lado, []))[1].append((endereco, valor))
        for lado, dele in por_lado.values():
            lado.escrever(planilha_id, dele)

    def criar_aba_status(self, planilha_id, nome, linhas):
        if self._pode_gravar():
            self._lado(planilha_id, nome).criar_aba_status(planilha_id, nome, linhas)

    def criar_aba_log(self, planilha_id, nome, cabecalho):
        if self._pode_gravar():
            self._lado(planilha_id, nome).criar_aba_log(planilha_id, nome, cabecalho)

    def inserir_no_topo(self, planilha_id, aba, linhas):
        if self._pode_gravar():
            self._lado(planilha_id, aba).inserir_no_topo(planilha_id, aba, linhas)

    def substituir_aba(self, planilha_id, aba, linhas):
        if self._pode_gravar():
            self._lado(planilha_id, aba).substituir_aba(planilha_id, aba, linhas)

    def garantir_colunas(self, planilha_id, aba, cabecalho):
        if self._pode_gravar():
            self._lado(planilha_id, aba).garantir_colunas(planilha_id, aba, cabecalho)

    def anexar_linhas(self, planilha_id, aba, linhas):
        if self._pode_gravar():
            self._lado(planilha_id, aba).anexar_linhas(planilha_id, aba, linhas)

    def apagar_linhas(self, planilha_id, aba, inicio, fim, novas=None):
        if self._pode_gravar():
            self._lado(planilha_id, aba).apagar_linhas(planilha_id, aba, inicio, fim, novas)

    def apagar_aba(self, planilha_id, aba):
        if self._pode_gravar():
            self._lado(planilha_id, aba).apagar_aba(planilha_id, aba)


# ---------------------------------------------------------------- o que os programas chamam
def _api(servidor, google, cfg):
    """O cliente do servidor, já sabendo achar o servidor de novo se o IP dele mudar (central/descoberta.py)."""
    return BackendAPI(servidor["url"], servidor["token"], descoberta=DescobertaPeloGoogle(google, cfg["planilha_central_id"]),
                      servidor_id=servidor.get("servidor_id", ""))


def criar_backend(cfg, somente_leitura=False):
    """O backend deste PC: o Google de sempre, ou o roteado quando `estado/central_api.json` está ligado."""
    google = BackendGoogle(caminho_chave_google(cfg), somente_leitura=somente_leitura)
    servidor = configuracao_local(cfg)
    if not servidor:
        return google
    return BackendRoteado(google, _api(servidor, google, cfg), cfg["planilha_central_id"], somente_leitura=somente_leitura)


def criar_backend_casa(cfg):
    """Modo casa (só visualização): lê os dados reais e nunca grava, nem no Google nem no servidor."""
    google = BackendSoLeitura(caminho_chave_google(cfg))
    servidor = configuracao_local(cfg)
    if not servidor:
        return google
    return BackendRoteado(google, _api(servidor, google, cfg), cfg["planilha_central_id"], ignorar_gravacao=True)
