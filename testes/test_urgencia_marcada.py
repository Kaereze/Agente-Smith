"""Botão direito no e-mail: urgência marcada pela equipe e e-mail da Ouvidoria urgente (usuário, 20/10/2026).
A marca fica no Outlook do PC dono (categoria) e vale na hora pelo evento da equipe."""
import datetime

import correio
import envio_nf
import espelho_emails as ee
from test_correio_acoes import SEM_FORM, _espelho_do_dono, _servico
from test_envio_nf import CAIXA, Relogio, _ler, _prep

D = datetime.datetime
AGORA = D(2026, 10, 20, 12, 0)


def _email(i, de="hospede@x.com", nome="Hóspede", classes=(), atualizado="2026-10-20T11:00:00"):
    return {"id": i, "pasta": "entrada", "caixa": "nf@hotel.com", "de": de, "nome": nome, "assunto": "Nota",
            "quando": "2026-10-20T09:00:00", "classes": list(classes), "atualizado": atualizado}


def test_categoria_do_outlook_vira_marca():
    assert ee.marca_das_categorias("Pedido de NF, Urgente (Painel)") == "marcado_urgente"
    assert ee.marca_das_categorias("Sem urgência (Painel)") == "marcado_normal"
    assert ee.marca_das_categorias("") == ""
    assert ee.com_marca(["pedido_nf", "marcado_normal"], "marcado_urgente") == ["pedido_nf", "marcado_urgente"]


def test_ouvidoria_entra_como_urgente():
    entrada, _, _ = correio.juntar([_email("a", de="ouvidoria1@andradehoteis.com.br", nome="Ouvidoria")], {}, AGORA)
    assert entrada[0]["urgente"] and entrada[0]["motivo_urgencia"] == "E-mail da Ouvidoria"


def test_marca_do_outlook_manda_na_urgencia():
    emails = [_email("u", classes=["marcado_urgente"]), _email("n", de="outro@x.com", classes=["corrigir", "marcado_normal"])]
    entrada = {e["id"]: e for e in correio.juntar(emails, {}, AGORA)[0]}
    assert entrada["u"]["urgente"] and entrada["u"]["motivo_urgencia"] == "Marcado como urgente"
    assert not entrada["n"]["urgente"]   # tirou a urgência: nem o pedido de correção deixa urgente


def test_clique_vale_na_hora_ate_o_outlook_gravar():
    linhas = [ee.CAB_EVENTOS, ee.evento("a", "URGENTE", "Clara", "PC-C", D(2026, 10, 20, 11, 30))]
    eventos = ee.dobrar_eventos(linhas)
    assert eventos["a"]["urgencia"] == "urgente" and eventos["a"]["urgencia_por"] == "Clara"
    entrada, _, _ = correio.juntar([_email("a")], eventos, AGORA)
    assert entrada[0]["urgente"] and entrada[0]["motivo_urgencia"] == "Marcado como urgente por Clara"
    # o espelho atualizou depois do clique e o Outlook não tem a categoria: vale o Outlook
    entrada, _, _ = correio.juntar([_email("a", atualizado="2026-10-20T11:45:00")], eventos, AGORA)
    assert not entrada[0]["urgente"]


def test_pc_dono_poe_a_categoria(cfg, planilha, tmp_path, monkeypatch):
    _espelho_do_dono(tmp_path, monkeypatch)
    _prep(planilha)
    rel, feitos = Relogio(), []
    joao = _servico(planilha, cfg, "PC-JOAO", ["nf@ondina.com"], feitos, rel)
    dono = _servico(planilha, cfg, "PC-BERNARDO", [CAIXA], feitos, rel)
    dono.marcar_urgencia = lambda entry, marcar: feitos.append(("urgencia", "PC-BERNARDO", entry, marcar))
    dono.tick(_ler(planilha), "Bernardo")
    joao.tick(_ler(planilha), "João")
    r = joao.pedir(SEM_FORM, "", "Nota", CAIXA, [], "João", mensagem="urgente", responder="abc123", acao=envio_nf.URGENCIA)
    assert r["ok"] and r["destino"] == "PC-BERNARDO"
    dono.tick(_ler(planilha), "Bernardo")
    assert feitos == [("urgencia", "PC-BERNARDO", "ENTRY-OUTLOOK-1", "urgente")]   # nada enviado, nenhuma NF registrada
    assert joao.situacao(r["id"], envio_nf.dobrar_fila(_ler(planilha)[envio_nf.ABA_FILA]))["estado"] == "enviado"
