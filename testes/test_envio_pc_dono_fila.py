"""Plano B do envio pelo PC dono (15/10/2026): a rede do escritório não chega no PC dono (o PC da Clara ficou em outra
faixa de rede e o firewall só aceita a mesma faixa), então o pedido vai pela fila da Central (Envios_NF), o Painel do
PC dono manda da caixa do hotel para ela mesma e o robô confirma pela fila."""
import datetime
import json
import urllib.error

import envio_nf as en
import envio_pc_dono as epd
from conftest import CENTRAL
from modelos import EmailMontado

CAIXA = "notafiscal@aracaju.com.br"
PCS = [{"pc": "PC-CLARA", "agente": "Clara", "contas_lista": [CAIXA], "online": True, "rede": "10.80.0.2:8766"}]


class Relogio:
    def __init__(self):
        self.t = datetime.datetime(2026, 10, 15, 12, 0, 0)

    def __call__(self):
        return self.t


class Monotonic:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def _sem_rede(*_a, **_k):
    raise TimeoutError("a rede não chega (outra faixa)")


def _prep(planilha):
    for aba, cab in ((en.ABA_FILA, en.CAB_FILA), (en.ABA_ANEXOS, en.CAB_ANEXOS), (en.ABA_PCS, en.CAB_PCS)):
        planilha.criar_aba_log(CENTRAL, aba, cab)


def _email(codigo="NF-0123456789"):
    return EmailMontado(operador=CAIXA, destinatario=CAIXA, assunto="Solicitação NF - ARACAJU",
                        html="<p>Pedido do hóspede · Código de envio: " + codigo + "</p>", codigo=codigo, solicitacoes=[])


class LocalFalso:
    contas = {"notafiscal@estrela.com.br": object()}

    def esta_nos_enviados(self, *a, **k):
        return False

    def esta_na_caixa_saida(self, *a, **k):
        return False


def _robo(planilha, mono=None):
    fila = epd.FilaCentral(planilha, CENTRAL, este_pc="PC-JOAO", relogio=Relogio(), monotonic=mono or Monotonic())
    return epd.OutlookComPcDono(LocalFalso(), lambda: PCS, b"s", este_pc="PC-JOAO", perguntar=_sem_rede, fila=fila)


def _servico_da_clara(planilha, cfg, enviar=None, conferir=None):
    nada = lambda *a, **k: (_ for _ in ()).throw(AssertionError("não é envio de NF"))   # noqa: E731
    s = en.ServicoEnvio(planilha, dict(cfg, dropbox_notas={}), "PC-CLARA", nada, enviar=nada,
                        ler_contas=lambda: [CAIXA], relogio=Relogio())
    s.caixas_de_hotel = lambda: {CAIXA: "ARACAJU"}
    s.enviar_formulario = enviar
    s.conferir_formulario = conferir
    return s


def _eventos(planilha):
    return [l[2] for l in planilha.aba(en.ABA_FILA)[1:]]


def test_rede_nao_chega_vai_pela_fila_e_o_html_fica_fora_da_fila(cfg, planilha):
    _prep(planilha)
    robo = _robo(planilha)
    robo.enviar(_email())
    (pedido,) = planilha.aba(en.ABA_FILA)[1:]
    dados = json.loads(pedido[5])
    assert pedido[2] == en.PEDIDO and dados["acao"] == en.ACAO_FORMULARIO and dados["pc_formulario"] == "PC-CLARA"
    assert dados["para"] == dados["conta_de"] == CAIXA and dados["codigo"] == "NF-0123456789"
    assert "pc_destino" not in dados          # Painel de versão antiga ignora (não manda como se fosse NF)
    assert "html" not in dados and "Código de envio" not in pedido[5]   # a fila que todos leem fica leve
    nome, html = en.juntar_anexo(planilha.aba(en.ABA_ANEXOS), pedido[1] + "#0")
    assert nome == "formulario.html" and b"NF-0123456789" in html
    assert robo.esta_nos_enviados("NF-0123456789", None, destinatario=CAIXA) is False
    assert robo.esta_na_caixa_saida("NF-0123456789", destinatario=CAIXA) is True   # a caminho: o robô não reenvia


def test_pc_dono_pega_da_fila_manda_e_o_robo_confirma(cfg, planilha):
    _prep(planilha)
    mono = Monotonic()
    robo = _robo(planilha, mono)
    robo.enviar(_email())
    mandados = []
    clara = _servico_da_clara(planilha, cfg, enviar=lambda corpo, caixas: mandados.append((corpo, caixas)) or True)
    clara.fila = en.dobrar_fila(planilha.aba(en.ABA_FILA))
    clara.executar_pendentes()
    (corpo, caixas), = mandados
    assert corpo["para"] == CAIXA and corpo["codigo"] == "NF-0123456789" and "Código de envio" in corpo["html"]
    assert caixas == {CAIXA: "ARACAJU"}
    assert _eventos(planilha) == [en.PEDIDO, en.ASSUMIDO, en.ENVIADO]
    assert json.loads(planilha.aba(en.ABA_FILA)[-1][5]) == {"confirmado": True}
    assert all(not l[4] for l in planilha.aba(en.ABA_ANEXOS)[1:])          # o HTML sai da planilha depois do envio
    mono.t += 60
    assert robo.esta_nos_enviados("NF-0123456789", None, destinatario=CAIXA) is True
    clara.fila = en.dobrar_fila(planilha.aba(en.ABA_FILA))
    clara.executar_pendentes()
    assert len(mandados) == 1                                              # não manda duas vezes


