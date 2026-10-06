import os
import datetime
import time

import envio_nf as en
from conftest import CENTRAL

SOL = {"chave": "k1", "aba": "Aba X", "carimbo": "9/30/2026 10:00:00", "email": "hospede@x.com", "hotel": "NOVO CWB",
       "nome": "FH Manutenção Industrial LTDA", "emails": ["hospede@x.com", "financeiro@fh.com"], "nomes": []}
CAIXA = "nf@novocwb.com.br"


class Relogio:
    def __init__(self):
        self.t = datetime.datetime(2026, 10, 1, 10, 0, 0)

    def __call__(self):
        return self.t


def _prep(planilha):
    for aba, cab in ((en.ABA_FILA, en.CAB_FILA), (en.ABA_ANEXOS, en.CAB_ANEXOS), (en.ABA_PCS, en.CAB_PCS)):
        planilha.criar_aba_log(CENTRAL, aba, cab)


def _ler(planilha):
    return planilha.ler_abas(CENTRAL, [en.ABA_FILA, en.ABA_PCS])[0]


def _servico(planilha, cfg, pc, contas, enviados, relogio, registradas=None, falhar=False):
    def enviar(conta_de, para, cc, assunto, mensagem, anexos, agente="", selo=""):
        if falhar:
            raise RuntimeError("Outlook fechado")
        enviados.append((pc, conta_de, para, assunto, b"".join(open(a, "rb").read() for a in anexos)))
    return en.ServicoEnvio(planilha, dict(cfg, dropbox_notas={}), pc,
                           lambda p, q: (registradas if registradas is not None else []).append((p["nfs"], q)),
                           enviar=enviar, ler_contas=lambda: list(contas), relogio=relogio)


def _esperar(serv, id_envio):
    for _ in range(100):
        if serv.locais.get(id_envio, {}).get("estado") not in (None, "enviando"):
            return serv.locais[id_envio]
        time.sleep(0.02)
    return serv.locais.get(id_envio)


def test_assunto_e_destinatarios():
    assert en.assunto_sugerido("NF 1212 - FH MANUTENCAO.pdf", "", "x") == "NF 1212 - FH MANUTENCAO"
    assert en.assunto_sugerido("nota.pdf", "77", "Fh Manutenção") == "NF 77 - FH MANUTENÇÃO"
    assert en.destinatarios(SOL) == ["hospede@x.com", "financeiro@fh.com"]


def test_sugestao_so_mostra_nota_que_confere_com_o_pedido(tmp_path, cfg):
    """[06/10/2026] "não tenha nenhuma possível nota fiscal": só a que o PDF confirma."""
    import datetime as dt
    import time as tm
    for nome in ("NF 1561 - MAICON FERNANDO DOS SANTOS - 1.pdf", "NF 900 - CHARLES MACARIO - 2.pdf",
                 "NF 901 - CHARLES MACARIO DOS SANTOS FILHO - 3.pdf", "NF 4371 - JUNIOR SANTOS - 4.pdf",
                 "NF 375 - CHARLES - 5.pdf", "NF 902 - CHARLES MACARIO DOS SANTOS FILHO - 6.pdf"):
        (tmp_path / nome).write_bytes(b"x")
    velho = tm.mktime(dt.datetime(2025, 1, 10).timetuple())
    os.utime(tmp_path / "NF 902 - CHARLES MACARIO DOS SANTOS FILHO - 6.pdf", (velho, velho))   # estadia antiga
    sol = dict(SOL, nome="Charles Macario dos Santos Filho", nomes=[], data=dt.date.today().isoformat(),
               campos=[("CPF Tomador", "012.345.678-90")])
    corpo = (" PREFEITURA MUNICIPAL NOTA FISCAL DE SERVIÇOS ELETRÔNICA PRESTADOR REDE ANDRADE HOTEL LTDA "
             "DISCRIMINAÇÃO DOS SERVIÇOS HOSPEDAGEM DIÁRIAS VALOR TOTAL DA NOTA ") * 2
    textos = {"3.pdf": "TOMADOR CHARLES MACARIO DOS SANTOS FILHO CPF 012.345.678-90" + corpo,
              "2.pdf": "TOMADOR CHARLES MACARIO CPF 999.888.777-66" + corpo, "6.pdf": "CPF 012.345.678-90" + corpo}
    lidos = []
    def ler(caminho, mtime):
        lidos.append(os.path.basename(caminho))
        return next((v for k, v in textos.items() if caminho.endswith(k)), "")
    c = dict(cfg, dropbox_notas={"pastas": [str(tmp_path)]})
    en.listar_notas_dropbox(c, forcar=True)
    sug = [a["nome"] for a in en.sugestoes_dropbox(sol, c, ler_texto=ler)]
    assert sug == ["NF 901 - CHARLES MACARIO DOS SANTOS FILHO - 3.pdf"]
    assert not any("MAICON" in n or "JUNIOR" in n or "- 6.pdf" in n for n in lidos)   # nem abre essas


