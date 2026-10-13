# -*- coding: utf-8 -*-
"""Classifica as solicitacoes de NF da caixa de entrada e aplica as categorias do Outlook.

Nao cria, move nem apaga pasta nenhuma: so escreve em item.Categories, e so nas
categorias deste robo — o que a equipe marcou a mao fica onde esta.

Roda igual em qualquer PC: as caixas saem do cruzamento entre as contas do Outlook
da maquina e a coluna B do Cadastro_Hoteis. Nada de lista fixa no codigo, que
obrigaria a editar o arquivo a cada PC e a cada hotel que entra ou sai.

O vocabulario de categorias e o do conferente (controle_nf), com emoji e cor. Os dois
escrevem no mesmo campo: com nomes diferentes, o conferente nao reconheceria as tags
daqui e elas ficariam presas no email pra sempre.

    python src\\organizador_emails.py --simular     mostra o que faria, sem gravar
    python src\\organizador_emails.py               classifica e grava
    python src\\organizador_emails.py --detalhe     imprime email por email com o motivo
    python src\\organizador_emails.py --dias 15     so os emails dos ultimos 15 dias
"""
import datetime
import json
import os
import re
import sys
import outlook_vivo

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import carregar_config, caminho_chave_google
from controle_nf import (CATEGORIA_CONCLUIDO, CATEGORIA_DIVIDIDA, CATEGORIA_PENDENTE,
                         CATEGORIA_TRATATIVA, CORES_CATEGORIAS)
from sheets import BackendGoogle
from tratamento import normalizar

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_INDICE = os.path.join(RAIZ, "estado", "indice_notas.json")
CACHE_HORAS = 6

# As quatro primeiras vem do conferente; as tres ultimas sao deste organizador.
TAG_FALTA = "⚠️ Faltando dados"
TAG_DUPLICADA = "🔁 Duplicada"
TAG_FORA_PADRAO = "📨 Fora do padrão"

# Nao reaproveita 💬 Tratativa pra email fora do formulario: no conferente ela quer dizer
# "tratativa aberta numa solicitacao", que e outra coisa.
CORES = {**CORES_CATEGORIAS, TAG_FALTA: 3, TAG_DUPLICADA: 6, TAG_FORA_PADRAO: 15}
NOSSAS = (CATEGORIA_CONCLUIDO, CATEGORIA_PENDENTE, CATEGORIA_TRATATIVA, CATEGORIA_DIVIDIDA,
          TAG_FALTA, TAG_DUPLICADA, TAG_FORA_PADRAO)

OLFOLDER_INBOX = 6

# "NF 356 - CLAUDIO MARCIO - 10724" e tambem "10724 - CLAUDIO MARCIO"
RE_COM_NF = re.compile(r'^NF\s*-?\s*(\d+)\s*-\s*(.+?)\s*-\s*([\d\s\-]+)$', re.IGNORECASE)
RE_SEM_NF = re.compile(r'^(\d{3,7})\s*-\s*(.+)$')
RE_INVALIDA = re.compile(r'\(\s*(CA[CN]+ELADA|SUBSTITU[IÍ]DA)\s*\)', re.IGNORECASE)
RE_SUFIXO_COPIA = re.compile(r'\(\d+\)$')


def so_digitos(texto):
    return re.sub(r'\D', '', texto or "")


# --------------------------------------------------------------------- caixas da maquina

