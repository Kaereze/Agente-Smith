"""Auditoria da cópia: compara a planilha de cada hotel com a aba correspondente na Central.

Só lê os hotéis; grava o resultado na aba "Conferência da Cópia".

    python src\\conferir_copia.py
"""
import datetime
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_utf8 import garantir_utf8

garantir_utf8()

from config import PASTA_ESTADO, carregar_config, caminho_chave_google
from log_util import configurar_logging
from sheets import VALORES_PENDENTE, _achar_coluna, _celula
from sincronizar import PAUSA_ENTRE_LEITURAS, _chave_linha, _gravar_aba, _hora, _ler_planilha_hotel, mapear_fontes
from tratamento import detectar_formato_data, normalizar

logger = configurar_logging("conferir_copia")

ABA_RESULTADO = "Conferência da Cópia"
CABECALHO_RESULTADO = [
    "Hotel", "Resultado", "O que foi encontrado", "Planilha do hotel (Drive)", "Aba na Central",
    "Solicitações na planilha do hotel", "Solicitações na Central", "Faltando na Central",
    "Dados diferentes", "TRUE que sumiu", "Só na Central", "Conferido em",
]
OK, NOVIDADE, PROBLEMA = "✔ Igual", "⏳ Novidade ainda não copiada", "✖ Diferente"
MAX_EXEMPLOS = 3


def _linhas_com_dados(linhas):
    return [l for l in linhas[1:] if any(str(v).strip() for v in l)]


def _resumo_linha(l, i_car, i_email, i_nome):
    partes = [_celula(l, i_car), _celula(l, i_nome) if i_nome is not None else "", _celula(l, i_email)]
    return " · ".join(p for p in partes if p)


def comparar(origem, central, cfg):
    """origem e central: linhas com cabeçalho. -> dict com contagens, faltando, diferenças e TRUE perdido."""
    col = cfg["colunas"]
    r = {"linhas_origem": 0, "linhas_central": 0, "faltando": [], "faltando_quando": [], "so_central": 0,
         "diferencas": [], "true_sumiu": [], "colunas_faltando": []}
    if not origem or len(origem) < 2:
        r["linhas_central"] = len(_linhas_com_dados(central)) if central else 0
        return r
    cab_o = [str(c).strip() for c in origem[0]]
    cab_c = [str(c).strip() for c in central[0]] if central else []
    i_env_o, i_car_o = _achar_coluna(cab_o, col["enviado"]), _achar_coluna(cab_o, col["carimbo"])
    i_mail_o, i_nome_o = _achar_coluna(cab_o, col.get("email_hospede", "")), _achar_coluna(cab_o, col.get("nome_hospede", ""))
    i_env_c, i_car_c = _achar_coluna(cab_c, col["enviado"]), _achar_coluna(cab_c, col["carimbo"])
    i_mail_c = _achar_coluna(cab_c, col.get("email_hospede", ""))

    pos_c = {normalizar(c): i for i, c in enumerate(cab_c) if c}
    comparaveis = []
    for i, c in enumerate(cab_o):
        if not c or i == i_env_o or i == i_car_o:   # carimbo já entra na chave de casamento
            continue
        if normalizar(c) in pos_c:
            comparaveis.append((c, i, pos_c[normalizar(c)]))
        else:
            r["colunas_faltando"].append(c)

    linhas_o, linhas_c = _linhas_com_dados(origem), _linhas_com_dados(central) if central else []
    r["linhas_origem"], r["linhas_central"] = len(linhas_o), len(linhas_c)
    fmt_o = detectar_formato_data((_celula(l, i_car_o) for l in linhas_o), cfg.get("formato_data_planilha", "americano"))
    fmt_c = detectar_formato_data((_celula(l, i_car_c) for l in linhas_c), fmt_o) if i_car_c is not None else fmt_o

    # Chave (dia, hora, e-mail); linha sem hora casa só por dia+e-mail; repetidas casam na ordem
    exatas, soltas, usadas = {}, {}, set()
    if i_car_c is not None:
        for idx, l in enumerate(linhas_c):
            k = _chave_linha(l, i_car_c, i_mail_c, fmt_c)
            if k[1]:
                exatas.setdefault(k, []).append(idx)
            soltas.setdefault((k[0], k[2]), []).append(idx)

    def casar(k):
        for idx in exatas.get(k, []) + soltas.get((k[0], k[2]), []):
            hora_c = _hora(_celula(linhas_c[idx], i_car_c))
            if idx not in usadas and (not hora_c or not k[1] or hora_c == k[1]):
                usadas.add(idx)
                return idx
        return None

    for l in linhas_o:
        k = _chave_linha(l, i_car_o, i_mail_o, fmt_o)
        idx = casar(k)
        if idx is None:
            r["faltando"].append(_resumo_linha(l, i_car_o, i_mail_o, i_nome_o))
            r["faltando_quando"].append(k)
            continue
        lc = linhas_c[idx]
        for nome, io, ic in comparaveis:
            vo, vc = _celula(l, io), _celula(lc, ic)
            if vo != vc:
                r["diferencas"].append(f"{_resumo_linha(l, i_car_o, i_mail_o, i_nome_o)} — coluna '{nome}': "
                                       f"no hotel '{vo[:40]}', na Central '{vc[:40]}'")
        true_o = i_env_o is not None and normalizar(_celula(l, i_env_o)) not in VALORES_PENDENTE
        true_c = i_env_c is not None and normalizar(_celula(lc, i_env_c)) not in VALORES_PENDENTE
        if true_o and not true_c:
            r["true_sumiu"].append(_resumo_linha(l, i_car_o, i_mail_o, i_nome_o))
    r["so_central"] = len(linhas_c) - len(usadas)
    return r


