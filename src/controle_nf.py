"""Controle das NFs: registro de cada solicitação enviada e reconhecimento da NF saindo pro hóspede."""
import contextlib
import datetime
import html
import json
import msvcrt
import os
import re
import time

from tratamento import normalizar
from arquivos import salvar_json

# "NF 1212 - NOME", "NFe 1212 - NOME - 363305", "RES: NF-1212 - NOME"
PADRAO_ASSUNTO_NF = re.compile(
    r"^\s*(?:(?:re|res|enc|fw|fwd|tr)\s*:\s*)*nf-?e?\s*[-:nº°#]*\s*(\d+)\s*-\s*(.+?)\s*$", re.IGNORECASE)
PREFIXO_CONTADOR = re.compile(r"^\[\d+/\d+ ✅\]\s*")

CATEGORIA_CONCLUIDO = "✅ NF concluído"
CATEGORIA_PENDENTE = "⏳ NF pendente"
CATEGORIA_TRATATIVA = "💬 Tratativa"
CATEGORIAS_DO_ROBO = (CATEGORIA_CONCLUIDO, CATEGORIA_PENDENTE, CATEGORIA_TRATATIVA)
CATEGORIA_DIVIDIDA = "Nota dividida"   # fica no e-mail pra sempre (não entra em CATEGORIAS_DO_ROBO)
# Cores do Outlook (OlCategoryColor): 5 verde, 4 amarelo, 2 laranja, 8 azul
CORES_CATEGORIAS = {CATEGORIA_CONCLUIDO: 5, CATEGORIA_PENDENTE: 4, CATEGORIA_TRATATIVA: 2, CATEGORIA_DIVIDIDA: 8}

# Hóspede pede mais de uma nota (campo "Nota Dividida = Sim" ou pedido escrito)
_ROTULOS_DIVISAO = re.compile(r"nota dividida\s*[:\s]*(nao|não|sim)\b|dividida em quantas( vezes)?\s*[:\s]*\S*", re.I)
_PEDIDO_DIVISAO = re.compile(
    r"\b(separad[ao]s?|separar|separe|separando|dividir|divida|dividid[ao]s?)\b"
    r"|\buma (nota )?(para|pra|por) cada\b|\bcada (uma|um) (em )?(sua |uma )?nota\b"
    r"|\bnotas? (distintas|diferentes|individuais|individual)\b|\b(duas|tres|três|2|3|4) notas\b", re.I)


def pede_nota_dividida(texto):
    """True se o texto do e-mail/solicitação pede a nota dividida ou separada."""
    t = re.sub(r"\s+", " ", texto or "")
    if re.search(r"nota dividida\s*[:\s]*sim\b|dividida em quantas( vezes)?\s*[:\s]*[2-9]\b", t, re.I):
        return True
    return bool(_PEDIDO_DIVISAO.search(_ROTULOS_DIVISAO.sub(" ", t)))


# --- Regras ---
def ler_assunto_nf(assunto):
    """'NF 1212 - JOÃO SILVA - 363305' -> ('1212', 'JOÃO SILVA'). None se não for assunto de NF."""
    m = PADRAO_ASSUNTO_NF.match(assunto or "")
    if not m:
        return None
    return m.group(1), m.group(2).split(" - ")[0].strip()


def tem_anexo_nf(nomes_arquivos, extensoes):
    extensoes = {("." + e.lower().lstrip(".")) for e in extensoes}
    return any(os.path.splitext(str(n).lower())[1] in extensoes for n in nomes_arquivos)


def _tokens(nome):
    return {t for t in normalizar(nome).split() if len(t) >= 3}


def nome_bate(nome_assunto, nomes_solicitacao):
    """Todas as palavras do nome no assunto (3+ letras) aparecem num dos nomes da solicitação."""
    procurados = _tokens(nome_assunto)
    if not procurados:
        return False
    return any(procurados <= _tokens(n) for n in nomes_solicitacao)


