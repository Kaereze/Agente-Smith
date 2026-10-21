"""Envio da NF ao hóspede pelo Painel, saindo da caixa do próprio hotel.

Se a caixa do hotel está no Outlook deste PC, envia na hora. Se está em outro PC, o pedido vai pra
fila compartilhada (aba Envios_NF da Central) e o Painel daquele PC envia. Cada Painel publica na aba
PCs_Painel quais caixas tem, pra quem pede saber se existe um PC ligado capaz de enviar.

Envios_NF é append-only, como a aba Tratamento: PEDIDO, ASSUMIDO, ENVIADO, FALHOU. Anexo vindo do
Dropbox viaja como caminho relativo (cada PC lê do seu Dropbox); arquivo do computador viaja em partes
na aba Envios_NF_Anexos e é apagado depois do envio.

Envio direto pela rede (usuário, 21/10/2026): depois de gravar o PEDIDO, quem pede avisa o PC dono pela rede do
escritório e ele envia na hora, em vez de esperar a próxima leitura da fila (15 s a 1 min). O PC dono relê o pedido
na fila e envia pelo mesmo caminho dela; a rede só adianta a vez. Sem rede até ele, nada muda: a fila resolve.
"""
import base64
import datetime
import json
import os
import re
import tempfile
import threading
import uuid
from pathlib import Path

from controle_nf import _tokens, ler_assunto_nf
from log_util import configurar_logging
import outlook_vivo

logger = configurar_logging("envio_nf")

ABA_FILA = "Envios_NF"
CAB_FILA = ["Quando", "ID", "Evento", "PC", "Quem", "Dados (JSON)"]
ABA_ANEXOS = "Envios_NF_Anexos"
CAB_ANEXOS = ["ID", "Parte", "Total", "Nome", "Base64"]
ABA_PCS = "PCs_Painel"
CAB_PCS = ["PC", "Agente", "Contas", "Visto em", "Outlook", "Versão", "Papel", "Última conferência", "Rede", "Cota", "Uso",
           "Saúde"]

PEDIDO, ASSUMIDO, ENVIADO, FALHOU = "PEDIDO", "ASSUMIDO", "ENVIADO", "FALHOU"
CONFIRMADO = "CONFIRMADO"        # e-mail do robô: apareceu em Itens Enviados depois do ENVIADO
# E-mail do formulário do robô (envio_pc_dono, 15/10/2026): o PC dono que a rede não alcança recebe pela fila. Vai
# em "pc_formulario" (não em "pc_destino") de propósito: Painel de versão antiga ignora o pedido em vez de mandar errado.
ACAO_FORMULARIO = "formulario"
RECONFERIR_SEGUNDOS = 60
TAMANHO_PARTE = 45_000            # limite de célula do Sheets é 50 mil caracteres
MAX_ANEXO_BYTES = 8 * 1024 * 1024
PC_ONLINE_SEGUNDOS = 180
SEM_RESPOSTA_SEGUNDOS = 90
FILA_ESPERA_HORAS = 24           # PC dono desligado: o pedido espera ele ligar por até 24 h; depois expira
TEMPO_AVISO_DONO = 45            # envio direto: o PC dono envia e responde (Outlook + 2 gravações na planilha)
RECONFERIR_ENVIO_APOS = 120      # e-mail do Painel ASSUMIDO aqui sem ENVIADO há mais que isso: o Painel caiu no meio
FALHOU_SEM_ACHAR_APOS = 300      # ... e não está em Itens Enviados nem na Caixa de Saída depois disso: FALHOU (confira)
MAX_ITENS_CONFERIDOS = 3000      # Itens Enviados é lido do mais novo até a hora do envio; isto é só o teto
EXCLUIR, ENCAMINHAR = "excluir", "encaminhar"   # ações no Outlook do PC dono (além de enviar/responder)
URGENCIA = "urgencia"   # botão direito no Painel: categoria "Urgente (Painel)" / "Sem urgência (Painel)" no e-mail
DISPID_SEND_USING_ACCOUNT = 64209

MENSAGEM_PADRAO = (
    "Prezado(a) hóspede,\n\n"
    "Agradecemos por escolher a Rede Andrade para a sua estadia.\n\n"
    "Conforme solicitado, segue em anexo a Nota Fiscal referente à sua hospedagem.\n\n"
    "📢 Sua opinião é muito importante para nós!\n"
    "Gostaríamos de saber como foi sua experiência com o processo de emissão da Nota Fiscal.\n"
    "A pesquisa é anônima e leva menos de 2 minutos.\n\n"
    "👉 Clique aqui para avaliar: https://forms.gle/LLkYN3hv2da6svhj7\n\n"
    "Atenciosamente,")


def mensagem_padrao(cfg):
    return (cfg.get("envio_nf") or {}).get("mensagem") or MENSAGEM_PADRAO


def versao_do_codigo():
    """Commit curto em que este PC está, pra dar pra ver quem ficou pra trás.

    Lê o .git direto, em vez de chamar o git: a tarefa roda sem console e nem todo PC
    tem o executável no PATH. Qualquer falha devolve "", que só deixa a coluna vazia.
    """
    git = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".git")
    try:
        with open(os.path.join(git, "HEAD"), encoding="utf-8") as f:
            cabeca = f.read().strip()
        if not cabeca.startswith("ref:"):
            return cabeca[:7]                      # HEAD solto, sem branch
        ref = cabeca[4:].strip()
        solto = os.path.join(git, *ref.split("/"))
        if os.path.exists(solto):
            with open(solto, encoding="utf-8") as f:
                return f.read().strip()[:7]
        with open(os.path.join(git, "packed-refs"), encoding="utf-8") as f:
            for linha in f:                        # ref empacotada depois de um gc
                if linha.rstrip().endswith(" " + ref):
                    return linha.split()[0][:7]
    except (OSError, IndexError, UnicodeDecodeError):
        pass
    return ""


def mensagem_html(texto):
    """Texto digitado -> HTML do e-mail: quebras de linha e links clicáveis."""
    from html import escape
    linhas = []
    for linha in (texto or "").splitlines():
        linha = escape(linha)
        linha = re.sub(r"(https?://[^\s<]+)", r'<a href="\1">\1</a>', linha)
        linhas.append(linha)
    return ('<div style="font-family:Calibri,Arial,sans-serif;font-size:11pt;color:#222">'
            + "<br>".join(linhas) + "</div>")


# ---------- assinatura do Outlook (uma por caixa: "Nome (caixa).htm") ----------
PASTA_ASSINATURAS = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Signatures"


def achar_assinatura(conta, agente="", pasta=None):
    """A assinatura .htm desta caixa; com várias, a do operador do PC, senão a mais recente."""
    from tratamento import normalizar
    pasta = Path(pasta or PASTA_ASSINATURAS)
    try:
        candidatas = [p for p in pasta.glob("*.htm") if f"({conta.lower()})" in p.name.lower()]
    except OSError:
        return None
    if not candidatas:
        return None
    primeiro = normalizar(agente).split()[0][:4] if normalizar(agente) else ""
    do_operador = [p for p in candidatas if primeiro and primeiro in normalizar(p.stem)]
    return max(do_operador or candidatas, key=lambda p: p.stat().st_mtime)


def _ler_htm(caminho):
    bruto = Path(caminho).read_bytes()
    m = re.search(rb'charset=["\']?([\w-]+)', bruto[:3000], re.I)
    return bruto.decode(m.group(1).decode() if m else "utf-8", errors="replace")


_IMG_SRC = re.compile(r'((?:src|o:href)\s*=\s*)(["\'])([^"\']+?\.(?:png|jpe?g|gif|bmp))\2', re.I)


def assinatura_html(caminho):
    """-> (html da assinatura com as imagens trocadas por cid:, [(arquivo da imagem, cid)])"""
    from urllib.parse import unquote
    html = _ler_htm(caminho)
    corpo = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    html = corpo.group(1) if corpo else html
    base = Path(caminho).parent
    imagens = {}

    def trocar(m):
        arquivo = base / unquote(m.group(3)).replace("/", os.sep)
        if not arquivo.exists():
            return m.group(0)
        cid = imagens.setdefault(str(arquivo), f"assinatura{len(imagens) + 1}")
        return f"{m.group(1)}{m.group(2)}cid:{cid}{m.group(2)}"

    html = _IMG_SRC.sub(trocar, html)
    return html, [(Path(a), c) for a, c in imagens.items()]


