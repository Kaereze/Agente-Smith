"""Envio da NF ao hóspede pelo Painel, saindo da caixa do próprio hotel.

Se a caixa do hotel está no Outlook deste PC, envia na hora. Se está em outro PC, o pedido vai pra
fila compartilhada (aba Envios_NF da Central) e o Painel daquele PC envia. Cada Painel publica na aba
PCs_Painel quais caixas tem, pra quem pede saber se existe um PC ligado capaz de enviar.

Envios_NF é append-only, como a aba Tratamento: PEDIDO, ASSUMIDO, ENVIADO, FALHOU. Anexo vindo do
Dropbox viaja como caminho relativo (cada PC lê do seu Dropbox); arquivo do computador viaja em partes
na aba Envios_NF_Anexos e é apagado depois do envio.
"""
import base64
import datetime
import json
import os
import re
import tempfile
import uuid
from pathlib import Path

from controle_nf import _tokens, ler_assunto_nf
from log_util import configurar_logging

logger = configurar_logging("envio_nf")

ABA_FILA = "Envios_NF"
CAB_FILA = ["Quando", "ID", "Evento", "PC", "Quem", "Dados (JSON)"]
ABA_ANEXOS = "Envios_NF_Anexos"
CAB_ANEXOS = ["ID", "Parte", "Total", "Nome", "Base64"]
ABA_PCS = "PCs_Painel"
CAB_PCS = ["PC", "Agente", "Contas", "Visto em", "Outlook", "Versão", "Papel", "Última conferência"]

PEDIDO, ASSUMIDO, ENVIADO, FALHOU = "PEDIDO", "ASSUMIDO", "ENVIADO", "FALHOU"
TAMANHO_PARTE = 45_000            # limite de célula do Sheets é 50 mil caracteres
MAX_ANEXO_BYTES = 8 * 1024 * 1024
PC_ONLINE_SEGUNDOS = 180
SEM_RESPOSTA_SEGUNDOS = 90
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
LARGURA_SELO = 460


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
                                         "resultado": None, "detalhe": "", "pc": ""})
        if ev == PEDIDO and e["pedido"] is None:
            e.update(pedido=dados, pedido_em=quando, quem=quem)
        elif ev == ASSUMIDO and not e["assumido_por"]:
            e["assumido_por"] = pc          # o primeiro gravado vence, como no Assumir da fila
        elif ev in (ENVIADO, FALHOU) and e["resultado"] is None:
            e.update(resultado=ev, detalhe=dados.get("detalhe", ""), pc=pc)
    return envios


def pcs_online(linhas_pcs, agora_=None, segundos=PC_ONLINE_SEGUNDOS):
    """-> {conta: pc} das caixas de PCs com o Painel visto há pouco."""
    agora_ = agora_ or agora()
    contas = {}
    for l in linhas_pcs[1:]:
        l = list(l) + [""] * (4 - len(l))
        pc, _agente, lista, visto = (str(v) for v in l[:4])
        try:
            if agora_ - datetime.datetime.fromisoformat(visto) > datetime.timedelta(seconds=segundos):
                continue
        except ValueError:
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
    import win32com.client
    pythoncom.CoInitialize()
    ns = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
    return [str(c.SmtpAddress or "").strip().lower() for c in ns.Accounts if c.SmtpAddress]


PR_ATTACH_CONTENT_ID = "http://schemas.microsoft.com/mapi/proptag/0x3712001F"


def enviar_pelo_outlook(conta_de, para, cc, assunto, mensagem, anexos, agente="", selo=""):
    """Envia saindo da conta `conta_de` deste Outlook, com a mensagem + o selo escolhido (ou, sem selo,
    a assinatura da caixa no Outlook), imagens embutidas, e os anexos. Levanta erro legível."""
    import pythoncom
    import win32com.client
    pythoncom.CoInitialize()
    outlook = win32com.client.Dispatch("Outlook.Application")
    ns = outlook.GetNamespace("MAPI")
    conta = next((c for c in ns.Accounts if str(c.SmtpAddress or "").strip().lower() == conta_de.lower()), None)
    if conta is None:
        raise RuntimeError(f"a caixa {conta_de} não está no Outlook deste PC")
    mail = outlook.CreateItem(0)
    mail.To = para
    if cc:
        mail.CC = cc
    mail.Subject = assunto
    html_assinatura, imagens = "", []
    arquivo_selo = caminho_selo(selo)
    if arquivo_selo:
        mail.HTMLBody = corpo_com_selo(mensagem)
        imagens = [(arquivo_selo, CID_SELO)]
    else:
        caminho_ass = achar_assinatura(conta_de, agente)
        if caminho_ass:
            html_assinatura, imagens = assinatura_html(caminho_ass)
        mail.HTMLBody = corpo_do_email(mensagem, html_assinatura)
    for arquivo, cid in imagens:
        anexo_img = mail.Attachments.Add(str(arquivo))
        anexo_img.PropertyAccessor.SetProperty(PR_ATTACH_CONTENT_ID, cid)
    for anexo in anexos:
        mail.Attachments.Add(str(anexo))
    mail._oleobj_.Invoke(*(DISPID_SEND_USING_ACCOUNT, 0, 8, 0, conta))
    mail.Send()
    try:
        ns.SendAndReceive(False)
    except Exception:
        pass


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


