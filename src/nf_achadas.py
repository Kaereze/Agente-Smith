"""NF achadas nas pastas do Dropbox pelo CPF/CNPJ de dentro do PDF (27/10/2026, desenho aprovado pelo João).

Um fio em segundo plano olha as pastas de notas (só leitura), lê o PDF novo (texto, ou imagem/OCR se for escaneado) e guarda
o CPF/CNPJ do tomador. Quando alguém abre o Enviar NF de um pedido, `achadas_do_pedido` cruza as notas dos últimos
30 dias com o pedido e devolve as sugestões. NUNCA envia nada: só sugere (a pessoa confere e clica em enviar).

Cuidados que o João pediu:
- a tag "NF enviada" não é prova: a nota é cruzada mesmo em pedido já marcado, e um pedido pode ter várias notas;
- a mesma nota (mesmo nº) já ligada ao pedido não volta a aparecer, e nota ligada a outro pedido do mesmo hotel também não;
- pedido já com NF só ganha "outra nota" quando a nota não é de outro pedido que a explica melhor.
"""
import datetime
import json
import os
import threading
import time
import types

from arquivos import salvar_json, so_na_nuvem
from controle_nf import conferir_conteudo, documento_tomador, ler_assunto_nf, provas_da_solicitacao
from log_util import configurar_logging

logger = configurar_logging("nf_achadas")

JANELA_DIAS = 30            # notas dos últimos 30 dias (também as que já estavam nas pastas)
INTERVALO_SEGUNDOS = 45     # entre uma olhada e outra nas pastas
MAX_LIDAS_POR_VOLTA = 12    # PDF escaneado (OCR) leva segundos: uma fatia por volta, sem pesar
MAX_TEXTO = 8000            # do texto de cada nota (o resto não serve pra conferir)
LIMITE_SUGESTOES = 6


class Indice:
    """{caminho: {"mtime", "nome", "nf", "doc", "texto", "sem_texto"}} guardado em estado/nf_achadas.json."""

    def __init__(self, caminho):
        self.caminho = caminho
        self.lock = threading.Lock()
        try:
            self.dados = json.load(open(caminho, encoding="utf-8"))
        except (OSError, ValueError):
            self.dados = {}

    def salvar(self):
        with self.lock:
            salvar_json(self.caminho, self.dados, indent=None)

    def itens(self):
        with self.lock:
            return list(self.dados.items())


def pdfs_recentes(cfg, desde, listar=None):
    """[(caminho, mtime, nome)] dos PDFs das pastas de notas modificados desde `desde` (epoch). Só leitura."""
    listar = listar or _listar_pasta
    saida = []
    for pasta in (cfg.get("dropbox_notas") or {}).get("pastas", []):
        for caminho, mtime, nome in listar(pasta):
            if nome.lower().endswith(".pdf") and mtime >= desde:
                saida.append((caminho, mtime, nome))
    return saida


def _listar_pasta(pasta):
    try:
        for e in os.scandir(pasta):
            if e.is_file():
                yield e.path, e.stat().st_mtime, e.name
    except OSError:
        return


def varrer(cfg, indice, ler_texto, agora=None, listar=None, na_nuvem=so_na_nuvem):
    """Lê as notas novas (ou trocadas) e guarda o CPF/CNPJ do tomador de cada uma. -> quantas leu.
    Arquivo ainda só na nuvem (Dropbox online-only) não é lido: ler puxaria o PDF inteiro para o disco."""
    agora = agora or datetime.datetime.now()
    desde = (agora - datetime.timedelta(days=JANELA_DIAS)).timestamp()
    recentes = pdfs_recentes(cfg, desde, listar)
    lidas = 0
    for caminho, mtime, nome in sorted(recentes, key=lambda x: -x[1]):
        atual = indice.dados.get(caminho)
        if atual and atual.get("mtime") == mtime:
            continue
        if lidas >= MAX_LIDAS_POR_VOLTA:
            break
        if na_nuvem(caminho):
            continue
        try:
            texto = ler_texto(caminho) or ""
        except Exception:
            logger.debug(f"nota ilegível: {caminho}", exc_info=True)
            texto = ""
        nf = ler_assunto_nf(os.path.splitext(nome)[0])
        with indice.lock:
            indice.dados[caminho] = {"mtime": mtime, "nome": nome, "nf": str(nf[0]) if nf else "",
                                     "doc": documento_tomador(texto), "sem_texto": len(texto.strip()) < 30,
                                     "texto": texto[:MAX_TEXTO]}
        lidas += 1
    with indice.lock:   # esquece o que saiu da janela ou foi apagado
        existentes = {c for c, _, _ in recentes}
        for c in [c for c in indice.dados if c not in existentes]:
            del indice.dados[c]
    if lidas:
        indice.salvar()
        logger.info(f"📄 NF achadas: {lidas} nota(s) nova(s) lida(s) nas pastas do Dropbox")
    return lidas