def assinatura_previa(conta, agente=""):
    """HTML da assinatura com as imagens embutidas (data:), pra mostrar na janela do Painel."""
    caminho = achar_assinatura(conta, agente)
    if not caminho:
        return ""
    html, imagens = assinatura_html(caminho)
    for arquivo, cid in imagens:
        tipo = "jpeg" if arquivo.suffix.lower() in (".jpg", ".jpeg") else arquivo.suffix.lower().lstrip(".")
        html = html.replace(f"cid:{cid}", f"data:image/{tipo};base64,{base64.b64encode(arquivo.read_bytes()).decode()}")
    return re.sub(r"<script.*?</script>", "", html, flags=re.S | re.I)


def assinatura_tem_mensagem(html):
    """As assinaturas do time já trazem a mensagem padrão inteira (Prezado... pesquisa... Atenciosamente)."""
    texto = re.sub(r"<[^>]+>", " ", html or "").lower()
    return "forms.gle" in texto or "prezado" in texto


def _so_letras(texto):
    return re.sub(r"\W+", "", (texto or "").lower())


def corpo_do_email(mensagem, html_assinatura):
    """Igual ao Outlook: a assinatura da caixa vai inteira; o texto digitado entra acima dela.
    Se a assinatura já tem a mensagem padrão, o padrão não é repetido; sem assinatura, ele entra."""
    texto = (mensagem or "").strip()
    if assinatura_tem_mensagem(html_assinatura):
        if _so_letras(texto) == _so_letras(MENSAGEM_PADRAO):
            texto = ""
    elif not texto:
        texto = MENSAGEM_PADRAO
    partes = [mensagem_html(texto) + "<br>"] if texto else []
    return f"<html><body>{''.join(partes)}{html_assinatura}</body></html>"


CORPO_PADRAO = MENSAGEM_PADRAO


# ---------- selos pré-salvos (app_ui/assinaturas/<nome>.png) ----------
# Pedido do usuário (06/10/2026): a mensagem é sempre a mesma, só muda o selo de quem envia.
# Trocar/incluir um selo = pôr o PNG na pasta (o nome do arquivo é o do operador).
PASTA_SELOS = Path(__file__).resolve().parent.parent / "app_ui" / "assinaturas"
NOMES_SELOS = {"joao": "João"}
ORDEM_SELOS = ["joao", "cristian", "clara", "bernardo"]
CID_SELO = "selo_nf"
LARGURA_SELO = 520   # 13/10/2026: assinatura nova é mais larga (2400x760)


def selos():
    """[{"id": "joao", "nome": "João"}] dos PNGs da pasta, na ordem da equipe."""
    try:
        ids = [p.stem.lower() for p in PASTA_SELOS.glob("*.png")]
    except OSError:
        return []
    ids.sort(key=lambda i: (ORDEM_SELOS.index(i) if i in ORDEM_SELOS else 99, i))
    return [{"id": i, "nome": NOMES_SELOS.get(i, i.title())} for i in ids]


def caminho_selo(selo_id):
    if not selo_id or not str(selo_id).isalnum():
        return None
    caminho = PASTA_SELOS / f"{str(selo_id).lower()}.png"
    return caminho if caminho.exists() else None


def selo_do_agente(agente):
    """Selo do operador deste PC ("João" -> "joao"), senão o primeiro."""
    from tratamento import normalizar
    primeiro = normalizar(agente).split()[0] if normalizar(agente) else ""
    lista = selos()
    return next((s["id"] for s in lista if s["id"] == primeiro), lista[0]["id"] if lista else "")


def corpo_com_selo(mensagem):
    """Mensagem (padrão quando vazia, termina em "Atenciosamente,") + o selo embutido por cid."""
    texto = (mensagem or "").strip() or MENSAGEM_PADRAO
    return (f'<html><body>{mensagem_html(texto)}<br>'
            f'<img src="cid:{CID_SELO}" width="{LARGURA_SELO}" alt="Andrade Hotéis"></body></html>')


def agora():
    return datetime.datetime.now()


def _iso(d):
    return d.isoformat(timespec="seconds")


# ---------- assunto, destinatários, sugestões ----------
def assunto_sugerido(nome_arquivo, numero_nf, nome):
    """Usa o nome do arquivo quando ele já está no padrão "NF 1212 - NOME"; senão monta com o número."""
    base = os.path.splitext(os.path.basename(nome_arquivo or ""))[0]
    if ler_assunto_nf(base):
        return re.sub(r"\s+", " ", base).strip()
    return f"NF {numero_nf} - {nome.upper()}" if numero_nf else f"NF - {nome.upper()}"


def destinatarios(sol):
    vistos = []
    for e in [sol.get("email", "")] + list(sol.get("emails", [])):
        e = (e or "").strip().lower()
        if "@" in e and e not in vistos:
            vistos.append(e)
    return vistos


def raiz_dropbox(cfg):
    """Pasta raiz do Dropbox neste PC (onde fica 'REDE ANDRADE Dropbox')."""
    padrao = Path.home() / "REDE ANDRADE Dropbox"
    if padrao.exists():
        return padrao
    for pasta in (cfg.get("dropbox_notas") or {}).get("pastas", []):
        partes = Path(pasta).parts
        for i, p in enumerate(partes):
            if "dropbox" in p.lower():
                return Path(*partes[: i + 1])
    return None


PALAVRAS_COMUNS = {"dos", "das", "des", "del", "ltda", "eireli", "epp", "s/a", "sa", "me", "cia", "filho", "junior",
                   "neto", "comercio", "servicos", "industria", "empresa", "hotel"}


def _palavras(nome):
    return _tokens(nome) - PALAVRAS_COMUNS


def _primeira_palavra(nome):
    from tratamento import normalizar
    p = normalizar(nome).split()
    return p[0] if p else ""


def _nota(t, alvos, primeiros=()):
    """3 = nome da nota (2+ palavras) inteiro dentro do nome pedido; 2 = 2+ palavras em comum;
    1 = a nota tem uma palavra só e ela é o primeiro nome de alguém do pedido; 0 = não bate.
    Uma palavra solta (ex.: "SANTOS") não basta: sobrenome comum casa com muita gente."""
    if not t:
        return 0
    if len(t) == 1:
        return 1 if next(iter(t)) in primeiros else 0
    if any(t <= a for a in alvos):
        return 3
    return 2 if any(len(t & a) >= 2 for a in alvos) else 0


_LISTAGEM = {"em": None, "chave": None, "itens": []}
LISTAGEM_SEGUNDOS = 300


def marca_das_pastas(cfg):
    """Quando cada pasta de notas mudou por último (nota nova = pasta muda): o vigia olha isso a cada 20 s."""
    marca = []
    for pasta in (cfg.get("dropbox_notas") or {}).get("pastas", []):
        try:
            marca.append(os.stat(pasta).st_mtime_ns)
        except OSError:
            marca.append(0)
    return tuple(marca)


def listar_notas_dropbox(cfg, forcar=False):
    """[(nome, caminho, mtime, (nº, nome na NF))] das pastas de notas — em cache: ler o Dropbox leva segundos."""
    pastas = tuple((cfg.get("dropbox_notas") or {}).get("pastas", []))
    velha = _LISTAGEM["em"] is None or (agora() - _LISTAGEM["em"]).total_seconds() > LISTAGEM_SEGUNDOS
    if forcar or velha or _LISTAGEM["chave"] != pastas:
        itens = []
        for pasta in pastas:
            try:
                entradas = list(os.scandir(pasta))
            except OSError:
                continue
            for e in entradas:
                if e.is_file() and e.name.lower().endswith((".pdf", ".xml")):
                    nf = ler_assunto_nf(os.path.splitext(e.name)[0])
                    if nf:
                        itens.append((e.name, e.path, e.stat().st_mtime, nf))
        _LISTAGEM.update(em=agora(), chave=pastas, itens=itens)
    return _LISTAGEM["itens"]


