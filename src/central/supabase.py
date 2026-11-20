"""Conexão com o Supabase (banco de dados central, 20/11/2026): ler, gravar, apagar, dar sinal de vida e entrar com a credencial do PC.

Fala com a API REST do próprio Supabase (PostgREST e Auth) usando `requests`, que já está instalado: nenhuma biblioteca nova.
Nada aqui liga sozinho. O Painel só usa o banco quando existir o arquivo da chave neste PC (`chave-supabase.json`,
ao lado da chave do Google, FORA do repositório) e a configuração mandar usar (`banco.abas`). Até lá a Planilha Central segue valendo.

Dois jeitos de entrar (o arquivo da chave diz qual):
- só `url` + `chave` (publicável): vale para as tabelas de TESTE, que aceitam qualquer um com a chave.
- `url` + `chave` + `email` + `senha`: cada PC entra com a SUA credencial (usuário do Supabase Auth). É o que vale para dado de hóspede:
  as regras do banco (RLS) só deixam entrar quem está na lista `pcs_autorizados`. Ver `ferramentas/supabase_fila.sql`.

Segurança: a chave e a senha nunca aparecem em log, erro ou tela (`ErroBanco` só leva o código HTTP e um pedaço curto da resposta).
Dados de teste são sempre fictícios (regra do João: nunca dado real de hóspede em teste).
"""
import datetime
import json
import os
import re
import threading
import time

import requests

import ajustes
from central.rede_util import com_retry
from sistema.log_util import configurar_logging

logger = configurar_logging(__name__)

ARQUIVO_PADRAO = os.path.join("%APPDATA%", "SolicitacoesNF", "chave-supabase.json")
_ENDERECO = re.compile(r"^https://[a-z0-9]{8,40}\.supabase\.(co|in)/?$")
_FOLGA_TOKEN = 60   # renova a credencial um minuto antes de vencer


class ErroBanco(Exception):
    """Falha ao falar com o banco. `codigo` é o status HTTP (0 = nem chegou: sem internet ou tempo esgotado)."""

    def __init__(self, texto, codigo=0):
        super().__init__(texto)
        self.codigo = codigo


def caminho_da_chave(cfg=None):
    cfg = cfg or {}
    return os.path.expandvars(str((cfg.get("supabase", {}) or {}).get("caminho_chave") or ARQUIVO_PADRAO))


def carregar(caminho):
    """Lê `{"url": "https://xxxx.supabase.co", "chave": "...", "email": "...", "senha": "..."}` (email e senha são opcionais).
    Devolve (url, chave, email, senha). Erro de arquivo/endereço vira ErroBanco SEM o conteúdo da chave."""
    try:
        with open(caminho, encoding="utf-8") as f:
            dados = json.load(f)
    except FileNotFoundError:
        raise ErroBanco(f"Não achei o arquivo da chave do Supabase em {caminho}") from None
    except (OSError, ValueError):
        raise ErroBanco(f"O arquivo {caminho} não pôde ser lido (precisa ser um JSON com 'url' e 'chave')") from None
    dados = dados if isinstance(dados, dict) else {}
    url, chave = str(dados.get("url", "")).strip(), str(dados.get("chave", "")).strip()
    email, senha = str(dados.get("email", "")).strip(), str(dados.get("senha", ""))
    if not _ENDERECO.match(url):
        raise ErroBanco("O 'url' do arquivo da chave precisa ser o endereço do projeto: https://xxxxxxxx.supabase.co")
    if len(chave) < 20:
        raise ErroBanco("A 'chave' do arquivo está vazia ou curta demais (use a chave publicável do projeto)")
    if bool(email) != bool(senha):
        raise ErroBanco("O arquivo da chave precisa ter 'email' E 'senha' juntos (ou nenhum dos dois)")
    return url.rstrip("/"), chave, email, senha


def _passageiro(erro):
    """Vale tentar de novo: sem internet, tempo esgotado, 'devagar' (429) ou erro do servidor (5xx)."""
    return isinstance(erro, ErroBanco) and (erro.codigo == 0 or erro.codigo == 429 or erro.codigo >= 500)


