# -*- coding: utf-8 -*-
"""Classifica as solicitacoes de NF da caixa de entrada e aplica as categorias do Outlook.

Nao cria, move nem apaga pasta nenhuma: so escreve em item.Categories.

    python src\\organizador_emails.py            classifica e grava as categorias
    python src\\organizador_emails.py --simular  mostra o que faria, sem gravar
    python src\\organizador_emails.py --detalhe  imprime email por email com o motivo
"""
import datetime
import json
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import carregar_config

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_INDICE = os.path.join(RAIZ, "estado", "indice_notas.json")

TAG_PENDENTE = "NF pendente"
TAG_CONCLUIDO = "NF concluído"
TAG_TRATATIVA = "Tratativa"
TAG_DIVIDIDA = "Nota dividida"
TAG_FALTA = "Faltando dados"
TAG_DUPLICADA = "Duplicada"

CAIXAS = {
    "notafiscal@plazasalvador.com.br": "Plaza Salvador",
    "notafiscal@redeandradebraz.com.br": "Braz",
    "notafiscal@redeandradesanmartin.com.br": "San Martin",
    "notafiscal@redeandradeslz.com.br": "SLZ",
    "notafiscal@redeandradesolmar.com.br": "Solmar",
    "notafiscal@redeandradecanada.com.br": "Canada",
    "notafiscal@estreladalvapraiahotel.com.br": "Estrela D'Alva",
    "notafiscal@hotelmirantefoz.com.br": "Mirante Foz",
    "notafiscal@plazarecife.com.br": "Plaza Recife",
    "notafiscal@redeandradedocas.com.br": "Docas",
    "notafiscal@redeandradearacaju.com.br": "Aracaju",
    "notafiscal@redeandradeportoseguro.com.br": "Porto Seguro",
    "notafiscal@redeandradecenterpremium.com.br": "Center Premium",
    "notafiscal@redeandradelginn.com.br": "LG Inn",
    "notafiscal@redeandradeitabuna.com.br": "Itabuna",
    "notafiscal@redeandrademinihotel.com.br": "Mini Hotel",
    "notafiscal@redeandradepousadadonorte.com.br": "Pousada do Norte",
    "notafiscal@redeandradenavegantesbps.com.br": "Navegantes BPS",
}

# "NF 356 - CLAUDIO MARCIO - 10724"  e tambem "10724 - CLAUDIO MARCIO"
RE_COM_NF = re.compile(r'^NF\s*-?\s*(\d+)\s*-\s*(.+?)\s*-\s*([\d\s\-]+)$', re.IGNORECASE)
RE_SEM_NF = re.compile(r'^(\d{3,7})\s*-\s*(.+)$')
RE_INVALIDA = re.compile(r'\(\s*(CA[CN]+ELADA|SUBSTITUIDA|SUBSTITUÍDA)\s*\)', re.IGNORECASE)
RE_SUFIXO_COPIA = re.compile(r'\(\d+\)$')
RE_DOC = re.compile(r'\b\d{11}\b|\b\d{14}\b|\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}')


def normalizar(texto):
    """Minusculas, sem acento, espacos colapsados."""
    if not texto:
        return ""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', texto).strip().lower()


def so_digitos(texto):
    return re.sub(r'\D', '', texto or "")


# --------------------------------------------------------------------------- Dropbox