# ---------- NF do Dropbox de um e-mail sem formulário (pedido do usuário, 08/10/2026) ----------
# Ex.: a recepção repassa "NF 62222 ESTADA HOTEL SAO FRANCISCO" e a nota sai como
# "NF 590 - COERNELIO NOGUEIRA - 62222.pdf": nº da estada + nome (com erro de digitação) ligam os dois.
_ROTULO_RESERVA = re.compile(r"(?:estada|estadia|reserva|localizador|itiner[aá]rio|booking|c[oó]digo)\D{0,25}?(\d{4,10})",
                             re.IGNORECASE)
_NOME_HOSPEDE = re.compile(r"(?:nome d[oa] h[oó]spede|reservado para|reserva feita para|h[oó]spede\s*:|nome\s*:)[\s:]*"
                           r"([A-Za-zÀ-ÿ][A-Za-zÀ-ÿ' .]{4,80})", re.IGNORECASE)
_INDICE_NOTAS = {"em": None, "por_reserva": {}, "por_palavra": {}}
JANELA_NOTA_EMAIL_DIAS = (-3, 30)


def _reservas_do_arquivo(nome_arquivo):
    """"NF 590 - COERNELIO NOGUEIRA - 62222.pdf": os nºs da estada ficam depois do nome."""
    resto = " ".join(os.path.splitext(nome_arquivo)[0].split(" - ")[2:])
    return set(re.findall(r"\d{4,10}", resto))


def _indice_notas(cfg):
    itens = listar_notas_dropbox(cfg)
    if _INDICE_NOTAS["em"] is not _LISTAGEM["em"] or not _INDICE_NOTAS["por_palavra"]:
        por_reserva, por_palavra = {}, {}
        for item in itens:
            nome_nf = item[3][1]
            for r in _reservas_do_arquivo(item[0]):
                por_reserva.setdefault(r, []).append(item)
            for p in _palavras(nome_nf):
                por_palavra.setdefault(p, []).append(item)
        _INDICE_NOTAS.update(em=_LISTAGEM["em"], por_reserva=por_reserva, por_palavra=por_palavra)
    return _INDICE_NOTAS


def palavra_parecida(a, b):
    """Igual, ou uma letra a mais/a menos/trocada em palavras de 5+ letras (COERNELIO x CORNELIO)."""
    if a == b:
        return True
    if min(len(a), len(b)) < 5 or abs(len(a) - len(b)) > 1:
        return False
    if len(a) > len(b):
        a, b = b, a
    i = 0
    while i < len(a) and a[i] == b[i]:
        i += 1
    return a[i + 1:] == b[i + 1:] if len(a) == len(b) else a[i:] == b[i + 1:]


def nomes_do_email(e):
    texto = f"{e.get('texto', '')}"
    nomes = [m.group(1).strip() for m in _NOME_HOSPEDE.finditer(texto)]
    nomes += list(e.get("hospedes_quartos") or [])
    if not nomes and e.get("nome"):
        nomes.append(e["nome"])   # sem nome no texto: o remetente é o próprio hóspede
    return [n for n in nomes if _palavras(n)]


_DOCUMENTO = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b|\b\d{2}\.?\d{3}\.?\d{3}/?\d{4}-?\d{2}\b")


def _confere_no_pdf(caminho, mtime, documentos, nomes):
    """Abre o PDF da nota (sem baixar arquivo que está só na nuvem) e confere CPF/CNPJ ou o nome inteiro."""
    from arquivos import so_na_nuvem
    if so_na_nuvem(caminho):
        return ""
    texto = _texto_da_nota_rapido(caminho, mtime) or ""
    digitos = re.sub(r"\D", "", texto)
    if any(d in digitos for d in documentos):
        return "nome no arquivo e CPF/CNPJ do e-mail no PDF"
    palavras_pdf = _palavras(texto)
    if any(n <= palavras_pdf for n in nomes):
        return "nome no arquivo e no PDF"
    return ""


def notas_do_email(e, cfg):
    """NFs do Dropbox emitidas pra este e-mail -> [{nome, nf, rel, prova, modificado, forte}].
    1) nº da estada/reserva (assunto ou texto) igual ao do arquivo E uma palavra do nome parecida;
    2) sem nº: nome do hóspede (2+ palavras iguais) e nota salva de 3 dias antes a 30 depois do e-mail. Se o e-mail diz
       a estada, o arquivo tem que ser dela (ou não ter nº) — usuário, 21/10/2026: a NF 1286 da estada 21653 caiu em
       pedidos das 21656/21657 do mesmo nome."""
    idx = _indice_notas(cfg)
    texto = f"{e.get('assunto', '')}\n{e.get('texto', '')}"
    rotuladas = set(_ROTULO_RESERVA.findall(texto))   # "Estada: 21657" (nº solto no assunto pode ser outra coisa)
    reservas = rotuladas | set(re.findall(r"\b\d{4,10}\b", e.get("assunto", "")))
    palavras = set().union(set(), *(_palavras(n) for n in nomes_do_email(e)))
    achadas = {}
    for r in reservas:
        for item in idx["por_reserva"].get(r, []):
            nome_nf = item[3][1]
            if any(palavra_parecida(p, q) for p in _palavras(nome_nf) for q in palavras):
                achadas.setdefault(item[1], (item, f"nº {r} e nome no arquivo"))
    if not achadas:
        # Só pelo nome é fraco ("FRANCISCO XAVIER PEREIRA" x "FRANCISCO ALISSON PEREIRA GURGEL"): o nome inteiro
        # de alguém do e-mail tem que estar no arquivo E o PDF tem que conferir (CPF/CNPJ do e-mail ou o nome)
        try:
            recebido = datetime.datetime.fromisoformat(e.get("recebido", "")).date()
        except ValueError:
            recebido = None
        nomes = [_palavras(n) for n in nomes_do_email(e)]
        nomes = [n for n in nomes if len(n) >= 2]
        documentos = {d for d in (re.sub(r"\D", "", x) for x in _DOCUMENTO.findall(texto)) if len(d) in (11, 14)}
        vistos = {}
        for n in nomes:
            for p in n:
                for item in idx["por_palavra"].get(p, []):
                    vistos[item[1]] = item
        for caminho, item in vistos.items():
            numeros = _reservas_do_arquivo(item[0])
            if rotuladas and numeros and not numeros & rotuladas:
                continue   # o e-mail diz a estada e este arquivo é de outra
            t = _palavras(item[3][1])
            atraso = (datetime.date.fromtimestamp(item[2]) - recebido).days if recebido else 0
            if not (len(t) >= 2 and any(n <= t for n in nomes)
                    and JANELA_NOTA_EMAIL_DIAS[0] <= atraso <= JANELA_NOTA_EMAIL_DIAS[1]):
                continue
            prova = _confere_no_pdf(caminho, item[2], documentos, nomes)
            if prova:
                achadas.setdefault(caminho, (item, prova))
    raiz = raiz_dropbox(cfg)
    saida = [{"nome": item[0], "nf": item[3][0], "forte": True, "prova": prova,
              "modificado": datetime.datetime.fromtimestamp(item[2]).strftime("%d/%m/%Y %H:%M"),
              "rel": os.path.relpath(item[1], raiz) if raiz else item[1]}
             for item, prova in achadas.values()]
    return sorted(saida, key=lambda n: n["modificado"][6:10] + n["modificado"][3:5] + n["modificado"][:2], reverse=True)[:4]


_TEXTOS_SUGESTAO = {}   # (caminho, mtime) -> texto do PDF
CANDIDATAS_SUGESTAO = 8
JANELA_SUGESTAO_DIAS = (-3, 90)   # nota salva de 3 dias antes a 90 depois do pedido


