"""Google Sheets: Planilha Central (abas de hotel, Status, Log)."""
import datetime
import hashlib
import re
import socket

from gspread.utils import rowcol_to_a1

from log_util import configurar_logging
from modelos import Hotel, Solicitacao
from rede_util import com_retry, e_erro_passageiro_google
from tratamento import campos_para_email, detectar_formato_data, ler_data, normalizar

logger = configurar_logging(__name__)

ESCOPOS = ["https://www.googleapis.com/auth/spreadsheets"]
# Modo SIMULACAO: o Google só deixa LER. Qualquer tentativa de gravar é recusada.
ESCOPOS_SO_LEITURA = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
TIMEOUT_GOOGLE_SEGUNDOS = 30

SEPARADOR = chr(31)  # caractere que nunca aparece em resposta de formulário
VALORES_PENDENTE = {"", "false", "falso"}
VALORES_DESLIGADO = {"false", "falso", "nao", "n", "0", "inativo"}

# Layout da aba Status (coluna A = rótulo, coluna B = valor)
STATUS_ROTULO_A1 = "Robô ligado?"
STATUS_LINHAS = [
    [STATUS_ROTULO_A1, False],
    ["Última execução com sucesso", ""],
    ["Resumo da última execução", ""],
    ["Última tentativa", ""],
    ["Modo", ""],
    ["Máquina", ""],
    # Conversa com o menu da planilha (apps_script/menu_planilha_central.gs):
    ["Comando", ""],                          # B7: "ENVIAR" (menu ⚡ Ativar Claudio) / "EM ANDAMENTO"
    ["Pedido por", ""],                       # B8: "email | 2026-09-24T14:05:00.000Z"
    ["Resposta do robô", ""],                 # B9
    ["Última verificação de pendências", ""], # B10 (escrito pelo menu 📋 Verificar Pendências)
    ["Configuração do robô", ""],             # B11: JSON com agentes/modo (o menu mostra pra onde vai)
    ["Robô online (último sinal)", ""],       # B12
    ["Seleção do envio separado", ""],        # B13: "aba | 131, 132 | reenviar" (menu Envio Separado)
    ["Cota de envio", ""],                    # B14: JSON da cota do servidor (menu 📊 Cota de Envio)
    ["Andamento do envio (ao vivo)", ""],     # B15: o que o robô está fazendo agora (tela do Claudio mostra)
    ["Conferência da cópia (ao vivo)", ""],   # B16: log da conferência hotel por hotel (menu 🔍 Conferir Cópia)
]
LINHA_COMANDO, LINHA_PEDIDO, LINHA_RESPOSTA, LINHA_CONFIG, LINHA_ONLINE, LINHA_SELECAO = 7, 8, 9, 11, 12, 13
LINHA_COTA, LINHA_ANDAMENTO, LINHA_CONFERENCIA = 14, 15, 16


class ErroPlanilha(Exception):
    """Problema que impede o robô de seguir (aba Hoteis faltando, aba Status de outra pessoa...)."""


def nome_intervalo(aba):
    """Nome de aba pronto pra API: 'Hotel D'Ávila' -> 'Hotel D''Ávila' entre aspas simples."""
    return "'" + str(aba).replace("'", "''") + "'"


