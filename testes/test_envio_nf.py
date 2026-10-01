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
    def enviar(conta_de, para, assunto, corpo, anexo):
        if falhar:
            raise RuntimeError("Outlook fechado")
        enviados.append((pc, conta_de, para, assunto, open(anexo, "rb").read()))
    return en.ServicoEnvio(planilha, dict(cfg, dropbox_notas={}), pc,
                           lambda p, q: (registradas if registradas is not None else []).append((p["nf"], q)),
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


def test_sugestao_ignora_palavras_comuns(tmp_path, cfg):
    for nome in ("NF 1561 - MAICON FERNANDO DOS SANTOS - 1.pdf", "NF 900 - CHARLES MACARIO - 2.pdf",
                 "NF 901 - CHARLES MACARIO DOS SANTOS FILHO - 3.pdf", "NF 4371 - JUNIOR SANTOS - 4.pdf",
                 "NF 375 - CHARLES - 5.pdf"):
        (tmp_path / nome).write_bytes(b"x")
    sol = dict(SOL, nome="Charles Macario dos Santos Filho", nomes=[])
    en.listar_notas_dropbox(dict(cfg, dropbox_notas={"pastas": [str(tmp_path)]}), forcar=True)
    sug = {a["nome"]: a for a in en.sugestoes_dropbox(sol, dict(cfg, dropbox_notas={"pastas": [str(tmp_path)]}))}
    assert "NF 1561 - MAICON FERNANDO DOS SANTOS - 1.pdf" not in sug
    assert "NF 4371 - JUNIOR SANTOS - 4.pdf" not in sug               # só "SANTOS" não basta
    assert sug["NF 901 - CHARLES MACARIO DOS SANTOS FILHO - 3.pdf"]["forte"]
    assert not sug["NF 375 - CHARLES - 5.pdf"]["forte"]                # primeiro nome: aparece, mas sem pré-seleção


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
    r = pc_a.pedir(SOL, "hospede@x.com", "NF 1212 - FH", CAIXA, {"tipo": "arquivo", "nome": "NF 1212 - FH.pdf",
                                                                  "conteudo": b"%PDF teste"}, "João")
    assert r["ok"] and r["destino"] == "PC-CRISTIAN" and not enviados
    assert pc_a.situacao(r["id"], en.dobrar_fila(_ler(planilha)[en.ABA_FILA]))["estado"] == "aguardando"
    pc_b.tick(_ler(planilha), "Cristian")                 # o PC do Cristian pega e envia
    assert enviados == [("PC-CRISTIAN", CAIXA, "hospede@x.com", "NF 1212 - FH", b"%PDF teste")]
    assert registradas == [("1212", "João")]
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
    r = pc.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, {"tipo": "arquivo", "nome": "n.pdf", "conteudo": b"x"}, "João")
    assert r["destino"] == "PC-JOAO" and _esperar(pc, r["id"])["estado"] == "enviado"
    assert len(planilha.aba(en.ABA_ANEXOS)) == 1           # local: anexo nem passa pela planilha


def test_nenhum_pc_com_a_caixa(cfg, planilha):
    _prep(planilha)
    pc = _servico(planilha, cfg, "PC-JOAO", ["nf@ondina.com"], [], Relogio())
    pc.tick(_ler(planilha), "João")
    r = pc.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, {"tipo": "dropbox", "rel": "a.pdf"}, "João")
    assert r["ok"] is False and "Nenhum PC" in r["motivo"] and r["contas_locais"] == ["nf@ondina.com"]


def test_pc_desligado_vira_sem_resposta_e_pc_velho_nao_conta(cfg, planilha):
    _prep(planilha)
    rel = Relogio()
    pc_a = _servico(planilha, cfg, "PC-JOAO", [], [], rel)
    pc_b = _servico(planilha, cfg, "PC-CRISTIAN", [CAIXA], [], rel)
    pc_b.tick(_ler(planilha), "Cristian")
    pc_a.tick(_ler(planilha), "João")
    r = pc_a.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, {"tipo": "dropbox", "rel": "a.pdf"}, "João")
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
    r = pc_a.pedir(SOL, "hospede@x.com", "NF 9 - FH", CAIXA, {"tipo": "arquivo", "nome": "n.pdf", "conteudo": b"x"}, "João")
    pc_b.tick(_ler(planilha), "Cristian")
    s = pc_a.situacao(r["id"], en.dobrar_fila(_ler(planilha)[en.ABA_FILA]))
    assert s["estado"] == "falhou" and "Outlook fechado" in s["detalhe"] and s["contas_locais"] == ["nf@ondina.com"]


def test_primeiro_assumido_vence():
    linhas = [en.CAB_FILA, en.evento(datetime.datetime(2026, 10, 1), "E1", en.PEDIDO, "A", "João", {"x": 1}),
              en.evento(datetime.datetime(2026, 10, 1), "E1", en.ASSUMIDO, "B", "João"),
              en.evento(datetime.datetime(2026, 10, 1), "E1", en.ASSUMIDO, "C", "João")]
    assert en.dobrar_fila(linhas)["E1"]["assumido_por"] == "B"