def _texto_da_nota_rapido(caminho, mtime):
    """Texto do PDF (cópia temporária; sem OCR, que leva segundos por nota)."""
    chave = (caminho, mtime)
    if chave not in _TEXTOS_SUGESTAO:
        import shutil
        pasta = tempfile.mkdtemp(prefix="nf_sug_")
        try:
            copia = os.path.join(pasta, "nota" + os.path.splitext(caminho)[1].lower())
            shutil.copyfile(caminho, copia)
            if copia.endswith(".xml"):
                texto = open(copia, encoding="utf-8", errors="replace").read()
            else:
                from pypdf import PdfReader
                texto = "\n".join((p.extract_text() or "") for p in PdfReader(copia).pages[:3])
        except Exception:
            texto = ""
        finally:
            shutil.rmtree(pasta, ignore_errors=True)
        _TEXTOS_SUGESTAO[chave] = texto
    return _TEXTOS_SUGESTAO[chave]


def sugestoes_dropbox(sol, cfg, limite=6, ler_texto=None):
    """NFs do Dropbox que SÃO deste pedido (pedido do usuário, 06/10/2026: nada de "possível" nota).
    O nome do arquivo escolhe as candidatas; fica só a que foi salva perto do pedido e cujo PDF confere
    com ele (CPF/CNPJ do tomador, ou nome + datas/valor — a mesma conferência do robô). Nota escaneada,
    sem texto, não aparece."""
    import types
    from controle_nf import conferir_conteudo, provas_da_solicitacao
    ler_texto = ler_texto or _texto_da_nota_rapido
    raiz = raiz_dropbox(cfg)
    nomes = [n for n in [sol.get("nome", "")] + list(sol.get("nomes", [])) if n]
    alvos = [t for t in (_palavras(n) for n in nomes) if t]
    primeiros = {_primeira_palavra(n) for n in nomes} - {""}
    try:
        dia_pedido = datetime.date.fromisoformat(sol.get("data") or "")
    except ValueError:
        dia_pedido = None
    candidatas = []
    for nome, caminho, mtime, nf in listar_notas_dropbox(cfg):
        nota = _nota(_palavras(nf[1]), alvos, primeiros)
        if not nota:
            continue
        if dia_pedido:
            atraso = (datetime.date.fromtimestamp(mtime) - dia_pedido).days
            if not JANELA_SUGESTAO_DIAS[0] <= atraso <= JANELA_SUGESTAO_DIAS[1]:
                continue
        candidatas.append((nota, mtime, nome, caminho, nf))
    candidatas.sort(key=lambda c: (-c[0], -c[1]))
    alvo = {"nomes": nomes, "data_pedido": sol.get("data", ""),
            **provas_da_solicitacao(types.SimpleNamespace(campos=sol.get("campos", [])))}
    achadas = []
    for nota, mtime, nome, caminho, nf in candidatas[:CANDIDATAS_SUGESTAO]:
        resultado, prova = conferir_conteudo(alvo, ler_texto(caminho, mtime))
        if resultado == "confere":
            achadas.append({"nome": nome, "nf": nf[0], "forte": True, "nota": nota, "prova": prova,
                            "modificado": datetime.datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M"),
                            "rel": os.path.relpath(caminho, raiz) if raiz else caminho})
    return achadas[:limite]


# ---------- fila compartilhada ----------
def evento(quando, id_envio, ev, pc, quem, dados=None):
    return [_iso(quando), id_envio, ev, pc, quem, json.dumps(dados or {}, ensure_ascii=False)]


def dobrar_fila(linhas):
    """-> {id: {"pedido": dados, "pedido_em", "assumido_por", "resultado": ENVIADO|FALHOU|None, "detalhe", "pc"}}"""
    envios = {}
    for l in linhas[1:]:
        l = list(l) + [""] * (6 - len(l))
        quando, id_envio, ev, pc, quem, dados = (str(v) for v in l[:6])
        try:
            dados = json.loads(dados) if dados else {}
        except ValueError:
            dados = {}
        e = envios.setdefault(id_envio, {"pedido": None, "pedido_em": "", "quem": "", "assumido_por": "",
                                         "assumido_em": "", "marca_id": False,
                                         "resultado": None, "detalhe": "", "pc": "", "confirmado": False})
        if ev == PEDIDO and e["pedido"] is None:
            e.update(pedido=dados, pedido_em=quando, quem=quem)
        elif ev == ASSUMIDO and not e["assumido_por"]:
            e["assumido_por"] = pc          # o primeiro gravado vence, como no Assumir da fila
            e["assumido_em"], e["marca_id"] = quando, bool(dados.get("marca_id"))
        elif ev in (ENVIADO, FALHOU) and e["resultado"] is None:
            e.update(resultado=ev, detalhe=dados.get("detalhe", ""), pc=pc,
                     confirmado=ev == ENVIADO and bool(dados.get("confirmado", True)))
        elif ev == CONFIRMADO:
            e["confirmado"] = True
    return envios


def pcs_online(linhas_pcs, agora_=None, segundos=PC_ONLINE_SEGUNDOS):
    """-> {conta: pc} das caixas de PCs com o Painel visto há pouco."""
    agora_ = agora_ or agora()
    contas = {}
    for l in linhas_pcs[1:]:
        l = list(l) + [""] * (4 - len(l))
        pc, _agente, lista, visto = (str(v) for v in l[:4])
        from rede_pcs import _data   # a planilha devolve "2026-10-07 9:10:19" (sem o zero da hora)
        quando = _data(visto)
        if quando is None or agora_ - quando > datetime.timedelta(seconds=segundos):
            continue
        for c in lista.split(","):
            if c.strip():
                contas.setdefault(c.strip().lower(), pc)
    return contas


def partes_do_anexo(id_envio, nome, conteudo):
    b64 = base64.b64encode(conteudo).decode()
    pedacos = [b64[i:i + TAMANHO_PARTE] for i in range(0, len(b64), TAMANHO_PARTE)] or [""]
    return [[id_envio, i + 1, len(pedacos), nome, p] for i, p in enumerate(pedacos)]


def juntar_anexo(linhas_anexos, id_envio):
    partes = sorted((int(l[1]), l) for l in linhas_anexos[1:] if l and str(l[0]) == id_envio and len(l) >= 5 and l[4])
    if not partes or len(partes) != int(partes[0][1][2]):
        return None, None
    return partes[0][1][3], base64.b64decode("".join(l[4] for _, l in partes))


# ---------- Outlook ----------
def contas_do_outlook():
    import pythoncom
    pythoncom.CoInitialize()
    ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
    return [str(c.SmtpAddress or "").strip().lower() for c in ns.Accounts if c.SmtpAddress]


PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"


def tirar_assinatura_automatica(html):
    """O Outlook põe sozinho a assinatura padrão da caixa no Reply()/Forward() (marca "_MailAutoSig"). Somada à do
    Painel, saíam duas assinaturas (usuário, 13/10/2026). -> (html sem ela, cids das imagens dela)."""
    i = html.find("_MailAutoSig")
    if i < 0:
        return html, set()
    inicio = max(html.rfind("<p", 0, i), html.rfind("<div", 0, i))
    fim = -1
    for marca in ("border-top:solid #E1E1E1", "divRplyFwdMsg", "<hr"):
        k = html.find(marca, i)
        if k > 0:
            fim = max(html.rfind("<div", i, k), html.rfind("<p", i, k)) if marca != "<hr" else k
            if fim < i:
                fim = k
            break
    if inicio < 0 or fim < 0:
        return html, set()
    bloco = html[inicio:fim]
    cids = {c.lower() for c in re.findall(r"cid:([^\"'>\s]+)", bloco, re.I)}
    return html[:inicio] + html[fim:], cids


