"""Registro das solicitações enviadas e reconhecimento da NF que sai para o hóspede.

Uma NF é reconhecida pelo assunto "NF 1234 - NOME" com anexo, ou por um PDF salvo no Dropbox;
em ambos os casos o conteúdo da nota é comparado com a solicitação antes de marcar ✅.
"""
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
CATEGORIA_DIVIDIDA = "Nota dividida"   # permanente: fora de CATEGORIAS_DO_ROBO de propósito
CORES_CATEGORIAS = {CATEGORIA_CONCLUIDO: 5, CATEGORIA_PENDENTE: 4, CATEGORIA_TRATATIVA: 2, CATEGORIA_DIVIDIDA: 8}   # OlCategoryColor

_ROTULOS_DIVISAO = re.compile(r"nota dividida\s*[:\s]*(nao|não|sim)\b|dividida em quantas( vezes)?\s*[:\s]*\S*", re.I)
_PEDIDO_DIVISAO = re.compile(
    r"\b(separad[ao]s?|separar|separe|separando|dividir|divida|dividid[ao]s?)\b"
    r"|\buma (nota )?(para|pra|por) cada\b|\bcada (uma|um) (em )?(sua |uma )?nota\b"
    r"|\bnotas? (distintas|diferentes|individuais|individual)\b|\b(duas|tres|três|2|3|4) notas\b", re.I)


def pede_nota_dividida(texto):
    """Pelo campo do formulário ou por pedido escrito ("uma nota pra cada", "separadas"...)."""
    t = re.sub(r"\s+", " ", texto or "")
    if re.search(r"nota dividida\s*[:\s]*sim\b|dividida em quantas( vezes)?\s*[:\s]*[2-9]\b", t, re.I):
        return True
    return bool(_PEDIDO_DIVISAO.search(_ROTULOS_DIVISAO.sub(" ", t)))


def ler_assunto_nf(assunto):
    """'NF 1212 - JOÃO SILVA - 363305' -> ('1212', 'JOÃO SILVA') | None"""
    m = PADRAO_ASSUNTO_NF.match(assunto or "")
    if not m:
        return None
    return m.group(1), m.group(2).split(" - ")[0].strip()


def tem_anexo_nf(nomes_arquivos, extensoes):
    extensoes = {("." + e.lower().lstrip(".")) for e in extensoes}
    return any(os.path.splitext(str(n).lower())[1] in extensoes for n in nomes_arquivos)


def numeros_do_envio(numero_assunto, nomes_anexos):
    """NFs que um e-mail leva: os números dos anexos "NF 123 - NOME.pdf" (nota dividida = 2 anexos);
    sem número no nome, o do assunto. Cada PDF a mais sem número vira "123 (2º anexo)" — o PDF e o
    XML da mesma nota contam uma vez só."""
    nos_anexos = []
    for nome in nomes_anexos:
        nf = ler_assunto_nf(os.path.splitext(str(nome))[0])
        if nf and nf[0] not in nos_anexos:
            nos_anexos.append(nf[0])
    numeros = nos_anexos or [numero_assunto]
    pdfs = sum(1 for n in nomes_anexos if str(n).lower().endswith(".pdf"))
    numeros += [f"{numero_assunto} ({i}º anexo)" for i in range(len(numeros) + 1, pdfs + 1)]
    return numeros


def _tokens(nome):
    return {t for t in normalizar(nome).split() if len(t) >= 3}


def nome_bate(nome_assunto, nomes_solicitacao):
    """Todas as palavras (3+ letras) do nome no assunto estão num dos nomes da solicitação."""
    procurados = _tokens(nome_assunto)
    if not procurados:
        return False
    return any(procurados <= _tokens(n) for n in nomes_solicitacao)


def nome_parecido(nome_assunto, nomes_solicitacao):
    """Nome do assunto dentro de um nome do pedido, ou 2+ palavras em comum ("MARIA CLEUZA CARVALHO"
    x "Maria Cleuza Carvalho da Cruz")."""
    procurados = _tokens(nome_assunto)
    return bool(procurados) and any(procurados <= _tokens(n) or len(procurados & _tokens(n)) >= 2
                                    for n in nomes_solicitacao)


# --- Conteúdo da nota (texto do PDF ou OCR do Windows) ---
MINIMO_TEXTO_LEGIVEL = 200   # abaixo disso o PDF é imagem ou o OCR falhou
_DINHEIRO = re.compile(r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*|\d+),(\d{2})\b")
_DATA = re.compile(r"\b(\d{2})[/f](\d{2})[/f](\d{4})\b")   # OCR lê "/" como "f"

