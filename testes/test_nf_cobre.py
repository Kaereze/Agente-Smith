"""A NF já enviada cobre o que o hóspede pede agora? (27/10/2026): só compara; nunca tira nem apaga e-mail sozinho."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "src"))

import nf_cobre  # noqa: E402

NOTA = ("DANFSe v1.0 Documento Auxiliar da NFS-e\nChave de Acesso 4120000000000000000000000000000000000000000000000\n"
        "TOMADOR DO SERVIÇO CNPJ / CPF / NIF 12.345.678/0001-90 Nome EMPRESA EXEMPLO LTDA\n"
        "Descrição do Serviço DATA DE CHECK-IN: 30/09/2026 DATA DE CHECK-OUT: 02/10/2026 VALOR DA DIÁRIA: R$ 140,00 "
        "HOSPEDAGEM CONFORME CONTRATO 4471/2026 " + "x" * 80)


def linhas(r):
    return {l["rotulo"]: l["ok"] for l in r["linhas"]}


def test_agradecimento_nao_pede_nada_e_a_nota_cobre():
    r = nf_cobre.analisar("Obrigado pela nota! Estava tudo certo na hospedagem.", [NOTA])
    assert r["cobre"] is True and not r["pede_nova"] and r["motivos"] == []
    assert linhas(r)["Serviço"] is True and linhas(r)["Datas"] is True and linhas(r)["CPF/CNPJ"] is True


def test_pede_consumo_e_a_nota_so_tem_diarias():
    r = nf_cobre.analisar("Boa tarde. Poderiam emitir também uma nota do consumo do restaurante?", [NOTA])
    assert r["pede_nova"] and linhas(r)["Serviço"] is False and "consumo" in r["motivos"][0] and "diárias" in r["motivos"][0]


def test_pede_outras_datas():
    r = nf_cobre.analisar("Preciso da nota da segunda estadia, de 12/10 a 14/10.", [NOTA])
    assert r["pede_nova"] and linhas(r)["Datas"] is False and "12/10" in r["motivos"][0]


def test_datas_da_propria_nota_nao_disparam():
    r = nf_cobre.analisar("Solicito a correção: a estadia foi de 30/09 a 02/10, ok?", [NOTA])
    assert linhas(r)["Datas"] is True


def test_pede_outro_cnpj():
    r = nf_cobre.analisar("Favor emitir de novo no CNPJ 98.765.432/0001-10.", [NOTA])
    assert r["pede_nova"] and linhas(r)["CPF/CNPJ"] is False


def test_descricao_pedida_que_a_nota_nao_traz():
    r = nf_cobre.analisar('Preciso que a descrição seja "Hospedagem conforme proposta 99/2026".', [NOTA])
    assert r["pede_nova"] and linhas(r)["Descrição"] is False
    ok = nf_cobre.analisar('Gostaria que a descrição fosse "Hospedagem conforme contrato 4471/2026".', [NOTA])
    assert linhas(ok)["Descrição"] is True and not ok["pede_nova"]


def test_sem_intencao_nunca_vira_nova_nota():
    r = nf_cobre.analisar("Tudo certo com o consumo e com a estadia de 12/10, valeu.", [NOTA])
    assert not r["pede_nova"]   # sem pedido de nota, citar consumo ou outra data não dispara


def test_nota_ilegivel_nao_conclui_nada():
    r = nf_cobre.analisar("Poderiam emitir a nota do consumo?", ["curto"])
    assert r["cobre"] is None and not r["pede_nova"] and r["linhas"][0]["ok"] is None


def test_duas_notas_somam_o_que_cobrem():
    consumo = NOTA.replace("VALOR DA DIÁRIA: R$ 140,00", "VALOR DO CONSUMO: R$ 80,00")
    r = nf_cobre.analisar("Poderiam emitir também o consumo?", [NOTA, consumo])
    assert linhas(r)["Serviço"] is True and not r["pede_nova"]


def test_motivo_curto_da_urgencia():
    r = nf_cobre.analisar("Poderiam emitir uma nota do consumo?", [NOTA])
    assert nf_cobre.motivo_curto(r, ["2186"]).startswith("Pede nova nota (NF 2186): serviço:")
    assert nf_cobre.motivo_curto(nf_cobre.analisar("Obrigado!", [NOTA]), ["2186"]) == ""


def test_ligacoes_no_servidor_e_na_tela():
    srv = "".join((RAIZ / "src" / f).read_text(encoding="utf-8") for f in ("app_servidor.py", "estado_correio.py"))
    envio = (RAIZ / "src" / "envio_nf.py").read_text(encoding="utf-8")
    js = (RAIZ / "app_ui" / "correio.js").read_text(encoding="utf-8")
    assert 'url.path == "/api/nf_cobre"' in srv and 'path == "/api/correio/concluir"' in srv
    assert "acao=envio_nf.MOVER_NF" in srv and "mover_para_nf_enviada_no_outlook" in envio
    assert 'p.get("acao") not in (ENCAMINHAR, MOVER_NF)' in envio       # mover pasta nunca registra NF enviada
    assert "def mover_para_nf_enviada_no_outlook" in envio and "item.Delete()" not in envio.split("def mover_para_nf_enviada_no_outlook")[1].split("# ---------- pedido")[0]
    assert "data-nf-concluir" in js and "mostrarDesfazer(" in js and "Nada é apagado" in js    # só por clique, com desfazer de 10 s
    assert "concluir" not in srv.split("def _alertas_nova_nota")[1].split("def nf_cobre")[0]    # a urgência nunca move e-mail


HISTORICO = ("Boa tarde, me chamo Marcos Exemplo e estive hospedado no hotel do dia 19 a 23 de outubro, solicito a NF de hospedagem e a "
             "NF do estacionamento, sendo duas NFs separadas.\nSegue Dados:\nMarcos Exemplo da Silva\nCPF 111.444.777-35\n"
             "Data hospedagem 19 a 23 de outubro. Valor pago R$ 1.188,00\n\nEstacionamento 19 a 23 valor pago R$120,00.\n")


def nota_de(servico_rotulo, valor, total):
    return ("DANFSe v1.0 Documento Auxiliar da NFS-e\nTOMADOR DO SERVIÇO CNPJ / CPF / NIF 111.444.777-35 Nome MARCOS EXEMPLO\n"
            f"Descrição do Serviço DATA DE CHECK-IN: 19/10/2026 DATA DE CHECK-OUT: 23/10/2026 {servico_rotulo}: R$ {valor} "
            f"Valor do serviço R$ {total} " + "x" * 80)


def test_pedido_do_historico_inteiro_acha_hospedagem_e_estacionamento():
    itens = nf_cobre.pedido_do_historico([HISTORICO, HISTORICO])   # a parte citada repete o texto: não duplica
    assert itens == [{"servico": "diaria", "valor": "1.188,00", "datas": ["19/10", "23/10"]},
                     {"servico": "estacionamento", "valor": "120,00", "datas": ["19/10", "23/10"]}]


def test_as_duas_notas_cobrem_o_historico_do_hospede():
    notas = [{"nf": "1391", "texto": nota_de("VALOR DA DIÁRIA", "297,00", "1.188,00")},
             {"nf": "1392", "texto": nota_de("VALOR DO ESTACIONAMENTO", "30,00", "120,00")}]
    r = nf_cobre.comparar_historico(nf_cobre.pedido_do_historico([HISTORICO]), notas)
    assert r["completo"] and [(i["nome"], i["nf"], i["ok"]) for i in r["itens"]] == [("hospedagem", "1391", True), ("estacionamento", "1392", True)]


def test_falta_a_nota_do_estacionamento_ou_o_valor_nao_bate():
    so_diaria = [{"nf": "1391", "texto": nota_de("VALOR DA DIÁRIA", "297,00", "1.188,00")}]
    r = nf_cobre.comparar_historico(nf_cobre.pedido_do_historico([HISTORICO]), so_diaria)
    assert not r["completo"] and r["itens"][1]["ok"] is False and r["itens"][1]["nf"] == "" and "ainda não há nota" in r["itens"][1]["detalhe"]
    errada = [{"nf": "1391", "texto": nota_de("VALOR DA DIÁRIA", "250,00", "1.000,00")}, {"nf": "1392", "texto": nota_de("VALOR DO ESTACIONAMENTO", "30,00", "120,00")}]
    r2 = nf_cobre.comparar_historico(nf_cobre.pedido_do_historico([HISTORICO]), errada)
    assert not r2["completo"] and "valor R$ 1.188,00 não bate" in r2["itens"][0]["detalhe"]


def test_botao_direito_tirar_da_entrada_vale_ate_para_respondido_e_nunca_apaga():
    srv = "".join((RAIZ / "src" / f).read_text(encoding="utf-8") for f in ("app_servidor.py", "estado_correio.py"))
    js = (RAIZ / "app_ui" / "correio.js").read_text(encoding="utf-8")
    assert 'path == "/api/correio/mover_nf"' in srv and "def mover_email_nf" in srv
    corpo = srv.split("def mover_email_nf")[1].split("def concluir_conversa")[0]
    assert "acao=envio_nf.MOVER_NF" in corpo and "acao=envio_nf.EXCLUIR" not in corpo and "excluir_email(" not in corpo
    assert 'data-ctx="tirar"' in js and "function tirarDaEntrada" in js and 'if (acao === "tirar") return tirarDaEntrada(id);' in js
    assert "if (!e || cx.resolvendo[id]) return;" not in js          # a linha cinza (já respondida) abre o menu
    assert 'mostrarDesfazer("E-mail movido para' in js                # Desfazer de 10 s, nada é apagado


def test_tela_de_carregamento_trava_a_tela_ate_terminar_e_nao_prende_para_sempre():
    js = (RAIZ / "app_ui" / "pecas" / "carregando.js").read_text(encoding="utf-8")
    css = (RAIZ / "app_ui" / "pecas" / "carregando.css").read_text(encoding="utf-8")
    assert ".cg-veu.trava{pointer-events:auto" in css and "z-index:100" in css and "z-index:101" in css   # acima de avisos, caixas e janelas
    assert 'veu.classList.add("on", "trava")' in js and 'veu.classList.remove("trava");   // terminou: destrava' in js
    assert "e.stopImmediatePropagation(); e.preventDefault();" in js and "DESTRAVA_MS = 90000" in js   # atalhos travam; 90 s de segurança
    assert "mask" in js and 'url(#cg-mascara)' in js and ".cg-k .tr" not in css                       # aquarela: tinta cheia por máscara, sem linhas duplas
