"""Faxina diária da Central (só no PC principal) — pra nada virar bola de neve (usuário, 08/10/2026).

O Painel não é histórico: quem guarda é o Outlook e a planilha de cada hotel. As abas de registro só crescem
(cada ação vira uma linha nova), e o Painel de cada PC lê isso o tempo todo. Uma vez por dia:

- Tratamento: o que tem mais de 3 dias vira o RESUMO de cada solicitação — as NFs, pra quem a NF foi enviada,
  tratativas, nota única/dividida, quem está com ela. Sai o resto (as provas "NF 123 confirmada: CPF do PDF
  confere..."). Solicitação com mais de 150 dias sai inteira (o Painel mostra 120).
  Trava: antes de gravar, confere que o estado de CADA solicitação fica idêntico; se não ficar, não grava nada.
- Fila de envios, anexos, comandos, lido/excluído: 3 dias. Atividade do robô: 7 dias.
- Abas Emails_<PC> antigas (o espelho velho) somem quando o PC já publica o espelho novo (Correio_<PC>).

Tudo num pedido só por aba (atômico): o que outro PC acrescentar no fim enquanto isso fica intacto.
Antes de mexer na Tratamento, uma cópia vai pra estado/backup_tratamento_*.json (ficam as 3 últimas).
"""
import datetime
import json
import re

import app_dados as dados
import atividade
import envio_nf
import espelho_emails
import rede_pcs
from arquivos import salvar_json
from config import PASTA_ESTADO
from log_util import configurar_logging

logger = configurar_logging("faxina")

DIAS_REGISTROS = 3
DIAS_ATIVIDADE = 7
DIAS_SOLICITACAO = 150
DIAS_SEM_SOLICITACAO = 30         # evento de solicitação que não existe mais nas abas dos hotéis
HORAS_ENTRE = 20
CAMINHO = PASTA_ESTADO / "faxina.json"
BACKUPS = 3
ABAS_CURTAS = {envio_nf.ABA_FILA: DIAS_REGISTROS, rede_pcs.ABA_COMANDOS: DIAS_REGISTROS,
               espelho_emails.ABA_EVENTOS: DIAS_REGISTROS, atividade.ABA: DIAS_ATIVIDADE}
_OBS_QUE_FICA = (dados._ENVIO_ROBO, dados._ENVIO_PAINEL)


def obs_importa(texto):
    """OBS que alguém usa: envio da NF (o Painel e a conferência do robô leem, com a [marca] que evita repetir),
    NF confirmada pelo e-mail enviado e nota única. As provas ("CPF do PDF confere") são só histórico."""
    if any(p.search(texto) for p in _OBS_QUE_FICA) or texto.startswith("Hóspede aceita nota única:"):
        return True
    m = dados._CONFIRMADA.match(texto)
    return bool(m and "e-mail" in m.group(2))


def _corte(hoje, dias):
    return (hoje - datetime.timedelta(days=dias)).isoformat()


def resumo_da_solicitacao(linhas_dela):
    """Linhas antigas de UMA solicitação -> as poucas que guardam o mesmo estado."""
    est = dados.dobrar_eventos([dados.CABECALHO_TRATAMENTO] + linhas_dela)
    (e,) = est.values()
    base = linhas_dela[0]
    aba, carimbo, email = base[3], base[4], base[5]
    ultimo = {}
    for l in linhas_dela:
        ultimo[(l[6], l[7])] = l   # (ação, valor) -> a linha mais recente com isso
    saida = []

    def linha(acao, valor, quando="", agente="", pc=""):
        orig = ultimo.get((acao, valor))
        if orig:
            quando, agente, pc = orig[0], orig[1], orig[2]
        saida.append([quando, agente, pc, aba, carimbo, email, acao, valor])
    if e["dono"]:
        linha(dados.ASSUMIR, "", e["dono_desde"], e["dono"])
        saida[-1][1] = e["dono"]
    for nf in e["nfs"]:
        linha(dados.NF, nf)
    if e["dividida"] is not None:
        valor = next((l[7] for l in reversed(linhas_dela) if l[6] == dados.DIVIDIDA), "sim" if e["dividida"] else "nao")
        linha(dados.DIVIDIDA, valor)
    for t in e["tratativas"]:
        saida.append([t["quando"], t["agente"], "", aba, carimbo, email, dados.TRATATIVA, t["texto"]])
    vistas = set()
    for o in e["obs"]:
        if obs_importa(o["texto"]) and o["texto"] not in vistas:
            vistas.add(o["texto"])
            saida.append([o["quando"], o["agente"], "", aba, carimbo, email, dados.OBS, o["texto"]])
    return saida


