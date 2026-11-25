"""Ferramenta que troca CPF/CNPJ válido por exemplo (ferramentas/trocar_documento_por_exemplo.py). Números gerados na hora."""
import importlib.util
from pathlib import Path

import test_sem_documento_real as regra

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("trocar_documento", RAIZ / "ferramentas" / "trocar_documento_por_exemplo.py")
ferramenta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ferramenta)


def _cpf(base="390533447"):
    for n in (9, 10):
        base += str(((sum(int(base[i]) * (n + 1 - i) for i in range(n)) * 10) % 11) % 10)
    return base


def _cnpj(base="987654320001"):   # não pode ser a base de um dos EXEMPLOS da trava (123456780001), que a ferramenta deixa como está
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for n in (12, 13):
        p = pesos if n == 12 else [6] + pesos
        resto = sum(int(base[i]) * p[i] for i in range(n)) % 11
        base += str(0 if resto < 2 else 11 - resto)
    return base


def _pontuado_cpf(d):
    return f"{d[:3]}.{d[3:6]}.{d[6:9]}-{d[9:]}"


def _pontuado_cnpj(d):
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}"


def test_troca_cpf_e_cnpj_mantendo_a_pontuacao():
    cpf, cnpj = _cpf(), _cnpj()
    assert regra.cpf_valido(cpf) and regra.cnpj_valido(cnpj)
    texto = f"A {_pontuado_cpf(cpf)} B {cpf} C {_pontuado_cnpj(cnpj)} D {cnpj}"
    novo, n = ferramenta.trocar(texto)
    assert n == 4
    assert novo == "A 111.444.777-35 B 11144477735 C 11.222.333/0001-81 D 11222333000181"
    assert not regra.novos(novo)


def test_nao_mexe_em_exemplo_numero_invalido_nem_texto_comum():
    invalido = _cpf()[:-1] + str((int(_cpf()[-1]) + 1) % 10)
    texto = f"exemplo 111.444.777-35 e 11222333000181; invalido {invalido}; data 2026-11-25 22:10; nada aqui"
    novo, n = ferramenta.trocar(texto)
    assert n == 0 and novo == texto


def test_simulacao_nao_grava_e_confirmo_grava_sem_mexer_nas_quebras_de_linha(tmp_path, capsys):
    cpf = _cpf()
    arq = tmp_path / "ficha.html"
    original = f"linha 1\r\nCPF {_pontuado_cpf(cpf)}\r\nlinha 3\r\n"
    arq.write_bytes(original.encode("utf-8"))

    assert ferramenta.main([str(arq)]) == 0
    assert arq.read_bytes() == original.encode("utf-8")   # só contou
    assert cpf not in capsys.readouterr().out.replace(".", "").replace("-", "")   # nunca imprime o número

    assert ferramenta.main([str(arq), "--confirmo"]) == 0
    assert arq.read_bytes() == "linha 1\r\nCPF 111.444.777-35\r\nlinha 3\r\n".encode("utf-8")
    saida = capsys.readouterr().out
    assert "1 número(s) trocados" in saida and cpf not in saida.replace(".", "").replace("-", "")


def test_aceita_curinga_e_avisa_quando_nao_acha(tmp_path, capsys):
    (tmp_path / "a Nielsen v4.html").write_text(f"CPF {_cpf()}", encoding="utf-8")
    (tmp_path / "b Nielsen v5.html").write_text("sem numero", encoding="utf-8")
    assert ferramenta.main([str(tmp_path / "*Nielsen v*.html"), "--confirmo"]) == 0
    saida = capsys.readouterr().out
    assert "a Nielsen v4.html: 1 número(s) trocados" in saida and "b Nielsen v5.html: nenhum número para trocar" in saida
    assert ferramenta.main([str(tmp_path / "nao_existe*.html")]) == 1
