"""Planilha Central: abas de respostas dos hotéis, aba Status (painel/menu) e Log."""
import datetime
import hashlib
import re
import socket

from gspread.utils import rowcol_to_a1

from log_util import configurar_logging
from modelos import Hotel, Solicitacao
from cota_google import COTA, e_cota_estourada
from rede_util import com_retry, e_erro_passageiro_google
from tratamento import campos_para_email, detectar_formato_data, ler_data, normalizar

logger = configurar_logging(__name__)

ESCOPOS = ["https://www.googleapis.com/auth/spreadsheets"]
ESCOPOS_SO_LEITURA = ["https://www.googleapis.com/auth/spreadsheets.readonly"]   # SIMULACAO
TIMEOUT_GOOGLE_SEGUNDOS = 30

SEPARADOR = chr(31)   # nunca aparece numa resposta de formulário
VALORES_PENDENTE = {"", "false", "falso"}
VALORES_DESLIGADO = {"false", "falso", "nao", "n", "0", "inativo"}

# Aba Status: A = rótulo, B = valor. As linhas 7+ são o protocolo com apps_script/menu_planilha_central.gs.
STATUS_ROTULO_A1 = "Robô ligado?"
STATUS_LINHAS = [
    [STATUS_ROTULO_A1, False],
    ["Última execução com sucesso", ""],
    ["Resumo da última execução", ""],
    ["Última tentativa", ""],
    ["Modo", ""],
    ["Máquina", ""],
    ["Comando", ""],                          # 7: ENVIAR | ENVIAR_SEPARADO | CONFERIR_COPIA
    ["Pedido por", ""],                       # 8: "email | ISO-8601"
    ["Resposta do robô", ""],
    ["Última verificação de pendências", ""],
    ["Configuração do robô", ""],             # 11: JSON de config_publica()
    ["Robô online (último sinal)", ""],
    ["Seleção do envio separado", ""],        # 13: "aba | 131, 132 | reenviar"
    ["Cota de envio", ""],                    # 14: JSON de cota_envio.medir()
    ["Andamento do envio (ao vivo)", ""],
    ["Conferência da cópia (ao vivo)", ""],
]
LINHA_COMANDO, LINHA_PEDIDO, LINHA_RESPOSTA, LINHA_CONFIG, LINHA_ONLINE, LINHA_SELECAO = 7, 8, 9, 11, 12, 13
LINHA_COTA, LINHA_ANDAMENTO, LINHA_CONFERENCIA = 14, 15, 16


class ErroPlanilha(Exception):
    """Erro que impede a execução de seguir."""


def nome_intervalo(aba):
    """"D'Ávila" -> "'D''Ávila'" (notação A1)."""
    return "'" + str(aba).replace("'", "''") + "'"


_CLIENTES = {}      # (chave, só leitura) -> (cliente gspread, {planilha_id: Spreadsheet}) — 1 por programa
_ABAS = {}          # (planilha_id, aba) -> Worksheet: achar a aba custa 1 leitura; guarda pra não pagar toda vez
_TAMANHOS = {}      # (planilha_id, aba) -> (linhas, colunas) da última vez que substituir_aba gravou