# O mesmo hóspede costuma pedir diária e consumo em notas separadas
SERVICOS = {
    "diaria": re.compile(r"\bdi[aá]ria|hospedagem|hospedage\b", re.I),
    "consumo": re.compile(r"consumo|frigobar|restaurante|alimenta|refei[cç]|\bbar\b|lavanderia", re.I),
    "estacionamento": re.compile(r"estacionamento|garagem|vaga\b", re.I),
}


# Bloco "Descrição do Serviço" das NFs da rede:
#   DATA DE CHECK-IN: 24/09/2026 · DATA DE CHECK-OUT: 25/09/2026 · VALOR DA DIÁRIA: R$ 140,00 · VALOR DO ESTACIONAMENTO: R$ 20,00
_CHECK = re.compile(r"CHECK[\s-]*(IN|OUT)\s*:?\s*(\d{2})/(\d{2})/(\d{4})")
_VALOR_SERVICO = re.compile(r"VALOR\s+D[AOE]S?\s+([A-Z ]+?)\s*:?\s*R\$\s*([\d.]+,\d{2})")


def ler_descricao_nota(texto):
    """-> {"checkin": "dd/mm", "checkout": "dd/mm", "servicos": {com valor > 0}} | None"""
    import unicodedata
    t = "".join(c for c in unicodedata.normalize("NFD", texto or "") if unicodedata.category(c) != "Mn").upper()
    datas = {tipo: f"{d}/{m}" for tipo, d, m, _a in _CHECK.findall(t)}
    servicos = set()
    for rotulo, valor in _VALOR_SERVICO.findall(t):
        if float(valor.replace(".", "").replace(",", ".")) <= 0:
            continue
        servicos |= servicos_no_texto(rotulo) or ({"consumo"} if "CONSUMO" in rotulo else set())
    if not datas and not servicos:
        return None
    return {"checkin": datas.get("IN"), "checkout": datas.get("OUT"), "servicos": servicos}


def servicos_no_texto(texto):
    return {nome for nome, padrao in SERVICOS.items() if padrao.search(texto or "")}


def provas_da_solicitacao(solicitacao):
    """O que procurar dentro da nota: CPF/CNPJ, valores, datas de check-in/out e serviços."""
    from tratamento import tipo_documento
    docs, valores, datas, servicos = [], [], [], set()
    for campo, valor in solicitacao.campos:
        texto = str(valor)
        if "informa" in normalizar(campo) or "descri" in normalizar(campo):
            servicos |= servicos_no_texto(texto)
        digitos = re.sub(r"\D", "", texto)
        if tipo_documento(campo, {"documento tomador": "cpf_cnpj"}) in ("cpf", "cnpj", "cpf_cnpj") and len(digitos) in (11, 14):
            docs.append(digitos)
        for inteiro, centavos in _DINHEIRO.findall(texto):
            v = inteiro.replace(".", "") + "," + centavos
            if v not in ("0,00",) and v not in valores:
                valores.append(v)
        if "check" in normalizar(campo):
            datas += [f"{d}/{m}/{a}" for d, m, a in _DATA.findall(texto)]
    return {"documentos": sorted(set(docs)), "valores": valores, "datas": sorted(set(datas)), "servicos": sorted(servicos)}


def _normalizar_texto_nota(texto):
    """Erros comuns do OCR: 'f' por '/', 'oo' por '00', vírgula dos centavos sumida."""
    t = re.sub(r"(\d)f(\d)", r"\1/\2", texto or "")
    t = re.sub(r"(\d)\s?,\s?[Oo]{2}\b", r"\1,00", t)
    t = re.sub(r"(\d) (\d{2})\b", r"\1,\2", t)
    return t


