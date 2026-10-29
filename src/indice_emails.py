"""Índice local dos e-mails das caixas dos hotéis DESTE PC (usuário, 20/10/2026: pesquisa instantânea; muda a regra
de 08/10 "busca sempre ao vivo no Outlook").

- Fica só neste PC, em estado/indice_emails.sqlite (fora do git e do Google), com os últimos 12 meses de Caixa de
  Entrada, Itens Enviados e Itens Excluídos das caixas dos hotéis. Mais velho que isso sai sozinho (faxina diária).
- Quem monta é uma linha de fundo do Painel (Montador), em duas etapas, sempre ~1 s de Outlook e uma pausa (o robô e a
  tela continuam com o Outlook livre):
  1. rápida, pela tabela do Outlook (GetTable, ~1.100 e-mails/s no PC do João): assunto, quem mandou, para quem, data
     e o começo do texto (255 letras). Os 12 meses ficam pesquisáveis em poucos minutos;
  2. completa, e-mail por e-mail (~20/s), do mais novo pro mais velho: o texto inteiro de quem passou de 255 letras
     e o nome dos anexos de quem tem anexo.
  Depois de pronto, só pega o que mudou (LastModificationTime) e, a cada 30 min, tira o que saiu da pasta.
- A pesquisa responde em milissegundos (SQLite FTS5, sem acento, palavra pela metade: "Pereg" acha "Perego").
  O Outlook ao vivo continua no botão "Procurar também no Outlook".
- Só lê o Outlook: nada é marcado, movido ou apagado.
"""
import datetime
import json
import re
import sqlite3
import threading
import time

import busca_outlook
import espelho_emails as ee
from config import PASTA_ESTADO
from log_util import configurar_logging

logger = configurar_logging("indice_emails")

ARQUIVO = PASTA_ESTADO / "indice_emails.sqlite"
DIAS = 365
TEXTO_MAX = {"entrada": 1500, "enviado": 300, "excluido": 600}   # o que o hóspede escreveu pesa mais que a nossa resposta
PREVIA_TABELA = 255           # a tabela do Outlook corta o texto aqui
CAMPOS = ("id", "entry", "pasta", "caixa", "hotel", "de", "nome", "para", "assunto", "quando", "previa", "anexos")
COLUNAS = ("EntryID", "Subject", "SenderName", "SenderEmailAddress", "To", "ReceivedTime", "SentOn",
           "urn:schemas:httpmail:textdescription", "urn:schemas:httpmail:hasattachment",
           "http://schemas.microsoft.com/mapi/proptag/0x5D01001F")   # PR_SENDER_SMTP_ADDRESS
LINHAS_POR_VEZ = 200
PASSO_SEGUNDOS = 1.0          # tempo de Outlook por passo enquanto monta (depois vem a pausa)
PAUSA_MONTANDO = 4            # 1 s lendo, 4 s parado
PAUSA_PRONTO = 20             # pronto: só o que mudou, a cada 20 s
CONFERIR_SAIDOS_SEGUNDOS = 30 * 60
FAXINA_SEGUNDOS = 24 * 60 * 60
FOLGA_MINUTOS = 2


def _data_outlook(d):
    return f"{d:%d/%m/%Y %H:%M}"


def consulta_fts(termo):
    """'Lorena Pereg' -> '"lorena"* AND "pereg"*' (cada palavra pela metade, em qualquer campo). '' se não der."""
    palavras = re.findall(r"\w+", busca_outlook.limpar_termo(termo).lower())
    return " AND ".join(f'"{p}"*' for p in palavras)


