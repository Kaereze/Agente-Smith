"""Cópias de segurança dos dados deste PC (09/11/2026): o "banco local" ganha rede de proteção.

O Painel guarda os dados em arquivos (catálogo em `armazem.py`). Se um deles estraga (queda de luz no meio da gravação, disco
cheio, antivírus), antes o módulo dono quebrava ou recomeçava do zero. Agora:

- `fazer_copia()`  : um .zip por rodada em `estado/copias/AAAAMMDD_HHMMSS.zip`, com `manifesto.json` (tamanho e SHA-256 de cada arquivo).
                     O índice de e-mails (SQLite) é copiado pela API própria do SQLite, então a cópia nunca sai "pela metade".
- `aparar()`       : guarda só as N últimas (ajuste `limpeza.copias_guardadas`).
- `conferir()`     : acha arquivo que não abre (JSON quebrado, SQLite com falha no `integrity_check`).
- `autocurar()`    : no começo do Painel: arquivo quebrado vai para `*.quebrado-AAAAMMDD_HHMMSS` (nada é apagado) e a versão boa mais
                     recente da cópia volta no lugar. Quem não tem cópia boa fica sem o arquivo e o módulo dono refaz do Outlook/Planilha.
- `restaurar()`    : volta o que está numa cópia (usado por `ferramentas/restaurar_copia.py`); o que existia vira `*.antes-de-restaurar`.

As cópias têm dado de hóspede: ficam só neste PC, estão no catálogo (`copias`, marcado como pessoal) e saem no pedido do titular.
"""
import datetime
import hashlib
import json
import logging
import os
import sqlite3
import tempfile
import zipfile
from pathlib import Path

import ajustes
from sistema import armazem

logger = logging.getLogger("painel.copias")

PASTA = "copias"
MANIFESTO = "manifesto.json"
FORMATOS_COPIADOS = ("json", "sqlite")
PASTAS_COPIADAS = ("acessos",)   # registro de acessos: não dá para refazer de lugar nenhum


def pasta():
    p = armazem.caminho(PASTA)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _nomes_do_catalogo():
    """Arquivos do catálogo que valem cópia (o resto é cache, trava ou texto que se refaz sozinho)."""
    return [d.arquivo for d in armazem.DADOS.values() if d.formato in FORMATOS_COPIADOS] + list(PASTAS_COPIADAS)


def _sha(dados):
    return hashlib.sha256(dados).hexdigest()


def _bytes_do_sqlite(caminho):
    """Cópia consistente do SQLite (mesmo com o Painel gravando), pela API de backup do próprio SQLite."""
    with tempfile.TemporaryDirectory() as t:
        destino = Path(t) / "copia.sqlite"
        origem = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True, timeout=10)
        try:
            alvo = sqlite3.connect(destino)
            try:
                origem.backup(alvo)
            finally:
                alvo.close()
        finally:
            origem.close()
        return destino.read_bytes()


def _itens_para_copiar():
    """-> [(nome_no_zip, bytes)] do que existe agora. Falha em um arquivo não impede a cópia dos outros."""
    itens = []
    for nome in _nomes_do_catalogo():
        caminho = armazem.caminho(nome)
        try:
            if caminho.is_dir():
                for f in sorted(p for p in caminho.rglob("*") if p.is_file()):
                    itens.append((f"{nome}/{f.relative_to(caminho).as_posix()}", f.read_bytes()))
            elif caminho.is_file():
                itens.append((nome, _bytes_do_sqlite(caminho) if nome.endswith(".sqlite") else caminho.read_bytes()))
        except (OSError, sqlite3.Error) as e:
            logger.warning(f"Cópia: não li {nome}: {str(e)[:80]}")
    return itens


def fazer_copia(agora=None):
    """Grava uma cópia nova e apara as antigas. Devolve o caminho do .zip (ou None se não havia nada para guardar)."""
    agora = agora or datetime.datetime.now()
    itens = _itens_para_copiar()
    if not itens:
        return None
    manifesto = {"feita_em": agora.isoformat(timespec="seconds"),
                 "arquivos": {nome: {"bytes": len(dados), "sha256": _sha(dados)} for nome, dados in itens}}
    destino = pasta() / f"{agora:%Y%m%d_%H%M%S}.zip"
    temporario = destino.with_suffix(".zip.tmp")
    with zipfile.ZipFile(temporario, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr(MANIFESTO, json.dumps(manifesto, ensure_ascii=False, indent=1))
        for nome, dados in itens:
            z.writestr(nome, dados)
    os.replace(temporario, destino)
    aparar()
    logger.info(f"💾 Cópia de segurança: {destino.name} ({len(itens)} arquivos, {destino.stat().st_size // 1024} KB)")
    return destino


def listar():
    """As cópias deste PC, da mais nova para a mais antiga: [Path]."""
    return sorted(pasta().glob("*.zip"), reverse=True)


def aparar(guardar=None):
    guardar = guardar or ajustes.valor("limpeza.copias_guardadas")
    apagadas = 0
    for velha in listar()[guardar:]:
        try:
            velha.unlink()
            apagadas += 1
        except OSError:
            pass
    for sobra in pasta().glob("*.tmp"):   # cópia que ficou pela metade (queda de luz)
        try:
            sobra.unlink()
        except OSError:
            pass
    return apagadas


def data_da_ultima():
    """Quando foi a última cópia (pelo nome do arquivo) ou None."""
    for z in listar():
        try:
            return datetime.datetime.strptime(z.stem, "%Y%m%d_%H%M%S")
        except ValueError:
            continue
    return None


def precisa_de_copia(agora=None, horas=None):
    agora = agora or datetime.datetime.now()
    horas = horas or ajustes.valor("limpeza.copia_a_cada_horas")
    ultima = data_da_ultima()
    return ultima is None or agora - ultima >= datetime.timedelta(hours=horas)


def ler_copia(caminho_zip):
    """Abre uma cópia e confere cada arquivo contra o manifesto. -> (manifesto, {nome: bytes}). ValueError se estiver estragada."""
    try:
        with zipfile.ZipFile(caminho_zip) as z:
            manifesto = json.loads(z.read(MANIFESTO))
            conteudo = {}
            for nome, info in manifesto["arquivos"].items():
                dados = z.read(nome)
                if len(dados) != info["bytes"] or _sha(dados) != info["sha256"]:
                    raise ValueError(f"{nome} não confere com o manifesto")
                conteudo[nome] = dados
            return manifesto, conteudo
    except (zipfile.BadZipFile, KeyError, OSError, json.JSONDecodeError) as e:
        raise ValueError(f"cópia {Path(caminho_zip).name} estragada: {str(e)[:80]}") from e


def _json_ok(dados):
    try:
        json.loads(dados.decode("utf-8"))
        return True
    except (UnicodeDecodeError, json.JSONDecodeError):
        return False


def _sqlite_ok(caminho):
    try:
        con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True, timeout=10)
        try:
            return con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        finally:
            con.close()
    except sqlite3.Error:
        return False