# --- Camada da API ---
class BackendGoogle:
    def __init__(self, caminho_chave, somente_leitura=False):
        import gspread
        from google.oauth2.service_account import Credentials

        escopos = ESCOPOS_SO_LEITURA if somente_leitura else ESCOPOS
        credenciais = Credentials.from_service_account_file(caminho_chave, scopes=escopos)
        self._cliente = gspread.authorize(credenciais)
        # Sem isso, uma conexão travada ficaria pendurada pra sempre.
        self._cliente.set_timeout(TIMEOUT_GOOGLE_SEGUNDOS)
        self._planilhas = {}

    def _planilha(self, planilha_id):
        if planilha_id not in self._planilhas:
            self._planilhas[planilha_id] = com_retry(
                lambda: self._cliente.open_by_key(planilha_id), e_erro_passageiro_google)
        return self._planilhas[planilha_id]

    def ler_abas(self, planilha_id, nomes):
        """Lê várias abas de uma vez"""
        nomes = list(dict.fromkeys(nomes))
        if not nomes:
            return {}, {}
        planilha = self._planilha(planilha_id)
        parametros = {"valueRenderOption": "FORMATTED_VALUE"}
        try:
            resposta = com_retry(
                lambda: planilha.values_batch_get([nome_intervalo(n) for n in nomes], params=parametros),
                e_erro_passageiro_google)
            faixas = resposta.get("valueRanges", [])
            return {nome: faixas[i].get("values", []) for i, nome in enumerate(nomes)}, {}
        except Exception as erro_lote:
            if len(nomes) == 1:
                return {}, {nomes[0]: str(erro_lote)}
            logger.warning(f"⚠️ Leitura em lote falhou ({erro_lote}) — lendo aba por aba pra achar a com problema.")

        dados, erros = {}, {}
        for nome in nomes:
            try:
                resposta = com_retry(
                    lambda: planilha.values_batch_get([nome_intervalo(nome)], params=parametros),
                    e_erro_passageiro_google)
                dados[nome] = resposta.get("valueRanges", [{}])[0].get("values", [])
            except Exception as e:
                erros[nome] = str(e)
        return dados, erros

    def listar_abas(self, planilha_id):
        return [aba.title for aba in com_retry(lambda: self._planilha(planilha_id).worksheets(), e_erro_passageiro_google)]

    def escrever(self, planilha_id, atualizacoes):
        """atualizacoes = [("'Aba'!K5", valor), ...] — tudo numa chamada só."""
        if not atualizacoes:
            return
        planilha = self._planilha(planilha_id)
        corpo = {
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": faixa, "values": [[valor]]} for faixa, valor in atualizacoes],
        }
        com_retry(lambda: planilha.values_batch_update(corpo), e_erro_passageiro_google)

    def criar_aba_status(self, planilha_id, nome, linhas):
        planilha = self._planilha(planilha_id)
        aba = com_retry(lambda: planilha.add_worksheet(title=nome, rows=20, cols=4), e_erro_passageiro_google)
        com_retry(lambda: aba.update(range_name="A1", values=linhas, value_input_option="USER_ENTERED"),
                  e_erro_passageiro_google)
        # Caixa de seleção na célula B1 ("Robô ligado?")
        pedido = {"requests": [{"setDataValidation": {
            "range": {"sheetId": aba.id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 1, "endColumnIndex": 2},
            "rule": {"condition": {"type": "BOOLEAN"}},
        }}]}
        com_retry(lambda: planilha.batch_update(pedido), e_erro_passageiro_google)

    def criar_aba_log(self, planilha_id, nome, cabecalho):
        """Aba 'Log de Envios': cabeçalho verde #173f39 com texto creme #d5bda1, congelado, colunas largas."""
        planilha = self._planilha(planilha_id)
        aba = com_retry(lambda: planilha.add_worksheet(title=nome, rows=1000, cols=len(cabecalho)),
                        e_erro_passageiro_google)
        com_retry(lambda: aba.update(range_name="A1", values=[cabecalho], value_input_option="RAW"),
                  e_erro_passageiro_google)
        verde = {"red": 23 / 255, "green": 63 / 255, "blue": 57 / 255}
        creme = {"red": 213 / 255, "green": 189 / 255, "blue": 161 / 255}
        larguras = [140, 190, 190, 110, 110, 420, 250, 90, 150, 90, 120, 320, 120, 170]
        pedidos = [
            {"repeatCell": {"range": {"sheetId": aba.id, "startRowIndex": 0, "endRowIndex": 1},
                            "cell": {"userEnteredFormat": {"backgroundColor": verde, "textFormat": {
                                "foregroundColor": creme, "bold": True}, "wrapStrategy": "WRAP",
                                "verticalAlignment": "MIDDLE"}},
                            "fields": "userEnteredFormat(backgroundColor,textFormat,wrapStrategy,verticalAlignment)"}},
            {"repeatCell": {"range": {"sheetId": aba.id, "startRowIndex": 1},
                            "cell": {"userEnteredFormat": {"wrapStrategy": "WRAP", "verticalAlignment": "TOP"}},
                            "fields": "userEnteredFormat(wrapStrategy,verticalAlignment)"}},
            {"updateSheetProperties": {"properties": {"sheetId": aba.id, "gridProperties": {"frozenRowCount": 1},
                                                      "tabColorStyle": {"rgbColor": verde}},
                                       "fields": "gridProperties.frozenRowCount,tabColorStyle"}},
        ] + [{"updateDimensionProperties": {"range": {"sheetId": aba.id, "dimension": "COLUMNS",
                                                      "startIndex": i, "endIndex": i + 1},
                                            "properties": {"pixelSize": px}, "fields": "pixelSize"}}
             for i, px in enumerate(larguras[:len(cabecalho)])]
        com_retry(lambda: planilha.batch_update({"requests": pedidos}), e_erro_passageiro_google)

    def inserir_no_topo(self, planilha_id, aba, linhas):
        """Insere as linhas logo abaixo do cabeçalho (o mais recente fica em cima)."""
        planilha = self._planilha(planilha_id)
        planilha_aba = com_retry(lambda: planilha.worksheet(aba), e_erro_passageiro_google)
        com_retry(lambda: planilha.batch_update({"requests": [{"insertDimension": {
            "range": {"sheetId": planilha_aba.id, "dimension": "ROWS", "startIndex": 1, "endIndex": 1 + len(linhas)},
            "inheritFromBefore": False}}]}), e_erro_passageiro_google)
        com_retry(lambda: planilha.values_update(f"{nome_intervalo(aba)}!A2", params={"valueInputOption": "RAW"},
                                                 body={"values": linhas}), e_erro_passageiro_google)

    def anexar_linhas(self, planilha_id, aba, linhas):
        planilha = self._planilha(planilha_id)
        planilha_aba = com_retry(lambda: planilha.worksheet(aba), e_erro_passageiro_google)
        com_retry(lambda: planilha_aba.append_rows(linhas, value_input_option="RAW"), e_erro_passageiro_google)


