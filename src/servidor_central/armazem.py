"""Armazém do servidor central: guarda as abas da "Planilha Central" num arquivo SQLite (24/11/2026, início da API).

Fala exatamente a mesma língua do `BackendGoogle` (central/sheets.py): mesmos métodos, mesmos argumentos, mesmas respostas.
Por isso o resto do Painel não precisa saber se atrás está o Google ou este servidor.

Como a planilha é guardada: cada linha é uma lista de textos (como o Google devolve, `FORMATTED_VALUE`). A linha 1 é o
cabeçalho, a 2 é a primeira de dados. O `planilha_id` separa uma planilha da outra (a Central, o Mail Analytics...).

Pontos que copiam o jeito do Google:
- ler devolve só até a última linha com algo; célula vazia no fim da linha não aparece;
- aba que não existe na leitura vai para o dicionário de erros, sem derrubar as outras;
- cada aba tem um **número de versão** que sobe a cada gravação; `esperar_mudanca` segura a chamada até a versão mudar (ou dar o
  tempo), e é assim que um PC "fica sabendo" de um pedido de envio no instante em que ele chega, sem perguntar de segundo em segundo;
- `anexar_linhas`, `apagar_linhas` e `inserir_no_topo` são atômicos (uma transação só): o que outro PC acrescentou no fim
  enquanto isso fica intacto. Aqui isso é de graça; no Google dependia de um pedido só.
"""
import json
import re
import sqlite3
import threading
import time

_CELULA = re.compile(r"^'((?:[^']|'')*)'!([A-Za-z]+)(\d+)$")           # 'Aba'!K5
_FAIXA = re.compile(r"^([A-Za-z]+)(\d*)(?::([A-Za-z]*)(\d*))?$")       # A100:H  ·  A1:C5  ·  A2


TEMPO_MAXIMO_DE_ESPERA = 25.0   # segundos que `esperar_mudanca` pode segurar uma chamada


class ErroArmazem(Exception):
    """Pedido que o armazém não consegue atender (aba que não existe, endereço de célula inválido...)."""


def texto(valor):
    """O que o Google guardaria: números e textos viram texto; verdadeiro/falso viram TRUE/FALSE; nada vira vazio."""
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "TRUE" if valor else "FALSE"
    return str(valor)


def coluna_para_indice(letras):
    """A -> 0, B -> 1, AA -> 26."""
    n = 0
    for c in letras.upper():
        n = n * 26 + (ord(c) - 64)
    return n - 1


def _sem_vazios_no_fim(linha):
    linha = list(linha)
    while linha and linha[-1] == "":
        linha.pop()
    return linha