class BackendGoogle:
    """Toda chamada passa pela cota_google: o programa nunca usa mais que a fatia dele da cota."""

    def __init__(self, caminho_chave, somente_leitura=False):
        chave = (str(caminho_chave), bool(somente_leitura))
        if chave not in _CLIENTES:
            import gspread
            from google.oauth2.service_account import Credentials
            escopos = ESCOPOS_SO_LEITURA if somente_leitura else ESCOPOS
            credenciais = Credentials.from_service_account_file(caminho_chave, scopes=escopos)
            cliente = gspread.authorize(credenciais)
            cliente.set_timeout(TIMEOUT_GOOGLE_SEGUNDOS)
            _CLIENTES[chave] = (cliente, {})
        self._cliente, self._planilhas = _CLIENTES[chave]

    @staticmethod
    def _api(tipo, func):
        def chamada():
            COTA.usar(tipo)
            try:
                return func()
            except Exception as e:
                if e_cota_estourada(e):
                    COTA.pausar()
                raise
        return com_retry(chamada, e_erro_passageiro_google)

    def _planilha(self, planilha_id):
        if planilha_id not in self._planilhas:
            self._planilhas[planilha_id] = self._api("leitura", lambda: self._cliente.open_by_key(planilha_id))
        return self._planilhas[planilha_id]

    def _aba(self, planilha_id, aba):
        chave = (planilha_id, aba)
        if chave not in _ABAS:
            _ABAS[chave] = self._api("leitura", lambda: self._planilha(planilha_id).worksheet(aba))
        return _ABAS[chave]

    def _com_aba(self, planilha_id, aba, func):
        """Usa a aba guardada; se ela foi apagada/recriada na planilha (id velho), procura de novo uma vez."""
        try:
            return func(self._aba(planilha_id, aba))
        except Exception as e:
            if e_erro_passageiro_google(e) or (planilha_id, aba) not in _ABAS:
                raise
            _ABAS.pop((planilha_id, aba), None)
            _TAMANHOS.pop((planilha_id, aba), None)
            return func(self._aba(planilha_id, aba))

    def ler_abas(self, planilha_id, nomes, faixas=None):
        """Uma chamada pra todas as abas. faixas: {aba: "A100:H"} lê só esse pedaço (o resto, a aba inteira).
        Se o lote falhar por causa de uma aba (apagada, renomeada), tira só ela e lê o resto de novo — nunca aba por
        aba: 79 abas uma a uma seriam 79 leituras, 10 min da fatia da cota. -> ({aba: linhas}, {aba: erro})"""
        faixas = faixas or {}
        nomes, erros = list(dict.fromkeys(nomes)), {}
        planilha = self._planilha(planilha_id) if nomes else None
        parametros = {"valueRenderOption": "FORMATTED_VALUE"}
        for _tentativa in range(4):
            if not nomes:
                return {}, erros
            intervalos = [nome_intervalo(n) + (f"!{faixas[n]}" if n in faixas else "") for n in nomes]
            try:
                resposta = self._api("leitura", lambda: planilha.values_batch_get(intervalos, params=parametros))
                lidas = resposta.get("valueRanges", [])
                return {nome: lidas[i].get("values", []) for i, nome in enumerate(nomes)}, erros
            except Exception as erro:
                texto = str(erro)
                culpada = next((n for n in sorted(nomes, key=len, reverse=True) if n in texto), None)
                if culpada is None or e_erro_passageiro_google(erro):
                    return {}, {**erros, **{n: texto for n in nomes}}
                logger.warning(f"⚠️ A aba '{culpada}' não pôde ser lida ({texto[:120]}) — lendo as outras sem ela.")
                erros[culpada] = texto
                nomes.remove(culpada)
        return {}, {**erros, **{n: "leitura em lote falhou" for n in nomes}}

    def listar_abas(self, planilha_id):
        abas = self._api("leitura", lambda: self._planilha(planilha_id).worksheets())
        for aba in abas:   # de brinde: já guarda todas, os próximos acréscimos não precisam procurar a aba
            _ABAS[(planilha_id, aba.title)] = aba
        return [aba.title for aba in abas]

    def escrever(self, planilha_id, atualizacoes):
        """atualizacoes = [("'Aba'!K5", valor), ...]"""
        if not atualizacoes:
            return
        planilha = self._planilha(planilha_id)
        corpo = {
            "valueInputOption": "USER_ENTERED",
            "data": [{"range": faixa, "values": [[valor]]} for faixa, valor in atualizacoes],
        }
        self._api("escrita", lambda: planilha.values_batch_update(corpo))

    def criar_aba_status(self, planilha_id, nome, linhas):
        planilha = self._planilha(planilha_id)
        aba = self._api("escrita", lambda: planilha.add_worksheet(title=nome, rows=20, cols=4))
        _ABAS[(planilha_id, nome)] = aba
        self._api("escrita", lambda: aba.update(range_name="A1", values=linhas, value_input_option="USER_ENTERED"))
        pedido = {"requests": [{"setDataValidation": {
            "range": {"sheetId": aba.id, "startRowIndex": 0, "endRowIndex": 1,
                      "startColumnIndex": 1, "endColumnIndex": 2},
            "rule": {"condition": {"type": "BOOLEAN"}},
        }}]}
        self._api("escrita", lambda: planilha.batch_update(pedido))

    def criar_aba_log(self, planilha_id, nome, cabecalho):
        planilha = self._planilha(planilha_id)
        aba = self._api("escrita", lambda: planilha.add_worksheet(title=nome, rows=1000, cols=len(cabecalho)))
        _ABAS[(planilha_id, nome)] = aba
        self._api("escrita", lambda: aba.update(range_name="A1", values=[cabecalho], value_input_option="RAW"))
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
        self._api("escrita", lambda: planilha.batch_update({"requests": pedidos}))

    def inserir_no_topo(self, planilha_id, aba, linhas):
        planilha = self._planilha(planilha_id)

        def inserir(planilha_aba):
            self._api("escrita", lambda: planilha.batch_update({"requests": [{"insertDimension": {
                "range": {"sheetId": planilha_aba.id, "dimension": "ROWS", "startIndex": 1, "endIndex": 1 + len(linhas)},
                "inheritFromBefore": False}}]}))
        self._com_aba(planilha_id, aba, inserir)
        self._api("escrita", lambda: planilha.values_update(f"{nome_intervalo(aba)}!A2", params={"valueInputOption": "RAW"},
                                                            body={"values": linhas}))

    def substituir_aba(self, planilha_id, aba, linhas):
        """Reescreve a aba inteira (cria se faltar) — abas de passagem, como o espelho de e-mails.
        Numa escrita só: grava por cima e preenche de vazio o que sobrou da vez anterior (a aba nunca fica vazia)."""
        import gspread
        planilha = self._planilha(planilha_id)
        largura = max((len(l) for l in linhas), default=1)
        chave = (planilha_id, aba)
        try:
            planilha_aba = self._aba(planilha_id, aba)
        except gspread.exceptions.WorksheetNotFound:
            planilha_aba = self._api("escrita", lambda: planilha.add_worksheet(
                title=aba, rows=max(len(linhas) + 50, 100), cols=max(largura, 1)))
            _ABAS[chave] = planilha_aba
            _TAMANHOS[chave] = (0, largura)
        if planilha_aba.row_count < len(linhas) or planilha_aba.col_count < largura:
            self._api("escrita", lambda: planilha_aba.resize(rows=max(planilha_aba.row_count, len(linhas) + 50),
                                                             cols=max(planilha_aba.col_count, largura)))
        anterior = _TAMANHOS.get(chave)
        if anterior is None:   # 1ª vez neste programa: não sei o que tem embaixo — limpa tudo de uma vez
            self._api("escrita", lambda: planilha_aba.clear())
            anterior = (0, largura)
        altura, largura_total = max(len(linhas), anterior[0]), max(largura, anterior[1])
        corpo = [list(l) + [""] * (largura_total - len(l)) for l in linhas]
        corpo += [[""] * largura_total for _ in range(altura - len(corpo))]
        self._api("escrita", lambda: planilha.values_update(
            f"{nome_intervalo(aba)}!A1:{rowcol_to_a1(max(altura, 1), largura_total)}",
            params={"valueInputOption": "RAW"}, body={"values": corpo}))
        _TAMANHOS[chave] = (len(linhas), largura)

    def garantir_colunas(self, planilha_id, aba, cabecalho):
        """Aba criada com menos colunas (ex.: PCs_Painel de 4 pra 8): aumenta a grade e reescreve o cabeçalho."""
        planilha_aba = self._aba(planilha_id, aba)
        if planilha_aba.col_count < len(cabecalho):
            self._api("escrita", lambda: planilha_aba.add_cols(len(cabecalho) - planilha_aba.col_count))
        if self._api("leitura", lambda: planilha_aba.row_values(1))[:len(cabecalho)] != cabecalho:
            self._api("escrita", lambda: planilha_aba.update(range_name="A1", values=[cabecalho], value_input_option="RAW"))

    def anexar_linhas(self, planilha_id, aba, linhas):
        self._com_aba(planilha_id, aba, lambda planilha_aba: self._api(
            "escrita", lambda: planilha_aba.append_rows(linhas, value_input_option="RAW")))

    def apagar_linhas(self, planilha_id, aba, inicio, fim, novas=None):
        """Faxina: apaga as linhas [inicio, fim) (1 = cabeçalho, 2 = 1ª de dados) e, no mesmo pedido, põe `novas`
        no lugar. Um pedido só (atômico): o que outro PC acrescentou no fim enquanto isso fica intacto."""
        planilha = self._planilha(planilha_id)

        def faxinar(planilha_aba):
            pedidos = [{"deleteDimension": {"range": {"sheetId": planilha_aba.id, "dimension": "ROWS",
                                                      "startIndex": inicio - 1, "endIndex": fim - 1}}}]
            if novas:
                pedidos += [{"insertDimension": {"range": {"sheetId": planilha_aba.id, "dimension": "ROWS",
                                                           "startIndex": inicio - 1, "endIndex": inicio - 1 + len(novas)},
                                                 "inheritFromBefore": False}},
                            {"updateCells": {"start": {"sheetId": planilha_aba.id, "rowIndex": inicio - 1, "columnIndex": 0},
                                             "rows": [{"values": [{"userEnteredValue": {"stringValue": str(v)}} for v in l]}
                                                      for l in novas],
                                             "fields": "userEnteredValue"}}]
            self._api("escrita", lambda: planilha.batch_update({"requests": pedidos}))
        self._com_aba(planilha_id, aba, faxinar)

    def apagar_aba(self, planilha_id, aba):
        """Só pra abas de passagem (ex.: o espelho de e-mails antigo)."""
        planilha = self._planilha(planilha_id)
        self._com_aba(planilha_id, aba, lambda planilha_aba: self._api("escrita", lambda: planilha.del_worksheet(planilha_aba)))
        _ABAS.pop((planilha_id, aba), None)
        _TAMANHOS.pop((planilha_id, aba), None)


