"""Copia as respostas das planilhas dos hotéis (pasta do Drive) para as abas da Central.

    python src\\sincronizar.py                     prévia, não grava
    python src\\sincronizar.py --gravar
    python src\\sincronizar.py --agendado --enviar  ciclo do Agendador: copia e envia
"""
import datetime
import json
import os
import re
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_utf8 import garantir_utf8

garantir_utf8()

from arquivos import salvar_json
from config import PASTA_ESTADO, carregar_config, caminho_chave_google, e_principal
from log_util import configurar_logging
from sheets import BackendGoogle as _Backend

_api = _Backend._api   # conta na cota deste programa (cota_google)
from sheets import (VALORES_PENDENTE, _achar_coluna, _achar_colunas, _celula, _coluna_da_linha, nome_do_hotel_pela_aba,
                    nome_intervalo)
import robo_antigo
from tratamento import detectar_formato_data, ler_data, normalizar

logger = configurar_logging("sincronizar")

MIME_PLANILHA = "application/vnd.google-apps.spreadsheet"
PAUSA_ENTRE_LEITURAS = 1.1   # cota da Sheets API: 60 leituras/min


def hotel_da_planilha(nome_arquivo, cfg, cadastro):
    """'Nota Fiscal (Lg Inn) (respostas)' -> 'L GINN' | None"""
    fontes = cfg.get("fontes_hoteis", {})
    manual = {normalizar(k): v for k, v in fontes.get("planilha_para_hotel", {}).items()}
    if normalizar(nome_arquivo) in manual:
        return manual[normalizar(nome_arquivo)]
    partes = [p for p in re.findall(r"\(([^)]*)\)", nome_arquivo) if normalizar(p) != "respostas"]
    base = partes[0] if partes else re.sub(r"(?i)^\s*(solicita\S+\s+)?nota fiscal\s*|\s*\(respostas\)\s*$", "", nome_arquivo)
    chave = normalizar(base)
    apelidos = {normalizar(k): v for k, v in cfg.get("apelidos_hoteis", {}).items() if not k.startswith("_")}
    chave = normalizar(apelidos.get(chave, base))
    return cadastro.get(chave)


def _hora(texto):
    """'9:35:54' -> '09:35:54'; '' se não houver hora."""
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", texto or "")
    return f"{int(m.group(1)):02d}:{m.group(2)}:{m.group(3) or '00'}" if m else ""


def _chave_linha(linha, i_carimbo, i_email, formato):
    """Chave independente do formato de data (5/28 x 28/05). i_email: um índice ou a lista de _achar_colunas."""
    carimbo = _celula(linha, i_carimbo)
    data = ler_data(carimbo, formato)
    return (data.isoformat() if data else carimbo, _hora(carimbo), _celula(linha, _coluna_da_linha(linha, i_email)).lower())


def _no_futuro(quando):
    """Carimbo lido no formato errado (10/12 virando dezembro) não vale como atividade do robô antigo."""
    return quando > datetime.datetime.now() + datetime.timedelta(days=1)


def _ocorrencias(cabecalho):
    """['A', 'B', 'A'] -> [('a', 1), ('b', 1), ('a', 2)]: casa coluna pelo nome, mesmo repetido."""
    vistos, saida = {}, []
    for c in cabecalho:
        n = normalizar(c)
        vistos[n] = vistos.get(n, 0) + 1
        saida.append((n, vistos[n]))
    return saida


def _mapa_colunas(cab_de, cab_para):
    """Posição de cada coluna de cab_de em cab_para, pelo nome. None = mesmo cabeçalho, nada a mudar."""
    de, para = _ocorrencias(cab_de), _ocorrencias(cab_para)
    if de == para:
        return None
    pos = {k: i for i, k in enumerate(para)}
    return [pos.get(k) for k in de]


def _remapear(linha, mapa, largura):
    if mapa is None:
        return list(linha)
    nova = [""] * largura
    for j, v in enumerate(list(linha)[:len(mapa)]):
        if mapa[j] is not None:
            nova[mapa[j]] = v
    return nova


