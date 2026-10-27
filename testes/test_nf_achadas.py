"""NF achadas nas pastas pelo CPF/CNPJ dentro do PDF (27/10/2026): só sugere, nunca envia; a tag ✅ não é prova."""
import datetime
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import nf_achadas  # noqa: E402

AGORA = datetime.datetime(2026, 10, 27, 12, 0)
TEXTO = ("DANFSe v1.0 Documento Auxiliar da NFS-e\nChave de Acesso 4120000000000000000000000000000000000000000000000\n"
         "TOMADOR DO SERVIÇO CNPJ / CPF / NIF {doc} Nome / Nome Empresarial EMPRESA EXEMPLO LTDA\n"
         "Descrição do Serviço Hospedagem CHECK IN {ini} CHECK OUT {fim} HOSPEDE EXEMPLO\n"
         "Valor do serviço R$ {valor} Valor líquido R$ {valor} " + "x" * 80)


def nota(doc="12.345.678/0001-90", ini="30/09/2026", fim="02/10/2026", valor="1.480,00"):
    return TEXTO.format(doc=doc, ini=ini, fim=fim, valor=valor)


def sol(chave="p1", nome="HOSPEDE EXEMPLO", ini="30/09/2026 a 02/10/2026", valor="R$ 1.480,00", doc="12.345.678/0001-90", hotel="CENTER"):
    return {"chave": chave, "hotel": hotel, "nome": nome, "nomes": [nome], "data": "2026-10-01", "email": "h@x.com", "emails": [],
            "campos": [("Nome do tomador", "EMPRESA EXEMPLO LTDA"), ("CPF/CNPJ do tomador", doc),
                       ("Check-in / Check-out", ini), ("Valor das diárias", valor)]}


def indice(tmp_path, notas):
    """notas: {nome_do_arquivo: (texto, dias_atras)}"""
    ind = nf_achadas.Indice(tmp_path / "nf.json")
    for nome, (texto, dias) in notas.items():
        mtime = (AGORA - datetime.timedelta(days=dias)).timestamp()
        ind.dados[f"C:/d/{nome}"] = {"mtime": mtime, "nome": nome, "nf": nome.split()[1] if nome.startswith("NF") else "",
                                     "doc": nf_achadas.documento_tomador(texto), "sem_texto": False, "texto": texto}
    return ind


def achadas(ind, s, nfs=(), ligadas=(), outros=None):
    return nf_achadas.achadas_do_pedido(ind, s, list(nfs), set(ligadas), outros or {}, agora=AGORA)


def test_uma_nota_que_bate_vira_sugestao_forte(tmp_path):
    r = achadas(indice(tmp_path, {"NF 2186 - X.pdf": (nota(), 1)}), sol())
    assert len(r) == 1 and r[0]["forte"] and not r[0]["outra"] and not r[0]["possivel"] and r[0]["via"] == "documento"
    assert "CNPJ" in r[0]["prova"]


def test_nota_de_outro_documento_ou_fora_dos_30_dias_nao_aparece(tmp_path):
    ind = indice(tmp_path, {"NF 1 - A.pdf": (nota(doc="98.765.432/0001-10"), 1), "NF 2 - B.pdf": (nota(), 45)})
    assert achadas(ind, sol()) == []


def test_mesma_nota_ja_ligada_ao_pedido_nao_volta_a_aparecer(tmp_path):
    ind = indice(tmp_path, {"NF 2186 - X.pdf": (nota(), 1)})
    assert achadas(ind, sol(), nfs=["2186"]) == []


def test_nota_ligada_a_outro_pedido_do_mesmo_hotel_nao_aparece(tmp_path):
    ind = indice(tmp_path, {"NF 2186 - X.pdf": (nota(), 1)})
    assert achadas(ind, sol(), ligadas=[("CENTER", "2186")]) == []
    assert len(achadas(ind, sol(hotel="OUTRO"), ligadas=[("CENTER", "2186")])) == 1   # outro hotel tem outra numeração


def test_pedido_com_nf_ganha_outra_nota_quando_datas_ou_valor_diferem(tmp_path):
    ind = indice(tmp_path, {"NF 2230 - X.pdf": (nota(ini="12/10/2026", fim="14/10/2026", valor="980,00"), 1)})
    r = achadas(ind, sol(), nfs=["2186"])
    assert len(r) == 1 and r[0]["outra"] and not r[0]["forte"]
    assert achadas(ind, sol()) == []   # sem NF ligada, nota de outras datas não é deste pedido


