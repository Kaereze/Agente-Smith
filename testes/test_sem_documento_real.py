"""Trava contra CPF/CNPJ de hóspede em teste ou documento (LGPD, 27/10/2026).

O gancho de commit (ferramentas/checar_commit.py) compara com os backups da Central, mas só roda num PC que tem `estado/`.
Esta trava roda em qualquer lugar (casa, GitHub): qualquer CPF/CNPJ com dígitos verificadores válidos que apareça em
teste, cofre, CHANGELOG ou ferramentas, e que não esteja na lista abaixo, derruba os testes.

- EXEMPLOS: números inventados e conhecidos, pode usar à vontade.
- JA_EXISTIAM: impressão digital (SHA-256) dos números que já estavam nos testes em 27/10/2026 (só o resumo, nunca o
  número). Não crescem: número novo = use um exemplo, ou gere um inválido (ex.: troque o último dígito).
config.json fica de fora: os CNPJ lá são dos hotéis da rede, não de hóspedes.
"""
import hashlib
import re
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
EXTENSOES = (".py", ".md", ".html", ".js", ".txt", ".csv", ".bat", ".ps1", ".yml", ".json")
FORA = ("config.json", "package-lock.json")
EXEMPLOS = {"11144477735", "52998224725", "12345678909", "01234567890", "98765432100", "12345678000195", "11222333000181"}
JA_EXISTIAM = {
    "0601892f5b4c6830",
    "2eb50f04f470e2ad",
    "3ac88f4fa49c0530",
    "3e1074392928a50d",
    "9514d11150f2aa0f",
    "a0d33d1ff01c9725",
    "c357f5777da814c0",
    "c6fd69145051398f",
    "dba7f60663000b6a",
    "eba12a00a77c344f",
    "f15ac3c815973ffb",
    "fa53f235dd429db4",
}
NUMERO = re.compile(r"(?<![\d.\-/])(\d{3}\.\d{3}\.\d{3}-\d{2}|\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}|\d{11}|\d{14})(?!\d)")


def cpf_valido(d):
    if len(d) != 11 or len(set(d)) == 1:
        return False
    for n in (9, 10):
        soma = sum(int(d[i]) * (n + 1 - i) for i in range(n))
        if int(d[n]) != ((soma * 10) % 11) % 10:
            return False
    return True


def cnpj_valido(d):
    if len(d) != 14 or len(set(d)) == 1:
        return False
    pesos = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    for n in (12, 13):
        p = pesos if n == 12 else [6] + pesos
        resto = sum(int(d[i]) * p[i] for i in range(n)) % 11
        if int(d[n]) != (0 if resto < 2 else 11 - resto):
            return False
    return True


def documentos_validos(texto):
    """Dígitos de cada CPF/CNPJ válido do texto (com ou sem pontuação)."""
    achados = set()
    for m in NUMERO.finditer(texto):
        d = re.sub(r"\D", "", m.group(1))
        if cpf_valido(d) or cnpj_valido(d):
            achados.add(d)
    return achados


def impressao(d):
    return hashlib.sha256(d.encode()).hexdigest()[:16]


def novos(texto):
    return {d for d in documentos_validos(texto) if d not in EXEMPLOS and impressao(d) not in JA_EXISTIAM}


def arquivos_do_projeto():
    try:
        saida = subprocess.run(["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"], cwd=RAIZ, capture_output=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    nomes = [p for p in saida.decode("utf-8").split("\0") if p]
    return [RAIZ / n for n in nomes if n.endswith(EXTENSOES) and n.rsplit("/", 1)[-1] not in FORA]


def test_o_detector_acha_so_numero_valido():
    assert documentos_validos("CPF 111.444.777-35 e 11144477736 e CNPJ 11.222.333/0001-81 e 12.345.678/0001-96") == {
        "11144477735", "11222333000181"}
    assert novos("CPF 111.444.777-35") == set()
    base = "390533447"   # monta um CPF válido na hora (sem escrevê-lo aqui): fora das listas, a trava barra
    for n in (9, 10):
        base += str(((sum(int(base[i]) * (n + 1 - i) for i in range(n)) * 10) % 11) % 10)
    assert cpf_valido(base) and novos(f"CPF {base}") == {base}


def test_nenhum_cpf_ou_cnpj_novo_em_teste_ou_documento():
    arquivos = arquivos_do_projeto()
    if not arquivos:
        return   # sem git (pacote do pendrive): nada a conferir
    achados = []
    for arq in arquivos:
        try:
            texto = arq.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        achados += [f"{arq.relative_to(RAIZ).as_posix()} ({len(novos(texto))} número(s) válido(s))" for _ in [0] if novos(texto)]
    assert not achados, ("CPF/CNPJ válido fora das listas (pode ser de hóspede de verdade). Use 111.444.777-35 / 11.222.333/0001-81, "
                         "ou troque o último dígito para ficar inválido: " + "; ".join(achados))