class Indice:
    def __init__(self, caminho=ARQUIVO):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        self.db = sqlite3.connect(str(caminho), check_same_thread=False)
        with self.lock:
            self.db.execute("PRAGMA journal_mode=WAL")
            self.db.executescript("""
                CREATE TABLE IF NOT EXISTS emails (id TEXT UNIQUE, entry TEXT, pasta TEXT, caixa TEXT, hotel TEXT,
                    de TEXT, nome TEXT, para TEXT, assunto TEXT, quando TEXT, previa TEXT, anexos TEXT,
                    completo INTEGER DEFAULT 1);
                CREATE INDEX IF NOT EXISTS emails_quando ON emails(quando);
                CREATE INDEX IF NOT EXISTS emails_pasta ON emails(caixa, pasta);
                CREATE INDEX IF NOT EXISTS emails_completo ON emails(completo, quando);
                CREATE VIRTUAL TABLE IF NOT EXISTS busca USING fts5(assunto, pessoas, texto,
                    tokenize='unicode61 remove_diacritics 2');
                CREATE TABLE IF NOT EXISTS marcas (chave TEXT PRIMARY KEY, valor TEXT);
            """)
            self.db.commit()

    # --- marcas (até onde já montou cada pasta) ---
    def marca(self, chave, padrao=""):
        with self.lock:
            r = self.db.execute("SELECT valor FROM marcas WHERE chave=?", (chave,)).fetchone()
        return r[0] if r else padrao

    def marcar(self, chave, valor):
        with self.lock:
            self.db.execute("INSERT OR REPLACE INTO marcas VALUES (?, ?)", (chave, str(valor)))
            self.db.commit()

    # --- gravar / tirar ---
    def gravar(self, itens):
        """itens: [{CAMPOS..., "texto", "completo"}]. Mesmo id = atualiza (e-mail que mudou ou foi lido inteiro)."""
        with self.lock:
            for e in itens:
                antigo = self.db.execute("SELECT rowid FROM emails WHERE id=?", (e["id"],)).fetchone()
                valores = [json.dumps(e.get(c) or []) if c == "anexos" else str(e.get(c) or "") for c in CAMPOS]
                valores.append(int(e.get("completo", 1)))
                colunas = CAMPOS + ("completo",)
                if antigo:
                    rowid = antigo[0]
                    self.db.execute(f"UPDATE emails SET {', '.join(c + '=?' for c in colunas)} WHERE rowid=?", valores + [rowid])
                    self.db.execute("DELETE FROM busca WHERE rowid=?", (rowid,))
                else:
                    rowid = self.db.execute(f"INSERT INTO emails ({', '.join(colunas)}) VALUES ({', '.join('?' * len(colunas))})",
                                            valores).lastrowid
                pessoas = " ".join(str(e.get(c) or "") for c in ("de", "nome", "para", "caixa", "hotel"))
                texto = " ".join([str(e.get("texto") or "")[:TEXTO_MAX.get(e.get("pasta"), 600)]] + [str(a) for a in e.get("anexos") or []])
                self.db.execute("INSERT INTO busca(rowid, assunto, pessoas, texto) VALUES (?, ?, ?, ?)",
                                (rowid, str(e.get("assunto") or ""), pessoas, texto))
            self.db.commit()

    def _tirar_rowids(self, rowids):
        for r in rowids:
            self.db.execute("DELETE FROM busca WHERE rowid=?", (r,))
            self.db.execute("DELETE FROM emails WHERE rowid=?", (r,))

    def tirar(self, ids):
        with self.lock:
            self._tirar_rowids([r for i in ids for (r,) in self.db.execute("SELECT rowid FROM emails WHERE id=?", (i,))])
            self.db.commit()

    def tirar_fora_da_pasta(self, caixa, pasta, ids_que_ficam, desde_iso):
        """Conferência: o que o índice tem dessa pasta (desde a data) e o Outlook não tem mais = movido/apagado."""
        with self.lock:
            linhas = self.db.execute("SELECT rowid, id FROM emails WHERE caixa=? AND pasta=? AND quando>=?",
                                     (caixa, pasta, desde_iso)).fetchall()
            sair = [r for r, i in linhas if i not in ids_que_ficam]
            self._tirar_rowids(sair)
            self.db.commit()
        return len(sair)

    def faxina(self, agora):
        limite = (agora - datetime.timedelta(days=DIAS)).isoformat(timespec="seconds")
        with self.lock:
            velhos = [r for (r,) in self.db.execute("SELECT rowid FROM emails WHERE quando<?", (limite,))]
            self._tirar_rowids(velhos)
            self.db.commit()
        return len(velhos)

    def a_completar(self, quantos):
        """Os mais novos que só vieram da tabela (texto cortado ou anexo sem nome). -> [(id, entry, pasta, caixa, hotel)]"""
        with self.lock:
            return self.db.execute("SELECT id, entry, pasta, caixa, hotel FROM emails WHERE completo=0 "
                                   "ORDER BY quando DESC LIMIT ?", (int(quantos),)).fetchall()

    # --- pesquisa ---
    def confere(self, id_email, entry, caixa):
        """True se este e-mail (id e EntryID) está no índice DESTA caixa. Só o que o próprio PC indexou das caixas dos hotéis pode ser
        excluído por pedido vindo de outro lugar (29/10/2026): o EntryID chega da tela e nunca vale sozinho."""
        if not (id_email and entry and caixa):
            return False
        with self.lock:
            achou = self.db.execute("SELECT 1 FROM emails WHERE id=? AND entry=? AND lower(caixa)=lower(?)",
                                    (id_email, entry, caixa)).fetchone()
        return achou is not None

    def buscar(self, termo, limite=busca_outlook.LIMITE_POR_PC):
        consulta = consulta_fts(termo)
        if len(busca_outlook.limpar_termo(termo)) < 3 or not consulta:
            return []
        with self.lock:
            linhas = self.db.execute(
                f"SELECT {', '.join('e.' + c for c in CAMPOS)} FROM busca JOIN emails e ON e.rowid = busca.rowid "
                "WHERE busca MATCH ? ORDER BY e.quando DESC LIMIT ?", (consulta, int(limite))).fetchall()
        return [{**dict(zip(CAMPOS, linha)), "anexos": json.loads(linha[-1] or "[]")} for linha in linhas]

    def total(self):
        with self.lock:
            return self.db.execute("SELECT count(*) FROM emails").fetchone()[0]