def test_saiu_sem_aparecer_em_enviados_e_reconferido_depois(cfg, planilha):
    _prep(planilha)
    mono = Monotonic()
    robo = _robo(planilha, mono)
    robo.enviar(_email())
    achou = {"enviados": False}
    clara = _servico_da_clara(planilha, cfg, enviar=lambda corpo, caixas: False, conferir=lambda corpo, caixas: dict(achou))
    clara.fila = en.dobrar_fila(planilha.aba(en.ABA_FILA))
    clara.executar_pendentes()
    assert json.loads(planilha.aba(en.ABA_FILA)[-1][5]) == {"confirmado": False}
    mono.t += 60
    assert robo.esta_nos_enviados("NF-0123456789", None, destinatario=CAIXA) is False
    assert robo.esta_na_caixa_saida("NF-0123456789", destinatario=CAIXA) is True     # segura: não reenvia
    achou["enviados"] = True
    clara.reconferidos.clear()
    clara.fila = en.dobrar_fila(planilha.aba(en.ABA_FILA))
    clara.executar_pendentes()
    assert _eventos(planilha)[-1] == en.CONFIRMADO
    mono.t += 60
    assert robo.esta_nos_enviados("NF-0123456789", None, destinatario=CAIXA) is True


def test_painel_reiniciou_no_meio_sem_ter_saido_vira_falhou_e_libera_o_reenvio(cfg, planilha):
    _prep(planilha)
    mono = Monotonic()
    robo = _robo(planilha, mono)
    robo.enviar(_email())
    id_envio = planilha.aba(en.ABA_FILA)[1][1]
    planilha.anexar_linhas(CENTRAL, en.ABA_FILA, [en.evento(Relogio()(), id_envio, en.ASSUMIDO, "PC-CLARA", "Robô")])
    clara = _servico_da_clara(planilha, cfg, enviar=lambda *a: (_ for _ in ()).throw(AssertionError("não reenvia")),
                              conferir=lambda corpo, caixas: {"enviados": False, "saida": False})
    clara.fila = en.dobrar_fila(planilha.aba(en.ABA_FILA))
    clara.executar_pendentes()
    assert _eventos(planilha)[-1] == en.FALHOU
    mono.t += 60
    assert robo.esta_nos_enviados("NF-0123456789", None, destinatario=CAIXA) is False
    assert robo.esta_na_caixa_saida("NF-0123456789", destinatario=CAIXA) is False   # o robô manda de novo


def test_pedido_do_robo_de_outro_pc_nao_e_executado(cfg, planilha):
    _prep(planilha)
    _robo(planilha).enviar(_email())
    outro = _servico_da_clara(planilha, cfg, enviar=lambda *a: (_ for _ in ()).throw(AssertionError("não é dele")))
    outro.pc = "PC-CRISTIAN"
    outro.fila = en.dobrar_fila(planilha.aba(en.ABA_FILA))
    outro.executar_pendentes()
    assert _eventos(planilha) == [en.PEDIDO]


def test_pc_dono_desligado_nao_vai_pra_fila(cfg, planilha):
    _prep(planilha)
    fila = epd.FilaCentral(planilha, CENTRAL, este_pc="PC-JOAO", relogio=Relogio(), monotonic=Monotonic())
    robo = epd.OutlookComPcDono(LocalFalso(), lambda: [{**PCS[0], "online": False}], b"s", este_pc="PC-JOAO",
                                perguntar=_sem_rede, fila=fila)
    try:
        robo.enviar(_email())
    except epd.NaoEnviado as e:
        assert "desligado" in str(e)
    else:
        raise AssertionError("devia dar NaoEnviado")
    assert planilha.aba(en.ABA_FILA)[1:] == []


def test_url_error_no_envio_pela_rede_cai_na_fila(cfg, planilha):
    _prep(planilha)
    chamadas = []

    def rede(segredo, endereco, acao, corpo, tempo):
        chamadas.append(acao)
        if acao == "ping":
            return {}
        raise urllib.error.URLError(ConnectionResetError("caiu"))
    fila = epd.FilaCentral(planilha, CENTRAL, este_pc="PC-JOAO", relogio=Relogio(), monotonic=Monotonic())
    epd.OutlookComPcDono(LocalFalso(), lambda: PCS, b"s", este_pc="PC-JOAO", perguntar=rede, fila=fila).enviar(_email())
    assert chamadas == ["ping", "enviar"] and _eventos(planilha) == [en.PEDIDO]