def _impressao(est, sol=None):
    """O que tem que ficar igual depois da faxina."""
    sol = sol or {"email": ""}
    return (est["dono"], sorted(est["nfs"]), est["dividida"], [t["texto"] for t in est["tratativas"]],
            sorted(json.dumps(x, sort_keys=True) for x in dados.envios_nf(sol, est)),
            next((o["texto"] for o in est["obs"] if o["texto"].startswith("Hóspede aceita nota única:")), ""))


def compactar_tratamento(linhas, datas, hoje):
    """linhas: a aba inteira (com cabeçalho). datas: {chave: data iso da solicitação}.
    -> (fim do bloco antigo k, linhas novas pro lugar de linhas[1:k]) ou (0, None) se não há o que fazer."""
    corte_evento = _corte(hoje, DIAS_REGISTROS)
    k = 1
    while k < len(linhas) and str(linhas[k][0] if linhas[k] else "")[:10] < corte_evento:
        k += 1
    antigas = [list(map(str, l)) + [""] * (8 - len(l)) for l in linhas[1:k]]
    if not antigas:
        return 0, None
    por_chave = {}
    for l in antigas:
        if l[6] in dados.ACOES and l[3]:
            por_chave.setdefault(dados.chave(l[3], l[4], l[5]), []).append(l[:8])
    corte_sol, corte_orfa = _corte(hoje, DIAS_SOLICITACAO), _corte(hoje, DIAS_SEM_SOLICITACAO)
    recentes = linhas[k:]
    com_novidade = {dados.chave(*map(str, l[3:6])) for l in recentes if len(l) > 5}
    novas, mantidas = [], set()
    for ch, ls in por_chave.items():
        data = datas.get(ch)
        if ch not in com_novidade:   # mexeram nela nos últimos 3 dias: o resumo fica, por mais velha que seja
            if data is not None and data and data < corte_sol:
                continue
            if data is None and max(l[0][:10] for l in ls) < corte_orfa:
                continue
        novas += resumo_da_solicitacao(ls)
        mantidas.add(ch)
    # trava: o estado de cada solicitação que fica é idêntico ao de antes (com as linhas novas por cima)
    antes = dados.dobrar_eventos([dados.CABECALHO_TRATAMENTO] + antigas + recentes)
    depois = dados.dobrar_eventos([dados.CABECALHO_TRATAMENTO] + novas + recentes)
    for ch in mantidas | com_novidade:
        if ch in antes and _impressao(antes[ch]) != _impressao(depois.get(ch, dados.estado_inicial())):
            raise RuntimeError(f"faxina mudaria o estado de {ch} — nada gravado")
    return k, novas


def _datas_das_solicitacoes(backend, cfg, central):
    from sheets import ler_hoteis
    hoteis, _ = ler_hoteis(backend, dict(cfg, somente_hoteis=[]))
    lidas, erros = backend.ler_abas(central, [h.aba for h in hoteis])
    if erros:
        raise RuntimeError(f"não li todas as abas dos hotéis ({len(erros)} com erro) — sem faxina hoje")
    return {s["chave"]: s["data"] for h in hoteis for s in dados.ler_solicitacoes(h.aba, h.nome, lidas.get(h.aba, []), cfg)}


def _backup(linhas, hoje):
    PASTA_ESTADO.mkdir(parents=True, exist_ok=True)
    salvar_json(PASTA_ESTADO / f"backup_tratamento_{hoje:%Y%m%d}.json", linhas, indent=None)
    for velho in sorted(PASTA_ESTADO.glob("backup_tratamento_*.json"))[:-BACKUPS]:
        try:
            velho.unlink()
        except OSError:
            pass