def conferir_conteudo(sol, texto):
    """-> ("confere" | "nao_confere" | "sem_texto", provas legíveis)

    Confere com CPF/CNPJ, ou com dois entre valor, data e nome. Mesmo com o documento batendo,
    a estadia e o serviço da nota têm que ser os do pedido: empresas se hospedam várias vezes.
    """
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
    dias_nota = {x[:5] for x in datas_nota}   # só dia/mês: o ano vem errado com frequência ("0026")
    data = next((d for d in sol.get("datas", []) if d[:5] in dias_nota), None)
    if data:
        provas.append(f"check-in/out {data[:5]} confere")
    nome = any(_tokens(n) and _tokens(n) <= _tokens(t) for n in sol.get("nomes", []))
    if nome:
        provas.append("nome confere")
    desc = ler_descricao_nota(texto)
    pedidas = {d[:5] for d in sol.get("datas", [])}
    if desc and desc["checkin"] and pedidas:
        # Basta um dos dois: a nota às vezes sai com o mês do check-out errado
        if not ({desc["checkin"], desc["checkout"]} & pedidas):
            return "nao_confere", " · ".join(provas + [f"estadia da nota (check-in {desc['checkin']}) não é a do pedido"])
        if not data:
            provas.append(f"check-in {desc['checkin']} confere")
            data = desc["checkin"]
    elif sol.get("datas") and not data and len(datas_nota) >= 2:
        return "nao_confere", " · ".join(provas + ["datas da estadia não batem"])
    pedidos = set(sol.get("servicos", []))
    na_nota = desc["servicos"] if desc and desc["servicos"] else servicos_no_texto(t)
    if pedidos and na_nota and not (pedidos & na_nota):
        return "nao_confere", " · ".join(provas + [f"serviço diferente (pediu {', '.join(sorted(pedidos))}; "
                                                    f"nota de {', '.join(sorted(na_nota))})"])
    if doc or (valor and (data or nome)) or (nome and data):
        return "confere", " · ".join(provas)
    return "nao_confere", " · ".join(provas) or "nada da solicitação aparece na nota"


def situacao(sol):
    """-> ('ok' | 'conferir' | 'parcial' | 'tratativa' | 'aguardando', texto do selo)"""
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
COR_TEXTO_SELO = {"aguardando": "#0b4a43"}   # fundo creme pede texto escuro

VISUAL = "classico"   # "classico" | "verde"; definido por montar_email a partir do config
VERDE, CREME, VERDE_CARTAO, CREME_APAGADO = "#173f39", "#d5bda1", "#1f4b44", "#a8977f"
ESTILO_SELO_VERDE = {
    "ok": f"background:{CREME};color:{VERDE};border:1px solid {CREME};",
    "parcial": f"background:{VERDE};color:{CREME};border:1px solid {CREME};",
    "conferir": f"background:{VERDE};color:{CREME};border:1px dashed {CREME};",
    "tratativa": f"background:{VERDE};color:{CREME};border:1px dashed {CREME};",
    "aguardando": f"background:{VERDE_CARTAO};color:{CREME_APAGADO};border:1px solid {VERDE_CARTAO};",
}


def paragrafo_status(ref, sol):
    """Selo de status; o "[ref X]" no fim é a âncora que trocar_paragrafo_status procura."""
    tipo, texto = situacao(sol)
    if VISUAL == "verde":
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
    """-> (feitas, total, tem_tratativa_aberta)"""
    tipos = [situacao(s)[0] for s in solicitacoes]
    return tipos.count("ok"), len(tipos), "tratativa" in tipos


def assunto_com_contador(assunto, feitas, total):
    return f"[{feitas}/{total} ✅] " + PREFIXO_CONTADOR.sub("", assunto or "")


def categorias_atualizadas(categorias_atuais, feitas, total, tem_tratativa):
    """Troca só as categorias do robô e preserva as que a equipe pôs à mão."""
    # Outlook pt-BR separa categorias com ";"
    outras = [c.strip() for c in re.split(r"[;,]", categorias_atuais or "")
              if c.strip() and c.strip() not in CATEGORIAS_DO_ROBO]
    nossas = [CATEGORIA_CONCLUIDO if feitas >= total else CATEGORIA_PENDENTE]
    if tem_tratativa and feitas < total:
        nossas.append(CATEGORIA_TRATATIVA)
    return ", ".join(outras + nossas)


