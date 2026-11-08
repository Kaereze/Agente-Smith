"""Tratamento dos campos do formulário: datas, CPF/CNPJ, CEP."""
import functools
import re
import unicodedata

_PADRAO_DATA_BARRA = re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})(\s+\d{1,2}:\d{2}(?::\d{2})?)?$")
_PADRAO_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[ T](\d{1,2}:\d{2}(?::\d{2})?))?$")
_SO_DIGITOS_E_PONTUACAO = re.compile(r"^[\d.\-/\s]+$")

# tipo: (tamanho, menor tamanho que ainda consideramos "zeros à esquerda comidos")
TAMANHOS_DOCUMENTO = {"cpf": (11, 9), "cnpj": (14, 12), "cep": (8, 7)}


def detectar_formato_data(valores, padrao="americano"):
    """O primeiro valor com dia > 12 decide; sem nenhum, fica o padrão."""
    for valor in valores:
        m = _PADRAO_DATA_BARRA.match(str(valor).strip())
        if not m:
            continue
        primeiro, segundo = int(m.group(1)), int(m.group(2))
        if primeiro > 12:
            return "brasileiro"
        if segundo > 12:
            return "americano"
    return padrao


@functools.lru_cache(maxsize=200_000)
def _normalizado(texto):
    nfkd = unicodedata.normalize("NFKD", texto)
    sem_acento = "".join(c for c in nfkd if not unicodedata.combining(c))
    return " ".join(sem_acento.lower().split())


def normalizar(texto):
    """'  Endereço de E-mail ' -> 'endereco de e-mail'
    Função pura chamada milhões de vezes por hora com os mesmos textos (cabeçalhos e valores da planilha): o resultado fica lembrado
    (29/10/2026: era o maior gasto de CPU do servidor do Painel, medido com py-spy; travava os cliques)."""
    return _normalizado(str(texto or ""))


@functools.lru_cache(maxsize=64)
def _padrao_da_palavra(palavra):
    return re.compile(rf"\b{palavra}\b")


def _tem_palavra(cabecalho_normalizado, palavra):
    # \b: "recepcao" contém "cep"
    return _padrao_da_palavra(palavra).search(cabecalho_normalizado) is not None


def tipo_documento(cabecalho, colunas_documento=None):
    """-> 'cpf' | 'cnpj' | 'cpf_cnpj' | 'cep' | None, pelo nome da coluna."""
    c = normalizar(cabecalho)
    for nome, tipo in (colunas_documento or {}).items():
        if normalizar(nome) == c:
            return tipo
    return _tipo_pelo_nome(c)


@functools.lru_cache(maxsize=4096)
def _tipo_pelo_nome(c):
    """A parte que só depende do nome (normalizado) da coluna: lembrada, porque o mesmo cabeçalho aparece em toda linha lida."""
    tem_cpf, tem_cnpj = _tem_palavra(c, "cpf"), _tem_palavra(c, "cnpj")
    if tem_cpf and tem_cnpj:
        return "cpf_cnpj"
    if tem_cpf:
        return "cpf"
    if tem_cnpj:
        return "cnpj"
    if _tem_palavra(c, "cep"):
        return "cep"
    return None


def completar_zeros(valor, tipo):
    texto = str(valor).strip()
    if not texto:
        return texto

    if "e+" in texto.lower():
        try:
            texto = str(int(float(texto.replace(",", "."))))
        except ValueError:
            return str(valor).strip()

    if not _SO_DIGITOS_E_PONTUACAO.match(texto):
        return str(valor).strip()
    digitos = re.sub(r"\D", "", texto)
    if not digitos:
        return str(valor).strip()

    if tipo == "cpf_cnpj":
        tipo = "cpf" if len(digitos) <= 11 else "cnpj"
    tamanho, minimo = TAMANHOS_DOCUMENTO[tipo]

    # A planilha come só os zeros à esquerda; se falta mais que isso, o valor está errado e fica como veio
    if not (minimo <= len(digitos) <= tamanho):
        return str(valor).strip()
    return digitos.zfill(tamanho)


def converter_data(valor, formato_planilha="americano"):
    """'9/3/2026 14:05:00' (americano: mês/dia/ano) -> '03/09/2026 14:05:00'"""
    texto = str(valor).strip()

    m = _PADRAO_DATA_ISO.match(texto)
    if m:
        ano, mes, dia, hora = m.groups()
        return f"{dia}/{mes}/{ano}" + (f" {hora}" if hora else "")

    m = _PADRAO_DATA_BARRA.match(texto)
    if not m:
        return texto
    primeiro, segundo, ano, hora = m.groups()
    if formato_planilha == "americano":
        mes, dia = int(primeiro), int(segundo)
    else:
        dia, mes = int(primeiro), int(segundo)
    if not (1 <= mes <= 12 and 1 <= dia <= 31):
        return texto
    return f"{dia:02d}/{mes:02d}/{ano}" + (hora or "")


def ler_data(valor, formato_planilha="americano"):
    """'9/3/2026 10:00' (americano) -> date(2026, 9, 3). None se não for data."""
    import datetime
    texto = converter_data(valor, formato_planilha)
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", texto)
    if not m:
        return None
    try:
        return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
    except ValueError:
        return None


def tratar_valor(cabecalho, valor, formato_planilha="americano", colunas_documento=None):
    tipo = tipo_documento(cabecalho, colunas_documento)
    if tipo:
        return completar_zeros(valor, tipo)
    return converter_data(valor, formato_planilha)


def campos_para_email(cabecalhos, linha, colunas_ocultas, formato_planilha="americano",
                      colunas_documento=None, indices_ocultos=()):
    """[(campo, valor)] na ordem das colunas, sem vazios e sem as colunas ocultas."""
    ocultas = {normalizar(c) for c in colunas_ocultas}
    campos = []
    for indice, cabecalho in enumerate(cabecalhos):
        if not str(cabecalho).strip() or normalizar(cabecalho) in ocultas or indice in indices_ocultos:
            continue
        valor = linha[indice] if indice < len(linha) else ""
        if valor is None or not str(valor).strip():
            continue
        campos.append((str(cabecalho).strip(),
                       tratar_valor(cabecalho, valor, formato_planilha, colunas_documento)))
    return campos