def prefixo_velho(linhas, dias, hoje, coluna=0):
    """Quantas linhas do começo (depois do cabeçalho) são mais velhas que `dias` (as abas só crescem no fim)."""
    corte = _corte(hoje, dias)
    k = 1
    while k < len(linhas) and str((linhas[k] or [""])[coluna])[:10] < corte and str((linhas[k] or [""])[coluna])[:2] == "20":
        k += 1
    return k - 1


def rodar(backend, cfg, hoje=None, forcar=False):
    hoje = hoje or datetime.date.today()
    try:
        ultima = json.load(open(CAMINHO, encoding="utf-8")).get("ultima", "")
    except (FileNotFoundError, ValueError):
        ultima = ""
    agora = datetime.datetime.now()
    if not forcar and ultima and agora - datetime.datetime.fromisoformat(ultima) < datetime.timedelta(hours=HORAS_ENTRE):
        return None
    central = cfg["planilha_central_id"]
    relatorio = {}
    todas = backend.listar_abas(central)
    nomes = [dados.ABA_TRATAMENTO, envio_nf.ABA_ANEXOS] + [a for a in ABAS_CURTAS if a in todas]
    lidas, erros = backend.ler_abas(central, nomes)
    if dados.ABA_TRATAMENTO in lidas and len(lidas[dados.ABA_TRATAMENTO]) > 1:
        linhas = lidas[dados.ABA_TRATAMENTO]
        k, novas = compactar_tratamento(linhas, _datas_das_solicitacoes(backend, cfg, central), hoje)
        if novas is not None and len(novas) < k - 1:
            _backup(linhas, hoje)
            backend.apagar_linhas(central, dados.ABA_TRATAMENTO, 2, k + 1, novas)
            relatorio[dados.ABA_TRATAMENTO] = f"{k - 1} linhas antigas viraram {len(novas)}"
    fila = lidas.get(envio_nf.ABA_FILA) or []
    fila_que_fica = {str(l[1]) for l in fila[prefixo_velho(fila, DIAS_REGISTROS, hoje) + 1:] if len(l) > 1}
    for aba, dias in ABAS_CURTAS.items():
        n = prefixo_velho(lidas.get(aba) or [], dias, hoje)
        if n:
            backend.apagar_linhas(central, aba, 2, n + 2)
            relatorio[aba] = f"{n} linhas com mais de {dias} dias"
    # anexos: só os de envios que ainda estão na fila (os outros já saíram ou expiraram)
    anexos = lidas.get(envio_nf.ABA_ANEXOS) or []
    n = 0
    while n + 1 < len(anexos) and str((anexos[n + 1] or [""])[0]).split("#")[0] not in fila_que_fica:
        n += 1
    pendentes = [x for x in envio_nf.dobrar_fila(lidas.get(envio_nf.ABA_FILA) or [[]]).values()
                 if x["pedido"] and not x["resultado"]]
    if n and not pendentes:   # nenhum envio em andamento: ninguém está pra gravar numa linha de anexo agora
        backend.apagar_linhas(central, envio_nf.ABA_ANEXOS, 2, n + 2)
        relatorio[envio_nf.ABA_ANEXOS] = f"{n} partes de anexo de envios encerrados"
    # espelho velho (Emails_<PC>): some quando o mesmo PC já publica o novo
    for aba in todas:
        if aba.startswith("Emails_") and espelho_emails.PREFIXO_ABA + aba[len("Emails_"):] in todas:
            backend.apagar_aba(central, aba)
            relatorio[aba] = "espelho antigo apagado (o PC já usa o novo)"
    salvar_json(CAMINHO, {"ultima": agora.isoformat(timespec="seconds"), "relatorio": relatorio})
    for aba, o_que in relatorio.items():
        logger.info(f"🧹 Faxina · {aba}: {o_que}")
    if not relatorio:
        logger.info("🧹 Faxina: nada pra limpar hoje.")
    return relatorio