def test_anexo_em_partes_volta_igual():
    conteudo = bytes(range(256)) * 600
    linhas = [en.CAB_ANEXOS] + en.partes_do_anexo("ENV-1", "nota.pdf", conteudo)
    assert len(linhas) > 3
    assert en.juntar_anexo(linhas, "ENV-1") == ("nota.pdf", conteudo)
    assert en.juntar_anexo(linhas[:-1], "ENV-1") == (None, None)   # faltando parte


def test_outro_pc_envia_da_caixa_do_hotel(cfg, planilha):
    _prep(planilha)
    rel, enviados, registradas = Relogio(), [], []
    pc_a = _servico(planilha, cfg, "PC-JOAO", ["nf@ondina.com"], enviados, rel)
    pc_b = _servico(planilha, cfg, "PC-CRISTIAN", [CAIXA], enviados, rel, registradas)
    pc_b.tick(_ler(planilha), "Cristian")                 # publica a caixa
    pc_a.tick(_ler(planilha), "João")
    r = pc_a.pedir(SOL, "hospede@x.com", "NF 1212 - FH", CAIXA, [{"tipo": "arquivo", "nome": "NF 1212 - FH.pdf", "conteudo": b"%PDF teste"}], "João")
    assert r["ok"] and r["destino"] == "PC-CRISTIAN" and not enviados
    assert pc_a.situacao(r["id"], en.dobrar_fila(_ler(planilha)[en.ABA_FILA]))["estado"] == "aguardando"
    pc_b.tick(_ler(planilha), "Cristian")                 # o PC do Cristian pega e envia
    assert enviados == [("PC-CRISTIAN", CAIXA, "hospede@x.com", "NF 1212 - FH", b"%PDF teste")]
    assert registradas == [(["1212"], "João")]
    fila = en.dobrar_fila(_ler(planilha)[en.ABA_FILA])
    assert pc_a.situacao(r["id"], fila)["estado"] == "enviado"
    assert all(not l[4] for l in planilha.aba(en.ABA_ANEXOS)[1:])   # anexo apagado da planilha
    pc_b.tick(_ler(planilha), "Cristian")
    assert len(enviados) == 1                              # não reenvia


def test_caixa_neste_pc_envia_na_hora(cfg, planilha):
    _prep(planilha)
    rel, enviados = Relogio(), []
    pc = _servico(planilha, cfg, "PC-JOAO", [CAIXA], enviados, rel)
    pc.tick(_ler(planilha), "João")
    r = pc.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, [{"tipo": "arquivo", "nome": "n.pdf", "conteudo": b"x"}], "João")
    assert r["destino"] == "PC-JOAO" and _esperar(pc, r["id"])["estado"] == "enviado"
    assert len(planilha.aba(en.ABA_ANEXOS)) == 1           # local: anexo nem passa pela planilha


