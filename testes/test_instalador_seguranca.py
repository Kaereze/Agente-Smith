"""PC novo (05/11/2026): o teste do instalador confere relógio e cifra; o instalador chama o teste e liga a segurança. Dados inventados."""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "Automacoes"))

import testar_pc_novo  # noqa: E402


def test_desvio_do_relogio_para_mais_para_menos_e_ilegivel():
    assert testar_pc_novo.deslocamento_do_relogio("Thu, 05 Nov 2026 12:00:00 GMT", agora=1793880005.0) == 5.0
    assert testar_pc_novo.deslocamento_do_relogio("Thu, 05 Nov 2026 12:00:00 GMT", agora=1793879990.0) == -10.0
    assert testar_pc_novo.deslocamento_do_relogio("lixo") is None
    assert testar_pc_novo.deslocamento_do_relogio(None) is None


def test_cifra_do_teste_funciona_com_um_segredo_qualquer(capsys):
    assert testar_pc_novo.conferir_cifra(bytes(range(32))) is True
    assert "Cifra da rede" in capsys.readouterr().out


def test_instalador_liga_a_seguranca_e_chama_o_teste():
    ps1 = (RAIZ / "Automacoes" / "coracao.ps1").read_text(encoding="utf-8-sig")
    for trecho in ("liberar_rede.ps1", "testar_pc_novo.py", "segredo-rede.txt", "import cryptography", "w32tm /resync", "[$n/11]"):
        assert trecho in ps1, trecho
    assert ps1.index("Passo 7 ") < ps1.index("Passo 8 ") < ps1.index("Passo 10 ")