# --- Regras de negócio ---
def _achar_coluna(cabecalhos, nomes_aceitos):
    """Posição da 1ª coluna cujo nome bate com algum dos aceitos (texto ou lista, na ordem de preferência)."""
    if isinstance(nomes_aceitos, str):
        nomes_aceitos = [nomes_aceitos]
    alvos = [normalizar(n) for n in nomes_aceitos if str(n).strip()]
    normalizados = [normalizar(c) for c in cabecalhos]
    for alvo in alvos:
        if alvo in normalizados:
            return normalizados.index(alvo)
    return None


def _celula(linha, indice):
    if indice is None or indice >= len(linha):
        return ""
    return str(linha[indice]).strip()


def _indice_coluna(letra):
    """'A' -> 0, 'C' -> 2."""
    return ord(str(letra).strip().upper()) - ord("A")


def ler_hoteis(backend, cfg):
    """Descobre quais abas de respostas existem e pra quem vai cada uma"""
    central = cfg["planilha_central_id"]
    aba_cadastro = cfg["aba_cadastro_hoteis"]
    dados, erros_leitura = backend.ler_abas(central, [aba_cadastro])
    if aba_cadastro in erros_leitura:
        raise ErroPlanilha(f"Não consegui ler a aba '{aba_cadastro}': {erros_leitura[aba_cadastro]}")
    linhas = dados.get(aba_cadastro, [])
    if not linhas:
        raise ErroPlanilha(f"A aba '{aba_cadastro}' está vazia.")

    colunas = cfg["cadastro_colunas"]
    i_hotel, i_agente = _indice_coluna(colunas["hotel"]), _indice_coluna(colunas["agente"])
    i_email_hotel = _indice_coluna(colunas.get("email_hotel", "B"))
    cadastro = {}
    for linha in linhas:
        nome, agente = _celula(linha, i_hotel), _celula(linha, i_agente)
        if not nome or normalizar(agente) in ("agente", "operador", "responsavel"):
            continue  # linha vazia ou cabeçalho
        cadastro.setdefault(normalizar(nome), (nome, agente, _celula(linha, i_email_hotel).lower()))

    agentes = {normalizar(k): str(v).strip().lower() for k, v in cfg.get("agentes", {}).items()
               if not str(k).startswith("_")}
    apelidos = {normalizar(k): v for k, v in cfg.get("apelidos_hoteis", {}).items() if not str(k).startswith("_")}
    ignoradas = {normalizar(a) for a in cfg.get("abas_ignoradas", [])}
    marcador = normalizar(cfg.get("marcador_aba_respostas", "(respostas)"))
    # Em SIMULACAO/TESTE nada vai pro agente de verdade, então agente sem e-mail não impede o teste —…
    sem_envio_real = cfg["modo"] in ("SIMULACAO", "TESTE")
    # `somente_hoteis` (teste): os outros hotéis nem entram — nem como erro.
    somente = {normalizar(h) for h in cfg.get("somente_hoteis", []) if str(h).strip()}

    hoteis, erros = [], []
    for titulo in backend.listar_abas(central):
        if marcador not in normalizar(titulo) or normalizar(titulo) in ignoradas:
            continue
        nome_na_aba = nome_do_hotel_pela_aba(titulo)
        chave = normalizar(apelidos.get(normalizar(nome_na_aba), nome_na_aba))
        if chave not in cadastro:
            erros.append(f"{titulo}: o hotel '{nome_na_aba}' não está no {aba_cadastro} "
                         f"(ou precisa de um apelido em 'apelidos_hoteis' no config.json)")
            continue
        nome, agente, email_hotel = cadastro[chave]
        if somente and normalizar(nome) not in somente:
            continue
        if cfg.get("destino_envio", "agente") == "hotel":
            # Cada hotel recebe as solicitações dele no próprio e-mail (coluna B do Cadastro_Hoteis)
            email = email_hotel
            if "@" not in email:
                erros.append(f"{titulo}: o hotel '{nome}' não tem e-mail na coluna B do {aba_cadastro}")
                continue
        else:
            email = agentes.get(normalizar(agente), "")
            if "@" not in email:
                if not sem_envio_real:
                    erros.append(f"{titulo}: o agente '{agente}' não tem e-mail em 'agentes' no config.json")
                    continue
                email = f"{agente} (e-mail ainda não configurado)"
        hoteis.append(Hotel(aba=titulo, nome=nome, operador=email, planilha_id=central, email_hotel=email_hotel,
                            agente=agente))

    for erro in erros:
        logger.error(f"❌ Aba pulada — {erro}")
    return hoteis, erros


