"""Ações no Outlook do PC dono a partir do Painel de outro PC: excluir, encaminhar, fila com o PC desligado."""
import datetime

import envio_nf as en
import espelho_emails as ee
from test_envio_nf import CAIXA, Relogio, _ler, _prep

SEM_FORM = {"aba": "", "carimbo": "", "email": "ana@gmail.com", "hotel": "NOVO CWB", "nome": "Ana"}


def _servico(planilha, cfg, pc, contas, feitos, relogio):
    def enviar(conta_de, para, cc, assunto, mensagem, anexos, **extra):
        feitos.append(("enviar", pc, conta_de, para, assunto, mensagem, extra))
    s = en.ServicoEnvio(planilha, dict(cfg, dropbox_notas={}), pc, lambda p, q: feitos.append(("registrou", p["nfs"])),
                        enviar=enviar, ler_contas=lambda: list(contas), relogio=relogio)
    s.excluir = lambda entry: feitos.append(("excluir", pc, entry))
    return s


def _espelho_do_dono(tmp_path, monkeypatch):
    caminho = tmp_path / "espelho.json"
    caminho.write_text('{"itens": {"abc123": {"entry_id": "ENTRY-OUTLOOK-1"}}}', encoding="utf-8")
    monkeypatch.setattr(ee, "CAMINHO_ESTADO", caminho)


def test_excluir_pelo_painel_de_outro_pc_move_no_outlook_do_dono(cfg, planilha, tmp_path, monkeypatch):
    _espelho_do_dono(tmp_path, monkeypatch)
    _prep(planilha)
    rel, feitos = Relogio(), []
    joao = _servico(planilha, cfg, "PC-JOAO", ["nf@ondina.com"], feitos, rel)
    bernardo = _servico(planilha, cfg, "PC-BERNARDO", [CAIXA], feitos, rel)
    bernardo.tick(_ler(planilha), "Bernardo")
    joao.tick(_ler(planilha), "João")
    r = joao.pedir(SEM_FORM, "", "Nota", CAIXA, [], "João", responder="abc123", acao=en.EXCLUIR)
    assert r["ok"] and r["destino"] == "PC-BERNARDO"
    bernardo.tick(_ler(planilha), "Bernardo")
    assert feitos == [("excluir", "PC-BERNARDO", "ENTRY-OUTLOOK-1")]   # nada enviado, nada registrado como NF
    assert joao.situacao(r["id"], en.dobrar_fila(_ler(planilha)[en.ABA_FILA]))["estado"] == "enviado"


def test_encaminhar_usa_o_email_original(cfg, planilha, tmp_path, monkeypatch):
    _espelho_do_dono(tmp_path, monkeypatch)
    _prep(planilha)
    rel, feitos = Relogio(), []
    dono = _servico(planilha, cfg, "PC-BERNARDO", [CAIXA], feitos, rel)
    dono.tick(_ler(planilha), "Bernardo")
    r = dono.pedir(SEM_FORM, "recepcao@hotel.com", "ENC: Nota", CAIXA, [], "Bernardo", mensagem="Vejam, por favor",
                   responder="abc123", acao=en.ENCAMINHAR)
    for _ in range(100):
        if dono.locais.get(r["id"], {}).get("estado") == "enviado":
            break
        import time
        time.sleep(0.02)
    assert feitos == [("enviar", "PC-BERNARDO", CAIXA, "recepcao@hotel.com", "ENC: Nota", "Vejam, por favor",
                       {"agente": "Bernardo", "selo": "", "encaminhar_de": "ENTRY-OUTLOOK-1"})]   # não vira "NF enviada"


def test_pc_dono_desligado_o_pedido_espera_e_sai_quando_ele_liga(cfg, planilha, tmp_path, monkeypatch):
    _espelho_do_dono(tmp_path, monkeypatch)
    _prep(planilha)
    rel, feitos = Relogio(), []
    joao = _servico(planilha, cfg, "PC-JOAO", [], feitos, rel)
    bernardo = _servico(planilha, cfg, "PC-BERNARDO", [CAIXA], feitos, rel)
    bernardo.tick(_ler(planilha), "Bernardo")
    rel.t += datetime.timedelta(hours=2)                  # Bernardo desligou o PC
    joao.tick(_ler(planilha), "João")
    r = joao.pedir(SEM_FORM, "ana@gmail.com", "RE: Nota", CAIXA, [], "João", mensagem="Segue", responder="abc123")
    assert r["ok"] and r["destino"] == "PC-BERNARDO" and "desligado" in r["aviso"]
    s = joao.situacao(r["id"], en.dobrar_fila(_ler(planilha)[en.ABA_FILA]))
    assert s["estado"] == "na_fila" and "quando ele ligar" in s["detalhe"]
    rel.t += datetime.timedelta(hours=1)                  # ligou
    bernardo.tick(_ler(planilha), "Bernardo")
    assert feitos and feitos[0][:5] == ("enviar", "PC-BERNARDO", CAIXA, "ana@gmail.com", "RE: Nota")


def test_pedido_parado_mais_de_24h_expira_e_nao_sai(cfg, planilha, tmp_path, monkeypatch):
    _espelho_do_dono(tmp_path, monkeypatch)
    _prep(planilha)
    rel, feitos = Relogio(), []
    joao = _servico(planilha, cfg, "PC-JOAO", [], feitos, rel)
    bernardo = _servico(planilha, cfg, "PC-BERNARDO", [CAIXA], feitos, rel)
    bernardo.tick(_ler(planilha), "Bernardo")
    rel.t += datetime.timedelta(hours=2)
    joao.tick(_ler(planilha), "João")
    r = joao.pedir(SEM_FORM, "ana@gmail.com", "RE: Nota", CAIXA, [], "João", mensagem="Segue", responder="abc123")
    rel.t += datetime.timedelta(hours=en.FILA_ESPERA_HORAS + 1)   # PC voltou só 2 dias depois
    bernardo.tick(_ler(planilha), "Bernardo")
    assert feitos == []
    assert joao.situacao(r["id"], en.dobrar_fila(_ler(planilha)[en.ABA_FILA]))["estado"] == "falhou"


def test_caixa_que_nenhum_pc_jamais_teve_continua_recusando(cfg, planilha):
    _prep(planilha)
    joao = _servico(planilha, cfg, "PC-JOAO", [], [], Relogio())
    joao.tick(_ler(planilha), "João")
    r = joao.pedir(SEM_FORM, "a@b.com", "x", "nf@nao-existe.com", [], "João", responder="abc", acao=en.EXCLUIR)
    assert r["ok"] is False and "Nenhum PC" in r["motivo"]