class BackendSoLeitura(BackendGoogle):
    """Modo casa (usuário, 12/10/2026): o Painel do PC de casa só VÊ os dados reais. Toda gravação é ignorada aqui,
    então ele não aparece como PC da equipe, não grava na Central e não mexe em nada (e a chave pode ser só leitura)."""

    def __init__(self, caminho_chave):
        super().__init__(caminho_chave, somente_leitura=True)

    def _ignorar(self, *args, **kwargs):
        return None

    escrever = criar_aba_status = criar_aba_log = inserir_no_topo = substituir_aba = _ignorar
    garantir_colunas = anexar_linhas = apagar_linhas = apagar_aba = _ignorar


def limitar_leitura():
    """Pra quem chama a API do Google por fora do BackendGoogle (cópia das planilhas dos hotéis)."""
    COTA.usar("leitura")


def _achar_coluna(cabecalhos, nomes_aceitos):
    """nomes_aceitos: str ou lista em ordem de preferência."""
    if isinstance(nomes_aceitos, str):
        nomes_aceitos = [nomes_aceitos]
    alvos = [normalizar(n) for n in nomes_aceitos if str(n).strip()]
    normalizados = [normalizar(c) for c in cabecalhos]
    for alvo in alvos:
        if alvo in normalizados:
            return normalizados.index(alvo)
    return None


