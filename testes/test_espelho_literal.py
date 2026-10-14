"""Espelho literal (14/10/2026: "o Outlook da Clara tem 192 e o Painel menos"): tudo o que está na Caixa de Entrada
aparece; respondido, formulário e aviso do Outlook ficam marcados e não viram urgência nem "esperando resposta"."""
import datetime

import correio
import espelho_emails as ee


def _e(i, de, quando, classes):
    return {"id": i, "pasta": ee.ENTRADA, "caixa": "nf@h.com", "hotel": "H", "de": de, "nome": de, "assunto": "x",
            "quando": quando, "classes": classes, "lido_outlook": False, "atualizado": quando, "pc": "PC-A"}


def test_formulario_aviso_e_respondido_ficam_na_lista_sem_urgencia():
    agora = datetime.datetime(2026, 10, 14, 12, 0)
    velho = "2026-10-01T10:00:00"   # 13 dias: viraria urgência se estivesse esperando resposta
    emails = [_e("a", "ana@x.com", velho, ["pedido_nf"]), _e("f", "robo@rede.com", velho, ["formulario"]),
              _e("v", "", velho, ["aviso"]), _e("r", "rui@x.com", velho, ["pedido_nf"]),
              {"id": "r:*", "pasta": ee.RESPOSTA, "caixa": "nf@h.com", "de": "rui@x.com", "assunto": "", "quando": "2026-10-02T09:00:00",
               "classes": [], "pc": "PC-A"}]
    entrada, _, _ = correio.juntar(emails, {}, agora)
    por = {e["id"]: e for e in entrada}
    assert set(por) == {"a", "f", "v", "r"}
    assert por["a"]["urgente"] and por["a"]["pendente"]
    assert not any(por[i]["urgente"] or por[i]["pendente"] for i in ("f", "v", "r"))
    assert por["r"]["respondido"]
    convs = correio.conversas([e for e in entrada if e["pendente"]])
    assert correio.contagem(convs, entrada)["entrada"] == 4