def extrair(item, pasta, caixa, hotel):
    """1 e-mail aberto no Outlook -> linha completa do índice (Body lido uma vez só)."""
    corpo = str(item.Body or "")
    r = busca_outlook.resumo_do_item(item, pasta, caixa, hotel, "", corpo=corpo)
    r.pop("pc", None)
    r["texto"], r["completo"] = ee.dividir_historico(corpo)[0], 1
    return r


def da_tabela(linha, pasta, caixa, hotel):
    """1 linha da tabela do Outlook (na ordem de COLUNAS) -> linha do índice; completo=0 quando falta texto/anexo."""
    entry, assunto, nome, endereco, para, recebido, enviado, previa, tem_anexo, smtp = linha
    de = str(smtp or endereco or "").strip().lower()
    previa = str(previa or "")
    if pasta == "enviado":
        de, nome, quando = caixa, "", ee._data(enviado) or ee._data(recebido)
    else:
        para, quando = caixa, ee._data(recebido)
    return {"id": ee.id_do_email(str(entry)), "entry": str(entry), "pasta": pasta, "caixa": caixa, "hotel": hotel,
            "de": de, "nome": str(nome or ""), "para": str(para or ""), "assunto": str(assunto or ""),
            "quando": quando.isoformat(timespec="seconds") if quando else "", "previa": ee.previa(previa), "anexos": [],
            "texto": previa, "completo": 0 if (tem_anexo or (pasta == "entrada" and len(previa) >= PREVIA_TABELA)) else 1}