def _achar_colunas(cabecalhos, nomes_aceitos):
    """Como _achar_coluna, mas todas as que casam, em ordem de preferência. A aba da Central de um hotel pode juntar
    o formulário antigo e o novo (15/10/2026): na linha do novo, 'Endereço de e-mail' fica vazio e o e-mail está em 'E-mail'."""
    if isinstance(nomes_aceitos, str):
        nomes_aceitos = [nomes_aceitos]
    normalizados = [normalizar(c) for c in cabecalhos]
    saida = []
    for alvo in (normalizar(n) for n in nomes_aceitos if str(n).strip()):
        saida += [i for i, c in enumerate(normalizados) if c == alvo and i not in saida]
    return saida


def _coluna_da_linha(linha, indices):
    """Das colunas de _achar_colunas, a primeira com valor nesta linha (nenhuma com valor: a primeira).
    Um índice só (int ou None) passa direto."""
    if not isinstance(indices, (list, tuple)):
        return indices
    for i in indices:
        if _celula(linha, i):
            return i
    return indices[0] if indices else None


def _celula(linha, indice):
    if indice is None or indice >= len(linha):
        return ""
    return str(linha[indice]).strip()


def _indice_coluna(letra):
    return ord(str(letra).strip().upper()) - ord("A")


def ler_hoteis(backend, cfg):
    """Casa cada aba '(respostas)' da Central com o Cadastro_Hoteis. -> (hoteis, erros)"""
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
            continue
        cadastro.setdefault(normalizar(nome), (nome, agente, _celula(linha, i_email_hotel).lower()))

    agentes = {normalizar(k): str(v).strip().lower() for k, v in cfg.get("agentes", {}).items()
               if not str(k).startswith("_")}
    apelidos = {normalizar(k): v for k, v in cfg.get("apelidos_hoteis", {}).items() if not str(k).startswith("_")}
    ignoradas = {normalizar(a) for a in cfg.get("abas_ignoradas", [])}
    marcador = normalizar(cfg.get("marcador_aba_respostas", "(respostas)"))
    sem_envio_real = cfg["modo"] in ("SIMULACAO", "TESTE")   # agente sem e-mail não bloqueia teste
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
    """Hash da linha sem a coluna Enviado; diferencia pedidos com mesmo carimbo e e-mail."""
    valores = [str(v).strip() for i, v in enumerate(linha) if i != i_enviado]
    while valores and not valores[-1]:
        valores.pop()
    return hashlib.sha1(SEPARADOR.join(valores).encode("utf-8")).hexdigest()[:16]


