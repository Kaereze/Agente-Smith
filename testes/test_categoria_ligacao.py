"""Botão Ligação -> categoria LIGAÇÃO do Outlook no e-mail enviado (27/10/2026). Dados inventados."""
import app_servidor
import envio_nf


class Cat:
    def __init__(self, nome):
        self.Name = nome


class Cats(list):
    def Add(self, nome, cor):
        self.append(Cat(nome)); self.cor = cor


class Ns:
    def __init__(self, nomes=()):
        self.Categories = Cats(Cat(n) for n in nomes)


class Mail:
    def __init__(self, categorias=""):
        self.Categories = categorias


def test_poe_a_categoria_sem_tirar_as_que_ja_tem():
    m = Mail("Nota dividida")
    assert envio_nf.aplicar_categoria_ligacao(Ns(["LIGAÇÃO"]), m)
    assert m.Categories == "Nota dividida, LIGAÇÃO"
    envio_nf.aplicar_categoria_ligacao(Ns(["LIGAÇÃO"]), m)
    assert m.Categories == "Nota dividida, LIGAÇÃO"       # não repete


def test_outlook_sem_a_categoria_cria_verde():
    ns, m = Ns(), Mail()
    assert envio_nf.aplicar_categoria_ligacao(ns, m)
    assert m.Categories == "LIGAÇÃO" and ns.Categories[0].Name == "LIGAÇÃO" and ns.Categories.cor == 5


def test_erro_na_categoria_nunca_impede_o_envio():
    class Ruim:
        @property
        def Categories(self):
            raise RuntimeError("Outlook ocupado")

        @Categories.setter
        def Categories(self, v):
            raise RuntimeError("Outlook ocupado")
    assert envio_nf.aplicar_categoria_ligacao(Ns(["LIGAÇÃO"]), Ruim()) is False


def _servico_de_teste(planilha, cfg, recebidos):
    import test_envio_nf as t
    t._prep(planilha)

    def enviar(conta_de, para, cc, assunto, mensagem, anexos, agente="", selo="", **extra):
        recebidos.append(extra)
    s = envio_nf.ServicoEnvio(planilha, dict(cfg, dropbox_notas={}), "PC-JOAO", lambda p, q: None, enviar=enviar,
                              ler_contas=lambda: [t.CAIXA], relogio=t.Relogio())
    s.tick(t._ler(planilha), "João")
    return s, t


def test_pedido_ligado_chega_ao_outlook_com_ligacao_e_desligado_sem(cfg, planilha):
    recebidos = []
    s, t = _servico_de_teste(planilha, cfg, recebidos)
    anexo = [{"tipo": "arquivo", "nome": "n.pdf", "conteudo": b"x"}]
    r1 = s.pedir(t.SOL, "h@x.com", "NF 1 - FH", t.CAIXA, anexo, "João", **app_servidor._kw_ligacao({"ligacao": True}))
    assert t._esperar(s, r1["id"])["estado"] == "enviado"
    r2 = s.pedir(t.SOL, "h@x.com", "NF 2 - FH", t.CAIXA, anexo, "João", **app_servidor._kw_ligacao({}))
    assert t._esperar(s, r2["id"])["estado"] == "enviado"
    assert recebidos[0].get("ligacao") is True and "ligacao" not in recebidos[1]


def test_pedido_na_fila_guarda_a_ligacao_para_o_pc_dono(cfg, planilha):
    recebidos = []
    s, t = _servico_de_teste(planilha, cfg, recebidos)
    r = s.pedir(t.SOL, "h@x.com", "NF 1 - FH", t.CAIXA, [{"tipo": "arquivo", "nome": "n.pdf", "conteudo": b"x"}], "João", ligacao=True)
    t._esperar(s, r["id"])
    fila = envio_nf.dobrar_fila(planilha.ler_abas("PLANILHA_CENTRAL", [envio_nf.ABA_FILA])[0][envio_nf.ABA_FILA])
    assert fila[r["id"]]["pedido"]["ligacao"] is True