def juntar_planilhas(lidas, cfg):
    """Todas as planilhas de um hotel numa origem só (15/10/2026: o formulário novo grava em 'Solicitação Nota Fiscal
    (X) (respostas)', com outras colunas, e a planilha antiga para; a cópia lia só a mais recente e 26 pedidos do
    Boa Viagem e do São Francisco ficaram sem envio).
    lidas: [(arquivo, aba, linhas)] com dados. -> (origem, fontes)
      origem: o cabeçalho da planilha mais antiga + as colunas que só a outra tem, no fim; as linhas de todas, na ordem
      fontes[j]: [(arquivo, aba, número da linha no Sheets)] da linha j da origem (a mesma solicitação nas duas = uma linha)"""
    if len(lidas) == 1:   # quase todos os hotéis: igual a antes
        arquivo, aba, linhas = lidas[0]
        return linhas, [[(arquivo, aba, n)] for n, l in enumerate(linhas[1:], start=2) if any(str(v).strip() for v in l)]
    col = cfg["colunas"]
    i_cars = {id(x): _achar_coluna([str(c).strip() for c in x[2][0]], col["carimbo"]) for x in lidas}
    fmt = detectar_formato_data((_celula(l, i_cars[id(x)]) for x in lidas for l in x[2][1:] if _celula(l, i_cars[id(x)])),
                                cfg.get("formato_data_planilha", "americano"))

    def primeiro_pedido(x):
        datas = [d for d in (ler_data(_celula(l, i_cars[id(x)]), fmt) for l in x[2][1:]) if d]
        return (min(datas).isoformat() if datas else "9999-12-31", x[0]["name"])

    ordem = sorted(lidas, key=primeiro_pedido)
    cab = [str(c).strip() for c in ordem[0][2][0]]
    posicao = {k: i for i, k in enumerate(_ocorrencias(cab))}
    for _arquivo, _aba, linhas in ordem[1:]:
        for c, k in zip(linhas[0], _ocorrencias(linhas[0])):
            if k not in posicao:
                posicao[k] = len(cab)
                cab.append(str(c).strip())
    i_car, i_env = _achar_coluna(cab, col["carimbo"]), _achar_coluna(cab, col["enviado"])
    i_emails = _achar_colunas(cab, col.get("email_hospede", ""))
    origem, fontes, vistas = [cab], [], {}
    for arquivo, aba, linhas in ordem:
        mapa = [posicao[k] for k in _ocorrencias(linhas[0])]
        desta = {}
        for numero, l in enumerate(linhas[1:], start=2):
            if not any(str(v).strip() for v in l):
                continue
            nova = _remapear([str(v) for v in l], mapa, len(cab))
            k = _chave_linha(nova, i_car, i_emails, fmt)
            j = vistas.get(k) if k[0] and k[1] else None
            if j is not None:   # a mesma solicitação copiada nas duas planilhas: uma linha, TRUE de qualquer uma
                fontes[j].append((arquivo, aba, numero))
                if i_env is not None and normalizar(nova[i_env]) not in VALORES_PENDENTE:
                    origem[j + 1][i_env] = nova[i_env]
                continue
            origem.append(nova)
            fontes.append([(arquivo, aba, numero)])
            desta.setdefault(k, len(fontes) - 1)
        for k, j in desta.items():
            vistas.setdefault(k, j)
    return origem, fontes


def mesclar(origem, destino, cfg, chaves_ja_enviadas=frozenset()):
    """Junta a planilha do hotel (origem) com a aba da Central (destino). -> (linhas, resumo)

    A origem manda nos dados; o TRUE vem de qualquer um dos lados (hotel, Central ou
    ja_enviadas). Linhas que só existem na Central vão pro fim e nunca são apagadas.
    """
    col = cfg["colunas"]
    cab = [str(c).strip() for c in origem[0]]
    if _achar_coluna(cab, col["enviado"]) is None:
        cab = cab + ["Enviado"]
    i_env = _achar_coluna(cab, col["enviado"])
    i_car = _achar_coluna(cab, col["carimbo"])
    i_email = _achar_colunas(cab, col.get("email_hospede", ""))
    fmt_o = detectar_formato_data((_celula(l, i_car) for l in origem[1:]), cfg.get("formato_data_planilha", "americano"))

    linhas_d, exatas, soltas = [], {}, {}
    if destino and len(destino) > 1:
        cab_d = [str(c).strip() for c in destino[0]]
        d_env, d_car = _achar_coluna(cab_d, col["enviado"]), _achar_coluna(cab_d, col["carimbo"])
        d_email = _achar_colunas(cab_d, col.get("email_hospede", ""))
        if d_car is not None:
            fmt_d = detectar_formato_data((_celula(l, d_car) for l in destino[1:]), fmt_o)
            for l in destino[1:]:
                if not any(str(v).strip() for v in l):
                    continue
                k = _chave_linha(l, d_car, d_email, fmt_d)
                true = d_env is not None and normalizar(_celula(l, d_env)) not in VALORES_PENDENTE
                idx = len(linhas_d)
                linhas_d.append((l, true))
                if k[1]:
                    exatas.setdefault(k, []).append(idx)
                soltas.setdefault((k[0], k[2]), []).append(idx)
    usadas = set()

    def casar(k):
        for idx in exatas.get(k, []):
            if idx not in usadas:
                usadas.add(idx)
                return idx
        for idx in soltas.get((k[0], k[2]), []):
            if idx not in usadas and not _chave_tem_hora_diferente(linhas_d, idx, k, destino, col, fmt_o):
                usadas.add(idx)
                return idx
        return None

    novas = [cab]
    resumo = {"linhas": 0, "true_origem": 0, "true_da_central": 0, "true_da_lista": 0, "pendentes": 0, "so_na_central": 0,
              "ultimo_antigo": None}
    for l in origem[1:]:
        if not any(str(v).strip() for v in l):
            continue
        l = [str(v) for v in l] + [""] * (len(cab) - len(l))
        k = _chave_linha(l, i_car, i_email, fmt_o)
        idx = casar(k)
        ja_true = normalizar(l[i_env]) not in VALORES_PENDENTE
        true_central = idx is not None and linhas_d[idx][1]
        true_lista = k in chaves_ja_enviadas
        if ja_true:
            resumo["true_origem"] += 1
            if not true_lista:   # TRUE no hotel que não fomos nós = robô antigo
                quando = robo_antigo.momento(_celula(l, i_car), fmt_o)
                if quando and not _no_futuro(quando) and (resumo["ultimo_antigo"] is None or quando > resumo["ultimo_antigo"]):
                    resumo["ultimo_antigo"] = quando
        elif true_central:
            resumo["true_da_central"] += 1
        elif true_lista:
            resumo["true_da_lista"] += 1
        else:
            resumo["pendentes"] += 1
        l[i_env] = bool(ja_true or true_central or true_lista)
        novas.append(l[:len(cab)])
        resumo["linhas"] += 1
    mapa = _mapa_colunas(destino[0], cab) if linhas_d else None   # cabeçalho mudou (planilhas juntadas): pelo nome
    for idx, (l, _true) in enumerate(linhas_d):
        if idx not in usadas:
            novas.append(_remapear(l, mapa, len(cab)))
            resumo["so_na_central"] += 1
    return novas, resumo