def assinatura_da_linha(linha, i_enviado):
    """Resumo curto de TODAS as células da linha, menos a coluna Enviado (que muda)."""
    valores = [str(v).strip() for i, v in enumerate(linha) if i != i_enviado]
    while valores and not valores[-1]:
        valores.pop()
    return hashlib.sha1(SEPARADOR.join(valores).encode("utf-8")).hexdigest()[:16]


def nome_do_hotel_pela_aba(nome_aba):
    """'Solicitação Nota Fiscal (MERCADO) (respostas)' -> 'MERCADO'."""
    partes = [p for p in re.findall(r"\(([^)]*)\)", nome_aba) if normalizar(p) != "respostas"]
    return partes[0].strip() if partes else nome_aba


def _nome_titulo(cabecalhos, linha, cfg):
    """Nome que aparece no título de cada solicitação"""
    colunas = cfg["colunas"]
    i_tomador = _achar_coluna(cabecalhos, colunas.get("reserva_no_tomador", ""))
    i_pf = _achar_coluna(cabecalhos, colunas.get("nome_pessoa_fisica", ""))
    i_hospede = _achar_coluna(cabecalhos, colunas.get("nome_hospede", ""))
    if normalizar(_celula(linha, i_tomador)) == "sim" and _celula(linha, i_pf):
        return _celula(linha, i_pf)
    return " ".join(_celula(linha, i_hospede).split()) or "Hóspede"