def iniciar(cfg, indice, ler_texto, intervalo=INTERVALO_SEGUNDOS):
    """Fio em segundo plano (roda no Painel de cada PC que tem as pastas do Dropbox)."""
    def rodar():
        while True:
            try:
                varrer(cfg, indice, ler_texto)
            except Exception:
                logger.debug("varredura das NF achadas", exc_info=True)
            time.sleep(intervalo)
    threading.Thread(target=rodar, name="nf_achadas", daemon=True).start()
    logger.info(f"🔎 NF achadas ligado: olha as pastas de notas a cada {intervalo}s (últimos {JANELA_DIAS} dias)")


def _alvo(sol):
    nomes = [n for n in [sol.get("nome", "")] + list(sol.get("nomes", [])) if n]
    return {"nomes": nomes, "data_pedido": sol.get("data", ""),
            **provas_da_solicitacao(types.SimpleNamespace(campos=sol.get("campos", [])))}


def achadas_do_pedido(indice, sol, nfs_do_pedido, ligadas_de_outros, outros_do_documento, agora=None, raiz=None):
    """Sugestões de NF para este pedido, pelo CPF/CNPJ dentro do PDF. Nunca marca nada como enviado.

    nfs_do_pedido: nºs já ligados a ESTE pedido (a tag ✅). ligadas_de_outros: {(hotel, nº)} ligadas a outros pedidos.
    outros_do_documento: {doc: [alvo de outro pedido com o mesmo CPF/CNPJ]} para ver se a nota é mais de outro pedido.
    -> [{nome, nf, rel, prova, modificado, via, forte, outra, possivel, mais_nova}]
    """
    agora = agora or datetime.datetime.now()
    desde = (agora - datetime.timedelta(days=JANELA_DIAS)).timestamp()
    alvo = _alvo(sol)
    ja = {str(n) for n in nfs_do_pedido}
    com_nf = bool(ja)
    achadas = []
    for caminho, e in indice.itens():
        doc = e.get("doc")
        if not doc or e.get("sem_texto") or e.get("mtime", 0) < desde or doc not in alvo["documentos"]:
            continue
        nf = e.get("nf", "")
        if nf and nf in ja:
            continue                                  # a mesma nota já está ligada a este pedido: nada aparece
        if nf and (sol.get("hotel", ""), nf) in ligadas_de_outros:
            continue                                  # já é de outro pedido deste hotel
        resultado, prova = conferir_conteudo(alvo, e.get("texto", ""))
        concorrentes = [o for o in outros_do_documento.get(doc, []) if conferir_conteudo(o, e.get("texto", ""))[0] == "confere"]
        if resultado == "confere":
            item = {"forte": True, "outra": com_nf, "possivel": bool(concorrentes)}
        elif com_nf and not concorrentes:
            item = {"forte": False, "outra": True, "possivel": False}   # pedido já com NF e a nota não é de outro pedido
        else:
            continue
        item.update(nome=e.get("nome", os.path.basename(caminho)), nf=nf, prova=prova, via="documento",
                    modificado=datetime.datetime.fromtimestamp(e["mtime"]).strftime("%d/%m/%Y %H:%M"),
                    rel=os.path.relpath(caminho, raiz) if raiz else caminho, _mtime=e["mtime"])
        achadas.append(item)
    achadas.sort(key=lambda a: -a["_mtime"])
    for i, a in enumerate(achadas):
        a["mais_nova"] = i == 0 and len(achadas) > 1
        a.pop("_mtime", None)
    return achadas[:LIMITE_SUGESTOES]


def sem_envio_confirmado(nfs_do_pedido, enviados, pedido_para):
    """Números da tag ✅ que não aparecem em nenhum e-mail dos Itens Enviados deste Painel para o hóspede (a tag não é prova;
    resposta do hóspede com a nota anexada não conta como envio, e por isso só olha o que a caixa do hotel enviou)."""
    sem = []
    para = {p.strip().lower() for p in pedido_para if p}
    for n in nfs_do_pedido:
        n = str(n)
        if not any(n in str(e.get("assunto", "")) and (not para or para & {x.strip().lower() for x in str(e.get("para", "")).split(",")})
                   for e in enviados):
            sem.append(n)
    return sem