def test_nota_que_e_mais_de_outro_pedido_nao_polui_este_pedido_ja_com_nf(tmp_path):
    ind = indice(tmp_path, {"NF 2230 - X.pdf": (nota(ini="12/10/2026", fim="14/10/2026", valor="980,00"), 1)})
    outro = nf_achadas._alvo(sol(chave="p2", nome="JOAO EXEMPLO", ini="12/10/2026 a 14/10/2026", valor="R$ 980,00"))
    assert achadas(ind, sol(), nfs=["2186"], outros={"12345678000190": [outro]}) == []


def test_mesmo_cnpj_em_varios_pedidos_vira_possivel(tmp_path):
    ind = indice(tmp_path, {"NF 2190 - X.pdf": (nota(), 1)})
    outro = nf_achadas._alvo(sol(chave="p2", nome="MARIA EXEMPLO"))
    r = achadas(ind, sol(), outros={"12345678000190": [outro]})
    assert len(r) == 1 and r[0]["possivel"]


def test_duas_notas_do_mesmo_pedido_a_mais_nova_em_destaque(tmp_path):
    ind = indice(tmp_path, {"NF 2186 - X.pdf": (nota(), 2), "NF 2201 - X.pdf": (nota(), 0)})
    r = achadas(ind, sol())
    assert [a["nf"] for a in r] == ["2201", "2186"] and r[0]["mais_nova"] and not r[1]["mais_nova"]


def test_nota_escaneada_sem_leitura_fica_de_fora(tmp_path):
    ind = indice(tmp_path, {"NF 5 - X.pdf": (nota(), 1)})
    for e in ind.dados.values():
        e["sem_texto"] = True
    assert achadas(ind, sol()) == []


def test_varrer_le_so_o_novo_e_guarda_o_documento(tmp_path):
    lista = {"C:/d/NF 2186 - X.pdf": ((AGORA - datetime.timedelta(days=1)).timestamp(), "NF 2186 - X.pdf"),
             "C:/d/velha.pdf": ((AGORA - datetime.timedelta(days=60)).timestamp(), "velha.pdf")}
    lidas = []

    def ler(c):
        lidas.append(c)
        return nota()
    cfg = {"dropbox_notas": {"pastas": ["P"]}}
    listar = lambda pasta: [(c, m, n) for c, (m, n) in lista.items()]   # noqa: E731
    ind = nf_achadas.Indice(tmp_path / "nf.json")
    assert nf_achadas.varrer(cfg, ind, ler, agora=AGORA, listar=listar, na_nuvem=lambda c: False) == 1
    assert ind.dados["C:/d/NF 2186 - X.pdf"]["doc"] == "12345678000190" and "C:/d/velha.pdf" not in ind.dados
    assert nf_achadas.varrer(cfg, ind, ler, agora=AGORA, listar=listar, na_nuvem=lambda c: False) == 0   # já vista: não lê de novo
    assert lidas == ["C:/d/NF 2186 - X.pdf"]


def test_arquivo_so_na_nuvem_nao_e_lido(tmp_path):
    ind = nf_achadas.Indice(tmp_path / "nf.json")
    listar = lambda pasta: [("C:/d/NF 1 - X.pdf", (AGORA - datetime.timedelta(days=1)).timestamp(), "NF 1 - X.pdf")]   # noqa: E731
    assert nf_achadas.varrer({"dropbox_notas": {"pastas": ["P"]}}, ind, lambda c: 1 / 0, agora=AGORA, listar=listar,
                             na_nuvem=lambda c: True) == 0


def test_tag_sem_envio_nos_itens_enviados_gera_aviso():
    enviados = [{"assunto": "NF 2186 - HOSPEDE EXEMPLO", "para": "h@x.com"}, {"assunto": "RES: NF 2201 - X", "para": "caixa@hotel.com"}]
    assert nf_achadas.sem_envio_confirmado(["2186"], enviados, ["h@x.com"]) == []
    assert nf_achadas.sem_envio_confirmado(["2201"], enviados, ["h@x.com"]) == ["2201"]   # a resposta do hóspede não vale
    assert nf_achadas.sem_envio_confirmado(["999"], enviados, ["h@x.com"]) == ["999"]


def test_tela_e_servidor_ligados_sem_marcar_outra_nota():
    ui = RAIZ / "app_ui" / "painel.js"
    js = ui.read_text(encoding="utf-8")
    srv = (RAIZ / "src" / "app_servidor.py").read_text(encoding="utf-8")
    assert "avisos_nf" in js and "outra nota" in js and "a.outra || a.possivel" in js
    assert "!o.sugestoes[0].outra && !o.sugestoes[0].possivel" in js          # "outra nota" e "possível" nunca vêm marcadas
    assert "estado.iniciar_nf_achadas()" in srv and "nf_achadas.achadas_do_pedido" in srv
    assert "nf_achadas" not in (RAIZ / "src" / "envio_nf.py").read_text(encoding="utf-8")   # a peça não envia nada