def enviar_pelo_outlook(conta_de, para, cc, assunto, mensagem, anexos, agente="", selo="", responder_a="",
                        encaminhar_de="", id_envio=""):
    """Envia saindo da conta `conta_de` deste Outlook, com a mensagem + o selo escolhido (ou, sem selo,
    a assinatura da caixa no Outlook), imagens embutidas, e os anexos. responder_a / encaminhar_de: EntryID do
    e-mail original (resposta ou encaminhamento de verdade, com o original embaixo). Levanta erro legível."""
    import pythoncom
    pythoncom.CoInitialize()
    outlook = outlook_vivo.aplicativo()
    ns = outlook.GetNamespace("MAPI")
    conta = next((c for c in ns.Accounts if str(c.SmtpAddress or "").strip().lower() == conta_de.lower()), None)
    if conta is None:
        raise RuntimeError(f"a caixa {conta_de} não está no Outlook deste PC")
    original = None
    if responder_a or encaminhar_de:   # mesma conversa, com o histórico do Outlook embaixo
        try:
            original = ns.GetItemFromID(responder_a or encaminhar_de)
        except Exception:
            if encaminhar_de:
                raise RuntimeError("o e-mail a encaminhar não está mais no Outlook deste PC")
            original = None
    if original is None:
        mail = outlook.CreateItem(0)
    else:
        mail = original.Forward() if encaminhar_de else original.Reply()
    historico = mail.HTMLBody if original is not None else ""
    historico, cids_automaticos = tirar_assinatura_automatica(historico)   # só a assinatura escolhida no Painel
    mail.To = para
    if cc:
        mail.CC = cc
    mail.Subject = assunto
    html_assinatura, imagens = "", []
    arquivo_selo = caminho_selo(selo)
    if arquivo_selo:
        mail.HTMLBody = corpo_com_selo(mensagem)
        imagens = [(arquivo_selo, CID_SELO)]
        if historico:
            mail.HTMLBody = re.sub(r"</body>\s*</html>\s*$", "", mail.HTMLBody) + "<br>" + historico
    else:
        caminho_ass = achar_assinatura(conta_de, agente)
        if caminho_ass:
            html_assinatura, imagens = assinatura_html(caminho_ass)
        mail.HTMLBody = corpo_do_email(mensagem, html_assinatura)
        if historico:   # sem selo também: a resposta/encaminhamento leva o e-mail original embaixo
            mail.HTMLBody = re.sub(r"</body>\s*</html>\s*$", "", mail.HTMLBody) + "<br>" + historico
    if cids_automaticos:   # a imagem da assinatura automática vem como anexo escondido: sai junto
        for k in range(mail.Attachments.Count, 0, -1):
            try:
                cid = str(mail.Attachments.Item(k).PropertyAccessor.GetProperty(PR_ATTACH_CONTENT_ID) or "").lower()
            except Exception:
                cid = ""
            if cid and cid in cids_automaticos:
                mail.Attachments.Item(k).Delete()
    for arquivo, cid in imagens:
        anexo_img = mail.Attachments.Add(str(arquivo))
        anexo_img.PropertyAccessor.SetProperty(PR_ATTACH_CONTENT_ID, cid)
    for anexo in anexos:
        mail.Attachments.Add(str(anexo))
    mail._oleobj_.Invoke(*(DISPID_SEND_USING_ACCOUNT, 0, 8, 0, conta))
    try:   # marca invisível: o espelho mostra "pelo Painel" nos Itens enviados
        import espelho_emails
        marca = f"{agente}|{agora().isoformat(timespec='seconds')}" + (f"|{id_envio}" if id_envio else "")
        mail.PropertyAccessor.SetProperty(espelho_emails.MARCA_PAINEL, marca)   # o id: achar o e-mail depois de um reinício
    except Exception:
        logger.debug("marca do Painel no e-mail", exc_info=True)
    mail.Send()
    try:
        ns.SendAndReceive(False)
    except Exception:
        pass


def conferir_envio_painel(conta_de, id_envio, desde):
    """O e-mail do Painel com esse id (na marca invisível) está em Itens Enviados / na Caixa de Saída da caixa? Procura
    na caixa do hotel e na padrão deste Outlook (a cópia do enviado pode ficar em qualquer uma). Itens Enviados é lido do
    mais novo para o mais velho até 1 h antes de `desde`. -> {"enviados", "saida", "completo"}; completo = leu tudo o
    que precisava (sem isso, "não achei" não quer dizer que não saiu)."""
    import pythoncom
    import envio_pc_dono
    import espelho_emails
    pythoncom.CoInitialize()
    ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
    conta = next((c for c in ns.Accounts if str(c.SmtpAddress or "").strip().lower() == str(conta_de).lower()), None)
    if conta is None:
        raise RuntimeError(f"a caixa {conta_de} não está no Outlook deste PC")
    fim, limite = f"|{id_envio}", desde - datetime.timedelta(hours=1)
    completo = True

    def tem(tipo):
        nonlocal completo
        for pasta in envio_pc_dono._pastas(ns, conta, tipo):
            try:
                itens = pasta.Items
                if tipo == envio_pc_dono.PASTA_ENVIADOS:
                    itens.Sort("[SentOn]", True)
            except Exception:
                completo = False
                continue
            for i, item in enumerate(itens):
                if i >= MAX_ITENS_CONFERIDOS:
                    completo = False
                    break
                try:
                    if str(item.PropertyAccessor.GetProperty(espelho_emails.MARCA_PAINEL) or "").endswith(fim):
                        return True
                except Exception:
                    pass
                if tipo == envio_pc_dono.PASTA_ENVIADOS:
                    try:
                        enviado = espelho_emails._data(item.SentOn)
                    except Exception:
                        enviado = None
                    if enviado and enviado < limite:
                        break
        return False
    enviados = tem(envio_pc_dono.PASTA_ENVIADOS)
    saida = tem(envio_pc_dono.PASTA_CAIXA_SAIDA)
    return {"enviados": enviados, "saida": saida, "completo": completo}


def excluir_no_outlook(entry_id):
    """Move o e-mail pra Itens Excluídos (o Outlook guarda; dá pra recuperar de lá)."""
    import pythoncom
    pythoncom.CoInitialize()
    ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
    try:
        item = ns.GetItemFromID(entry_id)
    except Exception:
        return False   # já não está mais lá (alguém excluiu/moveu pelo Outlook): nada a fazer
    item.Delete()
    return True


def marcar_urgencia_no_outlook(entry_id, marcar):
    """Põe a categoria de urgência no e-mail (tira a outra). marcar: "urgente" | "normal". Só mexe nas categorias."""
    import espelho_emails
    import pythoncom
    pythoncom.CoInitialize()
    ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
    try:
        item = ns.GetItemFromID(entry_id)
    except Exception:
        return False   # já não está mais lá
    nova = espelho_emails.CATEGORIA_URGENTE if marcar == "urgente" else espelho_emails.CATEGORIA_SEM_URGENCIA
    try:
        if nova not in {c.Name for c in ns.Categories}:
            ns.Categories.Add(nova, 1 if marcar == "urgente" else 0)   # 1 = vermelho
    except Exception:
        pass   # sem a lista mestra, a categoria funciona igual
    atuais = [c.strip() for c in re.split(r"[;,]", str(item.Categories or "")) if c.strip() and c.strip() not in espelho_emails.MARCAS]
    item.Categories = ", ".join(atuais + [nova])
    item.Save()
    return True


# ---------- pedido ----------
def novo_id():
    return "ENV-" + uuid.uuid4().hex[:10].upper()


def numeros_de_nf(assunto, anexos):
    """NFs do envio: a do assunto e as dos nomes dos arquivos ("NF 1212 - NOME.pdf") — nota dividida tem várias."""
    numeros = []
    for texto in [assunto] + [os.path.splitext(a.get("nome", ""))[0] for a in anexos]:
        nf = ler_assunto_nf(texto or "")
        if nf and nf[0] not in numeros:
            numeros.append(nf[0])
    return numeros


def montar_pedido(sol, para, cc, assunto, conta_de, anexos, mensagem, selo="", responder="", acao=""):
    """anexos: [{"tipo": "dropbox", "rel", "nome"} | {"tipo": "planilha"|"local", "nome", ...}]
    acao: "" (enviar/responder) | "encaminhar" | "excluir" — responder = id do e-mail do espelho."""
    return {"aba": sol["aba"], "carimbo": sol["carimbo"], "email": sol["email"], "hotel": sol["hotel"],
            "nome": sol["nome"], "para": para, "cc": cc, "assunto": assunto, "conta_de": conta_de,
            "anexos": anexos, "nfs": numeros_de_nf(assunto, anexos) if not acao else [], "mensagem": mensagem,
            "selo": selo, "responder": responder, "acao": acao}


