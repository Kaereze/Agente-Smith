"""Gera app_ui/pecas/tema_claro.css: a versão clara do desenho escuro do Painel (26/11/2026, pedido do João).

Por que existe: o desenho atual (o "modo Outlook" com o vidro escuro) tem as cores escritas direto nas regras (#1f1f1f, #f0f0f0,
rgba(8,8,8,.55)...), em vez de variáveis. Por isso o botão de tema trocava só a palavra ("Tema: Claro") e a tela continuava escura.

O que faz: lê os estilos do Painel na ordem em que a página carrega, pega as regras do modo Outlook (as que têm "modo-ol" no seletor) e
as dos arquivos do vidro (centro_leve.css e barra_flutuante.css), e para cada declaração com cor escreve a mesma regra com a cor clara,
valendo só quando o tema é Claro, ou Sistema com o Windows claro. Nada do tema escuro muda.

A regra de cor depende do que a cor pinta:
  - fundo escuro vira fundo claro; texto claro vira texto escuro; borda escura vira borda clara;
  - cor de destaque (azul, vermelho, âmbar) mantém o tom: como texto fica mais escura (contraste no branco), como fundo escuro vira um
    fundo claro do mesmo tom;
  - sombra continua preta, só mais fraca.
Ajustes feitos à mão, para o que a regra automática não acerta, ficam no fim do arquivo gerado (AJUSTES, abaixo).

Uso:  python ferramentas/gerar_tema_claro.py            (regrava o arquivo)
      python ferramentas/gerar_tema_claro.py --conferir (só diz se o arquivo está em dia; sai com 1 se não estiver)
Rode de novo sempre que mudar um estilo do modo escuro. O teste test_tema_claro.py avisa se esquecer.
"""
import colorsys
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_UI = RAIZ / "app_ui"
SAIDA = PASTA_UI / "pecas" / "tema_claro.css"

# a ordem do index.html (só os que têm regra do modo escuro importam; os outros passam sem gerar nada)
ARQUIVOS = ["pecas/etiqueta.css", "pecas/janela.css", "pecas/carregando.css", "pecas/caixas.css", "pecas/tokens.css", "pecas/escala.css",
            "pecas/busca_recente.css", "pecas/etapas.css", "pecas/resumo_dia.css", "pecas/filtro_hoteis.css", "estilo.css", "pecas/avisos.css",
            "pecas/visao_geral.css", "pecas/barra_flutuante.css", "pecas/centro_leve.css", "pecas/hospede.css", "pecas/novo_email.css",
            "pecas/colunas.css"]
ARQUIVOS_INTEIROS = {"pecas/barra_flutuante.css", "pecas/centro_leve.css"}   # todo o vidro escuro está nestes dois

CLARO = ':root[data-theme="light"]'
SISTEMA_CLARO = ':root:not([data-theme="dark"])'

COR = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^()]*\)|\b(?:white|black)\b")
PROPS_COR = re.compile(r"^(--.+|color|background(-color|-image)?|border(-[a-z]+)*|outline(-color)?|box-shadow|text-shadow|fill|stroke|"
                       r"caret-color|column-rule(-color)?|text-decoration(-color)?|accent-color|filter|-webkit-text-fill-color)$")

AJUSTES = """
/* ---- ajustes feitos à mão (o que a regra automática não acerta) ---- */
:root[data-theme="light"] .app.modo-ol{background:#eef1f4!important;color-scheme:light}
:root[data-theme="light"] .app.modo-ol::before{opacity:.45}
/* letra branca sobre cor forte (avatar do operador, selo NF, botão azul de Enviar): continua branca */
:root[data-theme="light"] :is(.op-btn .av,.op-item .av,.op-menu .av,.marca .selo,.capsula .selo){color:#ffffff!important}
@media (prefers-color-scheme: light){
:root:not([data-theme="dark"]) .app.modo-ol{background:#eef1f4!important;color-scheme:light}
:root:not([data-theme="dark"]) .app.modo-ol::before{opacity:.45}
:root:not([data-theme="dark"]) :is(.op-btn .av,.op-item .av,.op-menu .av,.marca .selo,.capsula .selo){color:#ffffff!important}
}
"""