def _letra_coluna(indice):
    """0 -> A, 25 -> Z, 26 -> AA (notação A1)."""
    letras, indice = "", indice + 1
    while indice:
        indice, resto = divmod(indice - 1, 26)
        letras = chr(65 + resto) + letras
    return letras


def linhas_para_marcar_no_hotel(lidas, fontes, novas, cfg):
    """TRUE também na planilha do hotel (usuário, 15/10/2026: o robô novo marcava só na Central e a planilha do hotel
    parecia "não enviada"). lidas: as planilhas do hotel com dados; fontes: de juntar_planilhas; novas: o resultado do
    mesclar (TRUE vindo da Central ou da lista do robô).
    -> [(arquivo, aba, letra da coluna Enviado | None, [linhas no Sheets ainda sem TRUE])], uma por planilha.
    Letra None: a planilha não tem a coluna Enviado (não criamos coluna na planilha de ninguém)."""
    enviado = cfg["colunas"]["enviado"]
    i_env_n = _achar_coluna([str(c).strip() for c in novas[0]], enviado)
    plano = {}
    for arquivo, aba, linhas in lidas:
        plano[arquivo["id"]] = (arquivo, aba, _achar_coluna([str(c).strip() for c in linhas[0]], enviado), linhas, [])
    for j, lista in enumerate(fontes):   # novas[1 + j] é a linha j da origem (mesma ordem do mesclar)
        if 1 + j >= len(novas) or novas[1 + j][i_env_n] is not True:
            continue
        for arquivo, _aba, numero in lista:
            _a, _b, i_env, linhas, marcar = plano[arquivo["id"]]
            if i_env is None or normalizar(_celula(linhas[numero - 1], i_env)) in VALORES_PENDENTE:
                marcar.append(numero)
    return [(a, aba, None if i_env is None else _letra_coluna(i_env), marcar) for a, aba, i_env, _l, marcar in plano.values()]


def marcar_true_nos_arquivos(cliente, plano):
    """Escreve o plano de linhas_para_marcar_no_hotel. -> (quantas linhas, [planilhas sem a coluna Enviado])"""
    n, sem_coluna = 0, []
    for arquivo, aba, letra, linhas in plano:
        if not linhas:
            continue
        if letra is None:
            sem_coluna.append(arquivo["name"])
            continue
        n += escrever_true_no_hotel(cliente, arquivo["id"], aba, letra, linhas)
    return n, sem_coluna


def escrever_true_no_hotel(cliente, arquivo_id, aba, letra, linhas):
    """Escreve TRUE só na coluna Enviado, nas linhas dadas (uma chamada a cada 500 células). -> quantas"""
    dados = [{"range": f"{nome_intervalo(aba)}!{letra}{n}", "values": [["TRUE"]]} for n in linhas]
    for i in range(0, len(dados), 500):
        lote = dados[i:i + 500]
        _api("escrita", lambda lote=lote: cliente.http_client.values_batch_update(
            arquivo_id, body={"valueInputOption": "USER_ENTERED", "data": lote}))
    return len(dados)


