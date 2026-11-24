"""API central, etapa 4: o PC dono é avisado pelo servidor assim que o pedido de envio chega. Só dados inventados."""
import datetime
import threading
import time
import types

import pytest

from central.backend_api import BackendAPI
from central.backend_roteado import BackendRoteado
from central.sheets import ErroPlanilha
from emails import envio_nf as en
from painel import estado_envio
from servidor_central import servidor
from servidor_central.armazem import Armazem

P = "central-teste"
CAIXA = "nf@novocwb.com.br"
SOL = {"chave": "k1", "aba": "Aba X", "carimbo": "9/30/2026 10:00:00", "email": "hospede@x.com", "hotel": "NOVO CWB",
       "nome": "FH Manutenção Industrial LTDA", "emails": ["hospede@x.com"], "nomes": []}


# ---------------------------------------------------------------- versões e espera, no armazém
def test_cada_gravacao_sobe_a_versao_da_aba_uma_vez_so():
    a = Armazem()
    assert a.versoes_das_abas(P, ["Fila"]) == {"Fila": 0}
    a.criar_aba_log(P, "Fila", ["id"])
    v1 = a.versoes_das_abas(P, ["Fila"])["Fila"]
    a.anexar_linhas(P, "Fila", [["1"], ["2"], ["3"]])          # 3 linhas, uma gravação: um passo só
    assert a.versoes_das_abas(P, ["Fila"])["Fila"] == v1 + 1
    a.ler_abas(P, ["Fila"])                                     # ler não mexe
    assert a.versoes_das_abas(P, ["Fila"])["Fila"] == v1 + 1


def test_gravacao_desfeita_nao_sobe_a_versao():
    a = Armazem()
    a.criar_aba_status(P, "Status", [["a"]])
    antes = a.versoes_das_abas(P, ["Status"])["Status"]
    with pytest.raises(Exception):
        a.escrever(P, [("'Status'!B1", "x"), ("'Falta'!A1", "y")])
    assert a.versoes_das_abas(P, ["Status"])["Status"] == antes


def test_a_versao_sobrevive_a_reiniciar_o_servidor(tmp_path):
    arquivo = str(tmp_path / "c.sqlite")
    a = Armazem(arquivo)
    a.criar_aba_log(P, "Fila", ["id"])
    a.anexar_linhas(P, "Fila", [["1"]])
    v = a.versoes_das_abas(P, ["Fila"])["Fila"]
    a.fechar()
    assert Armazem(arquivo).versoes_das_abas(P, ["Fila"])["Fila"] == v


def test_esperar_mudanca_acorda_quando_outro_pc_grava():
    a = Armazem()
    a.criar_aba_log(P, "Fila", ["id"])
    v = a.versoes_das_abas(P, ["Fila"])["Fila"]
    achou = {}

    def espera():
        inicio = time.monotonic()
        achou["versao"] = a.esperar_mudanca(P, "Fila", v, 10)
        achou["demorou"] = time.monotonic() - inicio
    fio = threading.Thread(target=espera)
    fio.start()
    time.sleep(0.3)
    a.anexar_linhas(P, "Fila", [["ENV-1"]])
    fio.join(5)
    assert achou["versao"] == v + 1 and achou["demorou"] < 3     # acordou na hora, não esperou os 10 s


def test_esperar_mudanca_com_versao_velha_responde_na_hora_e_sem_novidade_volta_no_tempo():
    a = Armazem()
    a.criar_aba_log(P, "Fila", ["id"])
    a.anexar_linhas(P, "Fila", [["1"]])
    atual = a.versoes_das_abas(P, ["Fila"])["Fila"]
    t = time.monotonic()
    assert a.esperar_mudanca(P, "Fila", -1, 10) == atual and time.monotonic() - t < 1     # versão velha: na hora
    t = time.monotonic()
    assert a.esperar_mudanca(P, "Fila", atual, 0.4) == atual and 0.3 < time.monotonic() - t < 2   # sem novidade: dá o tempo e volta


def test_o_servidor_diz_quantos_pcs_estao_esperando():
    a = Armazem()
    a.criar_aba_log(P, "Fila", ["id"])
    v = a.versoes_das_abas(P, ["Fila"])["Fila"]
    assert a.esperando == 0
    fio = threading.Thread(target=a.esperar_mudanca, args=(P, "Fila", v, 5))
    fio.start()
    time.sleep(0.3)
    assert a.esperando == 1
    a.anexar_linhas(P, "Fila", [["x"]])
    fio.join(3)
    assert a.esperando == 0