def _todas_depois(chaves, ultima_copia):
    """Tudo que falta chegou depois da última cópia (não é erro: entra na próxima)."""
    if not chaves or ultima_copia is None:
        return False
    for data_iso, hora, _email in chaves:
        try:
            quando = datetime.datetime.fromisoformat(f"{data_iso}T{hora or '00:00:00'}")
        except ValueError:
            return False
        if quando < ultima_copia:
            return False
    return True


def classificar(r, mudou_depois_da_copia):
    """-> (OK | NOVIDADE | PROBLEMA, frase para a planilha)"""
    problemas = []
    if r["colunas_faltando"]:
        problemas.append(f"coluna(s) da planilha do hotel que não existem na Central: {', '.join(r['colunas_faltando'])}")
    if r["diferencas"]:
        problemas.append(f"{len(r['diferencas'])} dado(s) diferente(s) — ex.: {r['diferencas'][0]}")
    if r["true_sumiu"]:
        problemas.append(f"{len(r['true_sumiu'])} solicitação(ões) TRUE no hotel e pendente(s) na Central "
                         f"(o robô reenviaria) — ex.: {r['true_sumiu'][0]}")
    if r["faltando"] and not mudou_depois_da_copia:
        problemas.append(f"{len(r['faltando'])} solicitação(ões) da planilha do hotel NÃO estão na Central — "
                         f"ex.: {'; '.join(r['faltando'][:MAX_EXEMPLOS])}")
    if problemas:
        return PROBLEMA, " | ".join(problemas)
    if r["faltando"]:
        return NOVIDADE, (f"{len(r['faltando'])} solicitação(ões) nova(s) chegaram depois da última cópia — "
                          f"entram na próxima (a cada 10 min): {'; '.join(r['faltando'][:MAX_EXEMPLOS])}")
    extra = f" ({r['so_central']} linha(s) antiga(s) que só existem na Central, mantidas)" if r["so_central"] else ""
    return OK, f"Todas as {r['linhas_origem']} solicitações estão na Central, com os mesmos dados{extra}."