def espelhar_true_nos_hoteis(backend, cfg, hoteis=None):
    """Põe TRUE na planilha do hotel em tudo que já foi enviado (TRUE na Central ou na lista do robô).
    hoteis: nomes do cadastro (None = todos). -> {hotel: quantas linhas marcadas | "sem coluna Enviado"}"""
    chave = caminho_chave_google(cfg)
    cliente, central = backend._cliente, cfg["planilha_central_id"]
    m = mapear_fontes(backend, cfg, chave)
    alvo = sorted(m["por_hotel"])
    if hoteis is not None:
        quero = {normalizar(h) for h in hoteis}
        alvo = [h for h in alvo if normalizar(h) in quero]
    destinos = m["destino_do_hotel"]
    dados_central, _ = backend.ler_abas(central, [destinos[h] for h in alvo if h in destinos])
    lista = chaves_da_lista_ja_enviadas(PASTA_ESTADO / "ja_enviadas.json")
    saida = {}
    for hotel in alvo:
        destino = dados_central.get(destinos.get(hotel, ""), [])
        lidas = []
        for arquivo in sorted(m["por_hotel"][hotel], key=lambda a: a["modifiedTime"], reverse=True):
            time.sleep(PAUSA_ENTRE_LEITURAS)
            aba_origem, origem = _ler_planilha_hotel(cliente, arquivo, cfg)
            if len(origem) > 1:   # as mesmas que a cópia junta: todas com dados
                lidas.append((arquivo, aba_origem, origem))
        if not lidas:
            continue
        origem, fontes = juntar_planilhas(lidas, cfg)
        novas, _ = mesclar(origem, destino, cfg, lista)
        n, sem_coluna = marcar_true_nos_arquivos(cliente, linhas_para_marcar_no_hotel(lidas, fontes, novas, cfg))
        if n:
            saida[hotel] = n
            logger.info(f"✔️ {hotel}: {n} linha(s) marcada(s) TRUE na planilha do hotel (já enviadas)")
        elif sem_coluna:
            saida[hotel] = "sem coluna Enviado"
    return saida


def _chave_tem_hora_diferente(linhas_d, idx, k, destino, col, fmt):
    """Casamento só por data+e-mail vale se a linha da Central não tiver hora ou tiver a mesma."""
    cab_d = [str(c).strip() for c in destino[0]]
    d_car = _achar_coluna(cab_d, col["carimbo"])
    hora = _hora(_celula(linhas_d[idx][0], d_car))
    return bool(hora) and bool(k[1]) and hora != k[1]


def chaves_da_lista_ja_enviadas(caminho):
    """estado/ja_enviadas.json -> chaves no formato de _chave_linha."""
    try:
        registros = json.load(open(caminho, encoding="utf-8"))
    except FileNotFoundError:
        return set()
    carimbos = [k.split(" | ")[2] for k in registros if len(k.split(" | ")) >= 4]
    formato = detectar_formato_data(carimbos, "americano")
    chaves = set()
    for k in registros:
        partes = k.split(" | ")
        if len(partes) < 4:
            continue
        carimbo, email = partes[2], partes[3]
        data = ler_data(carimbo, formato)
        chaves.add((data.isoformat() if data else carimbo, _hora(carimbo), email.lower()))
    return chaves


_sessoes_drive = {}
_trava_sessoes_drive = threading.Lock()


def _sessao_drive(caminho_chave, nova=False):
    """Uma sessão do Drive por chave, reaproveitada (29/10/2026, medido com py-spy): criar credencial nova a cada chamada (a vigia dos
    formulários chama de 10 em 10 s) gastava CPU na assinatura RSA e uma ida à internet só para pedir token. A biblioteca renova o
    token sozinha quando vence; nova=True descarta a guardada (chave trocada ou token recusado)."""
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials
    with _trava_sessoes_drive:
        if nova:
            _sessoes_drive.pop(caminho_chave, None)
        s = _sessoes_drive.get(caminho_chave)
        if s is None:
            s = _sessoes_drive[caminho_chave] = AuthorizedSession(Credentials.from_service_account_file(
                caminho_chave, scopes=["https://www.googleapis.com/auth/drive.readonly"]))
        return s