def test_esperar_mudanca_nao_segura_quem_grava():
    """Quem espera não pode travar o banco: os outros PCs continuam gravando e lendo enquanto um espera."""
    a = Armazem()
    a.criar_aba_log(P, "Fila", ["id"])
    v = a.versoes_das_abas(P, ["Fila"])["Fila"]
    fios = [threading.Thread(target=a.esperar_mudanca, args=(P, "Fila", v, 2)) for _ in range(5)]
    for f in fios:
        f.start()
    t = time.monotonic()
    for i in range(20):
        a.anexar_linhas(P, "Fila", [[str(i)]])
        a.ler_abas(P, ["Fila"])
    for f in fios:
        f.join(5)
    assert time.monotonic() - t < 3 and len(a.ler_abas(P, ["Fila"])[0]["Fila"]) == 21


# ---------------------------------------------------------------- pela rede (servidor + cliente) e no roteador
@pytest.fixture()
def no_ar():
    srv = servidor.servir(Armazem(), "t" * 32, porta=0, endereco="127.0.0.1")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()
    srv.server_close()


def test_esperar_mudanca_pela_rede(no_ar):
    ouvinte, gravador = BackendAPI(no_ar, "t" * 32), BackendAPI(no_ar, "t" * 32)
    gravador.criar_aba_log(P, "Envios_NF", ["id"])
    v = ouvinte.versoes_das_abas(P, ["Envios_NF"])["Envios_NF"]
    achou = {}
    fio = threading.Thread(target=lambda: achou.update(v=ouvinte.esperar_mudanca(P, "Envios_NF", v, 10)))
    fio.start()
    time.sleep(0.3)
    gravador.anexar_linhas(P, "Envios_NF", [["ENV-1"]])
    fio.join(5)
    assert achou["v"] == v + 1


def test_roteador_so_deixa_esperar_aba_que_mora_no_servidor():
    b = BackendRoteado(Armazem(), Armazem(), P)
    assert b.atende_pelo_servidor(P, "Envios_NF") is True
    assert b.atende_pelo_servidor(P, "Solicitação Nota Fiscal (X) (respostas)") is False
    assert b.atende_pelo_servidor("outra-planilha", "Envios_NF") is False
    with pytest.raises(ErroPlanilha):
        b.esperar_mudanca(P, "Cadastro_Hoteis", 0, 1)


# ---------------------------------------------------------------- o envio de ponta a ponta, sem o aviso direto entre PCs
class Relogio:
    def __init__(self):
        self.t = datetime.datetime(2026, 10, 1, 10, 0, 0)

    def __call__(self):
        return self.t


def _pc(servidor_armazem, cfg, pc, contas, enviados, relogio):
    """Um PC: o serviço de envio e o pedaço do Estado do Painel que vigia a fila, falando com o servidor por um roteador."""
    backend = BackendRoteado(Armazem(), servidor_armazem, cfg["planilha_central_id"])

    def enviar(conta_de, para, cc, assunto, mensagem, anexos, agente="", selo="", **extra):
        enviados.append((pc, conta_de, para, assunto, b"".join(open(a, "rb").read() for a in anexos)))
    servico = en.ServicoEnvio(backend, dict(cfg, dropbox_notas={}), pc, lambda p, q: None, enviar=enviar,
                              ler_contas=lambda: list(contas), relogio=relogio)

    def aviso_direto(*a, **k):
        raise AssertionError("com o servidor ninguém precisa do aviso direto entre PCs")
    servico.avisar_dono = aviso_direto
    classe = next(c for c in vars(estado_envio).values() if isinstance(c, type) and hasattr(c, "iniciar_vigia_de_envios"))
    estado = types.SimpleNamespace(backend=backend, central=cfg["planilha_central_id"], envio_nf=servico, versao_tela=0,
                                   VIGIA_ENVIOS_ESPERA=1, VIGIA_ENVIOS_RELER=60, parar_vigia=False)
    estado._vigiar_envios = types.MethodType(classe._vigiar_envios, estado)
    estado.iniciar_vigia_de_envios = types.MethodType(classe.iniciar_vigia_de_envios, estado)
    return servico, estado