def conferir(backend=None, cfg=None):
    cfg = cfg or carregar_config()
    chave = caminho_chave_google(cfg)
    if backend is None:
        from sheets import BackendGoogle
        backend = BackendGoogle(chave)
    central = cfg["planilha_central_id"]
    inicio = time.time()
    agora = datetime.datetime.now()

    logger.info("🔍 Conferência da cópia: lendo a pasta do Drive e a Planilha Central...")
    m = mapear_fontes(backend, cfg, chave)
    por_hotel, destino_do_hotel = m["por_hotel"], m["destino_do_hotel"]
    try:
        ultima_copia = datetime.datetime.fromisoformat(open(PASTA_ESTADO / "ultima_copia.txt", encoding="utf-8").read().strip())
    except (FileNotFoundError, ValueError):
        ultima_copia = None
    abas = [destino_do_hotel[h] for h in por_hotel if h in destino_do_hotel]
    dados_central, erros_central = backend.ler_abas(central, abas)
    logger.info(f"📂 {sum(len(v) for v in por_hotel.values())} planilha(s) de hotel na pasta · "
                f"{len(por_hotel)} hotel(éis) · {len(abas)} aba(s) de hotel na Central")

    resultados, total = [], len(por_hotel)
    for n, (hotel, arquivos) in enumerate(sorted(por_hotel.items()), start=1):
        aba_central = destino_do_hotel.get(hotel, "")
        lidas = []
        for a in sorted(arquivos, key=lambda x: x["modifiedTime"], reverse=True):
            linhas = None
            for tentativa in (1, 2):
                time.sleep(PAUSA_ENTRE_LEITURAS if tentativa == 1 else 45)
                try:
                    _, linhas = _ler_planilha_hotel(backend._cliente, a, cfg)
                    break
                except Exception as e:
                    logger.warning(f"⚠️ [{n}/{total}] {hotel}: não consegui ler a planilha '{a['name']}' "
                                   f"({str(e)[:90]})" + (" — espero 45s e tento de novo." if tentativa == 1 else ""))
            lidas.append((a, linhas))
        com_dados = [x for x in lidas if x[1] and len(x[1]) > 1]
        usada = com_dados[0] if com_dados else (lidas[0] if lidas else (None, None))
        arquivo, origem = usada
        central_linhas = dados_central.get(aba_central, []) if aba_central else []

        linha = {"hotel": hotel, "planilha": arquivo["name"] if arquivo else "", "aba": aba_central or "(não existe)"}
        if origem is None:
            resultado, frase, r = PROBLEMA, "Não consegui ler a planilha do hotel no Drive.", comparar([], central_linhas, cfg)
        elif not aba_central or aba_central in erros_central:
            r = comparar(origem, [], cfg)
            resultado, frase = PROBLEMA, "O hotel não tem aba na Planilha Central (a cópia ainda não criou)."
        else:
            r = comparar(origem, central_linhas, cfg)
            resultado, frase = classificar(r, _todas_depois(r["faltando_quando"], ultima_copia))
        # Hotel com duas planilhas: só a mais recente com dados é copiada; a outra não pode ter pedidos
        for outra, linhas_outra in lidas:
            if outra is not arquivo and linhas_outra and len(_linhas_com_dados(linhas_outra)) > 0:
                resultado = PROBLEMA
                frase += (f" | A planilha '{outra['name']}' também é deste hotel e tem "
                          f"{len(_linhas_com_dados(linhas_outra))} solicitação(ões) — ela NÃO é copiada.")
        linha.update(resultado=resultado, frase=frase, r=r)
        resultados.append(linha)
        marca = {OK: "✅", NOVIDADE: "⏳", PROBLEMA: "❌"}[resultado]
        logger.info(f"{marca} [{n}/{total}] {hotel}: hotel {r['linhas_origem']} · Central {r['linhas_central']} — {frase}")

    for nome in m["sem_hotel"]:
        logger.warning(f"⚠️ Planilha '{nome}' está na pasta mas não é de nenhum hotel do Cadastro_Hoteis — não é copiada.")
    sem_planilha = [h for h in m["cadastro"].values() if h not in por_hotel]
    for h in sem_planilha:
        logger.warning(f"⚠️ {h} está no Cadastro_Hoteis mas não tem planilha na pasta do Drive.")

    cont = {k: sum(1 for x in resultados if x["resultado"] == k) for k in (OK, NOVIDADE, PROBLEMA)}
    resumo = (f"{len(resultados)} hotel(éis) conferido(s) em {time.time() - inicio:.0f}s: {cont[OK]} igual(is), "
              f"{cont[NOVIDADE]} com novidade pra próxima cópia, {cont[PROBLEMA]} com diferença")
    (logger.warning if cont[PROBLEMA] else logger.info)(("⚠️ " if cont[PROBLEMA] else "✅ ") + resumo + ".")
    _gravar_resultado(backend, cfg, resultados, agora)
    return resultados, resumo


def _gravar_resultado(backend, cfg, resultados, agora):
    ordem = {PROBLEMA: 0, NOVIDADE: 1, OK: 2}
    quando = agora.strftime("%d/%m/%Y %H:%M")
    linhas = [CABECALHO_RESULTADO] + [[
        x["hotel"], x["resultado"], x["frase"], x["planilha"], x["aba"],
        x["r"]["linhas_origem"], x["r"]["linhas_central"], len(x["r"]["faltando"]),
        len(x["r"]["diferencas"]), len(x["r"]["true_sumiu"]), x["r"]["so_central"], quando,
    ] for x in sorted(resultados, key=lambda x: (ordem[x["resultado"]], x["hotel"]))]
    try:
        abas = backend.listar_abas(cfg["planilha_central_id"])
        _gravar_aba(backend, backend._cliente, cfg["planilha_central_id"], ABA_RESULTADO, linhas,
                    criar=ABA_RESULTADO not in abas)
        logger.info(f"📝 Resultado gravado na aba '{ABA_RESULTADO}' da Planilha Central.")
    except Exception as e:
        logger.warning(f"⚠️ Não consegui gravar a aba '{ABA_RESULTADO}' ({e}) — o resultado está no log.")


def rodar_com_trava():
    """Mesma trava da cópia: conferir no meio de uma cópia daria falso alarme."""
    from lock_execucao import adquirir_lock, liberar_lock
    if not adquirir_lock():
        return None, "A cópia ou um envio está rodando agora — tente conferir de novo em 2 minutos."
    try:
        return conferir()
    finally:
        liberar_lock()


if __name__ == "__main__":
    _, resumo = rodar_com_trava()
    print("\n" + resumo)
