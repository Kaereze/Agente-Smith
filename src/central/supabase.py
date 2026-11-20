"""Conexão com o Supabase (banco de dados central, 20/11/2026): só o necessário para ler, gravar, apagar e dar sinal de vida.

Fala com a API REST do próprio Supabase (PostgREST) usando `requests`, que já está instalado: nenhuma biblioteca nova.
Nada aqui liga sozinho. O Painel só usa o banco quando existir o arquivo da chave neste PC (`chave-supabase.json`,
ao lado da chave do Google, FORA do repositório) e uma etapa do plano mandar usar. Até lá a Planilha Central segue valendo.

Segurança: a chave nunca aparece em log, erro ou tela (`ErroBanco` só leva o código HTTP e um pedaço curto da resposta).
Dados de teste são sempre fictícios (regra do João: nunca dado real de hóspede em teste).
"""
import datetime
import json
import os
import re

import requests

import ajustes
from central.rede_util import com_retry
from sistema.log_util import configurar_logging

logger = configurar_logging(__name__)

ARQUIVO_PADRAO = os.path.join("%APPDATA%", "SolicitacoesNF", "chave-supabase.json")
_ENDERECO = re.compile(r"^https://[a-z0-9]{8,40}\.supabase\.(co|in)/?$")


class ErroBanco(Exception):
    """Falha ao falar com o banco. `codigo` é o status HTTP (0 = nem chegou: sem internet ou tempo esgotado)."""

    def __init__(self, texto, codigo=0):
        super().__init__(texto)
        self.codigo = codigo


def caminho_da_chave(cfg=None):
    cfg = cfg or {}
    return os.path.expandvars(str((cfg.get("supabase", {}) or {}).get("caminho_chave") or ARQUIVO_PADRAO))


def carregar(caminho):
    """Lê `{"url": "https://xxxx.supabase.co", "chave": "..."}`. Devolve (url, chave). Erro de arquivo/endereço vira ErroBanco
    SEM o conteúdo da chave."""
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except FileNotFoundError:
        raise ErroBanco(f"Não achei o arquivo da chave do Supabase em {caminho}") from None
    except (OSError, ValueError):
        raise ErroBanco(f"O arquivo {caminho} não pôde ser lido (precisa ser um JSON com 'url' e 'chave')") from None
    url, chave = str((dados or {}).get("url", "")).strip(), str((dados or {}).get("chave", "")).strip()
    if not _ENDERECO.match(url):
        raise ErroBanco("O 'url' do arquivo da chave precisa ser o endereço do projeto: https://xxxxxxxx.supabase.co")
    if len(chave) < 20:
        raise ErroBanco("A 'chave' do arquivo está vazia ou curta demais (use a chave publicável do projeto)")
    return url.rstrip("/"), chave


def _passageiro(erro):
    """Vale tentar de novo: sem internet, tempo esgotado, 'devagar' (429) ou erro do servidor (5xx)."""
    return isinstance(erro, ErroBanco) and (erro.codigo == 0 or erro.codigo == 429 or erro.codigo >= 500)


class Banco:
    def __init__(self, url, chave, sessao=None, tentativa_segundos=None, limite_segundos=None):
        self.url = url.rstrip("/")
        self._sessao = sessao or requests.Session()
        self._tentativa = tentativa_segundos or ajustes.valor("banco.tentativa_segundos")
        self._limite = limite_segundos or ajustes.valor("banco.chamada_limite_segundos")
        self._cabecalho = {"apikey": chave, "Content-Type": "application/json"}
        if chave.startswith("eyJ"):   # chave antiga (JWT) também vai como Bearer; a nova ("sb_publishable_...") só no apikey
            self._cabecalho["Authorization"] = f"Bearer {chave}"

    @classmethod
    def do_arquivo(cls, caminho):
        return cls(*carregar(caminho))

    def _chamar(self, metodo, tabela, params=None, corpo=None, extra=None):
        def uma_vez():
            try:
                r = self._sessao.request(metodo, f"{self.url}/rest/v1/{tabela}", params=params, timeout=self._tentativa,
                                         data=None if corpo is None else json.dumps(corpo, ensure_ascii=False).encode("utf-8"),
                                         headers={**self._cabecalho, **(extra or {})})
            except requests.RequestException as e:
                raise ErroBanco(f"sem resposta do banco ({type(e).__name__})") from None
            if r.status_code >= 400:
                raise ErroBanco(f"o banco respondeu {r.status_code}: {r.text[:160]}", r.status_code)
            return r
        return com_retry(uma_vez, _passageiro, tentativas=3, espera_inicial=1, orcamento=self._limite)

    def ler(self, tabela, filtros=None, colunas="*", limite=1000, ordem=None):
        """filtros: {coluna: "eq.valor"} (ou "gt.", "lt.", "in.(a,b)"). Devolve uma lista de dicionários."""
        params = {"select": colunas, "limit": limite, **(filtros or {})}
        if ordem:
            params["order"] = ordem
        return self._chamar("GET", tabela, params=params).json()

    def gravar(self, tabela, linhas, conflito=None):
        """Grava várias linhas numa chamada só. Com `conflito` (a coluna única), quem já existe é atualizado (upsert)."""
        if not linhas:
            return
        extra = {"Prefer": "return=minimal" + (",resolution=merge-duplicates" if conflito else "")}
        self._chamar("POST", tabela, params={"on_conflict": conflito} if conflito else None, corpo=list(linhas), extra=extra)

    def apagar(self, tabela, filtros):
        """Sem filtro não apaga (evita limpar a tabela por engano)."""
        if not filtros:
            raise ValueError("apagar precisa de pelo menos um filtro")
        self._chamar("DELETE", tabela, params=filtros, extra={"Prefer": "return=minimal"})

    def sinal_de_vida(self, pc, versao="", agora=None):
        """Um registro pequeno por PC: mantém o projeto 'ativo' (o plano gratuito pausa depois de 7 dias sem uso)
        e mostra, no Monitoramento, que o PC está falando com o banco."""
        quando = (agora or datetime.datetime.now(datetime.timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        self.gravar("painel_sinal", [{"pc": str(pc), "quando": quando, "versao": str(versao)}], conflito="pc")
