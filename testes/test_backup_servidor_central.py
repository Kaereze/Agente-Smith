"""ferramentas/backup_servidor_central.py: copia o banco do servidor central, confere a cópia e deixa um log sem dado de hóspede."""
import datetime
import importlib.util
from pathlib import Path

import pytest

from servidor_central.armazem import Armazem

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("backup_servidor_central", RAIZ / "ferramentas" / "backup_servidor_central.py")
ferramenta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ferramenta)

P = "planilha-de-teste"
SEGREDO = "NOME-DE-HOSPEDE-QUE-NAO-PODE-IR-PARA-O-LOG"


def _servidor_com_dados(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    a = Armazem(str(pasta / "central.sqlite"))
    a.criar_aba_log(P, "Aba", ["id"])
    a.anexar_linhas(P, "Aba", [[SEGREDO], ["2"]])
    a.fechar()


def test_faz_a_copia_confere_e_guarda_so_contagens_no_log(tmp_path):
    pasta = tmp_path / "ServidorCentral caminho com espaço é acento"   # o caminho real pode ter espaço e acento
    _servidor_com_dados(pasta)

    assert ferramenta.main(["--pasta", str(pasta)]) == 0

    copia = pasta / "copias" / f"central-{datetime.date.today().isoformat()}.sqlite"
    assert copia.exists()
    assert not list((pasta / "copias").glob("*-wal")) and not list((pasta / "copias").glob("*-shm"))   # a cópia é um arquivo só
    assert Armazem(str(copia)).ler_abas(P, ["Aba"])[0]["Aba"] == [["id"], [SEGREDO], ["2"]]
    log = (pasta / "copias" / "backup.log").read_text(encoding="utf-8")
    assert "OK" in log and "1 abas" in log and "3 linhas" in log
    assert SEGREDO not in log


def test_sem_banco_nao_cria_banco_vazio_e_avisa_no_log(tmp_path, capsys):
    pasta = tmp_path / "vazia"
    pasta.mkdir()

    assert ferramenta.main(["--pasta", str(pasta)]) == 1

    assert not (pasta / "central.sqlite").exists()      # não inventou um banco vazio para "copiar"
    assert "ERRO" in (pasta / "copias" / "backup.log").read_text(encoding="utf-8")
    assert "não achei o banco" in capsys.readouterr().out


def test_apaga_copias_com_mais_de_14_dias_e_mantem_as_recentes(tmp_path):
    pasta = tmp_path / "srv"
    _servidor_com_dados(pasta)
    copias = pasta / "copias"
    copias.mkdir()
    velha, recente = copias / "central-2026-01-01.sqlite", copias / "central-2026-11-20.sqlite"
    velha.write_bytes(b"x")
    recente.write_bytes(b"y")

    ferramenta.rodar(pasta, dias=14, hoje=datetime.date(2026, 11, 25))

    assert not velha.exists() and recente.exists() and (copias / "central-2026-11-25.sqlite").exists()


def test_copia_que_nao_abre_derruba_a_rodada(tmp_path):
    ruim = tmp_path / "ruim.sqlite"
    ruim.write_bytes(b"isto nao e um banco sqlite de verdade" * 40)
    with pytest.raises(Exception):
        ferramenta.conferir_copia(ruim)