def indexar_notas(cfg, usar_cache=True):
    """Le as pastas do Dropbox e devolve {'estadas': {...}, 'nomes': {...}}.

    O valor guardado e o timestamp do arquivo, pra dar pra comparar com a data da
    solicitacao. Notas (CANCELADA)/(SUBSTITUIDA) ficam de fora: nao valem como emitidas.
    """
    pastas = [os.path.expandvars(p) for p in cfg.get("dropbox_notas", {}).get("pastas", [])]
    pastas = [p for p in pastas if os.path.isdir(p)]

    if usar_cache and os.path.exists(CACHE_INDICE):
        try:
            with open(CACHE_INDICE, encoding="utf-8") as f:
                cache = json.load(f)
            idade = datetime.datetime.now().timestamp() - cache.get("gerado_em", 0)
            if idade < 6 * 3600 and cache.get("pastas") == pastas:
                return {"estadas": cache["estadas"], "nomes": cache["nomes"]}
        except (ValueError, KeyError, OSError):
            pass

    estadas, nomes = {}, {}
    descartadas = 0

    for pasta in pastas:
        for diretorio, _subdirs, arquivos in os.walk(pasta):
            for arquivo in arquivos:
                if not arquivo.lower().endswith((".pdf", ".xml", ".zip")):
                    continue
                base = os.path.splitext(arquivo)[0]
                if RE_INVALIDA.search(base):
                    descartadas += 1
                    continue
                base = RE_SUFIXO_COPIA.sub("", base).strip()

                m = RE_COM_NF.match(base)
                if m:
                    nome_hospede, bloco_estadas = m.group(2), m.group(3)
                else:
                    m = RE_SEM_NF.match(base)
                    if not m:
                        continue
                    bloco_estadas, nome_hospede = m.group(1), m.group(2)

                try:
                    quando = os.path.getmtime(os.path.join(diretorio, arquivo))
                except OSError:
                    quando = 0

                for estada in re.findall(r'\d{3,7}', bloco_estadas):
                    if quando > estadas.get(estada, 0):
                        estadas[estada] = quando

                chave_nome = normalizar(nome_hospede)
                if len(chave_nome) >= 8:
                    if quando > nomes.get(chave_nome, 0):
                        nomes[chave_nome] = quando

    os.makedirs(os.path.dirname(CACHE_INDICE), exist_ok=True)
    with open(CACHE_INDICE, "w", encoding="utf-8") as f:
        json.dump({"gerado_em": datetime.datetime.now().timestamp(), "pastas": pastas,
                   "estadas": estadas, "nomes": nomes, "descartadas": descartadas}, f)

    return {"estadas": estadas, "nomes": nomes}


# --------------------------------------------------------------------------- email

def ler_template(corpo):
    """Extrai os campos da solicitacao padrao. Devolve {} se o email nao for o template."""
    if "Dados para emiss" not in corpo:
        return {}
    campos = {}
    for linha in corpo.splitlines():
        if "\t" not in linha:
            continue
        partes = [p.strip() for p in linha.split("\t")]
        partes = [p for p in partes if p]
        if len(partes) >= 2:
            campos[normalizar(partes[0])] = partes[1]
    return campos


def itens_da_nota(campos):
    """{'diarias', 'consumo', 'estacionamento'} — o que a solicitacao pede.

    E o que separa duplicata de verdade de dois pedidos legitimos do mesmo hospede:
    diaria e estacionamento sao notas diferentes.
    """
    valor = normalizar(campos.get("informacoes necessarias na nota fiscal", ""))
    itens = set()
    if "diaria" in valor:
        itens.add("diarias")
    if "consumo" in valor:
        itens.add("consumo")
    if "estacionamento" in valor:
        itens.add("estacionamento")
    return itens


def quer_dividida(campos):
    """So e dividida quando o campo do formulario diz Sim."""
    return normalizar(campos.get("nota dividida", "")).startswith("sim")