# --- Provas de DENTRO da nota (PDF anexo, lido com texto ou com o OCR do Windows) ---
MINIMO_TEXTO_LEGIVEL = 200   # abaixo disso o PDF é imagem (ou o OCR não conseguiu ler)
_DINHEIRO = re.compile(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\b")
_DATA = re.compile(r"\b(\d{2})[/f](\d{2})[/f](\d{4})\b")


def provas_da_solicitacao(solicitacao):
    """O que dá pra procurar dentro da nota: CPF/CNPJ, valores em R$ e datas de check-in/out."""
    from tratamento import tipo_documento
    docs, valores, datas = [], [], []
    for campo, valor in solicitacao.campos:
        texto = str(valor)
        digitos = re.sub(r"\D", "", texto)
        if tipo_documento(campo, {"documento tomador": "cpf_cnpj"}) in ("cpf", "cnpj", "cpf_cnpj") and len(digitos) in (11, 14):
            docs.append(digitos)
        for inteiro, centavos in _DINHEIRO.findall(texto):
            v = inteiro.replace(".", "") + "," + centavos
            if v not in ("0,00",) and v not in valores:
                valores.append(v)
        if "check" in normalizar(campo):
            datas += [f"{d}/{m}/{a}" for d, m, a in _DATA.findall(texto)]
    return {"documentos": sorted(set(docs)), "valores": valores, "datas": sorted(set(datas))}


def _normalizar_texto_nota(texto):
    """Corrige os tropeços comuns do OCR: 'f' no lugar de '/', 'O' no lugar de '0' nos centavos."""
    t = re.sub(r"(\d)f(\d)", r"\1/\2", texto or "")
    t = re.sub(r"(\d)\s?,\s?[Oo]{2}\b", r"\1,00", t)
    t = re.sub(r"(\d) (\d{2})\b", r"\1,\2", t)          # "306 oo" / "15 30" -> "306,oo"/"15,30"
    return t


def conferir_conteudo(sol, texto):
    """Compara a solicitação com o texto da nota"""
    if not texto or len(texto.strip()) < MINIMO_TEXTO_LEGIVEL:
        return "sem_texto", "não consegui ler a nota (confira)"
    t = _normalizar_texto_nota(texto)
    digitos = re.sub(r"\D", "", t)
    provas = []
    doc = next((d for d in sol.get("documentos", []) if d in digitos), None)
    if doc:
        provas.append(("CNPJ" if len(doc) == 14 else "CPF") + " do tomador confere")
    valores_nota = {i.replace(".", "") + "," + c for i, c in _DINHEIRO.findall(t)}
    valor = next((v for v in sol.get("valores", []) if v in valores_nota), None)
    if valor:
        provas.append(f"valor R$ {valor} confere")
    datas_nota = {f"{d}/{m}/{a}" for d, m, a in _DATA.findall(t)}
    data = next((d for d in sol.get("datas", []) if d in datas_nota), None)
    if data:
        provas.append(f"check-in/out {data[:5]} confere")
    nome = any(_tokens(n) and _tokens(n) <= _tokens(t) for n in sol.get("nomes", []))
    if nome:
        provas.append("nome confere")
    if doc or (valor and (data or nome)) or (nome and data):
        return "confere", " · ".join(provas)
    return "nao_confere", " · ".join(provas) or "nada da solicitação aparece na nota"


def situacao(sol):
    """('ok' | 'parcial' | 'tratativa' | 'aguardando', texto do selo)."""
    todas = sol.get("nfs", {})
    nfs = {n: d for n, d in todas.items() if not d.get("conferir")}
    a_conferir = {n: d for n, d in todas.items() if d.get("conferir")}
    partes = int(sol.get("partes", 1) or 1)
    if len(nfs) >= partes:
        ultima = max(nfs.values(), key=lambda n: n["data"])
        numeros = ", ".join(sorted(nfs, key=lambda n: nfs[n]["data"]))
        prova = f" · {ultima['prova']}" if ultima.get("prova") else ""
        return "ok", f"✅ NF enviada · NF {numeros} · {_data_curta(ultima['data'])}{prova}"
    if a_conferir:
        return "conferir", (f"◌ NF {', '.join(sorted(a_conferir))} enviada — confira: "
                            f"não consegui ler a nota pra comparar com a solicitação")
    if nfs:
        return "parcial", f"◐ NF parcial · {len(nfs)} de {partes} · NF {', '.join(sorted(nfs))}"
    if sol.get("tratativas"):
        ultima = max(sol["tratativas"].values(), key=lambda t: t["data"])
        return "tratativa", f"💬 Tratativa · último contato {_data_curta(ultima['data'])}"
    return "aguardando", "⏳ Aguardando NF"


def _data_curta(iso):
    try:
        return datetime.datetime.fromisoformat(iso).strftime("%d/%m %H:%M")
    except (TypeError, ValueError):
        return str(iso)


CORES_SELO = {"ok": "#1e7e34", "parcial": "#1f5fa8", "tratativa": "#c26a00", "aguardando": "#d5bda1",
              "conferir": "#6b4f9e"}
# "Aguardando" ficou creme (paleta nova): texto verde escuro pra dar leitura
COR_TEXTO_SELO = {"aguardando": "#0b4a43"}


# Visual dos e-mails: "classico" (dourado) ou "verde" (paleta nova: verde #173f39 + creme #d5bda1)
VISUAL = "classico"
VERDE, CREME, VERDE_CARTAO, CREME_APAGADO = "#173f39", "#d5bda1", "#1f4b44", "#a8977f"
ESTILO_SELO_VERDE = {
    "ok": f"background:{CREME};color:{VERDE};border:1px solid {CREME};",
    "parcial": f"background:{VERDE};color:{CREME};border:1px solid {CREME};",
    "conferir": f"background:{VERDE};color:{CREME};border:1px dashed {CREME};",
    "tratativa": f"background:{VERDE};color:{CREME};border:1px dashed {CREME};",
    "aguardando": f"background:{VERDE_CARTAO};color:{CREME_APAGADO};border:1px solid {VERDE_CARTAO};",
}


def paragrafo_status(ref, sol):
    """O parágrafo de status de uma solicitação dentro do e-mail — sempre com o [ref ...] no fim."""
    tipo, texto = situacao(sol)
    if VISUAL == "verde":
        # sem emoji colorido: só as duas cores da rede
        texto = texto.replace("✅", "✔").replace("💬 ", "").replace("⏳ ", "")
        return (f'<p style="font-family:Segoe UI,Arial,sans-serif;margin:0 0 8px 0;">'
                f'<span style="display:inline-block;{ESTILO_SELO_VERDE[tipo]}border-radius:12px;'
                f'padding:3px 11px;font-size:12px;font-weight:bold;">{html.escape(texto)}</span> '
                f'<span style="color:{CREME_APAGADO};font-size:10px;">[ref {ref}]</span></p>')
    return (f'<p style="font-family:Segoe UI,Arial,sans-serif;margin:0 0 6px 0;">'
            f'<span style="display:inline-block;background:{CORES_SELO[tipo]};color:{COR_TEXTO_SELO.get(tipo, "#ffffff")};border-radius:4px;'
            f'padding:3px 9px;font-size:12px;font-weight:bold;">{html.escape(texto)}</span> '
            f'<span style="color:#b5b5b5;font-size:10px;">[ref {ref}]</span></p>')


def trocar_paragrafo_status(corpo_html, ref, novo_paragrafo):
    """Troca o parágrafo que contém '[ref X]' pelo novo"""
    marca = f"[ref {ref}]"
    pos = corpo_html.find(marca)
    if pos < 0:
        return corpo_html, False
    inicio = max(corpo_html.lower().rfind("<p ", 0, pos), corpo_html.lower().rfind("<p>", 0, pos))
    fim = corpo_html.lower().find("</p>", pos)
    if inicio < 0 or fim < 0:
        return corpo_html, False
    return corpo_html[:inicio] + novo_paragrafo + corpo_html[fim + 4:], True


def resumo_email(solicitacoes):
    """(feitas, total, tem_tratativa_aberta)"""
    tipos = [situacao(s)[0] for s in solicitacoes]
    return tipos.count("ok"), len(tipos), "tratativa" in tipos


def assunto_com_contador(assunto, feitas, total):
    return f"[{feitas}/{total} ✅] " + PREFIXO_CONTADOR.sub("", assunto or "")


def categorias_atualizadas(categorias_atuais, feitas, total, tem_tratativa):
    """Mantém as categorias que a equipe pôs à mão; troca só as do robô."""
    outras = [c.strip() for c in re.split(r"[;,]", categorias_atuais or "")
              if c.strip() and c.strip() not in CATEGORIAS_DO_ROBO]
    nossas = [CATEGORIA_CONCLUIDO if feitas >= total else CATEGORIA_PENDENTE]
    if tem_tratativa and feitas < total:
        nossas.append(CATEGORIA_TRATATIVA)
    return ", ".join(outras + nossas)


# --- Registro (estado\controle_nf.json) ---
class Registro:
    """{"solicitacoes": {ref: {...}}, "emails": {codigo: {...}}, "varredura": {conta: iso}} Sempre usado…"""

    def __init__(self, dados=None):
        dados = dados or {}
        self.solicitacoes = dados.get("solicitacoes", {})
        self.emails = dados.get("emails", {})
        self.varredura = dados.get("varredura", {})
        self.dropbox = dados.get("dropbox", {})   # arquivo do Dropbox -> data de modificação já lida

    def como_dict(self):
        return {"solicitacoes": self.solicitacoes, "emails": self.emails, "varredura": self.varredura,
                "dropbox": self.dropbox}

    # -- quando o robô de envio manda um consolidado -----------------------
    def registrar_email(self, email, agora):
        refs = []
        for s in email.solicitacoes:
            self.solicitacoes[s.ref] = {
                "codigo": email.codigo, "hotel": s.hotel.nome, "aba": s.hotel.aba,
                "email_hotel": s.hotel.email_hotel, "carimbo": s.carimbo, "data_pedido": s.data_pedido,
                "nome": s.nome_titulo, "emails": s.emails_contato, "nomes": s.nomes,
                "partes": s.partes_esperadas, "nfs": {}, "tratativas": {},
                **provas_da_solicitacao(s),
            }
            refs.append(s.ref)
        self.emails[email.codigo] = {
            "destinatario": email.destinatario.lower(), "assunto": email.assunto, "refs": refs,
            "criado_em": agora.isoformat(timespec="seconds"), "precisa_atualizar": False,
        }
        # Solicitação nova: a próxima volta do conferente relê os enviados desde a mais antiga em aberto (a…
        self.varredura = {}

    # -- consultas ----------------------------------------------------------
    def abertas(self):
        return {ref: s for ref, s in self.solicitacoes.items() if situacao(s)[0] != "ok"}

    def data_mais_antiga_aberta(self):
        datas = [s["data_pedido"] for s in self.abertas().values() if s.get("data_pedido")]
        return min(datas) if datas else None

    def ja_processado(self, entry_id):
        return any(entry_id in {n.get("entry_id") for n in s["nfs"].values()} or entry_id in s["tratativas"]
                   for s in self.solicitacoes.values())

    # -- quando o conferente acha um e-mail enviado -------------------------
    def aplicar_envio(self, envio, extensoes, ler_texto=None):
        """`envio`: {"entry_id", "conta", "destinatarios" (set), "assunto", "data" (datetime), "anexos"…"""
        if self.ja_processado(envio["entry_id"]):
            return None
        dia = envio["data"].date().isoformat()
        abertas = {ref: s for ref, s in self.abertas().items() if (s.get("data_pedido") or "") <= dia}
        destinos = {d.lower() for d in envio["destinatarios"]}
        por_email = [ref for ref, s in abertas.items() if destinos & set(s.get("emails", []))]

        nf = ler_assunto_nf(envio["assunto"])
        eh_nf = nf is not None and tem_anexo_nf(envio["anexos"], extensoes)
        registro_envio = {"data": envio["data"].isoformat(timespec="seconds"), "assunto": envio["assunto"],
                          "entry_id": envio["entry_id"]}

        if eh_nf:
            candidatas = por_email
            if not candidatas:
                # Enviou pra outro endereço: casa pelo nome do assunto, só no mesmo hotel.
                conta = (envio.get("conta") or "").lower()
                candidatas = [ref for ref, s in abertas.items()
                              if s.get("email_hotel", "").lower() == conta and nome_bate(nf[1], s.get("nomes", []))]
                if len(candidatas) > 1:
                    return None  # ambíguo: melhor não marcar a errada
            if not candidatas:
                return None
            ordem = lambda r: (abertas[r].get("data_pedido", ""), r)
            texto = ler_texto() if ler_texto else None
            if texto is None:   # sem leitor (testes antigos): comportamento antigo
                ref, resultado, prova = min(candidatas, key=ordem), "confere", ""
            else:
                avaliadas = {r: conferir_conteudo(abertas[r], texto) for r in candidatas}
                conferem = [r for r in candidatas if avaliadas[r][0] == "confere"]
                if conferem:
                    ref = min(conferem, key=ordem)
                elif all(a[0] == "nao_confere" for a in avaliadas.values()):
                    return None     # a nota tem texto e é de OUTRA pessoa/tomador: não é desta solicitação
                else:
                    ref = min(candidatas, key=ordem)    # não deu pra ler: fica "confira", sem ✅
                resultado, prova = avaliadas[ref]
            self.solicitacoes[ref]["nfs"].setdefault(nf[0], {**registro_envio, "prova": prova,
                                                            "conferir": resultado != "confere"})
            self._marcar_para_atualizar(ref)
            return ref, "nf"

        if por_email:
            ref = min(por_email, key=lambda r: (abertas[r].get("data_pedido", ""), r))
            self.solicitacoes[ref]["tratativas"][envio["entry_id"]] = registro_envio
            self._marcar_para_atualizar(ref)
            return ref, "tratativa"
        return None

    def aplicar_nota_dropbox(self, caminho, nf, data, ler_texto, fonte):
        """Nota achada na pasta do Dropbox (salva por qualquer um dos 4 agentes)"""
        chave = "dropbox:" + caminho
        if self.ja_processado(chave):
            return None
        dia = data.date().isoformat()
        abertas = {ref: s for ref, s in self.abertas().items()
                   if (s.get("data_pedido") or "") <= dia and nf[0] not in s.get("nfs", {})}
        if not abertas:
            return None
        texto = ler_texto()
        avaliadas = {ref: conferir_conteudo(s, texto) for ref, s in abertas.items()}
        conferem = [ref for ref, (res, _) in avaliadas.items() if res == "confere"]
        if not conferem:
            return None
        # mais de uma bate: fica com a que tem CPF/CNPJ conferido; empate -> a mais antiga
        com_doc = [r for r in conferem if "do tomador confere" in avaliadas[r][1]]
        escolhidas = com_doc or conferem
        if len(escolhidas) > 1 and not com_doc:
            return None     # só nome/valor, e bate com mais de uma: melhor não marcar a errada
        ref = min(escolhidas, key=lambda r: (abertas[r].get("data_pedido", ""), r))
        self.solicitacoes[ref]["nfs"][nf[0]] = {
            "data": data.isoformat(timespec="seconds"), "assunto": os.path.basename(caminho), "entry_id": chave,
            "prova": f"{avaliadas[ref][1]} · achada no Dropbox ({fonte})", "conferir": False,
        }
        self._marcar_para_atualizar(ref)
        return ref

    def _marcar_para_atualizar(self, ref):
        codigo = self.solicitacoes[ref]["codigo"]
        if codigo in self.emails:
            self.emails[codigo]["precisa_atualizar"] = True


@contextlib.contextmanager
def abrir_registro(caminho, tentativas=120):
    """Abre o registro com trava (outro processo espera até ~2 min)"""
    caminho = str(caminho)
    os.makedirs(os.path.dirname(caminho), exist_ok=True)
    with open(caminho + ".trava", "a+b") as trava:
        for tentativa in range(tentativas):
            try:
                msvcrt.locking(trava.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if tentativa == tentativas - 1:
                    raise
                time.sleep(1)
        try:
            try:
                with open(caminho, "r", encoding="utf-8") as f:
                    registro = Registro(json.load(f))
            except FileNotFoundError:
                registro = Registro()
            yield registro
            salvar_json(caminho, registro.como_dict())
        finally:
            trava.seek(0)
            msvcrt.locking(trava.fileno(), msvcrt.LK_UNLCK, 1)


def nfs_sem_prova(registro):
    """NFs marcadas antes de existir a conferência pelo conteúdo — o conferente relê essas notas."""
    # só reconfere quem tem os dados da solicitação guardados (CNPJ, valores...) — sem eles, "não achei…
    return [(ref, numero, d["entry_id"]) for ref, sol in registro.solicitacoes.items() if "documentos" in sol
            for numero, d in sol.get("nfs", {}).items() if "prova" not in d]


def reconferir(registro, ref, numero, texto):
    """Relê uma NF já marcada: se a nota for de outra pessoa, desfaz o ✅. Devolve o resultado."""
    sol = registro.solicitacoes[ref]
    resultado, prova = conferir_conteudo(sol, texto)
    if resultado == "nao_confere":
        sol["nfs"].pop(numero, None)
    else:
        sol["nfs"][numero].update(prova=prova, conferir=resultado != "confere")
    registro._marcar_para_atualizar(ref)
    return resultado, prova
