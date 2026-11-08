"""Armazém (08/11/2026): todo dado que o Painel grava em estado/ está no catálogo, descrito, e só o armazém monta o caminho."""
import re
from pathlib import Path

import pytest

import armazem

SRC = Path(__file__).resolve().parents[1] / "src"


def test_nome_fora_do_catalogo_e_erro():
    with pytest.raises(KeyError, match="catálogo"):
        armazem.caminho("arquivo_que_ninguem_declarou.json")


def test_caminho_usa_a_pasta_de_estado_na_hora(monkeypatch, tmp_path):
    monkeypatch.setattr(armazem, "raiz", lambda: tmp_path)
    assert armazem.caminho("nf_achadas.json") == tmp_path / "nf_achadas.json"
    assert armazem.backup_tratamento(__import__("datetime").date(2026, 11, 8)) == tmp_path / "backup_tratamento_20261108.json"


def test_todo_dado_tem_descricao_formato_e_dono_e_nome_unico():
    for nome, d in armazem.DADOS.items():
        assert nome == d.arquivo and d.para_que.strip() and d.quem.strip() and d.formato in {"json", "sqlite", "cache", "texto", "trava", "pasta"}, nome
        assert (SRC / f"{d.quem}.py").exists(), f"{nome}: o módulo '{d.quem}' não existe"


def test_ninguem_monta_caminho_de_estado_por_conta_propria():
    """Arquivo novo em estado/: declare em src/armazem.py e use armazem.caminho(). Só armazem.py e config.py podem montar o caminho."""
    fora = []
    for f in sorted(SRC.glob("*.py")):
        if f.name in ("armazem.py", "config.py"):
            continue
        for n, linha in enumerate(f.read_text(encoding="utf-8").split("\n"), 1):
            if re.search(r"PASTA_ESTADO\s*/", linha) and not linha.lstrip().startswith("#"):
                fora.append(f"{f.name}:{n}: {linha.strip()[:80]}")
    assert not fora, "caminho de estado/ montado fora do armazém:\n" + "\n".join(fora)


def test_dados_com_dado_de_hospede_estao_marcados():
    pessoais = {d.arquivo for d in armazem.pessoais()}
    for deve in ("indice_emails.sqlite", "nf_achadas.json", "espelho_emails.json", "cache_textos_nf.json"):
        assert deve in pessoais, deve
    assert "app.json" not in pessoais and "_painel.lock" not in pessoais


def test_resumo_lista_tudo_com_tamanho(monkeypatch, tmp_path):
    monkeypatch.setattr(armazem, "raiz", lambda: tmp_path)
    (tmp_path / "app.json").write_text("{}", encoding="utf-8")
    linhas = {l["arquivo"]: l for l in armazem.resumo()}
    assert set(linhas) == set(armazem.DADOS) and linhas["app.json"]["bytes"] == 2 and linhas["nf_achadas.json"]["bytes"] == 0