def descobrir_caixas(cfg, namespace):
    """{email: (hotel, agente)} das contas deste Outlook que estao no Cadastro_Hoteis."""
    contas = {str(getattr(c, "SmtpAddress", "") or "").strip().lower() for c in namespace.Accounts}
    contas.discard("")

    backend = BackendGoogle(caminho_chave_google(cfg), somente_leitura=True)
    aba = cfg["aba_cadastro_hoteis"]
    linhas = backend.ler_abas(cfg["planilha_central_id"], [aba])[0].get(aba, [])

    col = cfg.get("cadastro_colunas", {})
    i_h, i_e, i_a = (ord(col.get(k, d).upper()) - 65
                     for k, d in (("hotel", "A"), ("email_hotel", "B"), ("agente", "C")))

    caixas = {}
    for linha in linhas:
        email = (linha[i_e] if len(linha) > i_e else "").strip().lower()
        if not email or email not in contas:
            continue
        hotel = (linha[i_h] if len(linha) > i_h else "").strip()
        agente = (linha[i_a] if len(linha) > i_a else "").strip()
        if normalizar(agente) in ("agente", "operador"):
            continue
        caixas[email] = (hotel or email, agente)

    return caixas, sorted(contas - set(caixas))


# --------------------------------------------------------------------- Dropbox

def indexar_notas(cfg, usar_cache=True):
    """{'estadas': {...}, 'nomes': {...}} -> timestamp do arquivo da NF.

    Guarda o timestamp pra dar pra comparar com a data da solicitacao. Notas
    (CANCELADA)/(SUBSTITUIDA) ficam de fora: nao valem como emitidas.
    """
    pastas = [os.path.expandvars(p) for p in cfg.get("dropbox_notas", {}).get("pastas", [])]
    pastas = [p for p in pastas if os.path.isdir(p)]

    if usar_cache and os.path.exists(CACHE_INDICE):
        try:
            with open(CACHE_INDICE, encoding="utf-8") as f:
                cache = json.load(f)
            idade = datetime.datetime.now().timestamp() - cache.get("gerado_em", 0)
            if idade < CACHE_HORAS * 3600 and cache.get("pastas") == pastas:
                return {"estadas": cache["estadas"], "nomes": cache["nomes"]}
        except (ValueError, KeyError, OSError):
            pass

    estadas, nomes = {}, {}
    for pasta in pastas:
        for diretorio, _sub, arquivos in os.walk(pasta):
            for arquivo in arquivos:
                if not arquivo.lower().endswith((".pdf", ".xml", ".zip")):
                    continue
                base = os.path.splitext(arquivo)[0]
                if RE_INVALIDA.search(base):
                    continue
                base = RE_SUFIXO_COPIA.sub("", base).strip()

                achado = RE_COM_NF.match(base)
                if achado:
                    hospede, bloco = achado.group(2), achado.group(3)
                else:
                    achado = RE_SEM_NF.match(base)
                    if not achado:
                        continue
                    bloco, hospede = achado.group(1), achado.group(2)

                try:
                    quando = os.path.getmtime(os.path.join(diretorio, arquivo))
                except OSError:
                    quando = 0

                for estada in re.findall(r'\d{3,7}', bloco):
                    if quando > estadas.get(estada, 0):
                        estadas[estada] = quando

                chave = normalizar(hospede)
                if len(chave) >= 8 and quando > nomes.get(chave, 0):
                    nomes[chave] = quando

    os.makedirs(os.path.dirname(CACHE_INDICE), exist_ok=True)
    with open(CACHE_INDICE, "w", encoding="utf-8") as f:
        json.dump({"gerado_em": datetime.datetime.now().timestamp(), "pastas": pastas,
                   "estadas": estadas, "nomes": nomes}, f)

    return {"estadas": estadas, "nomes": nomes}


# --------------------------------------------------------------------- categorias

def garantir_categorias(namespace):
    """Cria as categorias coloridas que faltarem; sem elas a tag aparece, mas sem cor."""
    try:
        existentes = {c.Name for c in namespace.Categories}
        for nome, cor in CORES.items():
            if nome not in existentes:
                namespace.Categories.Add(nome, cor)
    except Exception:
        pass  # sem cor o organizador continua valendo


def mesclar_categorias(atuais, novas):
    """Troca so as categorias deste robo e preserva as que a equipe pos a mao."""
    outras = [c.strip() for c in re.split(r"[;,]", atuais or "")
              if c.strip() and c.strip() not in NOSSAS]
    return "; ".join(outras + list(novas))


# --------------------------------------------------------------------- email