def listar_pasta(caminho_chave, pasta_id):
    s = _sessao_drive(caminho_chave)
    arquivos, token = [], None
    while True:
        pedido = dict(timeout=30, params={
            "q": f"'{pasta_id}' in parents and trashed=false and mimeType='{MIME_PLANILHA}'",
            "pageSize": 1000, "pageToken": token, "fields": "nextPageToken, files(id,name,modifiedTime,version)"})
        r = s.get("https://www.googleapis.com/drive/v3/files", **pedido)
        if r.status_code == 401:   # token recusado: uma sessão nova, uma vez só
            s = _sessao_drive(caminho_chave, nova=True)
            r = s.get("https://www.googleapis.com/drive/v3/files", **pedido)
        r.raise_for_status()
        j = r.json()
        arquivos += j.get("files", [])
        token = j.get("nextPageToken")
        if not token:
            return arquivos


def _ler_planilha_hotel(cliente, arquivo, cfg):
    """Tenta a aba padrão numa chamada só; se ela não existir, abre a planilha e procura."""
    preferida = cfg.get("fontes_hoteis", {}).get("aba_respostas", "Respostas ao formulário 1")
    try:
        r = _api("leitura", lambda: cliente.http_client.values_batch_get(
            arquivo["id"], [nome_intervalo(preferida)], params={"valueRenderOption": "FORMATTED_VALUE"}))   # _api já repete o erro passageiro
        return preferida, r["valueRanges"][0].get("values", [])
    except Exception as e:
        if "unable to parse range" not in str(e).lower() and "400" not in str(e):
            raise
    sh = _api("leitura", lambda: cliente.open_by_key(arquivo["id"]))
    abas = [w.title for w in _api("leitura", sh.worksheets)]
    aba = preferida if preferida in abas else ([a for a in abas if "respostas" in a.lower()] or abas[:1])[0]
    time.sleep(PAUSA_ENTRE_LEITURAS)
    r = _api("leitura", lambda: sh.values_batch_get([nome_intervalo(aba)], params={"valueRenderOption": "FORMATTED_VALUE"}),
                  )
    return aba, r["valueRanges"][0].get("values", [])


def agrupar_por_hotel(arquivos, cfg, cadastro, ignorar=None):
    """Planilhas da pasta (listagem do Drive) -> ({hotel: [arquivos]}, [nomes sem hotel no cadastro])."""
    if ignorar is None:
        ignorar = {normalizar(n) for n in cfg.get("fontes_hoteis", {}).get("ignorar", [])}
    por_hotel, sem_hotel = {}, []
    for a in arquivos:
        if normalizar(a["name"]) in ignorar:
            continue
        h = hotel_da_planilha(a["name"], cfg, cadastro)
        (por_hotel.setdefault(h, []).append(a) if h else sem_hotel.append(a["name"]))
    return por_hotel, sem_hotel


def mapear_fontes(backend, cfg, chave, arquivos=None):
    """Planilhas da pasta por hotel e a aba da Central que recebe cada hotel. arquivos: listagem já feita (vigia)."""
    fontes = cfg.get("fontes_hoteis", {})
    central = cfg["planilha_central_id"]
    cad_linhas = backend.ler_abas(central, [cfg["aba_cadastro_hoteis"]])[0][cfg["aba_cadastro_hoteis"]]
    cadastro = {normalizar(l[0]): l[0].strip() for l in cad_linhas if l and l[0].strip()}
    ignorar = {normalizar(n) for n in fontes.get("ignorar", [])}

    arquivos = listar_pasta(chave, fontes["pasta_drive_id"]) if arquivos is None else arquivos
    por_hotel, sem_hotel = agrupar_por_hotel(arquivos, cfg, cadastro, ignorar)

    abas_central = backend.listar_abas(central)
    destino_do_hotel = {}
    apelidos = {normalizar(k): v for k, v in cfg.get("apelidos_hoteis", {}).items() if not k.startswith("_")}
    for aba in abas_central:
        if "(respostas)" in aba.lower():
            n = nome_do_hotel_pela_aba(aba)
            h = cadastro.get(normalizar(apelidos.get(normalizar(n), n)))
            if h and h not in destino_do_hotel:
                destino_do_hotel[h] = aba
    return {"cadastro": cadastro, "por_hotel": por_hotel, "sem_hotel": sem_hotel,
            "abas_central": abas_central, "destino_do_hotel": destino_do_hotel}


VERSOES = "sincronizacao_versoes.json"
COMPLETA_HORAS = 3   # leitura de todas as planilhas, mesmo sem mudança de versão (rede de segurança)


def hoteis_que_mudaram(por_hotel, versoes, completa):
    """Hotéis com alguma planilha cuja versão no Drive mudou desde a última cópia. O Drive não mexe no
    modifiedTime quando o Forms grava resposta, mas a "version" sobe a cada alteração (ela vem na mesma
    listagem da pasta, que não gasta a cota de leitura das planilhas)."""
    if completa:
        return dict(por_hotel)
    return {h: lista for h, lista in por_hotel.items()
            if any(not a.get("version") or versoes.get(a["id"]) != a["version"] for a in lista)}