def data_referencia(campos, recebido):
    """Check-in da hospedagem, se houver; senao a data em que o email chegou."""
    bruto = campos.get("check-in da hospedagem") or campos.get("check in da hospedagem") or ""
    m = re.search(r'(\d{2})/(\d{2})/(\d{4})', bruto)
    if m:
        try:
            return datetime.datetime(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    return recebido


def procurar_nota(indice, estada, nome, referencia):
    """Acha a NF ja emitida. Por estada vale sempre; por nome so se for posterior ao check-in.

    A margem de 7 dias cobre a nota emitida na vespera; sem ela, um homonimo de um ano
    atras marcaria a solicitacao de hoje como concluida.
    """
    if estada and estada in indice["estadas"]:
        return "estada %s" % estada

    chave = normalizar(nome)
    if len(chave) >= 8 and chave in indice["nomes"]:
        quando = datetime.datetime.fromtimestamp(indice["nomes"][chave])
        if quando >= referencia - datetime.timedelta(days=7):
            return "nome '%s' (nota de %s)" % (nome.strip(), quando.strftime("%d/%m/%Y"))
    return None


def estada_do_assunto(assunto):
    m = re.search(r'\b(?:estada|mestra|reserva)\b\D{0,12}(\d{4,7})', assunto, re.IGNORECASE)
    if m:
        return m.group(1)
    m = re.search(r'\b(\d{5,7})\b', assunto)
    return m.group(1) if m else None


def classificar(assunto, corpo, recebido, indice, ja_vistos):
    """Devolve (lista de tags, motivo legivel)."""
    campos = ler_template(corpo)
    tags, motivos = [], []

    if not campos:
        # Fora do formulario padrao: resposta, cobranca, duvida. Quem le decide.
        return [TAG_TRATATIVA], "fora do formulario padrao"

    documento = so_digitos(campos.get("documento tomador", ""))
    nome_tomador = campos.get("nome tomador", "")
    nome_titular = campos.get("nome do titular da reserva", "")
    itens = itens_da_nota(campos)
    referencia = data_referencia(campos, recebido)
    estada = estada_do_assunto(assunto)

    achada = procurar_nota(indice, estada, nome_titular or nome_tomador, referencia)
    if not achada and nome_tomador and nome_tomador != nome_titular:
        achada = procurar_nota(indice, None, nome_tomador, referencia)

    if achada:
        tags.append(TAG_CONCLUIDO)
        motivos.append("NF localizada no Dropbox por " + achada)
    else:
        tags.append(TAG_PENDENTE)
        motivos.append("sem NF correspondente no Dropbox")

    if quer_dividida(campos):
        tags.append(TAG_DIVIDIDA)
        vezes = campos.get("dividida em quantas vezes", "")
        motivos.append("formulario pede nota dividida" + (" em %s" % vezes if vezes else ""))

    faltando = []
    if not documento:
        faltando.append("documento do tomador")
    if not nome_tomador:
        faltando.append("nome do tomador")
    if not itens:
        faltando.append("o que entra na nota")
    if faltando:
        tags.append(TAG_FALTA)
        motivos.append("falta " + ", ".join(faltando))

    # Duplicata: mesmo tomador pedindo os mesmos itens. Diaria e estacionamento do
    # mesmo hospede sao pedidos distintos e nao entram aqui.
    if documento and itens:
        chave = (documento, frozenset(itens))
        anterior = ja_vistos.get(chave)
        if anterior and abs((recebido - anterior).days) <= 30:
            tags.append(TAG_DUPLICADA)
            motivos.append("mesmo tomador e mesmos itens de %s" % anterior.strftime("%d/%m"))
        else:
            ja_vistos[chave] = recebido

    return tags, "; ".join(motivos)


# --------------------------------------------------------------------------- execucao

def main():
    simular = "--simular" in sys.argv
    detalhe = "--detalhe" in sys.argv

    print("=" * 100)
    print("ORGANIZADOR DE EMAILS" + ("  [SIMULACAO - nada sera gravado]" if simular else ""))
    print("=" * 100)

    cfg = carregar_config()

    print("\nIndexando as notas do Dropbox...")
    indice = indexar_notas(cfg)
    print("  %d estadas e %d nomes de hospede indexados" % (len(indice["estadas"]), len(indice["nomes"])))

    import win32com.client
    ns = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")

    print("\nClassificando a caixa de entrada de cada hotel:\n")
    total = 0
    contagem = {}

    for conta in ns.Accounts:
        endereco = str(getattr(conta, "SmtpAddress", "") or "").lower()
        if endereco not in CAIXAS:
            continue
        hotel = CAIXAS[endereco]

        try:
            itens = conta.DeliveryStore.GetDefaultFolder(6).Items
        except Exception as erro:
            print("  %-18s nao consegui abrir a caixa (%s)" % (hotel, str(erro)[:40]))
            continue

        itens.Sort("[ReceivedTime]", False)
        ja_vistos = {}
        do_hotel = 0

        for i in range(itens.Count):
            try:
                item = itens(i + 1)
                assunto = str(item.Subject or "").strip()
                corpo = str(item.Body or "")
                recebido = datetime.datetime(item.ReceivedTime.year, item.ReceivedTime.month,
                                             item.ReceivedTime.day)
            except Exception:
                continue
            if not assunto:
                continue

            tags, motivo = classificar(assunto, corpo, recebido, indice, ja_vistos)
            if not tags:
                continue

            if not simular:
                try:
                    item.Categories = "; ".join(tags)
                    item.Save()
                except Exception:
                    continue

            do_hotel += 1
            total += 1
            for tag in tags:
                contagem[tag] = contagem.get(tag, 0) + 1

            if detalhe:
                print("    [%-42s] %s" % ("; ".join(tags), assunto[:52]))
                print("      %s" % motivo)

        if do_hotel:
            print("  %-18s %3d emails" % (hotel, do_hotel))

    print("\n" + "=" * 100)
    print("%d emails classificados" % total)
    print("=" * 100)
    for tag, n in sorted(contagem.items(), key=lambda x: -x[1]):
        print("  %-18s %3d" % (tag, n))

    if simular:
        print("\nSimulacao: nenhuma categoria foi gravada. Rode sem --simular pra aplicar.")


if __name__ == "__main__":
    main()