class Banco:
    def __init__(self, url, chave, email="", senha="", sessao=None, tentativa_segundos=None, limite_segundos=None, relogio=time.time):
        self.url = url.rstrip("/")
        self._sessao = sessao or requests.Session()
        self._tentativa = tentativa_segundos or ajustes.valor("banco.tentativa_segundos")
        self._limite = limite_segundos or ajustes.valor("banco.chamada_limite_segundos")
        self._chave, self._email, self._senha, self._relogio = chave, email, senha, relogio
        self._cabecalho = {"apikey": chave, "Content-Type": "application/json"}
        if chave.startswith("eyJ") and not email:   # chave antiga (JWT) também vai como Bearer; a nova ("sb_publishable_...") só no apikey
            self._cabecalho["Authorization"] = f"Bearer {chave}"
        self._token, self._token_ate, self._renovacao = "", 0.0, ""
        self._trava = threading.Lock()

    @classmethod
    def do_arquivo(cls, caminho, **kw):
        url, chave, email, senha = carregar(caminho)
        return cls(url, chave, email, senha, **kw)

    @property
    def com_credencial(self):
        return bool(self._email)

    # ---- entrada do PC (Supabase Auth) ----
    def _entrar(self, forcar=False):
        """Pega ou renova a credencial deste PC. Sem e-mail e senha no arquivo, não faz nada."""
        if not self._email:
            return
        with self._trava:
            if not forcar and self._token and self._relogio() < self._token_ate - _FOLGA_TOKEN:
                return
            for tipo, corpo in self._pedidos_de_entrada():
                try:
                    r = self._sessao.request("POST", f"{self.url}/auth/v1/token", params={"grant_type": tipo}, timeout=self._tentativa,
                                             data=json.dumps(corpo).encode("utf-8"), headers={"apikey": self._chave, "Content-Type": "application/json"})
                except requests.RequestException as e:
                    raise ErroBanco(f"sem resposta do banco na entrada ({type(e).__name__})") from None
                if r.status_code < 400:
                    d = r.json()
                    self._token, self._renovacao = d["access_token"], d.get("refresh_token", "")
                    self._token_ate = self._relogio() + int(d.get("expires_in", 3600))
                    return
                if r.status_code >= 500 or r.status_code == 429:
                    raise ErroBanco(f"o banco está indisponível na entrada ({r.status_code})", r.status_code)
            self._token, self._renovacao = "", ""
            raise ErroBanco("o banco recusou a entrada deste PC (confira 'email' e 'senha' no arquivo da chave)", 401)

    def _pedidos_de_entrada(self):
        if self._renovacao:
            yield "refresh_token", {"refresh_token": self._renovacao}
        yield "password", {"email": self._email, "password": self._senha}

    def _cabecalho_agora(self, extra=None):
        self._entrar()
        c = {**self._cabecalho, **(extra or {})}
        if self._email and self._token:
            c["Authorization"] = f"Bearer {self._token}"
        return c

    # ---- pedidos ----
    def _chamar(self, metodo, tabela, params=None, corpo=None, extra=None):
        def uma_vez():
            for tentativa in (1, 2):
                try:
                    r = self._sessao.request(metodo, f"{self.url}/rest/v1/{tabela}", params=params, timeout=self._tentativa,
                                             data=None if corpo is None else json.dumps(corpo, ensure_ascii=False).encode("utf-8"),
                                             headers=self._cabecalho_agora(extra))
                except requests.RequestException as e:
                    raise ErroBanco(f"sem resposta do banco ({type(e).__name__})") from None
                if r.status_code == 401 and self._email and tentativa == 1:   # credencial vencida antes da hora: entra de novo uma vez
                    self._entrar(forcar=True)
                    continue
                if r.status_code >= 400:
                    raise ErroBanco(f"o banco respondeu {r.status_code}: {r.text[:160]}", r.status_code)
                return r
        return com_retry(uma_vez, _passageiro, tentativas=3, espera_inicial=1, orcamento=self._limite)

    def ler(self, tabela, filtros=None, colunas="*", limite=1000, ordem=None, desloc=0):
        """filtros: {coluna: "eq.valor"} (ou "gt.", "lt.", "in.(a,b)"). Devolve uma lista de dicionários."""
        params = {"select": colunas, "limit": limite, **(filtros or {})}
        if ordem:
            params["order"] = ordem
        if desloc:
            params["offset"] = desloc
        return self._chamar("GET", tabela, params=params).json()

    def ler_tudo(self, tabela, filtros=None, colunas="*", ordem=None, pagina=1000, teto=100000):
        """Lê em páginas (o servidor entrega no máximo ~1000 linhas por pedido). `teto` evita ler sem fim."""
        todas = []
        while len(todas) < teto:
            parte = self.ler(tabela, filtros, colunas, limite=pagina, ordem=ordem, desloc=len(todas))
            todas += parte
            if len(parte) < pagina:
                break
        return todas

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
