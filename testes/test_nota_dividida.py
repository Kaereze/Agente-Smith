"""Tag "Nota dividida" (controle_nf.pede_nota_dividida)."""
from controle_nf import pede_nota_dividida


def test_campo_nota_dividida_sim():
    assert pede_nota_dividida("Nota Dividida\tSim\r\nDividida em quantas vezes\t3")


def test_campo_nota_dividida_nao_nao_marca():
    assert not pede_nota_dividida("Nota Dividida\tNão\r\nInformações necessárias\tValor Diárias, Valor Estacionamento")


def test_pedido_escrito():
    assert pede_nota_dividida("Observação: preciso de uma nota pra cada (diária, estacionamento e consumo)")
    assert pede_nota_dividida("Favor emitir notas separadas da hospedagem e do consumo")
    assert pede_nota_dividida("quero 2 notas")


def test_texto_normal_nao_marca():
    assert not pede_nota_dividida("Valor Diárias Hospedagem · Método de Envio E-mail · Estado BA")


def test_categorias_do_outlook_em_portugues_usam_ponto_e_virgula():
    from controle_nf import categorias_atualizadas
    r = categorias_atualizadas("⏳ NF pendente; 💬 Tratativa; Nota dividida", 1, 1, False)
    assert r == "Nota dividida, ✅ NF concluído"      # troca só as do robô e mantém a azul
