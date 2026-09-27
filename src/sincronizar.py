"""Cópia: traz as respostas das planilhas dos hotéis (Drive) pra Central.
Uso: python src\\sincronizar.py [--gravar | --agendado --enviar]
"""
import datetime
import json
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_utf8 import garantir_utf8

garantir_utf8()

from config import PASTA_ESTADO, carregar_config, caminho_chave_google, e_principal
from log_util import configurar_logging
from rede_util import com_retry, e_erro_passageiro_google
from sheets import VALORES_PENDENTE, _achar_coluna, _celula, nome_do_hotel_pela_aba, nome_intervalo
import robo_antigo
from tratamento import detectar_formato_data, ler_data, normalizar

logger = configurar_logging("sincronizar")

MIME_PLANILHA = "application/vnd.google-apps.spreadsheet"
PAUSA_ENTRE_LEITURAS = 1.1   # o Google deixa ~60 leituras por minuto pro robô


# --- Regras puras (testáveis sem Google) ---
def hotel_da_planilha(nome_arquivo, cfg, cadastro):
    """'Nota Fiscal (Lg Inn) (respostas)' -> 'L GINN' (nome no Cadastro_Hoteis) ou None."""
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
    """'9:35:54' e '09:35:54' viram a mesma coisa ('09:35:54'). '' se não tiver hora."""
    m = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", texto or "")
    return f"{int(m.group(1)):02d}:{m.group(2)}:{m.group(3) or '00'}" if m else ""


def _chave_linha(linha, i_carimbo, i_email, formato):
    """Identifica a resposta do Forms sem depender do formato de data (5/28 x 28/05)."""
    carimbo = _celula(linha, i_carimbo)
    data = ler_data(carimbo, formato)
    return (data.isoformat() if data else carimbo, _hora(carimbo), _celula(linha, i_email).lower())


def mesclar(origem, destino, cfg, chaves_ja_enviadas=frozenset()):
    """origem  = linhas da planilha do hotel (cabeçalho + dados)"""
    col = cfg["colunas"]
    cab = [str(c).strip() for c in origem[0]]
    if _achar_coluna(cab, col["enviado"]) is None:
        cab = cab + ["Enviado"]
    i_env = _achar_coluna(cab, col["enviado"])
    i_car = _achar_coluna(cab, col["carimbo"])
    i_email = _achar_coluna(cab, col.get("email_hospede", ""))
    fmt_o = detectar_formato_data((_celula(l, i_car) for l in origem[1:]), cfg.get("formato_data_planilha", "americano"))

    # Linhas que já estão na Central (com o TRUE que o robô marcou lá)
    linhas_d, exatas, soltas = [], {}, {}
    if destino and len(destino) > 1:
        cab_d = [str(c).strip() for c in destino[0]]
        d_env, d_car = _achar_coluna(cab_d, col["enviado"]), _achar_coluna(cab_d, col["carimbo"])
        d_email = _achar_coluna(cab_d, col.get("email_hospede", ""))
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
            if not true_lista:  # TRUE na planilha do hotel sem ter sido o nosso robô = robô antigo
                quando = robo_antigo.momento(_celula(l, i_car), fmt_o)
                if quando and (resumo["ultimo_antigo"] is None or quando > resumo["ultimo_antigo"]):
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
    # o que só existe na Central fica (no fim), nunca é apagado
    for idx, (l, _true) in enumerate(linhas_d):
        if idx not in usadas:
            novas.append(list(l))
            resumo["so_na_central"] += 1
    return novas, resumo


def _chave_tem_hora_diferente(linhas_d, idx, k, destino, col, fmt):
    """Casamento por data+e-mail só vale se a linha da Central NÃO tiver hora (ou tiver a mesma)."""
    cab_d = [str(c).strip() for c in destino[0]]
    d_car = _achar_coluna(cab_d, col["carimbo"])
    hora = _hora(_celula(linhas_d[idx][0], d_car))
    return bool(hora) and bool(k[1]) and hora != k[1]


def chaves_da_lista_ja_enviadas(caminho):
    """Transforma a lista de "já enviadas" do robô (estado/ja_enviadas.json) nas mesmas chaves de…"""
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