# ---------- cores ----------
def ler_cor(txt):
    """'#1f1f1f', '#fff', 'rgba(8,8,8,.55)', 'white' -> (r, g, b, a) em 0..1, ou None."""
    t = txt.strip().lower()
    if t == "white":
        return (1.0, 1.0, 1.0, 1.0)
    if t == "black":
        return (0.0, 0.0, 0.0, 1.0)
    if t.startswith("#"):
        h = t[1:]
        if len(h) in (3, 4):
            h = "".join(c * 2 for c in h)
        if len(h) not in (6, 8):
            return None
        r, g, b = (int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))
        a = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
        return (r, g, b, a)
    m = re.match(r"rgba?\(([^()]*)\)", t)
    if not m:
        return None
    partes = [p for p in re.split(r"[\s,/]+", m.group(1).strip()) if p]
    if len(partes) < 3:
        return None
    try:
        r, g, b = (float(p.rstrip("%")) * (2.55 if p.endswith("%") else 1) / 255 for p in partes[:3])
        a = float(partes[3].rstrip("%")) / (100 if partes[3].endswith("%") else 1) if len(partes) > 3 else 1.0
    except ValueError:
        return None
    return (r, g, b, a)


def escrever_cor(r, g, b, a):
    r, g, b = (max(0, min(255, round(x * 255))) for x in (r, g, b))
    if a >= 0.999:
        return f"#{r:02x}{g:02x}{b:02x}"
    return f"rgba({r},{g},{b},{round(a, 3):g})"


VAR_TEXTO = re.compile(r"texto|tinta|-txt|-fg\b|^--(atencao|erro|ok|info|roxo)$")   # as cores de aviso pintam texto (as de fundo são -fundo)


VAR_FUNDO = re.compile(r"vidro|fundo|folha|chao|-bg\b")
VAR_BORDA = re.compile(r"-rim\b|linha|borda")


def tipo_da_prop(prop):
    if prop.startswith("--"):
        if VAR_TEXTO.search(prop) or "ouro" in prop or "apagado" in prop:
            return "var-texto"
        if VAR_FUNDO.search(prop):
            return "fundo"
        if VAR_BORDA.search(prop):
            return "borda"
        return "var"
    if prop in ("box-shadow", "text-shadow", "filter"):
        return "sombra"
    if prop.startswith("background"):
        return "fundo"
    if prop.startswith(("border", "outline", "column-rule")):
        return "borda"
    return "texto"


def clarear(cor, tipo):
    """A cor do tema escuro -> a do tema claro, conforme o que ela pinta."""
    v = ler_cor(cor)
    if not v:
        return cor
    r, g, b, a = v
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    neutra = s < 0.18 or l < 0.06 or l > 0.97
    if tipo == "var-texto":   # variável com nome de texto (--tinta, --verde-texto...)
        tipo = "texto"
    elif tipo == "var":   # outra variável: neutra escura = fundo, neutra clara = texto; destaque de tom médio serve de fundo E de texto: fica
        if not neutra and 0.3 <= l <= 0.65:
            return cor
        tipo = "fundo" if l < 0.5 else "texto"
    if tipo == "sombra":
        if neutra and l < 0.5:
            return escrever_cor(r, g, b, a * 0.35)
        return escrever_cor(r, g, b, a)
    if neutra:
        if tipo == "fundo":
            if a < 0.999 and l < 0.5:   # vidro escuro -> vidro claro
                return escrever_cor(1, 1, 1, max(a, 0.72))
            if a < 0.999:   # brilho branco por cima -> sombreado leve
                return escrever_cor(0, 0, 0, a * 0.6)
            if l < 0.5:
                nl = 1 - 0.55 * l
            elif l < 0.85:
                nl = 1 - l
            else:
                nl = l
        elif tipo == "borda":
            if a < 0.999:
                return escrever_cor(0, 0, 0, min(1, a * 0.8)) if l >= 0.5 else escrever_cor(1, 1, 1, a)
            nl = 1 - 0.6 * l if l < 0.5 else 1 - l
        else:   # texto
            if a < 0.999 and l >= 0.5:   # texto branco meio transparente: no claro precisa de mais tinta para ler
                return escrever_cor(0, 0, 0, max(a, 0.82))
            nl = 0.06 + (1 - l) * 0.8 if l >= 0.5 else l
        nr, ng, nb = colorsys.hls_to_rgb(h, nl, s)
        return escrever_cor(nr, ng, nb, a)
    # cor de destaque: mantém o tom
    if tipo == "texto":
        nl = 0.28 if l > 0.4 else l
    elif tipo == "fundo":
        nl = 0.92 if l < 0.32 else l
    else:   # borda
        nl = 0.78 if l < 0.32 else (0.45 if l > 0.6 else l)
    nr, ng, nb = colorsys.hls_to_rgb(h, nl, s)
    return escrever_cor(nr, ng, nb, a)