def ler_template(corpo):
    """Campos da solicitacao padrao. {} se o email nao for o formulario."""
    if "Dados para emiss" not in corpo:
        return {}
    campos = {}
    for linha in corpo.splitlines():
        if "\t" not in linha:
            continue
        partes = [p.strip() for p in linha.split("\t") if p.strip()]
        if len(partes) >= 2:
            campos[normalizar(partes[0])] = partes[1]
    return campos


def itens_da_nota(campos):
    """{'diarias', 'consumo', 'estacionamento'} — o que a solicitacao pede.

    E o que separa duplicata de verdade de dois pedidos legitimos do mesmo hospede:
    diaria e estacionamento sao notas diferentes, e e assim que o hospede pede a
    nota separada.
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
    achado = re.search(r'(\d{2})/(\d{2})/(\d{4})', bruto)
    if achado:
        try:
            return datetime.datetime(int(achado.group(3)), int(achado.group(2)), int(achado.group(1)))
        except ValueError:
            pass
    return recebido


def estada_do_assunto(assunto):
    achado = re.search(r'\b(?:estada|mestra|reserva)\b\D{0,12}(\d{4,7})', assunto, re.IGNORECASE)
    if achado:
        return achado.group(1)
    achado = re.search(r'\b(\d{5,7})\b', assunto)
    return achado.group(1) if achado else None


def procurar_nota(indice, estada, nome, referencia):
    """Acha a NF ja emitida. Por estada vale sempre; por nome so se for posterior ao check-in.

    A margem de 7 dias cobre a nota emitida na vespera. Sem esse corte, um hospede
    recorrente com nota de meses atras marcaria como concluida a solicitacao de agora.
    """
    if estada and estada in indice["estadas"]:
        return "estada %s" % estada

    chave = normalizar(nome)
    if len(chave) >= 8 and chave in indice["nomes"]:
        quando = datetime.datetime.fromtimestamp(indice["nomes"][chave])
        if quando >= referencia - datetime.timedelta(days=7):
            return "nome '%s' (nota de %s)" % (nome.strip(), quando.strftime("%d/%m/%Y"))
    return None


def classificar(assunto, corpo, recebido, indice, ja_vistos):
    """(categorias, motivo legivel)."""
    campos = ler_template(corpo)
    if not campos:
        # Resposta, cobranca, duvida: quem le decide o que fazer.
        return [TAG_FORA_PADRAO], "fora do formulario padrao"

    tags, motivos = [], []
    documento = so_digitos(campos.get("documento tomador", ""))
    nome_tomador = campos.get("nome tomador", "")
    nome_titular = campos.get("nome do titular da reserva", "")
    itens = itens_da_nota(campos)
    referencia = data_referencia(campos, recebido)

    achada = procurar_nota(indice, estada_do_assunto(assunto), nome_titular or nome_tomador, referencia)
    if not achada and nome_tomador and nome_tomador != nome_titular:
        achada = procurar_nota(indice, None, nome_tomador, referencia)

    if achada:
        tags.append(CATEGORIA_CONCLUIDO)
        motivos.append("NF localizada no Dropbox por " + achada)
    else:
        tags.append(CATEGORIA_PENDENTE)
        motivos.append("sem NF correspondente no Dropbox")

    if quer_dividida(campos):
        tags.append(CATEGORIA_DIVIDIDA)
        vezes = campos.get("dividida em quantas vezes", "")
        motivos.append("o formulario pede nota dividida" + (" em %s" % vezes if vezes else ""))

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

    # Duplicata: mesmo tomador pedindo os mesmos itens. Diaria e estacionamento do mesmo
    # hospede sao pedidos distintos e nao entram aqui.
    if documento and itens:
        chave = (documento, frozenset(itens))
        anterior = ja_vistos.get(chave)
        if anterior and abs((recebido - anterior).days) <= 30:
            tags.append(TAG_DUPLICADA)
            motivos.append("mesmo tomador e mesmos itens de %s" % anterior.strftime("%d/%m"))
        else:
            ja_vistos[chave] = recebido

    return tags, "; ".join(motivos)


# --------------------------------------------------------------------- execucao

def argumento_dias():
    if "--dias" not in sys.argv:
        return None
    pos = sys.argv.index("--dias") + 1
    try:
        return int(sys.argv[pos])
    except (IndexError, ValueError):
        print("--dias precisa de um numero. Ex.: --dias 15")
        sys.exit(2)


def main():
    simular = "--simular" in sys.argv
    detalhe = "--detalhe" in sys.argv
    dias = argumento_dias()

    print("=" * 96)
    print("ORGANIZADOR DE EMAILS" + ("   [SIMULACAO - nada sera gravado]" if simular else ""))
    print("=" * 96)

    cfg = carregar_config()

    ns = outlook_vivo.aplicativo().GetNamespace("MAPI")

    caixas, fora_do_cadastro = descobrir_caixas(cfg, ns)
    if not caixas:
        print("\nNenhuma conta deste Outlook esta no Cadastro_Hoteis. Nada a fazer.")
        return

    agentes = {a for _h, a in caixas.values() if a}
    print("\n%d caixa(s) desta maquina no cadastro%s" % (
        len(caixas), " · agente: %s" % ", ".join(sorted(agentes)) if agentes else ""))
    for email in sorted(fora_do_cadastro):
        print("  fora do Cadastro_Hoteis, sera ignorada: %s" % email)

    print("\nIndexando as notas do Dropbox...")
    indice = indexar_notas(cfg)
    print("  %d estadas e %d nomes indexados" % (len(indice["estadas"]), len(indice["nomes"])))

    if not simular:
        garantir_categorias(ns)

    limite = datetime.datetime.now() - datetime.timedelta(days=dias) if dias else None
    print("\nClassificando%s:\n" % (" os ultimos %d dias" % dias if dias else ""))

    total, contagem = 0, {}

    for conta in ns.Accounts:
        endereco = str(getattr(conta, "SmtpAddress", "") or "").strip().lower()
        if endereco not in caixas:
            continue
        hotel = caixas[endereco][0]

        try:
            itens = conta.DeliveryStore.GetDefaultFolder(OLFOLDER_INBOX).Items
        except Exception as erro:
            print("  %-22s nao consegui abrir a caixa (%s)" % (hotel[:22], str(erro)[:40]))
            continue

        itens.Sort("[ReceivedTime]", False)
        ja_vistos, do_hotel = {}, 0

        for i in range(itens.Count):
            try:
                item = itens(i + 1)
                assunto = str(item.Subject or "").strip()
                corpo = str(item.Body or "")
                chegada = item.ReceivedTime
                recebido = datetime.datetime(chegada.year, chegada.month, chegada.day)
            except Exception:
                continue
            if not assunto:
                continue
            if limite and recebido < limite:
                break  # ordenado por data: daqui pra tras e tudo mais antigo

            tags, motivo = classificar(assunto, corpo, recebido, indice, ja_vistos)
            if not tags:
                continue

            if not simular:
                try:
                    item.Categories = mesclar_categorias(str(item.Categories or ""), tags)
                    item.Save()
                except Exception:
                    continue

            do_hotel += 1
            total += 1
            for tag in tags:
                contagem[tag] = contagem.get(tag, 0) + 1

            if detalhe:
                print("    [%-46s] %s" % ("; ".join(tags), assunto[:46]))
                print("      %s" % motivo)

        if do_hotel:
            print("  %-22s %3d emails" % (hotel[:22], do_hotel))

    print("\n" + "=" * 96)
    print("%d emails classificados" % total)
    print("=" * 96)
    for tag, n in sorted(contagem.items(), key=lambda x: -x[1]):
        print("  %-22s %3d" % (tag, n))

    if simular:
        print("\nSimulacao: nada foi gravado. Rode sem --simular pra aplicar.")


if __name__ == "__main__":
    main()