def arquivos_do_pedido(pedido, cfg, linhas_anexos, id_envio):
    """Caminhos locais dos anexos (cópia temporária quando vêm da planilha)."""
    caminhos = []
    for i, anexo in enumerate(pedido["anexos"]):
        if anexo["tipo"] == "local":
            caminhos.append(Path(anexo["caminho"]))
        elif anexo["tipo"] == "dropbox":
            raiz = raiz_dropbox(cfg)
            caminho = (raiz / anexo["rel"]) if raiz else Path(anexo["rel"])
            if not caminho.exists():
                raise RuntimeError(f"não achei a nota no Dropbox deste PC ({anexo['rel']}) — ele já sincronizou?")
            caminhos.append(caminho)
        else:
            nome, conteudo = juntar_anexo(linhas_anexos, f"{id_envio}#{i}")
            if conteudo is None:
                raise RuntimeError(f"o anexo {anexo.get('nome', '')} não chegou inteiro na planilha")
            destino = Path(tempfile.mkdtemp(prefix="nf_envio_")) / os.path.basename(nome or "nota.pdf")
            destino.write_bytes(conteudo)
            caminhos.append(destino)
    return caminhos


class ServicoEnvio:
    """Roda dentro do Painel de cada PC (thread do laço de atualização)."""
    avisar_dono = None                         # o Painel liga: (pc, corpo) -> resposta do PC dono pela rede
    conferir_envio = None                      # os testes trocam: (conta, id, desde) -> {"enviados", "saida", "completo"}
    reconferir_apos, falhou_apos = RECONFERIR_ENVIO_APOS, FALHOU_SEM_ACHAR_APOS

    def __init__(self, backend, cfg, pc, ao_registrar_nf, enviar=None, ler_contas=None, relogio=agora):
        self.backend, self.cfg, self.pc = backend, cfg, pc
        self.central = cfg["planilha_central_id"]
        self.ao_registrar_nf = ao_registrar_nf        # (pedido, quem) -> grava NF/OBS na aba Tratamento
        # resolvidos na hora da chamada (os testes trocam as funções do módulo)
        self.enviar = enviar or (lambda *a, **k: enviar_pelo_outlook(*a, **k))
        self.excluir = lambda entry: excluir_no_outlook(entry)
        self.marcar_urgencia = lambda entry, marcar: marcar_urgencia_no_outlook(entry, marcar)
        self.ler_contas = ler_contas or (lambda: contas_do_outlook())
        self.relogio = relogio
        self.agente = ""
        self.contas, self.contas_lidas_em = [], None
        self.fila, self.pcs_linhas, self.publicado_em = {}, [[]], None
        self.locais = {}                               # id -> resultado de envios feitos aqui (resposta imediata)
        self.caixas_de_hotel = lambda: {}              # o Painel troca: {caixa: hotel} do cadastro (e-mail do robô)
        self.reconferidos = {}                         # id -> quando conferiu de novo um e-mail do robô sem confirmação
        self.lock = threading.Lock()

    # chamado a cada volta do laço do Painel, com as abas já lidas no batch da Central
    def tick(self, lidas, agente):
        self.agente = agente
        self.fila = dobrar_fila(lidas.get(ABA_FILA, [[]]))
        self.pcs_linhas = lidas.get(ABA_PCS, [[]])
        self._ler_contas(datetime.timedelta(minutes=10))
        if self.publicado_em is None or self.relogio() - self.publicado_em > datetime.timedelta(seconds=60):
            self._publicar(agente)
        self.executar_pendentes()
        try:
            listar_notas_dropbox(self.cfg)   # deixa a lista do Dropbox pronta pro "Enviar NF" abrir na hora
        except Exception:
            logger.debug("listagem do Dropbox falhou", exc_info=True)

    def _publicar(self, agente):
        extras = getattr(self, "extras", None)
        linha = [self.pc, agente, ",".join(self.contas), _iso(self.relogio())] + (list(extras()) if extras else [])
        idx = next((i for i, l in enumerate(self.pcs_linhas[1:], start=2) if l and str(l[0]) == self.pc), None)
        from sheets import nome_intervalo
        if idx:
            self.backend.escrever(self.central, [(f"{nome_intervalo(ABA_PCS)}!{c}{idx}", v) for c, v in zip("ABCDEFGHIJKL", linha)])   # L = Saúde
        else:
            self.backend.anexar_linhas(self.central, ABA_PCS, [linha])
        self.publicado_em = self.relogio()

    def _ler_contas(self, validade):
        if self.contas_lidas_em is None or self.relogio() - self.contas_lidas_em > validade:
            try:
                self.contas = self.ler_contas()
            except Exception as e:
                logger.warning(f"⚠️ Não consegui ler as contas do Outlook ({e})")
            self.contas_lidas_em = self.relogio()

    def destino_para(self, conta_de, aceitar_desligado=False):
        """-> (pc que envia | None, motivo). aceitar_desligado: o PC dono está desligado, mas o pedido pode
        esperar na fila (até FILA_ESPERA_HORAS) e sai quando ele ligar."""
        self._ler_contas(datetime.timedelta(minutes=10))   # janela aberta antes da 1ª volta do laço
        conta_de = (conta_de or "").lower()
        if conta_de in self.contas:
            return self.pc, ""
        pc = pcs_online(self.pcs_linhas, self.relogio()).get(conta_de)
        if pc:
            return pc, ""
        dono = pcs_online(self.pcs_linhas, self.relogio(), segundos=10 ** 9).get(conta_de)
        if dono and aceitar_desligado:
            return dono, f"O PC {dono} está desligado agora: o pedido fica na fila e sai quando ele ligar (até 24 h)."
        return None, (f"Nenhum PC ligado agora tem a caixa {conta_de} no Outlook (o Painel do PC dela precisa"
                      f" estar aberto/rodando).")

    def pedir(self, sol, para, assunto, conta_de, anexos_entrada, quem, mensagem=None, cc="", selo="", responder="",
              acao="", livre=False):
        """responder: id do e-mail do espelho (espelho_emails) — sai como resposta, anexo opcional.
        acao: "encaminhar" | "excluir" (no Outlook do PC dono). anexos_entrada: [{"tipo": "dropbox", "rel", "nome"} |
        {"tipo": "arquivo", "nome", "conteudo": bytes}]. PC dono desligado: o pedido espera na fila."""
        destino, motivo = self.destino_para(conta_de, aceitar_desligado=True)
        if not destino:
            return {"ok": False, "motivo": motivo, "contas_locais": self.contas}
        if not anexos_entrada and not responder and not livre:
            return {"ok": False, "motivo": "Anexe a nota fiscal."}
        if sum(len(a.get("conteudo", b"")) for a in anexos_entrada) > MAX_ANEXO_BYTES:
            return {"ok": False, "motivo": "Os anexos passam de 8 MB."}
        id_envio = novo_id()
        anexos, partes = [], []
        for i, a in enumerate(anexos_entrada):
            if a["tipo"] == "dropbox":
                anexos.append({"tipo": "dropbox", "rel": a["rel"], "nome": a.get("nome") or os.path.basename(a["rel"])})
            elif destino == self.pc:
                caminho = Path(tempfile.mkdtemp(prefix="nf_envio_")) / os.path.basename(a["nome"])
                caminho.write_bytes(a["conteudo"])
                anexos.append({"tipo": "local", "caminho": str(caminho), "nome": a["nome"]})
            else:
                partes += partes_do_anexo(f"{id_envio}#{i}", a["nome"], a["conteudo"])
                anexos.append({"tipo": "planilha", "nome": a["nome"]})
        if partes:
            self.backend.anexar_linhas(self.central, ABA_ANEXOS, partes)
        pedido = montar_pedido(sol, para, cc, assunto, conta_de, anexos,
                               mensagem if (responder or livre) else (mensagem or mensagem_padrao(self.cfg)), selo, responder, acao)
        pedido["pc_destino"] = destino
        self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, PEDIDO, self.pc, quem, pedido)])
        if destino == self.pc:
            self.fila[id_envio] = {"pedido": pedido, "pedido_em": _iso(self.relogio()), "quem": quem,
                                   "assumido_por": "", "resultado": None, "detalhe": "", "pc": ""}
            threading.Thread(target=self._executar, args=(id_envio, self.fila[id_envio]), daemon=True).start()
        elif self.avisar_dono:   # o PEDIDO já está gravado: o aviso pela rede só adianta a vez do PC dono
            threading.Thread(target=self._acordar_dono, args=(destino, id_envio), daemon=True).start()
        return {"ok": True, "id": id_envio, "destino": destino, "aviso": motivo}

    def _acordar_dono(self, destino, id_envio):
        """Envio direto: avisa o PC dono pela rede. Erro ou demora = ele pega na próxima leitura da fila, como antes;
        daqui nunca sai e-mail, nem se tenta de novo (quem envia é só o PC dono)."""
        try:
            r = self.avisar_dono(destino, {"id": id_envio}) or {}
        except Exception as e:
            logger.info(f"ℹ️ {id_envio}: a rede não chegou no PC {destino} ({str(e)[:80]}) — segue pela fila")
            return
        if r.get("estado") in ("enviado", "falhou"):   # resposta na hora pra tela de quem pediu
            with self.lock:
                self.locais.setdefault(id_envio, {"estado": r["estado"], "detalhe": r.get("detalhe", ""),
                                                  "pc": r.get("pc") or destino})

    def receber_pela_rede(self, corpo):
        """O PC que pediu avisou pela rede (envio direto, 21/10/2026). Vale o que está gravado na fila, não o que veio
        pela rede: relê a Envios_NF e só envia pedido deste PC que ninguém assumiu, pelo mesmo _executar da fila (trava
        + ASSUMIDO antes de enviar + self.locais). Chegar pela rede e pela fila nunca manda duas vezes."""
        id_envio = str((corpo or {}).get("id") or "")
        if not id_envio.startswith("ENV-"):
            return {"ok": False, "estado": "recusado", "detalhe": "pedido sem id"}
        if id_envio in self.locais:
            return {"ok": True, **self.locais[id_envio], "pc": self.pc}
        linhas = self.backend.ler_abas(self.central, [ABA_FILA])[0].get(ABA_FILA, [[]])
        e = dobrar_fila(linhas).get(id_envio)
        if not e or not e["pedido"]:
            return {"ok": False, "estado": "recusado", "detalhe": "o pedido não está na fila Envios_NF"}
        p = e["pedido"]
        if e["resultado"] or e["assumido_por"]:   # a fila já andou com ele (inclusive antes de um reinício)
            return {"ok": True, **self.situacao(id_envio, {id_envio: e}), "pc": self.pc}
        if p.get("pc_destino") != self.pc or p.get("acao") == ACAO_FORMULARIO:
            return {"ok": False, "estado": "recusado", "detalhe": "não é pedido para este PC"}
        self._ler_contas(datetime.timedelta(minutes=10))
        if str(p.get("conta_de") or "").lower() not in {str(c).lower() for c in self.contas}:
            return {"ok": False, "estado": "recusado", "detalhe": "a caixa do hotel não está no Outlook deste PC"}
        self._executar(id_envio, e)
        return {"ok": True, **self.locais.get(id_envio, {"estado": "enviando"}), "pc": self.pc}

    def executar_pendentes(self):
        for id_envio, e in list(self.fila.items()):
            p = e["pedido"]
            if p and p.get("acao") == ACAO_FORMULARIO:   # e-mail do robô: o PC dono vem em "pc_formulario"
                if p.get("pc_formulario") != self.pc:
                    continue
                if e["resultado"] == ENVIADO and not e["confirmado"] and e["pc"] == self.pc:
                    self._reconferir_formulario(id_envio, p)
                    continue
                if e["assumido_por"] == self.pc and not e["resultado"] and id_envio not in self.locais:
                    self._reconferir_formulario(id_envio, p, interrompido=e)   # o Painel reiniciou no meio do envio
                    continue
                p = {**p, "pc_destino": self.pc}   # daqui pra baixo, um pedido deste PC como outro qualquer
                e = {**e, "pedido": p}
            if not p or e["resultado"] or p.get("pc_destino") != self.pc or id_envio in self.locais:
                continue
            if e["assumido_por"] and e["assumido_por"] != self.pc:
                continue
            if e["assumido_por"] == self.pc:   # já assumido aqui numa volta anterior: não reenvia
                if e.get("marca_id") and p.get("acao", "") in ("", ENCAMINHAR):
                    self._reconferir_envio(id_envio, e)   # o Painel caiu no meio? confere em Itens Enviados
                continue
            try:
                velho = self.relogio() - datetime.datetime.fromisoformat(e["pedido_em"]) > \
                    datetime.timedelta(hours=FILA_ESPERA_HORAS)
            except ValueError:
                velho = False
            if velho:   # ficou na fila com este PC desligado por mais de 24 h: não sai mais (pode estar desatualizado)
                self.locais[id_envio] = {"estado": "falhou", "detalhe": "expirou", "pc": self.pc}
                self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, FALHOU, self.pc, e["quem"],
                                                                         {"detalhe": "expirou: o PC ficou desligado mais de 24 h"})])
                continue
            self._executar(id_envio, e)

    def _executar(self, id_envio, e):
        with self.lock:
            if id_envio in self.locais:
                return
            self.locais[id_envio] = {"estado": "enviando"}
        p = e["pedido"]
        self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, ASSUMIDO, self.pc, e["quem"],
                                                                 {"marca_id": True})])   # o e-mail leva o id: dá pra achar
        na_planilha = any(a["tipo"] == "planilha" for a in p["anexos"])
        resultado = {}
        try:
            import espelho_emails
            acao = p.get("acao", "")
            if acao == ACAO_FORMULARIO:   # e-mail do robô: o HTML pronto, da caixa do hotel para ela mesma
                linhas = self.backend.ler_abas(self.central, [ABA_ANEXOS])[0].get(ABA_ANEXOS, [[]])
                _nome, html = juntar_anexo(linhas, f"{id_envio}#0")
                if html is None:
                    raise RuntimeError("o texto do e-mail do robô não está na aba Envios_NF_Anexos")
                import envio_pc_dono
                corpo = {"codigo": p.get("codigo", ""), "para": p["para"], "assunto": p["assunto"],
                         "html": html.decode("utf-8")}
                enviar = getattr(self, "enviar_formulario", None) or envio_pc_dono.enviar_e_conferir
                resultado = {"confirmado": bool(enviar(corpo, self.caixas_de_hotel()))}
            elif acao == EXCLUIR:
                entry = espelho_emails.entry_do_email(p["responder"])
                if entry:
                    self.excluir(entry)
            elif acao == URGENCIA:
                entry = espelho_emails.entry_do_email(p["responder"])
                if entry:
                    self.marcar_urgencia(entry, p.get("mensagem", ""))
            else:
                linhas = self.backend.ler_abas(self.central, [ABA_ANEXOS])[0].get(ABA_ANEXOS, [[]]) if na_planilha else [[]]
                arquivos = arquivos_do_pedido(p, self.cfg, linhas, id_envio)
                extra = {}
                if p.get("responder"):
                    entry = p.get("entry") or espelho_emails.entry_do_email(p["responder"])
                    extra["encaminhar_de" if acao == ENCAMINHAR else "responder_a"] = entry
                    if acao == ENCAMINHAR and not entry:
                        raise RuntimeError("o e-mail a encaminhar não está mais no espelho deste PC")
                self.enviar(p["conta_de"], p["para"], p.get("cc", ""), p["assunto"], p["mensagem"], arquivos,
                            agente=self.agente, selo=p.get("selo", ""), id_envio=id_envio, **extra)
        except Exception as erro:
            detalhe = str(erro)[:300]
            logger.warning(f"⚠️ Envio {id_envio} falhou: {detalhe}")
            self.backend.anexar_linhas(self.central, ABA_FILA,
                                       [evento(self.relogio(), id_envio, FALHOU, self.pc, e["quem"], {"detalhe": detalhe})])
            self.locais[id_envio] = {"estado": "falhou", "detalhe": detalhe, "pc": self.pc}
            return
        self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, ENVIADO, self.pc, e["quem"],
                                                                 resultado or None)])
        self.locais[id_envio] = {"estado": "enviado", "pc": self.pc}
        if p.get("acao") == ACAO_FORMULARIO:
            logger.info(f"📤 {id_envio} ({p.get('codigo')}): e-mail do robô saiu de {p['conta_de']} (pela fila)"
                        + ("" if resultado.get("confirmado") else " — ainda sem aparecer em Itens Enviados"))
            self._apagar_anexos(id_envio)
            return
        if p.get("acao") == URGENCIA:   # só categoria: não é NF, não registra nada
            logger.info(f"🚩 {id_envio}: e-mail \"{p['assunto']}\" de {p['conta_de']} marcado como "
                        f"{'urgente' if p.get('mensagem') == 'urgente' else 'sem urgência'} (pedido de {e['quem']})")
            return
        if p.get("acao") == EXCLUIR:
            logger.info(f"🗑️ {id_envio}: e-mail \"{p['assunto']}\" de {p['conta_de']} movido pra Itens Excluídos "
                        f"(pedido de {e['quem']})")
            return
        logger.info(f"📧 {id_envio}: \"{p['assunto']}\" enviado de {p['conta_de']} para {p['para']}")
        try:
            if p.get("acao") != ENCAMINHAR:
                self.ao_registrar_nf(p, e["quem"])
        except Exception:
            logger.exception("NF enviada, mas não consegui registrar na aba Tratamento")
        if na_planilha:
            self._apagar_anexos(id_envio)

    def _reconferir_formulario(self, id_envio, p, interrompido=None):
        """E-mail do robô que saiu daqui sem aparecer em Itens Enviados: confere de novo (1 vez por minuto) e, quando
        aparecer, grava CONFIRMADO (o robô só marca TRUE com a confirmação). interrompido: pedido ASSUMIDO aqui que
        nunca terminou (o Painel reiniciou no meio): está em Enviados = ENVIADO; nem lá nem na Caixa de Saída = FALHOU
        (não saiu, o robô manda de novo); na Caixa de Saída = espera."""
        import time as _time
        if _time.monotonic() - self.reconferidos.get(id_envio, -1e9) < RECONFERIR_SEGUNDOS:
            return
        self.reconferidos[id_envio] = _time.monotonic()
        try:
            import envio_pc_dono
            conferir = getattr(self, "conferir_formulario", None) or envio_pc_dono.conferir_local
            r = conferir({"codigo": p.get("codigo", ""), "para": p["para"]}, self.caixas_de_hotel())
            if interrompido is not None:
                if r.get("enviados"):
                    ev, dados = ENVIADO, {"confirmado": True}
                elif not r.get("saida"):
                    ev, dados = FALHOU, {"detalhe": "não saiu: o Painel reiniciou no meio do envio"}
                else:
                    return
                self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, ev, self.pc,
                                                                         interrompido.get("quem", "Robô"), dados)])
                self.locais[id_envio] = {"estado": "enviado" if ev == ENVIADO else "falhou", "pc": self.pc}
            elif r.get("enviados"):
                self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, CONFIRMADO, self.pc, "Robô")])
                self.fila.get(id_envio, {})["confirmado"] = True
        except Exception as e:
            logger.warning(f"⚠️ Não consegui conferir o e-mail do robô {p.get('codigo')} ({e})")

    def _reconferir_envio(self, id_envio, e):
        """E-mail do Painel ASSUMIDO aqui que nunca terminou: o Painel reiniciou entre o envio e o ENVIADO (21/10/2026, a
        simulação do envio direto achou a janela). Procura pela marca invisível com o id: achou = ENVIADO e a NF
        registrada, como num envio normal; nem em Itens Enviados nem na Caixa de Saída 5 min depois de assumido =
        FALHOU pedindo para conferir. Outlook fora, Caixa de Saída ou leitura incompleta = espera. Nunca envia de novo."""
        import time as _time
        if _time.monotonic() - self.reconferidos.get(id_envio, -1e9) < RECONFERIR_SEGUNDOS:
            return
        try:
            assumido = datetime.datetime.fromisoformat(e.get("assumido_em") or e["pedido_em"])
        except ValueError:
            return
        idade = (self.relogio() - assumido).total_seconds()
        if idade < self.reconferir_apos:
            return
        self.reconferidos[id_envio] = _time.monotonic()
        p = e["pedido"]
        try:
            r = (self.conferir_envio or conferir_envio_painel)(p["conta_de"], id_envio, assumido)
        except Exception as erro:
            logger.warning(f"⚠️ Não consegui conferir o envio interrompido {id_envio} ({erro})")
            return
        if r.get("enviados"):
            self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, ENVIADO, self.pc, e["quem"],
                                       {"confirmado": True, "detalhe": "achado em Itens Enviados depois de um reinício"})])
            self.locais[id_envio] = {"estado": "enviado", "pc": self.pc}
            logger.info(f"📧 {id_envio}: \"{p['assunto']}\" já tinha saído (achado em Itens Enviados depois de um reinício)")
            try:
                if p.get("acao") != ENCAMINHAR:
                    self.ao_registrar_nf(p, e["quem"])
            except Exception:
                logger.exception("NF enviada, mas não consegui registrar na aba Tratamento")
            if any(a["tipo"] == "planilha" for a in p["anexos"]):
                self._apagar_anexos(id_envio)
        elif not r.get("saida") and r.get("completo") and idade >= self.falhou_apos:
            detalhe = ("não saiu: o Painel reiniciou no meio do envio e o e-mail não está em Itens Enviados nem na Caixa"
                       " de Saída — confira lá antes de mandar de novo")
            self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, FALHOU, self.pc, e["quem"],
                                                                     {"detalhe": detalhe})])
            self.locais[id_envio] = {"estado": "falhou", "detalhe": detalhe, "pc": self.pc}
            logger.warning(f"⚠️ {id_envio}: {detalhe}")

    def _apagar_anexos(self, id_envio):
        from sheets import nome_intervalo
        linhas = self.backend.ler_abas(self.central, [ABA_ANEXOS])[0].get(ABA_ANEXOS, [[]])
        alvos = [i for i, l in enumerate(linhas[1:], start=2) if l and str(l[0]).split("#")[0] == id_envio]
        if alvos:
            self.backend.escrever(self.central, [(f"{nome_intervalo(ABA_ANEXOS)}!E{i}", "") for i in alvos])

    def situacao(self, id_envio, fila_fresca=None):
        """-> {"estado": aguardando|enviando|enviado|falhou|sem_resposta, "detalhe", "pc"}"""
        if id_envio in self.locais and self.locais[id_envio]["estado"] != "enviando":
            return self.locais[id_envio]
        e = (fila_fresca or self.fila).get(id_envio)
        if not e:
            return {"estado": "aguardando", "detalhe": ""}
        if e["resultado"] == ENVIADO:
            return {"estado": "enviado", "pc": e["pc"]}
        if e["resultado"] == FALHOU:
            return {"estado": "falhou", "detalhe": e["detalhe"], "pc": e["pc"], "contas_locais": self.contas}
        if e["assumido_por"]:
            return {"estado": "enviando", "pc": e["assumido_por"]}
        try:
            espera = (self.relogio() - datetime.datetime.fromisoformat(e["pedido_em"])).total_seconds()
        except ValueError:
            espera = 0
        destino = e["pedido"].get("pc_destino", "")
        if destino and destino not in pcs_online(self.pcs_linhas, self.relogio()).values() and destino != self.pc:
            return {"estado": "na_fila", "pc": destino,
                    "detalhe": f"O PC {destino} está desligado: o pedido sai quando ele ligar (até 24 h)."}
        if espera > SEM_RESPOSTA_SEGUNDOS:
            return {"estado": "sem_resposta", "contas_locais": self.contas,
                    "detalhe": f"O PC {e['pedido'].get('pc_destino')} não respondeu em {SEM_RESPOSTA_SEGUNDOS}s "
                               f"(desligado ou Painel fechado)."}
        return {"estado": "aguardando", "pc": e["pedido"].get("pc_destino", "")}
