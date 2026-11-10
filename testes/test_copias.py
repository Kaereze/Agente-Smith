"""Cópias de segurança (09/11/2026): cópia íntegra, aparar, conferir, autocurar, restaurar e aviso na faixa de saúde."""
import datetime
import json
import sqlite3
import zipfile

import pytest

from sistema import armazem, copias


@pytest.fixture
def estado(monkeypatch, tmp_path):
    monkeypatch.setattr(armazem, "raiz", lambda: tmp_path)
    (tmp_path / "app.json").write_text(json.dumps({"agente": "Maria"}), encoding="utf-8")
    (tmp_path / "ja_enviadas.json").write_text(json.dumps({"NF-1": "2026-11-09"}), encoding="utf-8")
    con = sqlite3.connect(tmp_path / "indice_emails.sqlite")
    con.execute("create table e(id text)")
    con.execute("insert into e values('a')")
    con.commit()
    con.close()
    (tmp_path / "acessos").mkdir()
    (tmp_path / "acessos" / "2026-11.jsonl").write_text('{"x":1}\n', encoding="utf-8")
    (tmp_path / "painel_cache.pkl").write_bytes(b"cache")   # cache não entra na cópia
    return tmp_path


def _hora(n=0):
    return datetime.datetime(2026, 11, 9, 10, 0, 0) + datetime.timedelta(hours=n)


def test_copia_guarda_dados_com_manifesto_e_deixa_o_cache_de_fora(estado):
    z = copias.fazer_copia(_hora())
    assert z.name == "20261109_100000.zip" and z.parent == estado / "copias"
    manifesto, conteudo = copias.ler_copia(z)
    assert set(conteudo) == {"app.json", "ja_enviadas.json", "indice_emails.sqlite", "acessos/2026-11.jsonl"}
    assert all(len(v["sha256"]) == 64 for v in manifesto["arquivos"].values())


def test_sem_nada_para_guardar_nao_cria_copia_vazia(monkeypatch, tmp_path):
    monkeypatch.setattr(armazem, "raiz", lambda: tmp_path)
    assert copias.fazer_copia(_hora()) is None and copias.listar() == []


def test_o_sqlite_da_copia_abre_e_tem_os_dados(estado, tmp_path):
    _, conteudo = copias.ler_copia(copias.fazer_copia(_hora()))
    arq = tmp_path / "volta.sqlite"
    arq.write_bytes(conteudo["indice_emails.sqlite"])
    con = sqlite3.connect(arq)
    assert con.execute("select id from e").fetchall() == [("a",)]
    con.close()


def test_aparar_guarda_so_as_ultimas(estado, monkeypatch):
    for n in range(5):
        copias.fazer_copia(_hora(n))
    monkeypatch.setattr(copias.ajustes, "valor", lambda c: 2 if c == "limpeza.copias_guardadas" else 12)
    assert copias.aparar() == 3
    assert [z.stem for z in copias.listar()] == ["20261109_140000", "20261109_130000"]


def test_precisa_de_copia_so_depois_do_intervalo(estado):
    assert copias.precisa_de_copia(_hora())
    copias.fazer_copia(_hora())
    assert not copias.precisa_de_copia(_hora(5), horas=12) and copias.precisa_de_copia(_hora(12), horas=12)


def test_copia_adulterada_e_recusada(estado):
    z = copias.fazer_copia(_hora())
    novo = z.with_name("20261109_110000.zip")
    with zipfile.ZipFile(z) as a, zipfile.ZipFile(novo, "w") as b:
        for i in a.infolist():
            b.writestr(i.filename, b"{}" if i.filename == "ja_enviadas.json" else a.read(i.filename))
    with pytest.raises(ValueError, match="não confere"):
        copias.ler_copia(novo)


def test_conferir_acha_json_e_sqlite_quebrados(estado):
    assert copias.conferir() == []
    (estado / "ja_enviadas.json").write_text('{"NF-1": ', encoding="utf-8")
    (estado / "indice_emails.sqlite").write_bytes(b"isto nao e um banco sqlite" * 50)
    assert sorted(copias.conferir()) == ["indice_emails.sqlite", "ja_enviadas.json"]


def test_autocurar_separa_o_quebrado_e_volta_a_versao_boa(estado):
    copias.fazer_copia(_hora())
    (estado / "ja_enviadas.json").write_text("{lixo", encoding="utf-8")
    feitos = copias.autocurar(_hora(1))
    assert feitos == [{"arquivo": "ja_enviadas.json", "restaurado_de": "20261109_100000.zip"}]
    assert json.loads((estado / "ja_enviadas.json").read_text(encoding="utf-8")) == {"NF-1": "2026-11-09"}
    assert (estado / "ja_enviadas.json.quebrado-20261109_110000").read_text(encoding="utf-8") == "{lixo"   # nada é apagado
    assert copias.autocurar(_hora(2)) == []


def test_autocurar_sem_copia_boa_deixa_o_modulo_refazer(estado):
    (estado / "ja_enviadas.json").write_text("{lixo", encoding="utf-8")
    assert copias.autocurar(_hora()) == [{"arquivo": "ja_enviadas.json", "restaurado_de": None}]
    assert not (estado / "ja_enviadas.json").exists()


def test_autocurar_pula_copia_estragada_e_usa_a_anterior(estado):
    copias.fazer_copia(_hora())
    (copias.pasta() / "20261109_120000.zip").write_bytes(b"nao e zip")
    (estado / "app.json").write_text("{", encoding="utf-8")
    assert copias.autocurar(_hora(3))[0]["restaurado_de"] == "20261109_100000.zip"


def test_restaurar_guarda_o_que_existia_e_aceita_so_alguns_arquivos(estado):
    z = copias.fazer_copia(_hora())
    (estado / "app.json").write_text('{"agente": "Outro"}', encoding="utf-8")
    (estado / "ja_enviadas.json").write_text("{}", encoding="utf-8")
    assert copias.restaurar(z, so={"app.json"}, agora=_hora(1)) == ["app.json"]
    assert json.loads((estado / "app.json").read_text(encoding="utf-8")) == {"agente": "Maria"}
    assert (estado / "app.json.antes-de-restaurar-20261109_110000").exists()
    assert (estado / "ja_enviadas.json").read_text(encoding="utf-8") == "{}"   # o que não foi pedido fica como está


def test_restaurar_pasta_de_acessos(estado):
    z = copias.fazer_copia(_hora())
    (estado / "acessos" / "2026-11.jsonl").unlink()
    assert "acessos/2026-11.jsonl" in copias.restaurar(z)
    assert (estado / "acessos" / "2026-11.jsonl").read_text(encoding="utf-8") == '{"x":1}\n'


def test_aviso_de_saude_quando_nao_ha_copia_ou_esta_velha(estado):
    assert "ainda não fez cópia" in copias.resumo_para_saude(_hora())[0]["texto"]
    copias.fazer_copia(_hora())
    assert copias.resumo_para_saude(_hora(5)) == []
    assert "última cópia de segurança" in copias.resumo_para_saude(_hora(40))[0]["texto"]


def test_a_propria_pasta_de_copias_esta_no_catalogo_e_e_pessoal():
    d = armazem.DADOS["copias"]
    assert d.pessoal and d.formato == "pasta" and not d.refaz
    assert "copias" not in copias._nomes_do_catalogo()   # a cópia não guarda cópias de si mesma
