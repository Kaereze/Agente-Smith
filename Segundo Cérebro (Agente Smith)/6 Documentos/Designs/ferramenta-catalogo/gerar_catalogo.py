"""Gera "Catalogo de pecas do Painel.html" (na pasta Designs, um nível acima) a partir de catalogo_pecas.json (HTML real
das peças, copiado do modo demonstração por copiar_pecas.js) e do CSS real do Painel (app_ui).
Uso: python gerar_catalogo.py <pasta do projeto> <pasta onde está o catalogo_pecas.json>"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parent
UI = Path(sys.argv[1]) / "app_ui"

# ---------- CSS do Painel ----------
fonte = (UI / "index.html").read_text(encoding="utf-8")
css = "\n".join(re.findall(r"<style>(.*?)</style>", fonte, re.S))
css += "\n" + (UI / "pecas" / "etiqueta.css").read_text(encoding="utf-8") + "\n" + (UI / "pecas" / "janela.css").read_text(encoding="utf-8")
css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)


def blocos(texto):
    """[(prelúdio, corpo ou None)] no nível de cima; corpo None = declaração solta (ex.: @import)."""
    saida, i, n = [], 0, len(texto)
    while i < n:
        j = i
        while j < n and texto[j] not in "{;}":
            j += 1
        if j >= n:
            break
        prel = texto[i:j].strip()
        if texto[j] == ";":
            saida.append((prel, None)); i = j + 1; continue
        if texto[j] == "}":
            i = j + 1; continue
        prof, k = 1, j + 1
        while k < n and prof:
            prof += {"{": 1, "}": -1}.get(texto[k], 0); k += 1
        saida.append((prel, texto[j + 1:k - 1])); i = k
    return saida


def trocar_seletor(sel):
    partes = []
    for s in sel.split(","):
        s = s.strip()
        if '[data-theme="light"]' in s or "[data-theme='light']" in s:
            continue
        s = s.replace(':root:not([data-theme="light"])', ".cat-raiz").replace(':root[data-theme="dark"]', ".cat-raiz")
        s = s.replace(':root:not([data-theme="dark"])', ".cat-raiz-claro")
        s = re.sub(r":root\b", ".cat-raiz", s)
        s = re.sub(r"(^|[\s>+~(])html\b", r"\1.cat-raiz", s)
        s = re.sub(r"(^|[\s>+~(])body\b", r"\1.cat-corpo", s)
        partes.append(s)
    return ", ".join(partes)


def transformar(texto):
    saida = []
    for prel, corpo in blocos(texto):
        if corpo is None:
            continue
        p = prel.replace(" ", "")
        if prel.startswith("@media"):
            if "prefers-color-scheme:light" in p or "prefers-reduced-motion" in p:
                continue
            interno = transformar(corpo)
            if "prefers-color-scheme:dark" in p:
                saida.append(interno)          # o catálogo é sempre o tema escuro, como o Painel da equipe
            elif interno.strip():
                saida.append(f"{prel}{{{interno}}}")
        elif prel.startswith(("@keyframes", "@font-face", "@supports", "@-webkit-keyframes")):
            saida.append(f"{prel}{{{corpo}}}")
        elif prel.startswith("@"):
            continue
        else:
            sel = trocar_seletor(prel)
            if sel:
                saida.append(f"{sel}{{{corpo}}}")
    return "\n".join(saida)


css_cat = transformar(css)
css_cat += """
.cat-pai{display:contents!important}
.cat-solto{position:relative!important;inset:auto!important;left:auto!important;right:auto!important;top:auto!important;bottom:auto!important;transform:none!important;margin:0!important;z-index:auto!important}
"""

# cores mais usadas (o Painel escuro usa muita cor fixa além dos tokens)
hexes = Counter(h.lower() for h in re.findall(r"#[0-9a-fA-F]{6}\b", css_cat))

dados = json.loads((Path(sys.argv[2]) / "catalogo_pecas.json").read_text(encoding="utf-8"))


def limpar(h):
    h = re.sub(r"([\w.+-]+)@(?![\w.-]*exemplo)[\w-]+(?:\.[\w-]+)+", r"\1@exemplo.com.br", h)
    h = re.sub(r"\(\d{2}\)\s?\d{4,5}-\d{4}", "(00) 0000-0000", h)
    h = re.sub(r"<img[^>]*>", "", h)
    # CPF/CNPJ sorteados pelo modo demonstração podem coincidir com os de alguém: viram zeros
    h = re.sub(r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b", "000.000.000-00", h)
    h = re.sub(r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b", "00.000.000/0000-00", h)
    h = re.sub(r"(?<![\d.,])\d{11}(?![\d.,])", "00000000000", h)
    h = re.sub(r"(?<![\d.,])\d{14}(?![\d.,])", "00000000000000", h)
    h = re.sub(r'\s(src|srcdoc)="[^"]*"', "", h)
    return h


# ---------- textos de cada peça ----------
GRUPOS = [
    ("fundamentos", "Fundamentos", "Cores, letras e ícones que todas as peças usam."),
    ("estrutura", "Estrutura da tela", "O que fica sempre na tela: barra da esquerda, faixa de cima, barra de baixo e a bolha de saúde."),
    ("botoes", "Botões", "Um de cada tipo, com os estados: normal, mouse em cima, foco pelo teclado e desligado."),
    ("pecas", "Etiquetas", "Peça única (pecas/etiqueta.js): as mesmas cores e palavras em todas as telas."),
    ("visao", "Visão geral", "Os blocos da tela Visão geral, de cima para baixo."),
    ("notas", "Notas fiscais", "Lista de pedidos, filtros e o pedido aberto."),
    ("emails", "E-mails", "A tela no jeito do Outlook: pastas, lista, e-mail aberto, filtro, botão direito e pesquisa."),
    ("escrever", "Escrever e enviar", "A tela de escrever (Novo e-mail, Responder, Enviar NF) e as partes dela."),
    ("envio", "Andamento do envio", "O que aparece no canto de baixo depois de clicar Enviar."),
    ("janelas", "Janelas e avisos", "Avisos rápidos e janelas por cima da tela."),
    ("robo", "Tela do robô", "Janela grande do robô, gaveta do pedido, robô minimizado e o aviso de fim."),
    ("maquinas", "Máquinas", "Os 4 PCs, versão, Outlook e saúde de cada um."),
    ("animacoes", "Animações", "Cada movimento do Painel rodando, com câmera lenta (a mesma página de antes, aqui dentro)."),
]
T = {
    "lateral-icones": ("Barra da esquerda · só ícones", "56 px, ícones com o número vermelho no canto. É o jeito que o Painel abre.", "Todas as telas"),
    "lateral-nomes": ("Barra da esquerda · com os nomes", "232 px, empurra a tela; os números viram selo no fim da linha.", "Botão do pé da barra"),
    "quem-esta": ("Quem está neste PC", "Lista dos agentes ao lado da barra, com \"você, neste PC\" e Fechar o Painel separado.", "Clique no avatar do pé da barra"),
    "topo": ("Faixa de cima", "Abas Página Inicial, Enviar/Receber e Exibir, Caixa de (agente) e a pesquisa nos Outlook dos 4 PCs.", "Todas as telas"),
    "rodape": ("Barra de baixo (status)", "Itens, não lidos, Central sincronizada, robô, PCs no ar, tema, modo professor e ajuda.", "Todas as telas"),
    "saude": ("Bolha de saúde com o painel aberto", "Avisos do sistema (Caixa de Saída travada, pedido sem envio etc.).", "Canto de baixo à direita"),
    "resumo-dia": ("Resumo do dia", "Ontem/Hoje com os números do dia e quem fez o quê.", "Topo da Visão geral"),
    "cab-operador": ("Título e escolha de operador", "Filtra a tela por agente: Todos, João, Clara, Cristian, Bernardo.", "Visão geral"),
    "dica-prof": ("Dica do modo professor", "Frase azul que explica a tela; some quando o modo professor é desligado.", "Várias telas"),
    "faixa-resumo": ("Faixa de indicadores", "5 números com tendência; a faixa colorida estica com o mouse em cima.", "Visão geral · Agora"),
    "tabela-operador": ("O que cada caixa tem agora", "Tabela por operador; clicar numa linha filtra a tela.", "Visão geral · Por operador"),
    "grafico-idade": ("Há quanto tempo esperam", "Barras por faixa de dias (verde, âmbar, vermelho).", "Visão geral · Por operador"),
    "cartao-ligacoes": ("Cartão Ligações", "Hoje, 7 dias e o mês, por hotel ou por agente (novo, 22/10).", "Visão geral"),
    "grafico-dias": ("Pedidos de cada dia", "Colunas empilhadas por dia, com 7/30/90 dias e Ver em tabela.", "Visão geral · Histórico"),
    "grafico-dias-tabela": ("Pedidos de cada dia · em tabela", "O mesmo gráfico em números (leitor de tela e quem prefere tabela).", "Botão Ver em tabela"),
    "notas-cab": ("Cabeçalho das Notas fiscais", "Título, dica, avisos, abas por operador e as pílulas de filtro.", "Notas fiscais"),
    "lista-vazia": ("Lista vazia", "\"Nada pendente\": quando não há solicitação na Caixa de Entrada.", "Notas fiscais"),
    "lista-pedidos": ("Lista de pedidos", "Cabeçalho com ordenação, linhas com etiqueta e prazo, paginação.", "Notas fiscais"),
    "linha-pedido-sel": ("Linha de pedido selecionada", "Uma linha da lista, com o destaque de selecionada.", "Notas fiscais"),
    "detalhe-pedido": ("Pedido aberto", "Ficha do pedido (tomador, documento, prazo) e as ações.", "Notas fiscais → clicar num pedido"),
    "filtro-aberto": ("Filtro aberto (Situação)", "A peça única do filtro com o menu aberto e quantos tem em cada opção.", "Notas fiscais"),
    "faixa-outlook": ("Faixa de botões do Outlook", "Novo e-mail, Excluir, Arquivar, Responder, Encaminhar… e Enviar NF.", "E-mails"),
    "pastas": ("Pastas (esquerda)", "Favoritos e as caixas de cada agente, com a pasta de um agente aberta.", "E-mails"),
    "lista-cab": ("Cabeçalho da lista", "Todas / Não lidos, Filtro e Por data.", "E-mails"),
    "linha-nao-lida": ("E-mail não lido", "Nome em negrito e a barra azul na esquerda.", "E-mails"),
    "linha-lida": ("E-mail lido", "Igual ao Outlook: sem negrito e sem barra.", "E-mails"),
    "linha-urgente": ("E-mail urgente", "Bandeira vermelha e etiqueta Urgente.", "E-mails"),
    "linha-form": ("E-mail de formulário", "Alfinete e etiqueta Formulário.", "E-mails"),
    "linha-selecionada": ("E-mail selecionado", "O destaque da linha aberta.", "E-mails"),
    "lista-emails": ("Lista de e-mails", "Grupo \"Hoje\" e as linhas, como no Outlook.", "E-mails"),
    "leitura": ("E-mail aberto", "Cabeçalho, de onde veio, anexos, a faixa do pedido e o texto.", "E-mails → clicar num e-mail"),
    "filtro-lista": ("Filtro da lista aberto", "Pedido de correção, Sem resposta, Com anexo, Nota dividida (e Só ligações em Itens Enviados).", "E-mails"),
    "menu-direito": ("Menu do botão direito", "Lido/não lido e urgência (em Itens Enviados: marcar ligação).", "E-mails → botão direito"),
    "busca": ("Pesquisa", "Procura nos Outlook dos 4 PCs: hóspede, CPF/CNPJ, NF.", "Faixa de cima"),
    "lista-enviados": ("Itens Enviados com a etiqueta Ligação", "O que saiu nas últimas 72 h; a etiqueta verde-água é a Ligação.", "E-mails → Itens Enviados"),
    "novo-email": ("Tela de escrever · Novo e-mail", "Janela inteira: Enviar + Ligação, De/Para/Cc/Assunto, anexo, respostas prontas, mensagem e assinatura.", "E-mails → Novo e-mail"),
    "escrever-topo-lig": ("Topo da tela de escrever com Ligação", "A etiqueta Ligação aparece no topo quando o botão está ligado.", "Tela de escrever"),
    "escrever-cab-lig": ("Cabeçalho com o botão Ligação ligado", "Enviar, Ligação (verde-água com ✓) e os campos.", "Tela de escrever"),
    "zona-anexo": ("Área de anexo", "Arraste o arquivo aqui ou clique para escolher.", "Tela de escrever"),
    "respostas-prontas": ("Respostas prontas", "Solicitação de dados, Segue a NF, NF corrigida…", "Tela de escrever"),
    "combo-de": ("Campo De com busca", "Digita parte do hotel, da caixa ou do agente e escolhe de qual caixa sai.", "Novo e-mail"),
    "responder-nf": ("Responder com a NF (dentro do e-mail)", "A mensagem abre no lugar do e-mail lido, com o original citado embaixo.", "E-mails → Enviar NF"),
    "pilula-enviando": ("Pílula · enviando", "Rodinha azul: o pedido foi entregue e o Outlook está mandando.", "Canto de baixo à esquerda"),
    "pilula-enviado": ("Pílula · enviado", "✓ verde; some sozinha em 3 s.", "Canto de baixo à esquerda"),
    "pilula-erro": ("Pílula · não enviou", "Fica até a pessoa clicar em Ver.", "Canto de baixo à esquerda"),
    "cartao-erro": ("Cartão do erro de envio", "O motivo e o botão Escrever de novo (reabre com o texto).", "Pílula vermelha → Ver"),
    "toast": ("Aviso rápido", "Recado curto que some sozinho.", "Todas as telas"),
    "toast-erro": ("Aviso rápido de erro", "O mesmo aviso, em vermelho.", "Todas as telas"),
    "ajuda": ("Janela de ajuda", "Atalhos de teclado e o que cada tela faz.", "Botão ? da barra de baixo"),
    "robo-agora": ("Tela do robô · Agora", "Estado, rodada atual com as etapas, pedidos esperando a NF e avisos.", "Lateral → Robô ou Enviar pendentes"),
    "robo-gaveta": ("Gaveta do pedido", "O caminho do pedido: recebido, enviado ao hotel, NF emitida, NF enviada.", "Tela do robô → clicar num pedido"),
    "robo-registro": ("Tela do robô · Registro", "O registro completo do robô, com filtro e busca.", "Tela do robô → Registro"),
    "robo-minimizado": ("Robô minimizado", "A rodada continua no canto, com a etapa e as últimas linhas.", "Minimizar a tela do robô"),
    "robo-fim": ("Aviso de fim da rodada", "Rodada concluída (some em 15 s) ou com aviso (fica até fechar).", "Canto de baixo à direita"),
    "maquinas": ("Tela Máquinas", "Cada PC: agente, versão, Outlook, saúde e os comandos (Atualizar todos).", "Lateral → Máquinas (só admin)"),
    "etiquetas": ("Todas as etiquetas", "Situação (pílula cheia), alertas (contorno) e a Ligação.", "Listas, e-mails e pedidos"),
    "bt-novo": ("Botão principal (Novo e-mail)", "Azul do Outlook, o mais forte da faixa.", "E-mails"),
    "bt-faixa": ("Botão da faixa", "Ícone + texto, fundo só no mouse em cima.", "E-mails"),
    "bt-enviar-pend": ("Enviar pendentes (lateral)", "Abre a tela do robô.", "Pé da barra da esquerda"),
    "bt-recolher": ("Mostrar os nomes / Só ícones", "Seta que gira meia volta.", "Pé da barra da esquerda"),
    "bt-filtro": ("Pílula de filtro", "Abre o menu do filtro; ligada fica azul com ✕ para tirar.", "Listas"),
    "bt-aba": ("Aba Todas / Não lidos", "Sublinhado azul na aba atual.", "E-mails"),
    "bt-pasta": ("Pasta da esquerda", "Favorito com contador.", "E-mails"),
    "bt-rodape": ("Botão da barra de baixo", "Pequeno, com contorno.", "Barra de baixo"),
    "bt-saude": ("Bolha de saúde", "Vermelha quando tem aviso.", "Canto de baixo à direita"),
    "bt-lateral": ("Item da barra da esquerda", "Ícone; a tela atual tem a barra azul na esquerda.", "Barra da esquerda"),
    "bt-seg": ("Botões em grupo (Ontem/Hoje)", "Um ligado por vez.", "Visão geral"),
    "bt-link": ("Botão de texto (Ver em tabela)", "Parece link.", "Cartões da Visão geral"),
    "bt-kpi": ("Indicador clicável", "Abre a lista daquele número.", "Visão geral"),
    "bt-enviar": ("Enviar (tela de escrever)", "Grande, desligado até ter Para e Assunto.", "Tela de escrever"),
    "bt-ligacao": ("Ligação", "Liga/desliga; ligado fica verde-água com ✓.", "Tela de escrever"),
    "bt-modelo": ("Resposta pronta", "Troca o texto da mensagem.", "Tela de escrever"),
    "bt-selo": ("Escolha da assinatura", "O selo usado embaixo da mensagem.", "Tela de escrever"),
    "bt-fechar": ("Fechar (×)", "Fecha a janela.", "Janelas"),
    "bt-robo": ("Chip do robô", "Verde tudo certo, azul enviando, vermelho com aviso.", "Barra de baixo"),
}
SOLTOS = {"robo-gaveta"}
MENUS = {"filtro-aberto": 300, "filtro-lista": 280}
PULAR = {"cx-cab", "busca-sugestoes", "bt-op", "bt-aba"}

pecas = []
for p in dados["pecas"]:
    if p["chave"] in PULAR or not p["largura"] or not p["altura"]:
        continue
    nome, desc, onde = T.get(p["chave"], (p["chave"], "", ""))
    pecas.append({"g": p["grupo"], "k": p["chave"], "n": nome, "d": desc, "o": onde, "m": "flutua" if p["chave"] in SOLTOS else p["modo"], "e": p["estados"],
                  "w": p["largura"], "h": p["altura"], "html": limpar(p["html"]), "pais": p["pais"],
                  "corpo": p.get("corpo", ""), "raiz": p.get("raiz", ""), "menu": MENUS.get(p["chave"], 0)})

ordem_g = {g: i for i, (g, _, _) in enumerate(GRUPOS)}
pecas.sort(key=lambda x: ordem_g.get(x["g"], 99))


def bonito(h, lim=400):
    """HTML com uma tag por linha e recuo (só pra ler)."""
    vazias = {"br", "hr", "img", "input", "meta", "link", "use", "path", "circle", "rect", "line", "polyline", "source"}
    linhas, nivel = [], 0
    for tok in re.findall(r"<[^>]+>|[^<]+", h):
        if tok.startswith("</"):
            nivel = max(0, nivel - 1); linhas.append("  " * nivel + tok)
        elif tok.startswith("<"):
            linhas.append("  " * nivel + tok)
            nome = re.match(r"<\s*([a-zA-Z0-9-]+)", tok)
            if nome and nome.group(1).lower() not in vazias and not tok.endswith("/>"):
                nivel += 1
        else:
            t = tok.strip()
            if t:
                linhas.append("  " * nivel + t)
    if len(linhas) > lim:
        linhas = linhas[:lim] + [f"… (+{len(linhas) - lim} linhas)"]
    return "\n".join(linhas)


for p in pecas:
    p["bonito"] = bonito(p["html"])

cores = [[n, v] for n, v in dados["tokens"]]
fixas = [[h, c] for h, c in hexes.most_common(28)]
sprite = "".join(limpar(s) for s in dados["simbolos"])
anim = (BASE / "animacoes_fonte.html").read_text(encoding="utf-8")

modelo = (BASE / "modelo_catalogo.html").read_text(encoding="utf-8")
saida = (modelo
         .replace("/*ANIM*/", anim.replace("<title>Animações do Painel</title>", ""))
         .replace("/*CSS_PAINEL*/", css_cat.replace("</", "<\\/"))
         .replace("/*DADOS*/", json.dumps({"pecas": pecas, "grupos": GRUPOS, "cores": cores, "fixas": fixas, "sprite": sprite},
                                          ensure_ascii=False).replace("</", "<\\/")))
(BASE.parent / "Catalogo de pecas do Painel.html").write_text(saida, encoding="utf-8")
print("peças:", len(pecas), "· página:", len(saida))