def test_nenhum_pc_com_a_caixa(cfg, planilha):
    _prep(planilha)
    pc = _servico(planilha, cfg, "PC-JOAO", ["nf@ondina.com"], [], Relogio())
    pc.tick(_ler(planilha), "João")
    r = pc.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, [{"tipo": "dropbox", "rel": "a.pdf"}], "João")
    assert r["ok"] is False and "Nenhum PC" in r["motivo"] and r["contas_locais"] == ["nf@ondina.com"]


def test_pc_desligado_vira_sem_resposta_e_pc_velho_nao_conta(cfg, planilha):
    _prep(planilha)
    rel = Relogio()
    pc_a = _servico(planilha, cfg, "PC-JOAO", [], [], rel)
    pc_b = _servico(planilha, cfg, "PC-CRISTIAN", [CAIXA], [], rel)
    pc_b.tick(_ler(planilha), "Cristian")
    pc_a.tick(_ler(planilha), "João")
    r = pc_a.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, [{"tipo": "dropbox", "rel": "a.pdf"}], "João")
    rel.t += datetime.timedelta(seconds=en.SEM_RESPOSTA_SEGUNDOS + 5)
    s = pc_a.situacao(r["id"], en.dobrar_fila(_ler(planilha)[en.ABA_FILA]))
    assert s["estado"] == "sem_resposta" and "não respondeu" in s["detalhe"]
    rel.t += datetime.timedelta(seconds=en.PC_ONLINE_SEGUNDOS)
    pc_a.tick(_ler(planilha), "João")
    assert pc_a.destino_para(CAIXA)[0] is None             # Painel do Cristian sumiu há mais de 3 min


def test_falha_no_envio_avisa_com_o_motivo(cfg, planilha):
    _prep(planilha)
    rel = Relogio()
    pc_a = _servico(planilha, cfg, "PC-JOAO", ["nf@ondina.com"], [], rel)
    pc_b = _servico(planilha, cfg, "PC-CRISTIAN", [CAIXA], [], rel, falhar=True)
    pc_b.tick(_ler(planilha), "Cristian")
    pc_a.tick(_ler(planilha), "João")
    r = pc_a.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, [{"tipo": "arquivo", "nome": "n.pdf", "conteudo": b"x"}], "João")
    pc_b.tick(_ler(planilha), "Cristian")
    s = pc_a.situacao(r["id"], en.dobrar_fila(_ler(planilha)[en.ABA_FILA]))
    assert s["estado"] == "falhou" and "Outlook fechado" in s["detalhe"] and s["contas_locais"] == ["nf@ondina.com"]


def test_nota_dividida_dois_anexos_por_outro_pc(cfg, planilha):
    _prep(planilha)
    rel, enviados, registradas = Relogio(), [], []
    pc_a = _servico(planilha, cfg, "PC-JOAO", [], enviados, rel)
    pc_b = _servico(planilha, cfg, "PC-CRISTIAN", [CAIXA], enviados, rel, registradas)
    pc_b.tick(_ler(planilha), "Cristian")
    pc_a.tick(_ler(planilha), "João")
    anexos = [{"tipo": "arquivo", "nome": "NF 1212 - FH.pdf", "conteudo": b"A" * 70_000},
              {"tipo": "arquivo", "nome": "NF 1213 - FH.pdf", "conteudo": b"B"}]
    r = pc_a.pedir(SOL, "hospede@x.com", "NF 1212 - FH", CAIXA, anexos, "João", cc="fin@fh.com")
    pc_b.tick(_ler(planilha), "Cristian")
    assert enviados[0][4] == b"A" * 70_000 + b"B"
    assert registradas == [(["1212", "1213"], "João")]
    assert en.dobrar_fila(_ler(planilha)[en.ABA_FILA])[r["id"]]["pedido"]["cc"] == "fin@fh.com"


def test_mensagem_vira_html_com_link():
    h = en.mensagem_html("Olá <b>\n👉 Clique: https://forms.gle/abc")
    assert "&lt;b&gt;" in h and "<br>" in h and '<a href="https://forms.gle/abc">' in h
    assert "forms.gle/LLkYN3hv2da6svhj7" in en.mensagem_padrao({})
    assert en.mensagem_padrao({"envio_nf": {"mensagem": "outra"}}) == "outra"