def sincronizar(gravar=False, completa=None, so_hoteis=None, mapa=None):
    """so_hoteis: só estes hotéis, lidos mesmo sem versão nova (vigia dos formulários, 23/10/2026). mapa: o resultado de
    mapear_fontes já pronto (a vigia guarda por 10 min e troca só a listagem do Drive)."""
    cfg = carregar_config()
    chave = caminho_chave_google(cfg)
    from sheets import BackendGoogle
    backend = BackendGoogle(chave, somente_leitura=not gravar)
    cliente, central = backend._cliente, cfg["planilha_central_id"]
    m = mapa or mapear_fontes(backend, cfg, chave)
    cadastro, por_hotel, sem_hotel = m["cadastro"], m["por_hotel"], m["sem_hotel"]
    abas_central, destino_do_hotel = m["abas_central"], m["destino_do_hotel"]

    estado = PASTA_ESTADO / "sincronizacao.json"
    try:
        marcas = json.load(open(estado, encoding="utf-8"))
    except FileNotFoundError:
        marcas = {}
    chaves_enviadas = chaves_da_lista_ja_enviadas(PASTA_ESTADO / "ja_enviadas.json")
    try:
        guardado = json.load(open(PASTA_ESTADO / VERSOES, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        guardado = {}
    versoes, ultima_completa = guardado.get("versoes", {}), guardado.get("ultima_completa", "")
    if completa is None:
        completa = not ultima_completa or datetime.datetime.now() - datetime.datetime.fromisoformat(ultima_completa)             >= datetime.timedelta(hours=COMPLETA_HORAS)
    if so_hoteis is not None:   # vigia dos formulários: só os hotéis que mudaram no Drive agora
        completa = False
        por_hotel = {h: lista for h, lista in por_hotel.items() if h in so_hoteis}
        a_ler = dict(por_hotel)
    else:
        a_ler = hoteis_que_mudaram(por_hotel, versoes, completa)
    lidas_agora = {}

    relatorio, copia_de_seguranca = [], {}
    inicio_copia = datetime.datetime.now()
    if gravar:
        os.makedirs(PASTA_ESTADO, exist_ok=True)
        arquivo_backup = PASTA_ESTADO / f"backup_central_{inicio_copia:%Y%m%d_%H%M%S}.json"
    dados_central, _ = backend.ler_abas(central, [destino_do_hotel[h] for h in a_ler if h in destino_do_hotel])
    for hotel in sorted(set(por_hotel) - set(a_ler)):
        relatorio.append({"hotel": hotel, "situacao": "sem mudança no Drive — não lida"})
    for hotel, lista in sorted(a_ler.items()):
        # Só os hotéis com versão nova no Drive (ou todos, na leitura completa). A aba só é regravada se mudou.
        lidas = []
        for a in sorted(lista, key=lambda x: x["modifiedTime"], reverse=True):
            time.sleep(PAUSA_ENTRE_LEITURAS)
            aba_origem, linhas = _ler_planilha_hotel(cliente, a, cfg)
            lidas.append((a, aba_origem, linhas))
        lidas_agora.update({a["id"]: a.get("version", "") for a in lista})
        com_dados = [x for x in lidas if len(x[2]) > 1]
        if not com_dados:
            relatorio.append({"hotel": hotel, "situacao": "planilha do hotel vazia — nada copiado"})
            continue
        # Todas as planilhas do hotel com dados, numa aba só (15/10/2026: o formulário novo grava numa planilha nova
        # e a antiga para; copiar só a mais recente deixou 26 pedidos sem envio no Boa Viagem e no São Francisco)
        origem, fontes = juntar_planilhas(com_dados, cfg)
        aba_destino = destino_do_hotel.get(hotel) or f"Solicitação Nota Fiscal ({hotel}) (respostas)"
        destino = dados_central.get(aba_destino, []) if aba_destino in abas_central else []
        novas, resumo = mesclar(origem, destino, cfg, chaves_enviadas)
        resumo.update(hotel=hotel, origem=" + ".join(x[0]["name"] for x in com_dados), planilhas=len(com_dados),
                      aba_destino=aba_destino, linhas_central_antes=max(len(destino) - 1, 0),
                      criar_aba=aba_destino not in abas_central,
                      outras_planilhas=[x[0]["name"] for x in lidas if len(x[2]) <= 1],
                      mudou=_como_texto(novas) != _como_texto(destino))
        if gravar and cfg.get("marcar_true_no_hotel", True):
            try:
                n, _sem_coluna = marcar_true_nos_arquivos(cliente, linhas_para_marcar_no_hotel(com_dados, fontes, novas, cfg))
                if n:
                    resumo["true_no_hotel"] = n
                    logger.info(f"✔️ {hotel}: {n} linha(s) marcada(s) TRUE na planilha do hotel (já enviadas)")
            except Exception as e:
                logger.warning(f"⚠️ {hotel}: não consegui marcar TRUE na planilha do hotel ({e}) — tento na próxima volta")
        relatorio.append(resumo)
        if gravar and resumo["mudou"]:
            if destino:
                copia_de_seguranca[aba_destino] = destino
            json.dump(copia_de_seguranca, open(arquivo_backup, "w", encoding="utf-8"), ensure_ascii=False)
            _gravar_aba(backend, cliente, central, aba_destino, novas, criar=aba_destino not in abas_central)
            logger.info(f"📥 {hotel}: {resumo['linhas']} linhas copiadas pra '{aba_destino}' ({resumo['pendentes']} pendentes"
                        + (f", juntando {len(com_dados)} planilhas" if len(com_dados) > 1 else "") + ")")
            for x in com_dados:
                marcas[x[0]["id"]] = x[0]["modifiedTime"]
    if gravar:
        os.makedirs(PASTA_ESTADO, exist_ok=True)
        json.dump(marcas, open(estado, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        salvar_json(PASTA_ESTADO / VERSOES, {"versoes": {**versoes, **lidas_agora},
                                             "ultima_completa": inicio_copia.isoformat(timespec="seconds") if completa
                                             else ultima_completa})
        open(PASTA_ESTADO / "ultima_copia.txt", "w", encoding="utf-8").write(inicio_copia.isoformat(timespec="seconds"))
        robo_antigo.registrar_atividade(PASTA_ESTADO / "robo_antigo.json",
                                        {r["hotel"]: r.get("ultimo_antigo") for r in relatorio if "linhas" in r})
        _limpar_backups_antigos()
    return relatorio, sem_hotel, [h for h in cadastro.values() if h not in por_hotel]


def _como_texto(linhas):
    """Normaliza como a API devolve (booleanos em texto, sem vazios à direita) pra comparar."""
    saida = []
    for l in linhas or []:
        l = ["TRUE" if v is True else "FALSE" if v is False else str(v) for v in l]
        while l and l[-1] == "":
            l.pop()
        saida.append(l)
    while saida and not saida[-1]:
        saida.pop()
    return saida


def _limpar_backups_antigos(manter=144):   # 24h de cópias a cada 10 min (usuário, 15/10/2026: era 30 min)
    backups = sorted(PASTA_ESTADO.glob("backup_central_*.json"))
    for velho in backups[:-manter]:
        try:
            velho.unlink()
        except OSError:
            pass


def _gravar_aba(backend, cliente, central, aba, linhas, criar):
    """Sobrescreve e só depois limpa as sobras: a aba nunca fica vazia no meio da gravação."""
    from gspread.utils import rowcol_to_a1
    planilha = backend._planilha(central)
    largura = max(len(l) for l in linhas)
    corpo = [l + [""] * (largura - len(l)) for l in linhas]
    if criar:
        ws = _api("escrita", lambda: planilha.add_worksheet(title=aba, rows=len(corpo) + 50, cols=largura),
                       )
    else:
        ws = _api("leitura", lambda: planilha.worksheet(aba))
        if ws.row_count < len(corpo) or ws.col_count < largura:
            _api("escrita", lambda: ws.resize(rows=max(ws.row_count, len(corpo) + 50), cols=max(ws.col_count, largura)),
                      )
    time.sleep(PAUSA_ENTRE_LEITURAS)
    _api("escrita", lambda: ws.update(range_name="A1", values=corpo, value_input_option="RAW"))
    time.sleep(PAUSA_ENTRE_LEITURAS)
    sobras = []
    if ws.col_count > largura:
        sobras.append(f"{rowcol_to_a1(1, largura + 1)}:{rowcol_to_a1(ws.row_count, ws.col_count)}")
    if ws.row_count > len(corpo):
        sobras.append(f"A{len(corpo) + 1}:{rowcol_to_a1(ws.row_count, largura)}")
    if sobras and not criar:
        _api("escrita", lambda: ws.batch_clear(sobras))
        time.sleep(PAUSA_ENTRE_LEITURAS)


def rodar_agendado():
    from lock_execucao import adquirir_lock, liberar_lock
    if not e_principal(carregar_config()):
        logger.warning("⛔ Este PC está como conferente (config.local.json) — a cópia só roda no PC principal.")
        return 0
    if not adquirir_lock(esperar=45):   # a vigia dos formulários segura a trava por segundos (23/10/2026)
        logger.info("⏸️ Cópia dos hotéis pulada: o robô está rodando agora. Tento de novo na próxima.")
        return 0
    try:
        inicio = time.time()
        relatorio, sem_hotel, _ = sincronizar(gravar=True)
        copiados = [r for r in relatorio if r.get("mudou")]
        pulados = len([r for r in relatorio if r.get("situacao", "").startswith("sem mudança no Drive")])
        logger.info(f"🔄 Cópia dos hotéis concluída em {time.time() - inicio:.0f}s: "
                    f"{len([r for r in relatorio if 'linhas' in r])} hotel(éis) lido(s), {pulados} sem mudança no Drive "
                    f"(não lidos), {len(copiados)} com novidade, "
                    f"{sum(r['pendentes'] for r in copiados)} pendente(s) neles.")
        if sem_hotel:
            logger.warning(f"⚠️ Planilhas na pasta sem hotel no cadastro (não copiadas): {', '.join(sem_hotel)}")
        salvar_json(PASTA_ESTADO / "planilhas_sem_cadastro.json", sorted(sem_hotel))   # o Painel mostra "Cadastro completo"
        return 0
    except Exception:
        logger.exception("❌ A cópia dos hotéis deu erro — nada foi perdido, tento de novo em 30 min.")
        return 1
    finally:
        liberar_lock()


CICLO = PASTA_ESTADO / "_ciclo_copia.txt"   # a rodada das 10 em 10 está rodando: a vigia dos formulários espera
CICLO_MAX_MINUTOS = 15                        # marca mais velha que isso = rodada que morreu no meio


def ciclo_rodando(agora=None):
    try:
        inicio = datetime.datetime.fromisoformat(CICLO.read_text(encoding="utf-8").strip())
    except (OSError, ValueError):
        return False
    return (agora or datetime.datetime.now()) - inicio < datetime.timedelta(minutes=CICLO_MAX_MINUTOS)


def copiar_e_enviar():
    """Ciclo do Agendador: copia e, em seguida, envia o que ficou pendente."""
    try:
        os.makedirs(PASTA_ESTADO, exist_ok=True)
        CICLO.write_text(datetime.datetime.now().isoformat(timespec="seconds"), encoding="utf-8")
    except OSError:
        logger.debug("marca da rodada", exc_info=True)
    try:
        return _copiar_e_enviar()
    finally:
        try:
            CICLO.unlink()
        except OSError:
            pass


def _copiar_e_enviar():
    codigo = rodar_agendado()
    try:
        import main as robo_envio
        from historico import ORIGEM_SOLICITACAO_NOVA
        logger.info("📨 Cópia feita — conferindo se tem solicitação pendente pra disparar...")
        codigo_envio = robo_envio.rodar(codigo_se_ocupado=0, origem=ORIGEM_SOLICITACAO_NOVA,
                                        quem="Robô (a cada 10 min)", esperar_lock=45)
    except Exception:
        logger.exception("❌ O envio automático deu erro — tento de novo na próxima volta.")
        codigo_envio = 1
    return codigo or codigo_envio


if __name__ == "__main__":
    import cota_google
    cota_google.configurar("sincronizar")
    if "--agendado" in sys.argv:
        sys.exit(copiar_e_enviar() if "--enviar" in sys.argv else rodar_agendado())
    gravar = "--gravar" in sys.argv
    inicio = time.time()
    relatorio, sem_hotel, sem_planilha = sincronizar(gravar, completa=True if "--completa" in sys.argv else None)
    print(("GRAVADO" if gravar else "PRÉVIA — nada foi gravado") + f" ({time.time() - inicio:.0f}s)\n")
    tot = {"linhas": 0, "pendentes": 0, "true_da_central": 0}
    for r in relatorio:
        if "linhas" not in r:
            print(f"  {r['hotel']:22} {r['situacao']}")
            continue
        for k in tot:
            tot[k] += r[k]
        extra = []
        if r["criar_aba"]:
            extra.append("CRIA ABA NOVA")
        if r["true_da_central"]:
            extra.append(f"{r['true_da_central']} TRUE mantido da Central")
        if r["so_na_central"]:
            extra.append(f"{r['so_na_central']} linha(s) só na Central (mantidas)")
        if r.get("planilhas", 1) > 1:
            extra.append(f"juntou {r['planilhas']} planilhas")
        if r["outras_planilhas"]:
            extra.append(f"sem dados: {', '.join(r['outras_planilhas'])}")
        print(f"  {r['hotel']:22} {r['linhas']:4} linhas (Central tinha {r['linhas_central_antes']:4}) | "
              f"{r['pendentes']:3} pendentes | origem: {r['origem'][:45]}" + (" | " + " · ".join(extra) if extra else ""))
    print(f"\nTOTAL: {tot['linhas']} linhas | {tot['pendentes']} pendentes | {tot['true_da_central']} TRUE mantidos da Central")
    print("Planilhas sem hotel no cadastro:", sem_hotel or "nenhuma")
    print("Hotéis do cadastro sem planilha:", sem_planilha or "nenhum")