# --- Google (Drive + Planilhas) ---
def listar_pasta(caminho_chave, pasta_id):
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2.service_account import Credentials
    s = AuthorizedSession(Credentials.from_service_account_file(
        caminho_chave, scopes=["https://www.googleapis.com/auth/drive.readonly"]))
    arquivos, token = [], None
    while True:
        r = s.get("https://www.googleapis.com/drive/v3/files", timeout=30, params={
            "q": f"'{pasta_id}' in parents and trashed=false and mimeType='{MIME_PLANILHA}'",
            "pageSize": 1000, "pageToken": token, "fields": "nextPageToken, files(id,name,modifiedTime)"})
        r.raise_for_status()
        j = r.json()
        arquivos += j.get("files", [])
        token = j.get("nextPageToken")
        if not token:
            return arquivos


def _ler_planilha_hotel(cliente, arquivo, cfg):
    """Lê a aba de respostas da planilha do hotel"""
    preferida = cfg.get("fontes_hoteis", {}).get("aba_respostas", "Respostas ao formulário 1")
    try:
        r = com_retry(lambda: cliente.http_client.values_batch_get(
            arquivo["id"], [nome_intervalo(preferida)], params={"valueRenderOption": "FORMATTED_VALUE"}),
            e_erro_passageiro_google)
        return preferida, r["valueRanges"][0].get("values", [])
    except Exception as e:
        if "unable to parse range" not in str(e).lower() and "400" not in str(e):
            raise
    sh = com_retry(lambda: cliente.open_by_key(arquivo["id"]), e_erro_passageiro_google)
    abas = [w.title for w in com_retry(sh.worksheets, e_erro_passageiro_google)]
    preferida = cfg.get("fontes_hoteis", {}).get("aba_respostas", "Respostas ao formulário 1")
    aba = preferida if preferida in abas else ([a for a in abas if "respostas" in a.lower()] or abas[:1])[0]
    time.sleep(PAUSA_ENTRE_LEITURAS)
    r = com_retry(lambda: sh.values_batch_get([nome_intervalo(aba)], params={"valueRenderOption": "FORMATTED_VALUE"}),
                  e_erro_passageiro_google)
    return aba, r["valueRanges"][0].get("values", [])


def mapear_fontes(backend, cfg, chave):
    """Qual planilha da pasta é de qual hotel, e qual aba da Central recebe cada hotel"""
    fontes = cfg.get("fontes_hoteis", {})
    central = cfg["planilha_central_id"]
    cad_linhas = backend.ler_abas(central, [cfg["aba_cadastro_hoteis"]])[0][cfg["aba_cadastro_hoteis"]]
    cadastro = {normalizar(l[0]): l[0].strip() for l in cad_linhas if l and l[0].strip()}
    ignorar = {normalizar(n) for n in fontes.get("ignorar", [])}

    # 1. Quais planilhas existem e de qual hotel é cada uma
    arquivos = listar_pasta(chave, fontes["pasta_drive_id"])
    por_hotel, sem_hotel = {}, []
    for a in arquivos:
        if normalizar(a["name"]) in ignorar:
            continue
        h = hotel_da_planilha(a["name"], cfg, cadastro)
        (por_hotel.setdefault(h, []).append(a) if h else sem_hotel.append(a["name"]))

    # 2. Aba de destino de cada hotel na Central
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