def _dados_para_conferencia(cabecalhos, linha, cfg):
    """E-mails de contato, nomes e em quantas partes a NF é dividida."""
    colunas = cfg["colunas"]
    emails, nomes = [], []
    for i, cab in enumerate(cabecalhos):
        c, valor = normalizar(cab), _celula(linha, i)
        if not valor:
            continue
        if ("e-mail" in c or "email" in c) and "@" in valor:
            for e in re.split(r"[;,\s]+", valor.lower()):
                if "@" in e and e not in emails:
                    emails.append(e)
        elif re.search(r"\bnome\b|razao social", c) and valor not in nomes:
            nomes.append(valor)
    partes = 1
    i_div = _achar_coluna(cabecalhos, colunas.get("nota_dividida", "Nota Dividida"))
    if normalizar(_celula(linha, i_div)) == "sim":
        i_qtd = _achar_coluna(cabecalhos, colunas.get("dividida_quantas", "Dividida em quantas vezes"))
        digitos = re.sub(r"\D", "", _celula(linha, i_qtd))
        partes = max(2, int(digitos)) if digitos else 2   # "Sim" sem número: pelo menos 2
    return emails, nomes, partes


def interpretar_aba(hotel, linhas, cfg, incluir_linhas=None):
    """Transforma as linhas de uma aba em solicitações PENDENTES"""
    if not linhas:
        return [], None
    cabecalhos = [str(c).strip() for c in linhas[0]]
    colunas = cfg["colunas"]
    i_enviado = _achar_coluna(cabecalhos, colunas["enviado"])
    i_carimbo = _achar_coluna(cabecalhos, colunas["carimbo"])
    i_email = _achar_coluna(cabecalhos, colunas.get("email_hospede", ""))
    if i_enviado is None:
        return [], f"sem a coluna '{colunas['enviado']}'"
    if i_carimbo is None:
        return [], f"sem a coluna '{colunas['carimbo']}'"

    # Cada aba pode vir num formato de data (Forms = americano; dado colado à mão costuma vir brasileiro)
    formato = detectar_formato_data((_celula(l, i_carimbo) for l in linhas[1:]),
                                    cfg.get("formato_data_planilha", "americano"))
    documentos = cfg.get("colunas_documento", {})
    # a coluna de e-mail usada em "Enviado por" não se repete dentro da tabela
    esconder = {i_email} if i_email is not None else set()
    pendentes = []
    for numero, linha in enumerate(linhas[1:], start=2):
        linha = list(linha) + [""] * (len(cabecalhos) - len(linha))
        if not any(str(v).strip() for v in linha):
            continue
        if incluir_linhas is not None:
            if numero not in incluir_linhas:
                continue
        elif normalizar(_celula(linha, i_enviado)) not in VALORES_PENDENTE:
            continue
        carimbo = _celula(linha, i_carimbo)
        if not carimbo:
            logger.warning(f"⚠️ {hotel.aba} linha {numero}: sem carimbo de data/hora — pulada (não dá pra identificar).")
            continue
        pendentes.append(Solicitacao(
            hotel=hotel,
            linha=numero,
            carimbo=carimbo,
            email_hospede=_celula(linha, i_email),
            nome_titulo=_nome_titulo(cabecalhos, linha, cfg),
            campos=campos_para_email(cabecalhos, linha, cfg["colunas_ocultas"], formato, documentos, esconder),
            linha_bruta=linha,
            assinatura=assinatura_da_linha(linha, i_enviado),
            formato_data=formato,
        ))
        s = pendentes[-1]
        s.emails_contato, s.nomes, s.partes_esperadas = _dados_para_conferencia(cabecalhos, linha, cfg)
        data = ler_data(carimbo, formato)
        s.data_pedido = data.isoformat() if data else ""
    return pendentes, None


def ler_pendentes(backend, cfg, hoteis):
    """Lê todas as abas dos hotéis (uma chamada por planilha) e devolve (solicitacoes_pendentes, erros)"""
    por_planilha = {}
    for hotel in hoteis:
        por_planilha.setdefault(hotel.planilha_id, []).append(hotel)

    solicitacoes, erros = [], []
    for planilha_id, lista in por_planilha.items():
        try:
            dados, erros_leitura = backend.ler_abas(planilha_id, [h.aba for h in lista])
        except Exception as e:
            for h in lista:
                erros.append(f"{h.aba}: não consegui abrir a planilha {planilha_id} ({e})")
            continue
        for hotel in lista:
            if hotel.aba in erros_leitura:
                erros.append(f"{hotel.aba}: {erros_leitura[hotel.aba]}")
                continue
            pendentes, erro = interpretar_aba(hotel, dados.get(hotel.aba, []), cfg)
            if erro:
                erros.append(f"{hotel.aba}: {erro}")
                continue
            solicitacoes.extend(pendentes)

    for erro in erros:
        logger.error(f"❌ Aba pulada — {erro}")
    return solicitacoes, erros


