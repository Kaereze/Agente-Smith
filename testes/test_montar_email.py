from conftest import CABECALHO_HOTEL, linha_hotel
from modelos import Hotel
from montar_email import montar_assunto, montar_emails
from sheets import interpretar_aba


def _solicitacoes(cfg, quantidade, hoteis):
    todas = []
    for i in range(quantidade):
        hotel = hoteis[i % len(hoteis)]
        pendentes, _ = interpretar_aba(hotel, [CABECALHO_HOTEL, linha_hotel(i, hotel.nome)], cfg)
        todas.extend(pendentes)
    return todas


def _hoteis():
    return [Hotel(f"aba{i}", nome, f"notafiscal{(i % 4) + 1}@andradehoteis.com.br", "P")
            for i, nome in enumerate(["Zeta", "Alfa", "Mirante", "Barra", "Coimbra", "Dunas", "Galeão", "Hangar"])]


def test_200_solicitacoes_divididas_pelo_limite(cfg):
    cfg["limite_solicitacoes_por_email"] = 40
    todas = _solicitacoes(cfg, 200, _hoteis())
    emails = montar_emails(todas, cfg)

    # 4 operadores com 50 cada -> 2 e-mails por operador (40 + 10)
    assert len(emails) == 8
    assert all(len(e.solicitacoes) <= 40 for e in emails)
    enviadas = [s.chave for e in emails for s in e.solicitacoes]
    assert sorted(enviadas) == sorted(s.chave for s in todas)  # nenhuma perdida, nenhuma repetida
    assert any("[parte 2/2]" in e.assunto for e in emails)
    assert len({e.codigo for e in emails}) == 8


def test_hoteis_em_ordem_e_juntos(cfg):
    todas = _solicitacoes(cfg, 40, _hoteis())
    for email in montar_emails(todas, cfg):
        nomes = [s.hotel.nome for s in email.solicitacoes]
        assert nomes == sorted(nomes)  # todas do hotel A juntas, depois B...
        assert email.destinatario == email.operador


def test_conteudo_do_html(cfg):
    hotel = Hotel("Estrela", "Estrela <b>d'Alva</b>", "notafiscal1@andradehoteis.com.br", "P")
    pendentes, _ = interpretar_aba(hotel, [CABECALHO_HOTEL, linha_hotel(1, "Estrela")], cfg)
    html = montar_emails(pendentes, cfg)[0].html
    assert "#00786c" in html and "#d5bda1" in html   # paleta nova: verde + letras creme
    assert "01234567890" in html          # CPF com zero
    assert "01310000" in html             # CEP com zero
    assert "03/09/2026" in html           # data convertida
    assert "Preenchimento intuitivo" not in html and "IMPORTANTE" not in html
    assert ">Enviado<" not in html
    assert "<b>d'Alva</b>" not in html    # nome escapado, não vira HTML
    assert "Hóspede Número" in html


def test_assunto(cfg):
    hoteis = [Hotel("a", "Alfa", "op@x", "P"), Hotel("b", "Beta", "op@x", "P")]
    todas = _solicitacoes(cfg, 3, hoteis)
    assert montar_assunto(todas) == "Solicitações NF (3) - Alfa, Beta"


def test_assunto_longo_e_cortado(cfg):
    hoteis = [Hotel(f"a{i}", f"Hotel Com Nome Bem Comprido Numero {i}", "op@x", "P") for i in range(20)]
    assunto = montar_assunto(_solicitacoes(cfg, 20, hoteis))
    assert len(assunto) <= 200 and "e mais" in assunto


def test_modo_teste_vai_pro_email_de_teste(cfg):
    cfg["modo"] = "TESTE"
    email = montar_emails(_solicitacoes(cfg, 2, _hoteis()[:1]), cfg)[0]
    assert email.destinatario == "teste@x.com"
    assert email.assunto.startswith("[TESTE]")
    assert "MODO TESTE" in email.html
