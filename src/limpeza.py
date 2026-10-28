"""Limpeza do que cresce sozinho (27/10/2026, auditoria): cache da janela do Painel e sobra de registros.

Medido nos PCs: estado/ com 695 MB, 560 MB deles cache do navegador da janela (app_edge e app_webview); logs/ com 99 MB
porque a saída antiga do console (31 MB) ficou como cópia girada e nunca mais foi apagada.

Nada aqui toca em dado do Painel: do navegador só saem as pastas de cache (o tema e as preferências ficam no
Local Storage / IndexedDB e são preservados); dos registros só saem cópias já giradas que passaram do teto.
"""
import os
import re
import shutil
from pathlib import Path

PERFIS_DA_JANELA = ("app_webview", "app_edge")
PASTAS_DE_CACHE = {"cache", "code cache", "gpucache", "grshadercache", "shadercache", "dawncache", "dawngraphitecache",
                   "dawnwebgpucache", "cachestorage", "scriptcache", "component_crx_cache"}
MINIMO_PARA_LIMPAR = 50_000_000   # abaixo disso não vale a pena mexer: abrir a janela continua rápido
TETO_DO_REGISTRO = 5_000_000
GIRADO = re.compile(r"\.(txt|log)\.\d+$", re.IGNORECASE)


def _tamanho(pasta):
    total = 0
    for raiz, _, nomes in os.walk(pasta):
        for n in nomes:
            try:
                total += os.path.getsize(os.path.join(raiz, n))
            except OSError:
                pass
    return total


def pastas_de_cache(perfil):
    """Pastas de cache dentro do perfil do navegador (qualquer profundidade), sem entrar dentro de uma já achada."""
    achadas = []
    for raiz, subpastas, _ in os.walk(perfil):
        restantes = []
        for nome in subpastas:
            if nome.lower() in PASTAS_DE_CACHE:
                achadas.append(Path(raiz) / nome)
            else:
                restantes.append(nome)
        subpastas[:] = restantes
    return achadas


def limpar_cache_da_janela(pasta_estado, minimo=MINIMO_PARA_LIMPAR):
    """Apaga só as pastas de cache dos perfis da janela, se juntas passarem de `minimo`. -> bytes liberados.
    Chamar com a janela ainda fechada; o que estiver em uso fica (erro ignorado) e sai na próxima vez."""
    caches = [c for perfil in PERFIS_DA_JANELA if (Path(pasta_estado) / perfil).is_dir()
              for c in pastas_de_cache(Path(pasta_estado) / perfil)]
    antes = sum(_tamanho(c) for c in caches)
    if antes < minimo:
        return 0
    for c in caches:
        shutil.rmtree(c, ignore_errors=True)
    return antes - sum(_tamanho(c) for c in caches if c.exists())


def aparar_registros(pasta_logs, teto=TETO_DO_REGISTRO):
    """Apaga cópias GIRADAS (.txt.1, .log.2...) maiores que 3 vezes o teto. O arquivo ativo nunca é tocado aqui: quem
    escreve nele (o logging do Painel ou o .bat do agendador) gira no teto. -> bytes liberados."""
    liberado = 0
    pasta = Path(pasta_logs)
    if not pasta.is_dir():
        return 0
    for arq in pasta.iterdir():
        if arq.is_file() and GIRADO.search(arq.name):
            try:
                tam = arq.stat().st_size
                if tam > 3 * teto:
                    arq.unlink()
                    liberado += tam
            except OSError:
                pass   # em uso por outro processo: fica para a próxima
    return liberado


def maiores_pastas(pasta_estado, quantas=3):
    """[(caminho relativo, MB)] das maiores pastas que sobraram nos perfis da janela: só nome e tamanho, pro registro
    mostrar o que mais pesa quando a limpeza do cache não basta."""
    base = Path(pasta_estado)
    itens = []
    for perfil in PERFIS_DA_JANELA:
        raiz = base / perfil / "EBWebView" if (base / perfil / "EBWebView").is_dir() else base / perfil
        if raiz.is_dir():
            itens += [(str(d.relative_to(base)), _tamanho(d) // 1_000_000) for d in raiz.iterdir() if d.is_dir()]
    return sorted(itens, key=lambda x: -x[1])[:quantas]