class Registro:
    """estado/controle_nf.json. Use sempre via abrir_registro(), que trava entre processos.

    solicitacoes: {ref: dados + nfs + tratativas}
    emails:       {codigo: destinatario, assunto, refs, precisa_atualizar}
    varredura:    {conta: até quando os Enviados já foram lidos (iso)}
    dropbox:      {caminho: mtime já lido}
    """

    def __init__(self, dados=None):
        dados = dados or {}
        self.solicitacoes = dados.get("solicitacoes", {})
        self.emails = dados.get("emails", {})
        self.varredura = dados.get("varredura", {})
        self.dropbox = dados.get("dropbox", {})

    def como_dict(self):
        return {"solicitacoes": self.solicitacoes, "emails": self.emails, "varredura": self.varredura,
                "dropbox": self.dropbox}

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
        # Força a próxima volta a reler Enviados desde a solicitação aberta mais antiga:
        # a NF pode ter saído antes do registro deste e-mail.
        self.varredura = {}

    def abertas(self):
        return {ref: s for ref, s in self.solicitacoes.items() if situacao(s)[0] != "ok"}

    def data_mais_antiga_aberta(self):
        datas = [s["data_pedido"] for s in self.abertas().values() if s.get("data_pedido")]
        return min(datas) if datas else None

    def igualar_gemeas(self):
        """Mesma solicitação em dois e-mails (agrupado e depois separado): NF e tratativa valem pros dois."""
        grupos = {}
        for ref, s in self.solicitacoes.items():
            grupos.setdefault((s.get("aba"), s.get("carimbo"), tuple(s.get("emails", []))), []).append(ref)
        mudou = 0
        for refs in (g for g in grupos.values() if len(g) > 1):
            nfs = {k: v for r in refs for k, v in self.solicitacoes[r].get("nfs", {}).items()}
            trat = {k: v for r in refs for k, v in self.solicitacoes[r].get("tratativas", {}).items()}
            for r in refs:
                s = self.solicitacoes[r]
                if s.get("nfs", {}) != nfs or s.get("tratativas", {}) != trat:
                    s["nfs"], s["tratativas"] = dict(nfs), dict(trat)
                    if s.get("codigo") in self.emails:
                        self.emails[s["codigo"]]["precisa_atualizar"] = True
                    mudou += 1
        return mudou

    def ja_processado(self, entry_id):
        return any(entry_id in {n.get("entry_id") for n in s["nfs"].values()} or entry_id in s["tratativas"]
                   for s in self.solicitacoes.values())

    def aplicar_envio(self, envio, extensoes, ler_texto=None):
        """Classifica um e-mail enviado como NF ou tratativa de alguma solicitação aberta.

        envio: {entry_id, conta, destinatarios: set, assunto, data: datetime, anexos: [nomes]}
        -> (ref, "nf" | "tratativa") | None
        """
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

        if eh_nf and por_email:
            # Pedido do usuário (05/10/2026): "se o email estiver com o anexo da nota pode concluir".
            # Enviada ao e-mail de quem pediu, com a NF anexada = emitida, mesmo com o PDF ilegível
            # (nota escaneada que o OCR lê torta). Com o nome do assunto batendo, nem abre o PDF.
            # Só recusa a nota legível de OUTRO tomador com outro nome no assunto (caso NF 801:
            # e-mail de empresa usado por vários hóspedes).
            ordem = lambda r: (abertas[r].get("data_pedido", ""), r)
            pelo_nome = [r for r in por_email if nome_parecido(nf[1], abertas[r].get("nomes", []))]
            prova = "enviada ao e-mail do pedido com a NF anexada"
            if len(pelo_nome) == 1:
                ref = pelo_nome[0]
            else:
                texto = ler_texto() if ler_texto else ""
                avaliadas = {r: conferir_conteudo(abertas[r], texto) for r in por_email} if texto else {}
                conferem = [r for r, (res, _) in avaliadas.items() if res == "confere"]
                if conferem:
                    ref = min(conferem, key=ordem)
                    prova = f"{avaliadas[ref][1]} · {prova}"
                elif avaliadas and all(res == "nao_confere" for res, _ in avaliadas.values()) and not pelo_nome:
                    return None   # nota legível de outra pessoa
                else:
                    ref = min(pelo_nome or por_email, key=ordem)
            for numero in numeros_do_envio(nf[0], envio["anexos"]):
                self.solicitacoes[ref]["nfs"].setdefault(numero, {**registro_envio, "prova": prova, "conferir": False})
            self._marcar_para_atualizar(ref)
            return ref, "nf"

        if eh_nf:
            candidatas = por_email
            if not candidatas:
                # Enviada pra outro endereço: casa pelo nome do assunto, só no mesmo hotel
                conta = (envio.get("conta") or "").lower()
                candidatas = [ref for ref, s in abertas.items()
                              if s.get("email_hotel", "").lower() == conta and nome_bate(nf[1], s.get("nomes", []))]
                if len(candidatas) > 1:
                    return None   # ambíguo
            if not candidatas:
                return None
            ordem = lambda r: (abertas[r].get("data_pedido", ""), r)
            texto = ler_texto() if ler_texto else None
            if texto is None:
                ref, resultado, prova = min(candidatas, key=ordem), "confere", ""
            else:
                avaliadas = {r: conferir_conteudo(abertas[r], texto) for r in candidatas}
                conferem = [r for r in candidatas if avaliadas[r][0] == "confere"]
                if conferem:
                    ref = min(conferem, key=ordem)
                elif all(a[0] == "nao_confere" for a in avaliadas.values()):
                    return None   # nota legível e de outra pessoa
                else:
                    ref = min(candidatas, key=ordem)   # ilegível: marca como "confira", sem ✅
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
        # Várias batem: vale a com CPF/CNPJ; sem documento e ambígua, não marca nenhuma
        com_doc = [r for r in conferem if "do tomador confere" in avaliadas[r][1]]
        escolhidas = com_doc or conferem
        if len(escolhidas) > 1 and not com_doc:
            return None
        ref = min(escolhidas, key=lambda r: (abertas[r].get("data_pedido", ""), r))
        self.solicitacoes[ref]["nfs"][nf[0]] = {
            "data": data.isoformat(timespec="seconds"), "assunto": os.path.basename(caminho), "entry_id": chave,
            "prova": f"{avaliadas[ref][1]} · achada no Dropbox ({fonte})", "conferir": False,
        }
        self._marcar_para_atualizar(ref)
        return ref

    def aplicar_nota_pelo_nome(self, caminho, nf, data, fonte, dias_max=60):
        """Nota da pasta do agente que está só na nuvem (lê-la baixaria o PDF): casa pelo NOME do arquivo.
        Pedido do usuário (06/10/2026): "dentro das pastas deles tem todas NF emitidas por eles mesmos".
        Vale quando o nome da nota e o do pedido contêm um ao outro (2+ palavras) e a nota foi salva até
        `dias_max` dias depois do pedido; com mais de um pedido assim, o mais perto da data da nota."""
        chave = "dropbox:" + caminho
        if self.ja_processado(chave):
            return None
        alvo = _tokens(nf[1])
        if len(alvo) < 2:
            return None
        dia = data.date()
        casam = []
        for ref, s in self.abertas().items():
            if nf[0] in s.get("nfs", {}) or not s.get("data_pedido"):
                continue
            atraso = (dia - datetime.date.fromisoformat(s["data_pedido"])).days
            if 0 <= atraso <= dias_max and any(alvo <= _tokens(n) or (len(_tokens(n)) >= 2 and _tokens(n) <= alvo)
                                               for n in s.get("nomes", [])):
                casam.append((atraso, ref))
        if not casam:
            return None
        ref = min(casam)[1]
        self.solicitacoes[ref]["nfs"][nf[0]] = {
            "data": data.isoformat(timespec="seconds"), "assunto": os.path.basename(caminho), "entry_id": chave,
            "prova": f"nome da nota na pasta do agente ({fonte}) bate com o pedido", "conferir": False,
        }
        self._marcar_para_atualizar(ref)
        return ref

    def _marcar_para_atualizar(self, ref):
        codigo = self.solicitacoes[ref]["codigo"]
        if codigo in self.emails:
            self.emails[codigo]["precisa_atualizar"] = True


@contextlib.contextmanager
def abrir_registro(caminho, tentativas=120):
    """Lê, entrega e grava o Registro sob trava de arquivo (espera até `tentativas` segundos)."""
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
    """NFs marcadas sem prova de conteúdo, em solicitações que já guardam os dados pra comparar."""
    return [(ref, numero, d["entry_id"]) for ref, sol in registro.solicitacoes.items() if "documentos" in sol
            for numero, d in sol.get("nfs", {}).items() if "prova" not in d]


def reconferir(registro, ref, numero, texto):
    """Desfaz o ✅ se a nota já marcada for de outra pessoa."""
    sol = registro.solicitacoes[ref]
    resultado, prova = conferir_conteudo(sol, texto)
    if resultado == "nao_confere":
        sol["nfs"].pop(numero, None)
    else:
        sol["nfs"][numero].update(prova=prova, conferir=resultado != "confere")
    registro._marcar_para_atualizar(ref)
    return resultado, prova