# ---------- ler o CSS ----------
def sem_comentarios(css):
    return re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def blocos(css):
    """Divide o CSS em [(cabeçalho, corpo)] no nível de cima. Corpo de @media/@supports volta como texto (o chamador desce nele)."""
    i, n, saida = 0, len(css), []
    while i < n:
        abre = css.find("{", i)
        if abre < 0:
            break
        cab = css[i:abre].strip()
        nivel, j = 1, abre + 1
        while j < n and nivel:
            if css[j] == "{":
                nivel += 1
            elif css[j] == "}":
                nivel -= 1
            j += 1
        saida.append((cab, css[abre + 1:j - 1]))
        i = j
    return saida


def declaracoes(corpo):
    """'a:b;c:d!important' -> [(prop, valor, importante)] (tira o ';' de dentro de url() e parênteses com cuidado)."""
    partes, nivel, atual = [], 0, ""
    for c in corpo:
        if c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
        if c == ";" and nivel == 0:
            partes.append(atual)
            atual = ""
        else:
            atual += c
    partes.append(atual)
    saida = []
    for p in partes:
        if ":" not in p:
            continue
        prop, valor = p.split(":", 1)
        prop, valor = prop.strip().lower(), valor.strip()
        imp = bool(re.search(r"!\s*important\s*$", valor))
        valor = re.sub(r"!\s*important\s*$", "", valor).strip()
        saida.append((prop, valor, imp))
    return saida


def seletor_claro(sel, raiz):
    sel = sel.strip()
    if sel.startswith(":root"):
        return raiz + sel[len(":root"):]
    if sel.startswith(("html", "body")) and not sel.startswith(("html ", "body ")) and sel in ("html", "body"):
        return f"{raiz} {sel}" if sel == "body" else raiz
    return f"{raiz} {sel}"


def dividir_seletores(cab):
    partes, nivel, atual = [], 0, ""
    for c in cab:
        if c in "([":
            nivel += 1
        elif c in ")]":
            nivel -= 1
        if c == "," and nivel == 0:
            partes.append(atual)
            atual = ""
        else:
            atual += c
    partes.append(atual)
    return [p.strip() for p in partes if p.strip()]


def _luz(cor):
    v = ler_cor(cor)
    if not v:
        return None
    r, g, b, a = v
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return l, s, a


def desenhada_no_escuro(decls):
    """Regra sem "modo-ol" no nome, mas feita para o fundo escuro (o modo Outlook está sempre ligado desde 15/10/2026):
    tem fundo escuro, ou texto claro sem fundo claro. As regras do tema claro antigo (fundo branco, texto escuro) ficam de fora."""
    fundo_escuro = fundo_claro = texto_claro = False
    for prop, valor, _ in decls:
        tipo = tipo_da_prop(prop)
        if tipo.startswith("var"):   # variável: escura = fundo, clara = texto
            x = [_luz(c) for c in COR.findall(valor)]
            if any(v and v[0] < 0.3 and v[2] >= 0.3 for v in x):
                fundo_escuro = True
            elif any(v and v[0] > 0.5 for v in x):
                texto_claro = True
            continue
        for cor in COR.findall(valor):
            x = _luz(cor)
            if not x:
                continue
            l, s, a = x
            if tipo == "fundo":
                if a >= 0.3 and l < 0.3:
                    fundo_escuro = True
                elif a >= 0.5 and l > 0.8:
                    fundo_claro = True
            elif tipo == "texto" and ((s < 0.25 and l > 0.5) or (s >= 0.25 and l > 0.55)):
                texto_claro = True
    return fundo_escuro or (texto_claro and not fundo_claro)