def test_assinatura_da_caixa_e_do_operador(tmp_path):
    for nome in ("Ass Joao S (nf@cecomtur.com).htm", "ASS CRIS (nf@cecomtur.com).htm", "Ass Joao S (nf@outro.com).htm"):
        (tmp_path / nome).write_text("<html><body>x</body></html>", encoding="utf-8")
    assert en.achar_assinatura("nf@cecomtur.com", "Cristian", tmp_path).name.startswith("ASS CRIS")
    assert en.achar_assinatura("nf@cecomtur.com", "João", tmp_path).name.startswith("Ass Joao S")
    assert en.achar_assinatura("nf@semassinatura.com", "João", tmp_path) is None


def test_assinatura_troca_imagem_por_cid(tmp_path):
    pasta = tmp_path / "Ass Joao S (nf@x.com)_arquivos"
    pasta.mkdir()
    (pasta / "image001.png").write_bytes(b"\x89PNG")
    htm = tmp_path / "Ass Joao S (nf@x.com).htm"
    htm.write_text('<html><head><meta charset="utf-8"></head><body><p>João</p>'
                   '<img src="Ass%20Joao%20S%20(nf@x.com)_arquivos/image001.png"></body></html>', encoding="utf-8")
    html, imagens = en.assinatura_html(htm)
    assert 'src="cid:assinatura1"' in html and "<head>" not in html
    assert imagens == [(pasta / "image001.png", "assinatura1")]


def test_numeros_de_nf_do_assunto_e_dos_arquivos():
    assert en.numeros_de_nf("NF 10 - X", [{"nome": "NF 10 - X.pdf"}, {"nome": "NF 11 - X.pdf"}, {"nome": "nota.pdf"}]) == ["10", "11"]


def test_primeiro_assumido_vence():
    linhas = [en.CAB_FILA, en.evento(datetime.datetime(2026, 10, 1), "E1", en.PEDIDO, "A", "João", {"x": 1}),
              en.evento(datetime.datetime(2026, 10, 1), "E1", en.ASSUMIDO, "B", "João"),
              en.evento(datetime.datetime(2026, 10, 1), "E1", en.ASSUMIDO, "C", "João")]
    assert en.dobrar_fila(linhas)["E1"]["assumido_por"] == "B"


def test_assinatura_com_a_mensagem_padrao_nao_repete_o_texto():
    ass = '<p>Prezado(a) hóspede,</p><p>👉 Clique aqui: https://forms.gle/LLkYN3hv2da6svhj7</p><img src="cid:assinatura1">'
    html = en.corpo_do_email(en.MENSAGEM_PADRAO, ass)
    assert html.count("Prezado") == 1 and "cid:assinatura1" in html
    extra = en.corpo_do_email("Segue também o XML.", ass)
    assert extra.index("Segue também o XML.") < extra.index("Prezado")


def test_sem_assinatura_a_mensagem_padrao_entra():
    html = en.corpo_do_email("", "")
    assert "Prezado(a) hóspede" in html and 'href="https://forms.gle/LLkYN3hv2da6svhj7"' in html


def test_selos_da_pasta_na_ordem_da_equipe_e_do_operador():
    lista = [s["id"] for s in en.selos()]
    assert lista[:4] == ["joao", "cristian", "clara", "bernardo"]
    assert en.selos()[0]["nome"] == "João"
    assert en.selo_do_agente("Cristian") == "cristian" and en.selo_do_agente("Fulano") == "joao"
    assert en.caminho_selo("clara") and en.caminho_selo("../config") is None and en.caminho_selo("") is None


def test_corpo_com_selo_leva_a_mensagem_padrao_e_a_imagem():
    html = en.corpo_com_selo("")
    assert "Prezado(a) hóspede" in html and "Atenciosamente," in html and f'cid:{en.CID_SELO}' in html
    assert "Segue também o XML" in en.corpo_com_selo("Segue também o XML")
