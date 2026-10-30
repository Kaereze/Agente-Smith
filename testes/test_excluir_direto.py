"""Excluir direto para o administrador (29/10/2026): Delete vale também em resultado de pesquisa e itens enviados."""
import time
import types
from pathlib import Path

import pytest

import app_servidor
import envio_nf as en
import indice_emails
from test_envio_nf import CAIXA, SOL, Relogio, _ler, _prep, _servico

RAIZ = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------- índice: só vale o que o próprio PC indexou da caixa
def _indice(tmp_path):
    ind = indice_emails.Indice(tmp_path / "indice.sqlite")
    ind.db.execute("INSERT INTO emails (id, entry, pasta, caixa, hotel) VALUES ('id1', 'ENT1', 'entrada', 'nf@novocwb.com.br', 'NOVO CWB')")
    ind.db.commit()
    return ind


def test_indice_confere_so_o_par_id_entry_da_caixa_certa(tmp_path):
    ind = _indice(tmp_path)
    assert ind.confere("id1", "ENT1", "nf@novocwb.com.br")
    assert ind.confere("id1", "ENT1", "NF@NovoCWB.com.br")          # caixa sem diferenciar maiúscula
    assert not ind.confere("id1", "OUTRO", "nf@novocwb.com.br")      # EntryID que não é o do índice
    assert not ind.confere("id1", "ENT1", "nf@outro.com.br")         # caixa errada
    assert not ind.confere("", "ENT1", "nf@novocwb.com.br") and not ind.confere("id1", "", "nf@novocwb.com.br")


# ---------------------------------------------------------------- PC dono: exclui pelo EntryID de pesquisa só se o índice confere
def _pedir_excluir(planilha, cfg, confere):
    _prep(planilha)
    excluidos = []
    serv = _servico(planilha, cfg, "PC-JOAO", [CAIXA], [], Relogio())
    serv.excluir = lambda entry: excluidos.append(entry)
    serv.entry_confere = confere
    serv.tick(_ler(planilha), "João")
    r = serv.pedir(SOL, "", "NF antiga", CAIXA, [], "João", responder="id-do-indice", acao=en.EXCLUIR, entry="ENT-DA-PESQUISA")
    for _ in range(100):
        if excluidos or serv.locais.get(r["id"], {}).get("estado") in ("enviado", "falhou"):
            break
        time.sleep(0.02)
    time.sleep(0.05)
    return r, excluidos


def test_dono_exclui_o_resultado_de_pesquisa_quando_o_indice_confere(cfg, planilha):
    chamadas = []
    r, excluidos = _pedir_excluir(planilha, cfg, lambda i, e, c: chamadas.append((i, e, c)) or True)
    assert r["ok"] and excluidos == ["ENT-DA-PESQUISA"]
    assert chamadas == [("id-do-indice", "ENT-DA-PESQUISA", CAIXA)]       # conferiu o par e a caixa do pedido


def test_dono_recusa_entryid_que_o_indice_nao_conhece(cfg, planilha):
    r, excluidos = _pedir_excluir(planilha, cfg, lambda i, e, c: False)
    assert r["ok"] and excluidos == []                                    # nada é excluído no Outlook


def test_sem_conferencia_configurada_nenhum_entryid_de_fora_vale(cfg, planilha):
    serv = _servico(planilha, cfg, "PC-JOAO", [CAIXA], [], Relogio())
    assert serv.entry_confere("id", "entry", CAIXA) is False


# ---------------------------------------------------------------- servidor: e-mail que não está no espelho
class _EnvioFalso:
    def __init__(self):
        self.pedidos = []

    def pedir(self, sol, para, assunto, conta_de, anexos, quem, **kw):
        self.pedidos.append((assunto, conta_de, quem, kw))
        return {"ok": True, "id": "ENV-1", "destino": "PC-X"}


def _estado_falso():
    def _email(id_email):
        raise KeyError("e-mail não está mais na lista")
    return types.SimpleNamespace(_email=_email, _caixas_de_hotel=lambda: {"nf@novocwb.com.br": "NOVO CWB"}, envio_nf=_EnvioFalso())


def test_servidor_pede_a_exclusao_de_resultado_de_pesquisa_ao_pc_dono():
    est = _estado_falso()
    extra = {"entry": "ENT9", "caixa": "NF@novocwb.com.br", "de": "fulano@exemplo.com.br", "nome": "Fulano", "hotel": "NOVO CWB", "assunto": "NF 1"}
    r = app_servidor.Estado.excluir_email(est, "id9", "João", extra)
    assert r["ok"]
    assunto, conta, quem, kw = est.envio_nf.pedidos[0]
    assert (assunto, conta, quem) == ("NF 1", "nf@novocwb.com.br", "João")
    assert kw["acao"] == en.EXCLUIR and kw["entry"] == "ENT9" and kw["responder"] == "id9"


@pytest.mark.parametrize("extra", [None, {}, {"entry": "E", "caixa": ""}, {"entry": "", "caixa": "nf@novocwb.com.br"},
                                   {"entry": "E", "caixa": "pessoal@gmail.com"}])
def test_servidor_recusa_quando_falta_dado_ou_a_caixa_nao_e_de_hotel(extra):
    est = _estado_falso()
    with pytest.raises(KeyError):
        app_servidor.Estado.excluir_email(est, "id9", "João", extra)
    assert est.envio_nf.pedidos == []


# ---------------------------------------------------------------- tela
def test_tela_delete_direto_so_para_o_administrador_e_em_todas_as_listas():
    js = (RAIZ / "app_ui" / "correio.js").read_text(encoding="utf-8")
    corte = js[js.index('if (e.key === "Delete")'):]
    corte = corte[:corte.index("if (e.ctrlKey && k === \"u\")")]
    assert "achaEmail(cx.sel)" in corte and "souAdmin() ? excluirDireto(alvo.id) : excluir(alvo.id)" in corte
    assert 'classList.contains("e-admin")' in js                                       # a mesma marca que já esconde o grupo Admin
    achar = js[js.index("function achaEmail"):]
    achar = achar[:achar.index("const souAdmin")]
    assert "cx.dados?.emails" in achar and "cx.dados?.enviados" in achar and "cx.live?.resultados" in achar
    assert "!cx.escondidos[e.id]" in js[js.index("function itensDaTela"):js.index("function desenharCorreio")]   # some na hora e volta no Desfazer
    assert 'api("/api/correio/excluir", { id, ...dadosDaExclusao(e) })' in js and "mostrarDesfazer(\"E-mail excluído\"" in js   # o Desfazer de 10 s fica
    assert "excluirAgora(e)" in js[js.index("function excluir(id)"):js.index("function mostrarDesfazer")]       # os outros agentes ainda veem a janela


def test_rota_de_excluir_passa_os_dados_do_e_mail():
    fonte = "".join(p.read_text(encoding="utf-8") for p in [RAIZ / "src" / "app_servidor.py", *sorted((RAIZ / "src").glob("estado_*.py"))])
    assert 'estado.excluir_email(str(corpo.get("id", "")), nome_do_agente(), corpo)' in fonte
    assert "self.envio_nf.entry_confere = lambda i, e, c" in fonte