def conferir():
    """Arquivos do catálogo que existem mas não abrem. -> [nome]"""
    ruins = []
    for d in armazem.DADOS.values():
        caminho = armazem.caminho(d.arquivo)
        if not caminho.is_file() or (d.formato == "sqlite" and caminho.stat().st_size == 0):
            continue
        try:
            if d.formato == "json" and not _json_ok(caminho.read_bytes()):
                ruins.append(d.arquivo)
            elif d.formato == "sqlite" and not _sqlite_ok(caminho):
                ruins.append(d.arquivo)
        except OSError:
            continue
    return ruins


def _versao_boa(nome):
    """Versão mais nova de `nome` que está numa cópia sã. -> (bytes, nome_da_cópia) ou (None, None)."""
    for z in listar():
        try:
            _, conteudo = ler_copia(z)
        except ValueError:
            continue
        dados = conteudo.get(nome)
        if dados is None:
            continue
        if nome.endswith(".json") and not _json_ok(dados):
            continue
        return dados, z.name
    return None, None


def _carimbo(agora):
    return f"{agora:%Y%m%d_%H%M%S}"


def autocurar(agora=None):
    """Roda ao abrir o Painel: arquivo quebrado sai do caminho e a última versão boa volta. -> [{"arquivo","restaurado_de"}]"""
    agora = agora or datetime.datetime.now()
    feitos = []
    for nome in conferir():
        caminho = armazem.caminho(nome)
        quebrado = caminho.with_name(f"{caminho.name}.quebrado-{_carimbo(agora)}")
        try:
            os.replace(caminho, quebrado)
        except OSError as e:
            logger.warning(f"Cópia: não consegui separar {nome} quebrado: {e}")
            continue
        for lateral in (caminho.with_name(caminho.name + "-wal"), caminho.with_name(caminho.name + "-shm")):
            lateral.unlink(missing_ok=True)
        dados, de = _versao_boa(nome)
        if dados is not None:
            caminho.write_bytes(dados)
        logger.warning(f"🩹 {nome} estava quebrado: guardei como {quebrado.name}"
                       + (f" e voltei a versão da cópia {de}." if de else "; sem cópia boa, o Painel refaz do Outlook/Planilha."))
        feitos.append({"arquivo": nome, "restaurado_de": de})
    return feitos


def restaurar(caminho_zip, so=None, agora=None):
    """Volta arquivos de uma cópia para estado/. O que já existia vira `*.antes-de-restaurar-<hora>`. -> [nomes restaurados]"""
    agora = agora or datetime.datetime.now()
    _, conteudo = ler_copia(caminho_zip)   # só mexe em algo depois de conferir a cópia inteira
    voltaram = []
    for nome, dados in conteudo.items():
        raiz_nome = nome.split("/")[0]
        if so and raiz_nome not in so and nome not in so:
            continue
        destino = armazem.caminho(raiz_nome) if "/" not in nome else armazem.caminho(raiz_nome) / nome.split("/", 1)[1]
        destino.parent.mkdir(parents=True, exist_ok=True)
        if destino.exists():
            os.replace(destino, destino.with_name(f"{destino.name}.antes-de-restaurar-{_carimbo(agora)}"))
        destino.write_bytes(dados)
        voltaram.append(nome)
    return voltaram


def resumo_para_saude(agora=None):
    """Avisos para a faixa de saúde do Painel: [{"nivel","pc","texto"}]."""
    agora = agora or datetime.datetime.now()
    avisos = []
    ultima = data_da_ultima()
    limite = ajustes.valor("limpeza.copia_a_cada_horas") * 3
    if ultima is None:
        avisos.append({"nivel": "aviso", "pc": "", "texto": "Este PC ainda não fez cópia de segurança dos dados (a primeira sai logo que o Painel abrir)"})
    elif agora - ultima > datetime.timedelta(hours=limite):
        avisos.append({"nivel": "aviso", "pc": "", "texto": f"A última cópia de segurança deste PC é de {ultima:%d/%m %H:%M}: "
                       "veja o registro do Painel (pasta logs) e se o disco está cheio"})
    return avisos


def contar_pasta():
    """(quantas cópias, bytes) para o Monitoramento."""
    zips = listar()
    return len(zips), sum(z.stat().st_size for z in zips)