def marcar_enviados(backend, cfg, solicitacoes):
    """Marca Enviado = TRUE nas solicitações já confirmadas como enviadas"""
    colunas = cfg["colunas"]
    por_planilha = {}
    for s in solicitacoes:
        por_planilha.setdefault(s.hotel.planilha_id, {}).setdefault(s.hotel.aba, []).append(s)

    total_marcadas, nao_encontradas = 0, []
    for planilha_id, por_aba in por_planilha.items():
        dados, erros = backend.ler_abas(planilha_id, list(por_aba))
        atualizacoes = []
        for aba, lista in por_aba.items():
            linhas = dados.get(aba)
            if aba in erros or not linhas:
                nao_encontradas.extend(lista)
                logger.error(f"❌ Não consegui reler '{aba}' pra marcar TRUE ({erros.get(aba, 'aba vazia')}).")
                continue
            cabecalhos = [str(c).strip() for c in linhas[0]]
            i_enviado = _achar_coluna(cabecalhos, colunas["enviado"])
            i_carimbo = _achar_coluna(cabecalhos, colunas["carimbo"])
            i_email = _achar_coluna(cabecalhos, colunas.get("email_hospede", ""))
            if i_enviado is None or i_carimbo is None:
                nao_encontradas.extend(lista)
                continue
            linhas_por_chave = {}
            for numero, linha in enumerate(linhas[1:], start=2):
                chave = (_celula(linha, i_carimbo), _celula(linha, i_email), assinatura_da_linha(linha, i_enviado))
                linhas_por_chave.setdefault(chave, []).append(numero)
            for s in lista:
                numeros = linhas_por_chave.get((s.carimbo, s.email_hospede, s.assinatura))
                if not numeros:
                    nao_encontradas.append(s)
                    continue
                for numero in numeros:
                    atualizacoes.append((f"{nome_intervalo(aba)}!{rowcol_to_a1(numero, i_enviado + 1)}", True))
                total_marcadas += 1
        backend.escrever(planilha_id, atualizacoes)

    for s in nao_encontradas:
        logger.warning(f"⚠️ Não achei a linha pra marcar TRUE: {s.hotel.aba} / carimbo {s.carimbo} "
                       f"(e-mail JÁ FOI enviado — confira na planilha).")
    return total_marcadas, nao_encontradas


def robo_ligado(backend, cfg):
    """Lê a caixa "Robô ligado?" (célula B1 da aba Status)"""
    central, aba = cfg["planilha_central_id"], cfg["aba_status"]
    dados, erros = backend.ler_abas(central, [aba])
    if aba in erros:
        logger.warning(f"⚠️ Aba '{aba}' não existe — criando, com o robô DESLIGADO. "
                       f"Marque a caixa '{STATUS_ROTULO_A1}' na aba '{aba}' pra ligar.")
        backend.criar_aba_status(central, aba, STATUS_LINHAS)
        return False
    linhas = dados.get(aba, [])
    if not linhas or _celula(linhas[0], 0) != STATUS_ROTULO_A1:
        raise ErroPlanilha(f"A aba '{aba}' já existe mas não é a do robô (A1 deveria ser '{STATUS_ROTULO_A1}'). "
                           f"Não vou mexer nela. Troque 'aba_status' no config.json por outro nome.")
    return normalizar(_celula(linhas[0], 1)) in ("true", "verdadeiro")


def gravar_status(backend, cfg, sucesso, resumo, agora=None):
    """"Batimento cardíaco": data/hora da última execução com sucesso + resumo."""
    # O apóstrofo força TEXTO: a planilha está em formato americano e leria "05/10/2026" como 10 de maio
    agora = "'" + (agora or datetime.datetime.now()).strftime("%d/%m/%Y %H:%M:%S")
    aba = nome_intervalo(cfg["aba_status"])
    atualizacoes = [
        (f"{aba}!B3", resumo),
        (f"{aba}!B4", agora),
        (f"{aba}!B5", cfg["modo"]),
        (f"{aba}!B6", socket.gethostname()),
    ]
    if sucesso:
        atualizacoes.append((f"{aba}!B2", agora))
    try:
        backend.escrever(cfg["planilha_central_id"], atualizacoes)
    except Exception as e:
        logger.error(f"❌ Não consegui gravar o status na aba '{cfg['aba_status']}': {e}")


