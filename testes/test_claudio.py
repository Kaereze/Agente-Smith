"""⚡ Ativar Claudio: o menu grava um pedido na aba Status e o conferente atende."""
import datetime
import json

import conferente
import main
from conftest import CENTRAL
from sheets import STATUS_LINHAS, config_publica, garantir_rotulos_status, ler_comando


def _status(planilha):
    return {l[0]: (l[1] if len(l) > 1 else "") for l in planilha.aba("Status")}


def _pedir(planilha, minutos_atras=0):
    garantir_rotulos_status_simples(planilha)
    quando = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=minutos_atras)
    aba = planilha.aba("Status")
    aba[6][1:] = ["ENVIAR"]
    aba[7][1:] = [f"joao@x.com | {quando.isoformat().replace('+00:00', 'Z')}"]


def garantir_rotulos_status_simples(planilha):
    aba = planilha.aba("Status")
    while len(aba) < len(STATUS_LINHAS):
        aba.append([STATUS_LINHAS[len(aba)][0], ""])


def test_rotulos_novos_sao_criados_na_aba_status_antiga(cfg, planilha):
    assert len(planilha.aba("Status")) == 6
    garantir_rotulos_status(planilha, cfg)
    rotulos = [l[0] for l in planilha.aba("Status")]
    assert rotulos[6:] == ["Comando", "Pedido por", "Resposta do robô", "Última verificação de pendências",
                           "Configuração do robô", "Robô online (último sinal)", "Seleção do envio separado",
                           "Cota de envio", "Andamento do envio (ao vivo)",
                           "Conferência da cópia (ao vivo)"]


def test_le_o_pedido(cfg, planilha):
    _pedir(planilha)
    comando, quem, quando = ler_comando(planilha, cfg)
    assert comando == "ENVIAR" and quem == "joao@x.com" and quando.tzinfo is not None


def test_pedido_e_atendido(cfg, planilha, monkeypatch):
    _pedir(planilha)
    chamadas = []

    def rodar_falso(codigo_se_ocupado=0, **info):
        chamadas.append(codigo_se_ocupado)
        assert info["origem"] == "Botão Ativar Claudio" and info["quem"] == "joao@x.com" and info["selecao"] is None
        planilha.aba("Status")[2][1] = "2 e-mail(s) enviado(s), 5 solicitação(ões) marcada(s) TRUE"
        return 0
    monkeypatch.setattr(main, "rodar", rodar_falso)

    assert conferente.atender_pedido(planilha, cfg) is True
    st = _status(planilha)
    assert chamadas == [main.OCUPADO]
    assert st["Comando"] == ""                                     # libera o botão de novo
    assert st["Resposta do robô"].startswith("✅ 2 e-mail(s) enviado(s)")
    assert conferente.atender_pedido(planilha, cfg) is False       # não roda duas vezes o mesmo pedido


def test_pedido_antigo_expira_sem_enviar(cfg, planilha, monkeypatch):
    _pedir(planilha, minutos_atras=45)
    monkeypatch.setattr(main, "rodar", lambda **k: (_ for _ in ()).throw(AssertionError("não devia enviar")))
    assert conferente.atender_pedido(planilha, cfg) is True
    st = _status(planilha)
    assert st["Comando"] == "" and "expirou" in st["Resposta do robô"]


def test_envio_ja_rodando(cfg, planilha, monkeypatch):
    _pedir(planilha)
    monkeypatch.setattr(main, "rodar", lambda codigo_se_ocupado=0, **info: main.OCUPADO)
    conferente.atender_pedido(planilha, cfg)
    assert "Já tinha um envio rodando" in _status(planilha)["Resposta do robô"]


def test_sinal_de_vida_publica_agentes_sem_segredos(cfg, planilha):
    garantir_rotulos_status_simples(planilha)
    conferente.publicar_sinal(planilha, cfg)
    st = _status(planilha)
    publicado = json.loads(st["Configuração do robô"])
    assert publicado["agentes"]["Clara"] == "notafiscal2@andradehoteis.com.br"
    assert "caminho_chave_google" not in publicado and "_ajuda" not in json.dumps(publicado)
    assert datetime.datetime.fromisoformat(st["Robô online (último sinal)"]).tzinfo is not None
    assert json.loads(config_publica(cfg))["modo"] == "PRODUCAO"


def test_status_criado_do_zero_ja_vem_com_as_linhas_novas(cfg, planilha):
    del planilha.planilhas[CENTRAL]["Status"]
    from sheets import robo_ligado
    robo_ligado(planilha, cfg)
    assert len(planilha.aba("Status")) == len(STATUS_LINHAS) == 16
