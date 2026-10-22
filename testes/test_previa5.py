"""Prévia 5 no Painel (20/10/2026): o visual do Outlook escuro e as peças que dependem dele.

O nome repetido entre arquivos da tela derruba o arquivo inteiro no navegador (aconteceu na prévia: "linhaPedido" e
"acompanharEnvio" já existiam). Este teste barra isso antes de chegar aos 4 PCs.
"""
import re
from collections import Counter
from pathlib import Path

UI = Path(__file__).resolve().parent.parent / "app_ui"
TOPO = re.compile(r"^(?:async\s+)?(?:function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=)", re.M)


def _scripts():
    html = (UI / "index.html").read_text(encoding="utf-8")
    blocos = re.findall(r"<script>([\s\S]*?)</script>", html)
    return blocos + [(UI / f).read_text(encoding="utf-8") for f in ("graficos.js", "correio.js", "painel.js", "robo.js")]


def test_nenhum_nome_repetido_entre_os_arquivos_da_tela():
    nomes = Counter(a or b for s in _scripts() for a, b in TOPO.findall(s))
    repetidos = sorted(n for n, q in nomes.items() if q > 1)
    assert not repetidos, f"nome declarado mais de uma vez no topo dos scripts da tela: {repetidos}"


def test_camada_da_previa5_no_fim_do_estilo():
    html = (UI / "index.html").read_text(encoding="utf-8")
    estilo = html[html.index("<style>"):html.index("</style>")]
    i = estilo.index("Prévia 5 no Painel")
    assert i > estilo.index("E-mails EXATAMENTE como a prévia aprovada")   # vem depois: vence as camadas antigas
    assert "#3da755" not in estilo[estilo.index("E-mails EXATAMENTE"):i].lower()   # verde da camada antiga trocado


def test_formulario_na_ordem_do_email():
    js = (UI / "correio.js").read_text(encoding="utf-8")
    ordem = re.search(r"const ORDEM_FORM = \[([\s\S]*?)\];", js).group(1)
    assert len(re.findall(r"/[^/]+/", ordem)) == 13   # os 13 campos do e-mail do Emissor Automático
    assert "Dados para emissão de Nota Fiscal:" in js and "Enviado por:" in js and "Enviado em:" in js


def test_pesquisa_mostra_os_pedidos_na_hora_e_envio_nao_espera():
    js_c = (UI / "correio.js").read_text(encoding="utf-8")
    js_p = (UI / "painel.js").read_text(encoding="utf-8")
    assert "function secoesDaBusca" in js_c and "secoesDaBusca(busca) + corpo" in js_c
    assert "envNF.fechar();\n  seguirEnvio(r.id, ctx);" in js_p   # a janela fecha antes de acompanhar