def regras_do_arquivo(css, arquivo):
    """-> [(media, seletores, declarações com cor, escura?)] de todas as regras com cor (fora as que já têm tema próprio)."""
    inteiro = arquivo in ARQUIVOS_INTEIROS
    saida = []

    def andar(texto, media):
        for cab, corpo in blocos(texto):
            if cab.startswith("@"):
                if cab.startswith(("@media", "@supports")):
                    if "prefers-color-scheme" in cab:
                        continue   # já tem tema próprio
                    andar(corpo, media + [cab])
                continue   # @keyframes, @font-face: sem cor de tema
            if "data-theme" in cab or (not inteiro and cab.strip() in (":root", "html", "body")):
                continue   # a paleta clara de base (:root de estilo.css) nunca entra; o :root do vidro (centro_leve) entra
            todas = declaracoes(corpo)
            com_cor = [(p, v, i) for p, v, i in todas if PROPS_COR.match(p) and COR.search(v)]
            if com_cor:
                escura = inteiro or "modo-ol" in cab or desenhada_no_escuro(todas)
                saida.append((media, dividir_seletores(cab), com_cor, escura))
    andar(sem_comentarios(css), [])
    return saida


def converter(decls):
    saida = []
    for prop, valor, imp in decls:
        tipo = tipo_da_prop(prop)
        saida.append((prop, COR.sub(lambda m, t=tipo: clarear(m.group(0), t), valor), imp))
    return saida


def irma(seletor, convertidos):
    """'.rb-tri i.f' é variação de '.rb-tri i' (convertida): precisa entrar também, senão a convertida (mais forte) passa por cima dela."""
    for base in convertidos:
        if seletor != base and seletor.startswith(base) and seletor[len(base)] in ".:[#":
            return True
    return False


def gerar():
    linhas = ["/* GERADO por ferramentas/gerar_tema_claro.py — não edite à mão: mude o gerador (ou AJUSTES nele) e rode de novo.",
              "   Tema claro do Painel: vale com o tema Claro, ou Sistema com o Windows claro. O tema escuro não muda. */"]
    por_arquivo = [(arq, regras_do_arquivo((PASTA_UI / arq).read_text(encoding="utf-8"), arq)) for arq in ARQUIVOS if (PASTA_UI / arq).exists()]
    convertidos = {s for _, regras in por_arquivo for _, sels, _, escura in regras if escura for s in sels}
    for arq, regras in por_arquivo:
        escolhidas = [(m, sels, converter(d)) for m, sels, d, escura in regras if escura or any(irma(s, convertidos) for s in sels)]
        if not escolhidas:
            continue
        linhas.append(f"\n/* ---- {arq} ---- */")
        for media, seletores, decls in escolhidas:
            corpo = ";".join(f"{p}:{v}{'!important' if imp else ''}" for p, v, imp in decls)
            claro = ",".join(seletor_claro(s, CLARO) for s in seletores)
            sistema = ",".join(seletor_claro(s, SISTEMA_CLARO) for s in seletores)
            regra = f"{claro}{{{corpo}}}\n@media (prefers-color-scheme: light){{{sistema}{{{corpo}}}}}"
            for m in reversed(media):
                regra = f"{m}{{{regra}}}"
            linhas.append(regra)
    linhas.append(AJUSTES)
    return "\n".join(linhas) + "\n"


def main():
    novo = gerar()
    if "--conferir" in sys.argv:
        atual = SAIDA.read_text(encoding="utf-8") if SAIDA.exists() else ""
        if atual != novo:
            print("tema_claro.css está desatualizado: rode python ferramentas/gerar_tema_claro.py")
            return 1
        print("tema_claro.css em dia")
        return 0
    SAIDA.write_text(novo, encoding="utf-8", newline="\n")
    print(f"gravado {SAIDA.relative_to(RAIZ)} ({novo.count(chr(10))} linhas)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