class Montador:
    """Monta e mantém o índice. passo(namespace, caixas) -> segundos até o próximo passo."""

    def __init__(self, indice, relogio=datetime.datetime.now, cronometro=time.monotonic):
        self.indice, self.relogio, self.cronometro = indice, relogio, cronometro
        self.ultima_mudanca = self.ultima_conferencia = self.ultima_faxina = -1e9
        self.pronto = False   # etapa rápida feita em todas as pastas (os 12 meses pesquisáveis)

    def _pastas(self, namespace, caixas):
        for conta in namespace.Accounts:
            caixa = str(conta.SmtpAddress or "").strip().lower()
            if caixa not in caixas:
                continue
            for numero, pasta in busca_outlook.PASTAS:
                try:
                    yield caixa, pasta, conta.DeliveryStore.GetDefaultFolder(numero)
                except Exception as e:
                    logger.debug(f"índice: pasta {pasta} de {caixa}: {e}")

    def passo(self, namespace, caixas):
        agora, t = self.relogio(), self.cronometro()
        pastas = list(self._pastas(namespace, caixas))
        if t - self.ultima_faxina >= FAXINA_SEGUNDOS:
            self.ultima_faxina = t
            n = self.indice.faxina(agora)
            if n:
                logger.info(f"🗂️ Índice de e-mails: {n} e-mail(s) com mais de 12 meses saíram")
        if t - self.ultima_mudanca >= PAUSA_PRONTO:
            self.ultima_mudanca = t
            self._o_que_mudou(pastas, caixas, agora)
        fim = self.cronometro() + PASSO_SEGUNDOS
        faltam = [x for x in pastas if self.indice.marca(f"{x[0]}|{x[1]}|feito") != "1"]
        for caixa, pasta, obj in faltam:
            if self.cronometro() >= fim:
                break
            self._montar(caixa, pasta, obj, caixas[caixa], agora, fim)
        antes, self.pronto = self.pronto, all(self.indice.marca(f"{c}|{p}|feito") == "1" for c, p, _ in pastas)
        if self.pronto and not antes and faltam:
            logger.info(f"🗂️ Índice de e-mails pesquisável: {self.indice.total()} e-mail(s) de 12 meses neste PC "
                        "(o texto inteiro continua entrando aos poucos)")
        if not self.pronto:
            return PAUSA_MONTANDO
        if self._completar(namespace, fim):
            return PAUSA_MONTANDO
        if t - self.ultima_conferencia >= CONFERIR_SAIDOS_SEGUNDOS:
            self.ultima_conferencia = t
            self._tirar_saidos(pastas, agora)
        return PAUSA_PRONTO

    def _montar(self, caixa, pasta, obj, hotel, agora, fim):
        """Etapa rápida: a tabela do Outlook, do mais novo pro mais velho, até o tempo do passo acabar."""
        chave = f"{caixa}|{pasta}"
        limite = agora - datetime.timedelta(days=DIAS)
        fronteira = self.indice.marca(chave + "|fronteira")
        ate = datetime.datetime.fromisoformat(fronteira) if fronteira else agora + datetime.timedelta(days=1)
        if not fronteira:   # 1ª vez: dali pra frente quem cuida é o "o que mudou"
            self.indice.marcar(chave + "|mudou", agora.isoformat(timespec="seconds"))
        tabela = obj.GetTable(f"[ReceivedTime] >= '{_data_outlook(limite)}' AND [ReceivedTime] <= '{_data_outlook(ate)}'")
        tabela.Sort("[ReceivedTime]", True)
        tabela.Columns.RemoveAll()
        for coluna in COLUNAS:
            tabela.Columns.Add(coluna)
        lote, mais_velho, acabou = [], None, True
        while not tabela.EndOfTable:
            if self.cronometro() >= fim:
                acabou = False
                break
            for linha in tabela.GetArray(LINHAS_POR_VEZ) or ():
                try:
                    e = da_tabela(linha, pasta, caixa, hotel)
                except Exception as erro:
                    logger.debug(f"índice: linha ilegível em {chave}: {erro}")
                    continue
                lote.append(e)
                recebido = ee._data(linha[5])
                if recebido and (mais_velho is None or recebido < mais_velho):
                    mais_velho = recebido
        self.indice.gravar(lote)
        if acabou:
            self.indice.marcar(chave + "|feito", "1")
        elif mais_velho:
            nova = mais_velho.replace(second=0, microsecond=0)
            if fronteira and nova >= ate.replace(second=0, microsecond=0):
                nova = ate - datetime.timedelta(minutes=1)   # mais de um passo de e-mails no mesmo minuto: anda 1 min
            self.indice.marcar(chave + "|fronteira", nova.isoformat(timespec="seconds"))

    def _completar(self, namespace, fim):
        """Etapa completa: abre o e-mail (texto inteiro e nome dos anexos). -> True se ainda falta algum."""
        while self.cronometro() < fim:
            fila = self.indice.a_completar(10)
            if not fila:
                return False
            lote, sumiram = [], []
            for id_email, entry, pasta, caixa, hotel in fila:
                try:
                    lote.append(extrair(namespace.GetItemFromID(entry), pasta, caixa, hotel))
                except Exception:
                    sumiram.append(id_email)   # saiu da pasta desde a tabela: a conferência/o que mudou acham o novo
            self.indice.gravar(lote)
            self.indice.tirar(sumiram)
        return True

    def _o_que_mudou(self, pastas, caixas, agora):
        """E-mail novo, movido pra cá ou alterado desde a última olhada (pela hora em que mudou no Outlook)."""
        for caixa, pasta, obj in pastas:
            chave = f"{caixa}|{pasta}|mudou"
            desde = self.indice.marca(chave)
            if not desde:
                continue   # pasta ainda não começou a ser montada
            inicio = datetime.datetime.fromisoformat(desde) - datetime.timedelta(minutes=FOLGA_MINUTOS)
            try:
                itens = obj.Items.Restrict(f"[LastModificationTime] >= '{_data_outlook(inicio)}'")
                lote = [extrair(i, pasta, caixa, caixas[caixa]) for i in itens if getattr(i, "Class", 43) == 43]
            except Exception as e:
                logger.debug(f"índice: o que mudou em {caixa}/{pasta}: {e}")
                continue
            self.indice.gravar(lote)
            self.indice.marcar(chave, agora.isoformat(timespec="seconds"))

    def _tirar_saidos(self, pastas, agora):
        limite = agora - datetime.timedelta(days=DIAS)
        desde = limite.isoformat(timespec="seconds")
        for caixa, pasta, obj in pastas:
            try:
                ficam = {ee.id_do_email(e) for e in _entry_ids(obj, limite)}
            except Exception as e:
                logger.debug(f"índice: conferência de {caixa}/{pasta}: {e}")
                continue
            n = self.indice.tirar_fora_da_pasta(caixa, pasta, ficam, desde)
            if n:
                logger.info(f"🗂️ Índice de e-mails: {n} e-mail(s) que saíram de {pasta} em {caixa} tirados")


def _entry_ids(pasta, desde):
    """EntryIDs da pasta desde a data, pela tabela do Outlook (só a coluna: milhares em menos de 1 s)."""
    tabela = pasta.GetTable(f"[ReceivedTime] >= '{_data_outlook(desde)}'")
    tabela.Columns.RemoveAll()
    tabela.Columns.Add("EntryID")
    saida = []
    while not tabela.EndOfTable:
        saida += [str(linha[0]) for linha in tabela.GetArray(1000) or ()]
    return saida