def nome_do_hotel_pela_aba(nome_aba):
    """'Solicitação Nota Fiscal (MERCADO) (respostas)' -> 'MERCADO'."""
    partes = [p for p in re.findall(r"\(([^)]*)\)", nome_aba) if normalizar(p) != "respostas"]
    return partes[0].strip() if partes else nome_aba


def _nome_titulo(cabecalhos, linha, cfg):
    colunas = cfg["colunas"]
    i_tomador = _achar_coluna(cabecalhos, colunas.get("reserva_no_tomador", ""))
    i_pf = _achar_coluna(cabecalhos, colunas.get("nome_pessoa_fisica", ""))
    i_hospede = _coluna_da_linha(linha, _achar_colunas(cabecalhos, colunas.get("nome_hospede", "")))
    if normalizar(_celula(linha, i_tomador)) == "sim" and _celula(linha, i_pf):
        return _celula(linha, i_pf)
    return " ".join(_celula(linha, i_hospede).split()) or "Hóspede"


def _dados_para_conferencia(cabecalhos, linha, cfg):
    """-> (emails de contato, nomes, partes da nota dividida)"""
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
        partes = max(2, int(digitos)) if digitos else 2
    return emails, nomes, partes


def interpretar_aba(hotel, linhas, cfg, incluir_linhas=None):
    """-> (pendentes, erro). Com incluir_linhas, pega essas linhas mesmo já marcadas TRUE."""
    if not linhas:
        return [], None
    cabecalhos = [str(c).strip() for c in linhas[0]]
    colunas = cfg["colunas"]
    i_enviado = _achar_coluna(cabecalhos, colunas["enviado"])
    i_carimbo = _achar_coluna(cabecalhos, colunas["carimbo"])
    i_emails = _achar_colunas(cabecalhos, colunas.get("email_hospede", ""))
    if i_enviado is None:
        return [], f"sem a coluna '{colunas['enviado']}'"
    if i_carimbo is None:
        return [], f"sem a coluna '{colunas['carimbo']}'"

    # Forms grava em mês/dia; linhas coladas à mão costumam vir em dia/mês
    formato = detectar_formato_data((_celula(l, i_carimbo) for l in linhas[1:]),
                                    cfg.get("formato_data_planilha", "americano"))
    documentos = cfg.get("colunas_documento", {})
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
        i_email = _coluna_da_linha(linha, i_emails)
        esconder = {i_email} if i_email is not None else set()
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
    """-> (pendentes, erros), uma leitura por planilha."""
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
    """Relê a aba e acha a linha pela chave, não pelo número (a aba pode ter mudado desde a leitura)."""
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
            i_emails = _achar_colunas(cabecalhos, colunas.get("email_hospede", ""))
            if i_enviado is None or i_carimbo is None:
                nao_encontradas.extend(lista)
                continue
            linhas_por_chave = {}
            for numero, linha in enumerate(linhas[1:], start=2):
                chave = (_celula(linha, i_carimbo), _celula(linha, _coluna_da_linha(linha, i_emails)),
                         assinatura_da_linha(linha, i_enviado))
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
    # Apóstrofo força texto: a planilha é en-US e leria "05/10/2026" como 10 de maio
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
    """Espelha as enviadas na aba Registros, como o Apps Script antigo fazia."""
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


# --- Protocolo com o menu da planilha ---
def garantir_rotulos_status(backend, cfg):
    """Completa os rótulos numa aba Status criada por uma versão antiga."""
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
    """-> (comando, quem, quando: datetime aware | None)"""
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
    """valores = {linha: texto}, gravados como texto na coluna B."""
    aba = nome_intervalo(cfg["aba_status"])
    backend.escrever(cfg["planilha_central_id"],
                     [(f"{aba}!B{linha}", ("'" + str(v)) if str(v) else "") for linha, v in valores.items()])


def config_publica(cfg):
    """Subconjunto do config que o menu pode ver (sem caminhos nem chave)."""
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