def sincronizar(gravar=False):
    cfg = carregar_config()
    chave = caminho_chave_google(cfg)
    from sheets import BackendGoogle
    backend = BackendGoogle(chave, somente_leitura=not gravar)
    cliente, central = backend._cliente, cfg["planilha_central_id"]
    m = mapear_fontes(backend, cfg, chave)
    cadastro, por_hotel, sem_hotel = m["cadastro"], m["por_hotel"], m["sem_hotel"]
    abas_central, destino_do_hotel = m["abas_central"], m["destino_do_hotel"]

    # 3. O que o robô já enviou (válvula de escape)
    estado = PASTA_ESTADO / "sincronizacao.json"
    try:
        marcas = json.load(open(estado, encoding="utf-8"))
    except FileNotFoundError:
        marcas = {}
    chaves_enviadas = chaves_da_lista_ja_enviadas(PASTA_ESTADO / "ja_enviadas.json")

    relatorio, copia_de_seguranca = [], {}
    inicio_copia = datetime.datetime.now()
    if gravar:
        os.makedirs(PASTA_ESTADO, exist_ok=True)
        arquivo_backup = PASTA_ESTADO / f"backup_central_{inicio_copia:%Y%m%d_%H%M%S}.json"
    # Todas as abas de hotel da Central numa leitura só
    dados_central, _ = backend.ler_abas(central, [destino_do_hotel[h] for h in por_hotel if h in destino_do_hotel])
    for hotel, lista in sorted(por_hotel.items()):
        # [ACHADO REAL 26/09/2026] O Drive NÃO muda a "data de modificação" quando o Google Forms grava uma…
        lidas = []
        for a in sorted(lista, key=lambda x: x["modifiedTime"], reverse=True):
            time.sleep(PAUSA_ENTRE_LEITURAS)
            aba_origem, linhas = _ler_planilha_hotel(cliente, a, cfg)
            lidas.append((a, aba_origem, linhas))
        com_dados = [x for x in lidas if len(x[2]) > 1]
        if not com_dados:
            relatorio.append({"hotel": hotel, "situacao": "planilha do hotel vazia — nada copiado"})
            continue
        arquivo, aba_origem, origem = com_dados[0]
        aba_destino = destino_do_hotel.get(hotel) or f"Solicitação Nota Fiscal ({hotel}) (respostas)"
        destino = dados_central.get(aba_destino, []) if aba_destino in abas_central else []
        novas, resumo = mesclar(origem, destino, cfg, chaves_enviadas)
        resumo.update(hotel=hotel, origem=arquivo["name"], aba_destino=aba_destino,
                      linhas_central_antes=max(len(destino) - 1, 0), criar_aba=aba_destino not in abas_central,
                      outras_planilhas=[x[0]["name"] for x in lidas[1:]] if len(lidas) > 1 else [],
                      mudou=_como_texto(novas) != _como_texto(destino))
        relatorio.append(resumo)
        if gravar and resumo["mudou"]:
            if destino:
                copia_de_seguranca[aba_destino] = destino
            # cópia de segurança do que havia na aba ANTES (gravada antes de mexer)
            json.dump(copia_de_seguranca, open(arquivo_backup, "w", encoding="utf-8"), ensure_ascii=False)
            _gravar_aba(backend, cliente, central, aba_destino, novas, criar=aba_destino not in abas_central)
            logger.info(f"📥 {hotel}: {resumo['linhas']} linhas copiadas pra '{aba_destino}' "
                        f"({resumo['pendentes']} pendentes)")
            marcas[arquivo["id"]] = arquivo["modifiedTime"]
    if gravar:
        os.makedirs(PASTA_ESTADO, exist_ok=True)
        json.dump(marcas, open(estado, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        # a conferência usa isto pra saber o que chegou DEPOIS da última cópia
        open(PASTA_ESTADO / "ultima_copia.txt", "w", encoding="utf-8").write(inicio_copia.isoformat(timespec="seconds"))
        robo_antigo.registrar_atividade(PASTA_ESTADO / "robo_antigo.json",
                                        {r["hotel"]: r.get("ultimo_antigo") for r in relatorio if "linhas" in r})
        _limpar_backups_antigos()
    return relatorio, sem_hotel, [h for h in cadastro.values() if h not in por_hotel]


def _como_texto(linhas):
    """Tabela como a planilha devolve: TRUE/FALSE em texto e sem células vazias no fim da linha."""
    saida = []
    for l in linhas or []:
        l = ["TRUE" if v is True else "FALSE" if v is False else str(v) for v in l]
        while l and l[-1] == "":
            l.pop()
        saida.append(l)
    while saida and not saida[-1]:
        saida.pop()
    return saida


def _limpar_backups_antigos(manter=48):
    """Guarda só as últimas `manter` cópias de segurança (a cópia roda a cada 30 min)."""
    backups = sorted(PASTA_ESTADO.glob("backup_central_*.json"))
    for velho in backups[:-manter]:
        try:
            velho.unlink()
        except OSError:
            pass


def _gravar_aba(backend, cliente, central, aba, linhas, criar):
    """Escreve POR CIMA primeiro e só depois limpa o que sobrou (linhas/colunas a mais da versão antiga)"""
    from gspread.utils import rowcol_to_a1
    planilha = backend._planilha(central)
    largura = max(len(l) for l in linhas)
    corpo = [l + [""] * (largura - len(l)) for l in linhas]
    if criar:
        ws = com_retry(lambda: planilha.add_worksheet(title=aba, rows=len(corpo) + 50, cols=largura),
                       e_erro_passageiro_google)
    else:
        ws = com_retry(lambda: planilha.worksheet(aba), e_erro_passageiro_google)
        if ws.row_count < len(corpo) or ws.col_count < largura:
            com_retry(lambda: ws.resize(rows=max(ws.row_count, len(corpo) + 50), cols=max(ws.col_count, largura)),
                      e_erro_passageiro_google)
    time.sleep(PAUSA_ENTRE_LEITURAS)
    com_retry(lambda: ws.update(range_name="A1", values=corpo, value_input_option="RAW"), e_erro_passageiro_google)
    time.sleep(PAUSA_ENTRE_LEITURAS)
    sobras = []
    if ws.col_count > largura:     # colunas a mais da versão antiga
        sobras.append(f"{rowcol_to_a1(1, largura + 1)}:{rowcol_to_a1(ws.row_count, ws.col_count)}")
    if ws.row_count > len(corpo):  # linhas a mais da versão antiga
        sobras.append(f"A{len(corpo) + 1}:{rowcol_to_a1(ws.row_count, largura)}")
    if sobras and not criar:
        com_retry(lambda: ws.batch_clear(sobras), e_erro_passageiro_google)
        time.sleep(PAUSA_ENTRE_LEITURAS)


def rodar_agendado():
    """Chamado a cada 30 min pelo Agendador de Tarefas"""
    from lock_execucao import adquirir_lock, liberar_lock
    if not e_principal(carregar_config()):
        logger.warning("⛔ Este PC está como conferente (config.local.json) — a cópia só roda no PC principal.")
        return 0
    if not adquirir_lock():
        logger.info("⏸️ Cópia dos hotéis pulada: o robô está rodando agora. Tento de novo na próxima.")
        return 0
    try:
        inicio = time.time()
        relatorio, sem_hotel, _ = sincronizar(gravar=True)
        copiados = [r for r in relatorio if r.get("mudou")]
        logger.info(f"🔄 Cópia dos hotéis concluída em {time.time() - inicio:.0f}s: "
                    f"{len([r for r in relatorio if 'linhas' in r])} hotel(éis) lido(s), {len(copiados)} com novidade, "
                    f"{sum(r['pendentes'] for r in copiados)} pendente(s) neles.")
        if sem_hotel:
            logger.warning(f"⚠️ Planilhas na pasta sem hotel no cadastro (não copiadas): {', '.join(sem_hotel)}")
        return 0
    except Exception:
        logger.exception("❌ A cópia dos hotéis deu erro — nada foi perdido, tento de novo em 30 min.")
        return 1
    finally:
        liberar_lock()


def copiar_e_enviar():
    """O ciclo automático (a cada 30 min): 1) copia as respostas novas dos hotéis pra Central; 2) roda o…"""
    codigo = rodar_agendado()
    try:
        import main as robo_envio
        from historico import ORIGEM_SOLICITACAO_NOVA
        logger.info("📨 Cópia feita — conferindo se tem solicitação pendente pra disparar...")
        codigo_envio = robo_envio.rodar(codigo_se_ocupado=0, origem=ORIGEM_SOLICITACAO_NOVA,
                                        quem="Robô (a cada 30 min)")
    except Exception:
        logger.exception("❌ O envio automático deu erro — tento de novo na próxima volta.")
        codigo_envio = 1
    return codigo or codigo_envio


if __name__ == "__main__":
    if "--agendado" in sys.argv:
        sys.exit(copiar_e_enviar() if "--enviar" in sys.argv else rodar_agendado())
    gravar = "--gravar" in sys.argv
    inicio = time.time()
    relatorio, sem_hotel, sem_planilha = sincronizar(gravar)
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
        if r["outras_planilhas"]:
            extra.append(f"ignorada: {', '.join(r['outras_planilhas'])}")
        print(f"  {r['hotel']:22} {r['linhas']:4} linhas (Central tinha {r['linhas_central_antes']:4}) | "
              f"{r['pendentes']:3} pendentes | origem: {r['origem'][:45]}" + (" | " + " · ".join(extra) if extra else ""))
    print(f"\nTOTAL: {tot['linhas']} linhas | {tot['pendentes']} pendentes | {tot['true_da_central']} TRUE mantidos da Central")
    print("Planilhas sem hotel no cadastro:", sem_hotel or "nenhuma")
    print("Hotéis do cadastro sem planilha:", sem_planilha or "nenhum")
