"""O hóspede diz o texto que tem de constar na nota e o robô procura no PDF inteiro (usuário, 20/10/2026: "o robô não está
conseguindo reconhecer os erros, a própria hóspede disse na mensagem… entra na nota e verifica se alguma parte dela aparece").
Caso real com o nome trocado: "não consta a identificação “UEM / Fulana”" virava "refazer a nota (o cliente não disse o
que mudar)"."""
import analise_nf as a

EMAIL = ("Prezados, bom dia!\nAgradeço pelo envio da nota fiscal. No entanto, não consta a identificação “UEM / Marina "
         "Exemplo Costa”, conforme solicitado anteriormente.\nPeço, por gentileza, que seja realizada a correção e "
         "encaminhada a nota fiscal atualizada, pois essa informação é indispensável para o reembolso pela universidade.\n"
         "Atenciosamente,\nMarina Exemplo Costa")
NF_SEM = ("NFS-e\nNúmero da NFS-e\n879\nValor Líquido da NFS-e\nR$ 525,00\nTOMADOR\nMarina Exemplo Costa\n"
          "Discriminação do serviço\nHospedagem 31/08/2026 a 31/08/2026")
NF_COM = NF_SEM + "\nObservação: UEM - MARINA EXEMPLO COSTA"


def test_reconhece_o_texto_pedido_entre_aspas():
    p = a.pedido_do_cliente("RE: NF 879 - MARINA EXEMPLO COSTA", EMAIL)
    assert p["textos"] == ["UEM / Marina Exemplo Costa"]
    motivo, _, _ = a.motivo_principal(p)
    assert motivo == "incluir na nota: “UEM / Marina Exemplo Costa”"


def test_procura_na_nota_inteira_e_diz_que_nao_aparece():
    p = a.pedido_do_cliente("RE: NF 879", EMAIL)
    r = a.completo(p, a.dados_do_pdf(NF_SEM), "879", "NF 879.pdf", texto_nf=NF_SEM)
    assert r["detalhe"] == "não aparece na NF 879"
    assert "“UEM / Marina Exemplo Costa” não aparece em nenhuma parte da nota" in r["comparacao"]
    assert "(texto na nota: “UEM / Marina Exemplo Costa”)" in r["resumo"] and "(texto)" not in r["resumo"]


def test_ja_aparece_mesmo_com_pontuacao_e_maiuscula_diferentes():
    p = a.pedido_do_cliente("RE: NF 879", EMAIL)
    r = a.completo(p, a.dados_do_pdf(NF_COM), "879", "NF 879.pdf", texto_nf=NF_COM)
    assert r["detalhe"] == "já aparece na NF 879"
    assert a.onde_aparece("UEM / Marina Exemplo Costa", "uem marina    exemplo\ncosta") == "inteiro"
    assert a.onde_aparece("UEM / Marina", "Marina ... UEM") == "em partes"
    assert a.onde_aparece("Projeto 123", NF_SEM) == ""


def test_aspas_que_nao_pedem_texto_na_nota_nao_contam():
    assert a.textos_pedidos("Obrigada pelo “ótimo” atendimento!") == []
    assert a.textos_pedidos("Favor incluir na nota a observação \"Empenho 2026NE0001\".") == ["Empenho 2026NE0001"]


def test_sem_aspas_continua_como_antes():
    p = a.pedido_do_cliente("NF errada", "O valor está errado, precisa cancelar")
    assert p["textos"] == [] and a.motivo_principal(p)[0] == "valor da nota"