def _esperar(condicao, segundos=6):
    fim = time.monotonic() + segundos
    while time.monotonic() < fim:
        if condicao():
            return True
        time.sleep(0.02)
    return False


def test_pedido_chega_no_pc_dono_pelo_servidor_e_o_resultado_volta_sem_aviso_direto(cfg):
    central = Armazem()
    for aba, cab in ((en.ABA_FILA, en.CAB_FILA), (en.ABA_ANEXOS, en.CAB_ANEXOS), (en.ABA_PCS, en.CAB_PCS)):
        central.criar_aba_log(cfg["planilha_central_id"], aba, cab)
    rel, enviados = Relogio(), []
    quem_pede, estado_a = _pc(central, cfg, "PC-JOAO", ["nf@ondina.com"], enviados, rel)
    dono, estado_b = _pc(central, cfg, "PC-CRISTIAN", [CAIXA], enviados, rel)
    lidas = lambda: central.ler_abas(cfg["planilha_central_id"], [en.ABA_FILA, en.ABA_PCS])[0]   # noqa: E731
    dono.tick(lidas(), "Cristian")                        # o PC dono aparece como online, com a caixa
    quem_pede.tick(lidas(), "João")
    assert estado_a.iniciar_vigia_de_envios() and estado_b.iniciar_vigia_de_envios()
    assert quem_pede.fila_ao_vivo and dono.fila_ao_vivo
    try:
        r = quem_pede.pedir(SOL, "hospede@x.com", "NF 1212 - FH", CAIXA,
                            [{"tipo": "arquivo", "nome": "NF 1212 - FH.pdf", "conteudo": b"%PDF teste"}], "João")
        assert r["ok"] and r["destino"] == "PC-CRISTIAN"
        assert _esperar(lambda: len(enviados) == 1), "o PC dono não enviou"       # veio do servidor, em menos de 6 s (sem volta de 15 s)
        assert enviados == [("PC-CRISTIAN", CAIXA, "hospede@x.com", "NF 1212 - FH", b"%PDF teste")]
        # e quem pediu fica sabendo do resultado sem ler nada por conta própria
        assert _esperar(lambda: quem_pede.situacao(r["id"])["estado"] == "enviado"), quem_pede.situacao(r["id"])
        time.sleep(0.5)
        assert len(enviados) == 1                                   # nunca duas vezes
    finally:
        estado_a.parar_vigia = estado_b.parar_vigia = True


def test_sem_servidor_o_vigia_nao_liga_e_tudo_segue_como_antes(cfg):
    backend = BackendRoteado(Armazem(), Armazem(), "outra-central")   # a Central do cfg não está no roteador: nada mora no servidor
    servico = en.ServicoEnvio(backend, dict(cfg, dropbox_notas={}), "PC-X", lambda p, q: None, ler_contas=lambda: [])
    classe = next(c for c in vars(estado_envio).values() if isinstance(c, type) and hasattr(c, "iniciar_vigia_de_envios"))
    estado = types.SimpleNamespace(backend=backend, central=cfg["planilha_central_id"], envio_nf=servico)
    estado.iniciar_vigia_de_envios = types.MethodType(classe.iniciar_vigia_de_envios, estado)
    assert estado.iniciar_vigia_de_envios() is False and servico.fila_ao_vivo is False

    class SoGoogle:   # o BackendGoogle puro não tem nem o método
        pass
    estado.backend = SoGoogle()
    assert estado.iniciar_vigia_de_envios() is False


def test_com_o_vigia_ligado_a_volta_do_painel_nao_sobrescreve_a_fila_nem_atende_duas_vezes(cfg):
    central = Armazem()
    for aba, cab in ((en.ABA_FILA, en.CAB_FILA), (en.ABA_PCS, en.CAB_PCS)):
        central.criar_aba_log(cfg["planilha_central_id"], aba, cab)
    servico, _ = _pc(central, cfg, "PC-X", [], [], Relogio())
    servico.fila_ao_vivo = True
    servico.fila = {"ENV-1": {"pedido": {}, "resultado": None}}
    servico.tick({en.ABA_FILA: [en.CAB_FILA], en.ABA_PCS: [[]]}, "Fulano")   # a volta traz uma fila mais velha: não vale
    assert "ENV-1" in servico.fila