def registrar_central(backend, cfg, solicitacoes):
    """Copia as solicitações enviadas pra aba Registros (o Apps Script antigo fazia isso)."""
    reg = cfg.get("registro_central", {})
    if not reg.get("ativo") or not solicitacoes:
        return
    linhas = [[str(v) for v in s.linha_bruta] for s in solicitacoes]
    try:
        backend.anexar_linhas(reg["planilha_id"], reg["aba"], linhas)
        logger.info(f"📒 {len(linhas)} solicitação(ões) copiada(s) pra aba '{reg['aba']}' (registro central).")
    except Exception as e:
        motivo = f"{type(e).__name__}: {e}".rstrip(": ")
        if isinstance(e, PermissionError) or "403" in str(e):
            motivo += " — a planilha de Registros não está compartilhada com a conta do robô"
        logger.warning(f"⚠️ Não consegui copiar pra aba '{reg['aba']}' do registro central ({motivo}). "
                       f"Os e-mails e o TRUE estão certos — só o registro ficou sem essas linhas.")


# --- Conversa com o menu da planilha (⚡ Ativar Claudio) ---
def garantir_rotulos_status(backend, cfg):
    """Escreve os rótulos novos (A7:A12) numa aba Status criada antes deles existirem."""
    central, aba = cfg["planilha_central_id"], cfg["aba_status"]
    dados, erros = backend.ler_abas(central, [aba])
    linhas = dados.get(aba, [])
    if aba in erros or not linhas or _celula(linhas[0], 0) != STATUS_ROTULO_A1:
        return
    faltando = [(f"{nome_intervalo(aba)}!A{i}", rotulo) for i, (rotulo, _) in enumerate(STATUS_LINHAS, start=1)
                if i > len(linhas) or _celula(linhas[i - 1], 0) != rotulo]
    if faltando:
        backend.escrever(central, faltando)


def ler_comando(backend, cfg):
    """(comando, quem, quando) da aba Status. `quando` é datetime com fuso, ou None."""
    central, aba = cfg["planilha_central_id"], cfg["aba_status"]
    dados, erros = backend.ler_abas(central, [aba])
    linhas = dados.get(aba, [])
    if aba in erros or len(linhas) < LINHA_COMANDO:
        return "", "", None
    comando = _celula(linhas[LINHA_COMANDO - 1], 1).upper().replace(" ", "_")
    pedido = _celula(linhas[LINHA_PEDIDO - 1], 1) if len(linhas) >= LINHA_PEDIDO else ""
    quem, _, quando_txt = pedido.partition(" | ")
    try:
        quando = datetime.datetime.fromisoformat(quando_txt.strip().replace("Z", "+00:00"))
    except ValueError:
        quando = None
    return comando, quem.strip(), quando


def escrever_linhas_status(backend, cfg, valores):
    """valores = {linha: texto} na coluna B da aba Status (sempre como texto)."""
    aba = nome_intervalo(cfg["aba_status"])
    backend.escrever(cfg["planilha_central_id"],
                     [(f"{aba}!B{linha}", ("'" + str(v)) if str(v) else "") for linha, v in valores.items()])


def config_publica(cfg):
    """O que o menu da planilha precisa saber do robô (sem chave, sem caminho de arquivo)."""
    import json
    limpo = lambda d: {k: v for k, v in d.items() if not str(k).startswith("_")}
    return json.dumps({
        "modo": cfg["modo"],
        "agentes": limpo(cfg.get("agentes", {})),
        "somente_hoteis": cfg.get("somente_hoteis", []),
        "abas_ignoradas": cfg.get("abas_ignoradas", []),
        "apelidos_hoteis": limpo(cfg.get("apelidos_hoteis", {})),
        "email_teste": cfg.get("email_teste", ""),
        "destino_envio": cfg.get("destino_envio", "agente"),
    }, ensure_ascii=False)
