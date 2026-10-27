"""Canal de teste (27/10/2026): a atualização automática só vai até a versão com etiqueta; e-mail de hóspede mascarado."""
import subprocess

import pytest

import atualizador
import log_util


def git(pasta, *args):
    return subprocess.run(["git", "-C", str(pasta), "-c", "user.email=t@x", "-c", "user.name=t", *args],
                          capture_output=True, text=True, check=True).stdout.strip()


def commit(pasta, nome):
    (pasta / nome).write_text(nome)
    git(pasta, "add", "-A")
    git(pasta, "commit", "-qm", nome)
    return git(pasta, "rev-parse", "--short", "HEAD")


@pytest.fixture
def cena(tmp_path, monkeypatch):
    origem, dev, pc = tmp_path / "origem.git", tmp_path / "dev", tmp_path / "pc"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origem)], check=True)
    subprocess.run(["git", "clone", "-q", str(origem), str(dev)], check=True, capture_output=True)
    git(dev, "checkout", "-q", "-b", "main")
    commit(dev, "a.txt"); git(dev, "tag", "2026.10.20"); git(dev, "push", "-q", "origin", "main", "--tags")
    subprocess.run(["git", "clone", "-q", str(origem), str(pc)], check=True, capture_output=True)
    monkeypatch.setattr(atualizador, "PASTA", pc)
    monkeypatch.setattr(atualizador, "pedir_reinicio", lambda: "reinício pedido")
    return dev, pc


real_run = subprocess.run


@pytest.fixture(autouse=True)
def _pip_falso(monkeypatch):
    def run(cmd, *a, **k):
        return subprocess.CompletedProcess(cmd, 0, "", "") if "pip" in cmd else real_run(cmd, *a, **k)
    monkeypatch.setattr(atualizador.subprocess, "run", run)


def test_commit_sem_etiqueta_nao_chega_sozinho_mas_chega_no_pedido_manual(cena):
    dev, pc = cena
    novo = commit(dev, "b.txt"); git(dev, "push", "-q", "origin", "main")        # sem etiqueta
    assert atualizador.situacao(so_etiquetadas=True)["atras"] == 0               # automática: nada a baixar
    assert atualizador.situacao()["atras"] == 1                                  # pedida por uma pessoa: tem 1
    ok, texto, _ = atualizador.atualizar(so_etiquetadas=True)
    assert git(pc, "rev-parse", "--short", "HEAD") != novo
    ok, texto, _ = atualizador.atualizar()
    assert ok and git(pc, "rev-parse", "--short", "HEAD") == novo


def test_versao_com_etiqueta_chega_sozinha_mas_so_ate_a_etiqueta(cena):
    dev, pc = cena
    commit(dev, "b.txt"); versao = commit(dev, "c.txt"); git(dev, "tag", "2026.10.27"); git(dev, "push", "-q", "origin", "main", "--tags")
    commit(dev, "d.txt"); git(dev, "push", "-q", "origin", "main")              # depois da etiqueta: não vai
    assert atualizador.situacao(so_etiquetadas=True)["atras"] == 2
    atualizador.atualizar(so_etiquetadas=True)
    assert git(pc, "rev-parse", "--short", "HEAD") == versao
    assert atualizador.situacao(so_etiquetadas=True)["atras"] == 0 and atualizador.situacao()["atras"] == 1


def test_sem_nenhuma_etiqueta_no_github_cai_no_ultimo_commit(tmp_path, monkeypatch):
    origem, dev, pc = tmp_path / "o.git", tmp_path / "d", tmp_path / "p"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(origem)], check=True)
    subprocess.run(["git", "clone", "-q", str(origem), str(dev)], check=True, capture_output=True)
    git(dev, "checkout", "-q", "-b", "main"); commit(dev, "a.txt"); git(dev, "push", "-q", "origin", "main")
    subprocess.run(["git", "clone", "-q", str(origem), str(pc)], check=True, capture_output=True)
    monkeypatch.setattr(atualizador, "PASTA", pc)
    commit(dev, "b.txt"); git(dev, "push", "-q", "origin", "main")
    assert atualizador.situacao(so_etiquetadas=True)["atras"] == 1


@pytest.mark.parametrize("entrada, saida", [
    ("Novo e-mail de notafiscal@redeandradeluxor.com.br para marina.exemplo@gmail.com: \"NF\"",
     "Novo e-mail de notafiscal@redeandradeluxor.com.br para m***@gmail.com: \"NF\""),
    ("remetente: joao.silva@hotmail.com e ana@uol.com.br", "remetente: j***@hotmail.com e a***@uol.com.br"),
    ("sem e-mail nenhum", "sem e-mail nenhum"),
    ("teste@exemplo.com.br", "teste@exemplo.com.br"),
])
def test_mascara_email_de_hospede_e_mantem_o_da_empresa(entrada, saida):
    assert log_util.mascarar_emails(entrada) == saida


def test_filtro_mascara_a_mensagem_formatada():
    import logging
    r = logging.LogRecord("x", logging.INFO, "", 0, "Novo e-mail de %s para %s", ("a@redeandradelagoa.com.br", "bruno@gmail.com"), None)
    log_util._MascaraDeEmail().filter(r)
    assert r.getMessage() == "Novo e-mail de a@redeandradelagoa.com.br para b***@gmail.com"