class Armazem:
    def __init__(self, caminho=":memory:"):
        self._tranca = threading.RLock()
        self._con = sqlite3.connect(caminho, check_same_thread=False, isolation_level=None)   # transações à mão (BEGIN)
        self._con.execute("PRAGMA journal_mode=WAL")
        self._con.execute("PRAGMA synchronous=NORMAL")
        self._con.executescript("""
            CREATE TABLE IF NOT EXISTS abas (p TEXT NOT NULL, aba TEXT NOT NULL, PRIMARY KEY (p, aba));
            CREATE TABLE IF NOT EXISTS linhas (p TEXT NOT NULL, aba TEXT NOT NULL, n INTEGER NOT NULL, v TEXT NOT NULL,
                                               PRIMARY KEY (p, aba, n));
            CREATE TABLE IF NOT EXISTS versoes (p TEXT NOT NULL, aba TEXT NOT NULL, v INTEGER NOT NULL, PRIMARY KEY (p, aba));
        """)
        # A versão também fica na memória, com a sua própria trava: quem espera mudança nunca disputa a trava do banco com quem grava.
        self._versoes_na_memoria = {(p, a): v for p, a, v in self._con.execute("SELECT p, aba, v FROM versoes")}
        self._mudou = threading.Condition()
        self._tocadas = set()
        self.esperando = 0   # quantos PCs estão pendurados em esperar_mudanca agora (aparece em /v1/saude)

    # ---------------------------------------------------------------- base
    def _transacao(self):
        armazem = self

        class _T:
            def __enter__(self):
                armazem._tranca.acquire()
                try:
                    armazem._con.execute("BEGIN IMMEDIATE")
                except Exception:
                    armazem._tranca.release()
                    raise
                armazem._tocadas = set()

            def __exit__(self, tipo, valor, rastro):
                tocadas = set()
                try:
                    armazem._con.execute("ROLLBACK" if tipo else "COMMIT")
                    if not tipo:
                        tocadas = armazem._tocadas
                finally:
                    armazem._tocadas = set()
                    armazem._tranca.release()
                if tocadas:   # fora da trava do banco: quem espera acorda e já enxerga o que foi gravado
                    with armazem._mudou:
                        for chave in tocadas:
                            armazem._versoes_na_memoria[chave] = armazem._versoes_na_memoria.get(chave, 0) + 1
                        armazem._mudou.notify_all()
        return _T()

    def _tocar(self, p, aba):
        """Marca que a aba mudou (dentro da transação): a versão sobe quando a gravação for confirmada."""
        if (p, aba) in self._tocadas:   # uma gravação = um passo de versão, mesmo que mexa em muitas linhas
            return
        self._con.execute("INSERT INTO versoes (p, aba, v) VALUES (?,?,1) ON CONFLICT(p, aba) DO UPDATE SET v = v + 1", (p, aba))
        self._tocadas.add((p, aba))

    def _existe(self, p, aba):
        return self._con.execute("SELECT 1 FROM abas WHERE p=? AND aba=?", (p, aba)).fetchone() is not None

    def _exigir(self, p, aba):
        if not self._existe(p, aba):
            raise ErroArmazem(f"A aba '{aba}' não existe")

    def _fim(self, p, aba):
        """Número da última linha que tem algo (0 se a aba está vazia)."""
        return self._con.execute("SELECT COALESCE(MAX(n), 0) FROM linhas WHERE p=? AND aba=?", (p, aba)).fetchone()[0]

    def _deslocar(self, p, aba, a_partir_de, quantas):
        """Empurra (quantas > 0) ou puxa (quantas < 0) as linhas de `a_partir_de` em diante. Passa por número negativo para a
        chave (aba, n) nunca bater com a de uma linha que ainda não andou."""
        if quantas == 0:
            return
        self._con.execute("UPDATE linhas SET n = -(n + ?) WHERE p=? AND aba=? AND n >= ?", (quantas, p, aba, a_partir_de))
        self._con.execute("UPDATE linhas SET n = -n WHERE p=? AND aba=? AND n < 0", (p, aba))

    def _gravar_linha(self, p, aba, n, linha):
        linha = _sem_vazios_no_fim(texto(c) for c in linha)
        if linha:
            self._con.execute("INSERT OR REPLACE INTO linhas (p, aba, n, v) VALUES (?,?,?,?)",
                              (p, aba, n, json.dumps(linha, ensure_ascii=False)))
        else:
            self._con.execute("DELETE FROM linhas WHERE p=? AND aba=? AND n=?", (p, aba, n))

    def _ler_linha(self, p, aba, n):
        r = self._con.execute("SELECT v FROM linhas WHERE p=? AND aba=? AND n=?", (p, aba, n)).fetchone()
        return json.loads(r[0]) if r else []

    # ---------------------------------------------------------------- leitura
    def planilhas(self):
        with self._tranca:
            return [r[0] for r in self._con.execute("SELECT DISTINCT p FROM abas ORDER BY p")]

    def listar_abas(self, planilha_id):
        with self._tranca:
            return [r[0] for r in self._con.execute("SELECT aba FROM abas WHERE p=? ORDER BY rowid", (planilha_id,))]

    def ler_abas(self, planilha_id, nomes, faixas=None):
        """-> ({aba: linhas}, {aba: erro}). faixas: {aba: "A100:H"} lê só desta linha em diante (e só até esta coluna)."""
        faixas = faixas or {}
        lidas, erros = {}, {}
        with self._tranca:
            for nome in dict.fromkeys(nomes):
                if not self._existe(planilha_id, nome):
                    erros[nome] = f"A aba '{nome}' não existe"
                    continue
                inicio, ultima_coluna = 1, None
                if nome in faixas:
                    m = _FAIXA.match(faixas[nome].strip())
                    if not m:
                        erros[nome] = f"faixa inválida: {faixas[nome]}"
                        continue
                    inicio = int(m.group(2) or 1)
                    ultima_coluna = coluna_para_indice(m.group(3)) if m.group(3) else None
                linhas = {n: json.loads(v) for n, v in self._con.execute(
                    "SELECT n, v FROM linhas WHERE p=? AND aba=? AND n >= ? ORDER BY n", (planilha_id, nome, inicio))}
                if not linhas:
                    lidas[nome] = []
                    continue
                corpo = []
                for n in range(inicio, max(linhas) + 1):
                    linha = linhas.get(n, [])
                    if ultima_coluna is not None:
                        linha = _sem_vazios_no_fim(linha[:ultima_coluna + 1])
                    corpo.append(linha)
                lidas[nome] = corpo
        return lidas, erros

    def versoes_das_abas(self, planilha_id, nomes):
        """-> {aba: versão}. Aba que nunca foi gravada tem versão 0. Barato: não lê linha nenhuma."""
        with self._mudou:
            return {n: self._versoes_na_memoria.get((planilha_id, n), 0) for n in nomes}

    def esperar_mudanca(self, planilha_id, aba, versao_vista, segundos=20):
        """Segura a chamada até a aba mudar em relação a `versao_vista` (ou até dar o tempo) e devolve a versão de agora.
        Quem chega com uma versão velha recebe a atual na hora. O tempo máximo é de 25 s (a rede não gosta de pedido pendurado)."""
        limite = time.monotonic() + max(0.0, min(float(segundos), TEMPO_MAXIMO_DE_ESPERA))
        chave = (planilha_id, aba)
        with self._mudou:
            self.esperando += 1
            try:
                while self._versoes_na_memoria.get(chave, 0) == versao_vista:
                    restante = limite - time.monotonic()
                    if restante <= 0:
                        break
                    self._mudou.wait(restante)
                return self._versoes_na_memoria.get(chave, 0)
            finally:
                self.esperando -= 1

    # ---------------------------------------------------------------- escrita
    def escrever(self, planilha_id, atualizacoes):
        """atualizacoes = [("'Aba'!K5", valor), ...]"""
        if not atualizacoes:
            return
        with self._transacao():
            for endereco, valor in atualizacoes:
                m = _CELULA.match(str(endereco).strip())
                if not m:
                    raise ErroArmazem(f"endereço de célula inválido: {endereco}")
                aba, coluna, n = m.group(1).replace("''", "'"), coluna_para_indice(m.group(2)), int(m.group(3))
                self._exigir(planilha_id, aba)
                self._tocar(planilha_id, aba)
                linha = self._ler_linha(planilha_id, aba, n)
                linha += [""] * (coluna + 1 - len(linha))
                linha[coluna] = texto(valor)
                self._gravar_linha(planilha_id, aba, n, linha)

    def criar_aba_status(self, planilha_id, nome, linhas):
        with self._transacao():
            self._criar(planilha_id, nome)
            for i, linha in enumerate(linhas, start=1):
                self._gravar_linha(planilha_id, nome, i, linha)

    def criar_aba_log(self, planilha_id, nome, cabecalho):
        with self._transacao():
            self._criar(planilha_id, nome)
            self._gravar_linha(planilha_id, nome, 1, cabecalho)

    def _criar(self, p, aba):
        if self._existe(p, aba):
            raise ErroArmazem(f"A aba '{aba}' já existe")
        self._con.execute("INSERT INTO abas (p, aba) VALUES (?,?)", (p, aba))
        self._tocar(p, aba)

    def inserir_no_topo(self, planilha_id, aba, linhas):
        """Põe as linhas logo abaixo do cabeçalho (a linha 2), empurrando o resto para baixo."""
        with self._transacao():
            self._exigir(planilha_id, aba)
            self._tocar(planilha_id, aba)
            self._deslocar(planilha_id, aba, 2, len(linhas))
            for i, linha in enumerate(linhas):
                self._gravar_linha(planilha_id, aba, 2 + i, linha)

    def substituir_aba(self, planilha_id, aba, linhas):
        """Reescreve a aba inteira (cria se faltar)."""
        with self._transacao():
            if not self._existe(planilha_id, aba):
                self._con.execute("INSERT INTO abas (p, aba) VALUES (?,?)", (planilha_id, aba))
            self._tocar(planilha_id, aba)
            self._con.execute("DELETE FROM linhas WHERE p=? AND aba=?", (planilha_id, aba))
            for i, linha in enumerate(linhas, start=1):
                self._gravar_linha(planilha_id, aba, i, linha)

    def garantir_colunas(self, planilha_id, aba, cabecalho):
        """Deixa o cabeçalho (linha 1) com as colunas pedidas; o que já havia além delas fica."""
        with self._transacao():
            self._exigir(planilha_id, aba)
            atual = self._ler_linha(planilha_id, aba, 1)
            if atual[:len(cabecalho)] != [texto(c) for c in cabecalho]:
                self._tocar(planilha_id, aba)
                self._gravar_linha(planilha_id, aba, 1, [texto(c) for c in cabecalho] + atual[len(cabecalho):])

    def anexar_linhas(self, planilha_id, aba, linhas):
        """Acrescenta no fim. Duas chamadas ao mesmo tempo nunca caem na mesma linha."""
        with self._transacao():
            self._exigir(planilha_id, aba)
            self._tocar(planilha_id, aba)
            n = self._fim(planilha_id, aba)
            for linha in linhas:
                n += 1
                self._gravar_linha(planilha_id, aba, n, linha)

    def apagar_linhas(self, planilha_id, aba, inicio, fim, novas=None):
        """Apaga as linhas [inicio, fim) (1 = cabeçalho, 2 = 1ª de dados) e, no mesmo pedido, põe `novas` no lugar."""
        with self._transacao():
            self._exigir(planilha_id, aba)
            self._tocar(planilha_id, aba)
            self._con.execute("DELETE FROM linhas WHERE p=? AND aba=? AND n >= ? AND n < ?", (planilha_id, aba, inicio, fim))
            self._deslocar(planilha_id, aba, fim, -(fim - inicio))
            if novas:
                self._deslocar(planilha_id, aba, inicio, len(novas))
                for i, linha in enumerate(novas):
                    self._gravar_linha(planilha_id, aba, inicio + i, linha)

    def apagar_aba(self, planilha_id, aba):
        with self._transacao():
            self._exigir(planilha_id, aba)
            self._tocar(planilha_id, aba)
            self._con.execute("DELETE FROM linhas WHERE p=? AND aba=?", (planilha_id, aba))
            self._con.execute("DELETE FROM abas WHERE p=? AND aba=?", (planilha_id, aba))

    def copiar_para(self, caminho):
        """Cópia de segurança consistente, com o servidor no ar (API de backup do SQLite): nunca pega arquivo pela metade."""
        destino = sqlite3.connect(caminho)
        try:
            with self._tranca:
                self._con.backup(destino)
        finally:
            destino.close()

    def fechar(self):
        with self._tranca:
            self._con.close()