def montar_pedido(sol, para, cc, assunto, conta_de, anexos, mensagem, selo=""):
    """anexos: [{"tipo": "dropbox", "rel", "nome"} | {"tipo": "planilha"|"local", "nome", ...}]"""
    return {"aba": sol["aba"], "carimbo": sol["carimbo"], "email": sol["email"], "hotel": sol["hotel"],
            "nome": sol["nome"], "para": para, "cc": cc, "assunto": assunto, "conta_de": conta_de,
            "anexos": anexos, "nfs": numeros_de_nf(assunto, anexos), "mensagem": mensagem, "selo": selo}


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

    def __init__(self, backend, cfg, pc, ao_registrar_nf, enviar=None, ler_contas=None, relogio=agora):
        self.backend, self.cfg, self.pc = backend, cfg, pc
        self.central = cfg["planilha_central_id"]
        self.ao_registrar_nf = ao_registrar_nf        # (pedido, quem) -> grava NF/OBS na aba Tratamento
        # resolvidos na hora da chamada (os testes trocam as funções do módulo)
        self.enviar = enviar or (lambda *a, **k: enviar_pelo_outlook(*a, **k))
        self.ler_contas = ler_contas or (lambda: contas_do_outlook())
        self.relogio = relogio
        self.agente = ""
        self.contas, self.contas_lidas_em = [], None
        self.fila, self.pcs_linhas, self.publicado_em = {}, [[]], None
        self.locais = {}                               # id -> resultado de envios feitos aqui (resposta imediata)
        import threading
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
            self.backend.escrever(self.central, [(f"{nome_intervalo(ABA_PCS)}!{c}{idx}", v) for c, v in zip("ABCDEFGH", linha)])
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

    def destino_para(self, conta_de):
        """-> (pc que envia | None, motivo)"""
        self._ler_contas(datetime.timedelta(minutes=10))   # janela aberta antes da 1ª volta do laço
        conta_de = (conta_de or "").lower()
        if conta_de in self.contas:
            return self.pc, ""
        pc = pcs_online(self.pcs_linhas, self.relogio()).get(conta_de)
        if pc:
            return pc, ""
        return None, (f"Nenhum PC ligado agora tem a caixa {conta_de} no Outlook (o Painel do PC dela precisa"
                      f" estar aberto/rodando).")

    def pedir(self, sol, para, assunto, conta_de, anexos_entrada, quem, mensagem=None, cc="", selo=""):
        """anexos_entrada: [{"tipo": "dropbox", "rel", "nome"} | {"tipo": "arquivo", "nome", "conteudo": bytes}]"""
        destino, motivo = self.destino_para(conta_de)
        if not destino:
            return {"ok": False, "motivo": motivo, "contas_locais": self.contas}
        if not anexos_entrada:
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
        pedido = montar_pedido(sol, para, cc, assunto, conta_de, anexos, mensagem or mensagem_padrao(self.cfg), selo)
        pedido["pc_destino"] = destino
        self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, PEDIDO, self.pc, quem, pedido)])
        if destino == self.pc:
            import threading
            self.fila[id_envio] = {"pedido": pedido, "pedido_em": _iso(self.relogio()), "quem": quem,
                                   "assumido_por": "", "resultado": None, "detalhe": "", "pc": ""}
            threading.Thread(target=self._executar, args=(id_envio, self.fila[id_envio]), daemon=True).start()
        return {"ok": True, "id": id_envio, "destino": destino}

    def executar_pendentes(self):
        for id_envio, e in list(self.fila.items()):
            p = e["pedido"]
            if not p or e["resultado"] or p.get("pc_destino") != self.pc or id_envio in self.locais:
                continue
            if e["assumido_por"] and e["assumido_por"] != self.pc:
                continue
            if e["assumido_por"] == self.pc:
                continue   # já assumido por este PC numa volta anterior: não reenvia
            self._executar(id_envio, e)

    def _executar(self, id_envio, e):
        with self.lock:
            if id_envio in self.locais:
                return
            self.locais[id_envio] = {"estado": "enviando"}
        p = e["pedido"]
        self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, ASSUMIDO, self.pc, e["quem"])])
        na_planilha = any(a["tipo"] == "planilha" for a in p["anexos"])
        try:
            linhas = self.backend.ler_abas(self.central, [ABA_ANEXOS])[0].get(ABA_ANEXOS, [[]]) if na_planilha else [[]]
            arquivos = arquivos_do_pedido(p, self.cfg, linhas, id_envio)
            self.enviar(p["conta_de"], p["para"], p.get("cc", ""), p["assunto"], p["mensagem"], arquivos,
                        agente=self.agente, selo=p.get("selo", ""))
        except Exception as erro:
            detalhe = str(erro)[:300]
            logger.warning(f"⚠️ Envio {id_envio} falhou: {detalhe}")
            self.backend.anexar_linhas(self.central, ABA_FILA,
                                       [evento(self.relogio(), id_envio, FALHOU, self.pc, e["quem"], {"detalhe": detalhe})])
            self.locais[id_envio] = {"estado": "falhou", "detalhe": detalhe, "pc": self.pc}
            return
        self.backend.anexar_linhas(self.central, ABA_FILA, [evento(self.relogio(), id_envio, ENVIADO, self.pc, e["quem"])])
        self.locais[id_envio] = {"estado": "enviado", "pc": self.pc}
        logger.info(f"📧 {id_envio}: \"{p['assunto']}\" enviado de {p['conta_de']} para {p['para']}")
        try:
            self.ao_registrar_nf(p, e["quem"])
        except Exception:
            logger.exception("NF enviada, mas não consegui registrar na aba Tratamento")
        if na_planilha:
            self._apagar_anexos(id_envio)

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
        if espera > SEM_RESPOSTA_SEGUNDOS:
            return {"estado": "sem_resposta", "contas_locais": self.contas,
                    "detalhe": f"O PC {e['pedido'].get('pc_destino')} não respondeu em {SEM_RESPOSTA_SEGUNDOS}s "
                               f"(desligado ou Painel fechado)."}
        return {"estado": "aguardando", "pc": e["pedido"].get("pc_destino", "")}
