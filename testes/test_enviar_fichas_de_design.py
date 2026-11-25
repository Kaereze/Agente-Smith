"""ferramentas/enviar_fichas_de_design.py com repositórios de verdade (um "remoto" e uma cópia), sem tocar no GitHub."""
import importlib.util
import subprocess
from pathlib import Path

from test_trocar_documento_por_exemplo import _cnpj, _cpf, _pontuado_cpf

RAIZ = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("enviar_fichas", RAIZ / "ferramentas" / "enviar_fichas_de_design.py")
enviar_fichas = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(enviar_fichas)

COFRE = "Segundo Cérebro (Agente Smith)"
DESIGNS = f"{COFRE}/6 Documentos/Designs"


def _git(pasta, *args):
    r = subprocess.run(["git", *args], cwd=pasta, capture_output=True, text=True, encoding="utf-8", check=True)
    return r.stdout.strip()


def _montar(tmp_path):
    remoto = tmp_path / "remoto.git"
    repo = tmp_path / "pc"
    subprocess.run(["git", "init", "-q", "--bare", str(remoto)], check=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "config", "user.name", "Teste")
    _git(repo, "config", "user.email", "teste@exemplo.com.br")
    (repo / DESIGNS).mkdir(parents=True)
    (repo / DESIGNS / "leia-me.md").write_text("designs", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base")
    _git(repo, "remote", "add", "origin", str(remoto))
    _git(repo, "push", "-q", "origin", "main")
    return remoto, repo


def _conteudo_no_remoto(remoto, ramo, caminho):
    return subprocess.run(["git", "show", f"{ramo}:{caminho}"], cwd=remoto, capture_output=True, check=True).stdout.decode("utf-8")


def test_fichas_na_area_de_trabalho_viram_branch_limpa_e_a_main_nao_muda(tmp_path):
    remoto, repo = _montar(tmp_path)
    desk = tmp_path / "desk"
    desk.mkdir()
    cpf, cnpj = _cpf(), _cnpj()
    (desk / "2026-11-20 Ficha Nielsen v4 (a).html").write_text(f"<p>CPF {_pontuado_cpf(cpf)}</p>\r\n", encoding="utf-8", newline="")
    (desk / "2026-11-20 Ficha Nielsen v5 (b).html").write_text(f"<p>{cnpj}</p>", encoding="utf-8")
    saidas = []

    assert enviar_fichas.enviar(raiz=repo, desktop=desk, dizer=saidas.append) == 0
    texto_saidas = "\n".join(saidas)
    assert cpf not in texto_saidas and cnpj not in texto_saidas and "PRONTO" in texto_saidas

    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "main"                    # voltou para a main
    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""             # PC limpo
    assert not list(desk.glob("*.html"))                                                 # saíram da Área de Trabalho
    assert _git(remoto, "rev-parse", "main") == _git(repo, "rev-parse", "main")          # a main do remoto não mudou
    ramo = enviar_fichas.RAMO
    v4 = _conteudo_no_remoto(remoto, ramo, f"{DESIGNS}/2026-11-20 Ficha Nielsen v4 (a).html")
    v5 = _conteudo_no_remoto(remoto, ramo, f"{DESIGNS}/2026-11-20 Ficha Nielsen v5 (b).html")
    assert "111.444.777-35" in v4 and "11222333000181" in v5
    assert cpf not in v4.replace(".", "").replace("-", "") and cnpj not in v5

    saidas.clear()
    assert enviar_fichas.enviar(raiz=repo, desktop=desk, dizer=saidas.append) == 0       # repetir não faz nada
    assert "Nenhuma ficha" in saidas[0]


def test_fichas_ja_preparadas_no_git_dentro_de_designs_tambem_funcionam(tmp_path):
    remoto, repo = _montar(tmp_path)
    cpf = _cpf()
    ficha = repo / DESIGNS / "2026-11-20 Ficha Nielsen v4 (a).html"
    ficha.write_text(f"CPF {cpf}", encoding="utf-8")
    _git(repo, "add", "--", f"{DESIGNS}/2026-11-20 Ficha Nielsen v4 (a).html")           # como ficou o PC do João: preparada, sem commit

    assert enviar_fichas.enviar(raiz=repo, desktop=tmp_path / "vazio", dizer=lambda _: None) == 0

    assert _git(repo, "status", "--porcelain", "--untracked-files=no") == ""
    assert "11144477735" in _conteudo_no_remoto(remoto, enviar_fichas.RAMO, f"{DESIGNS}/2026-11-20 Ficha Nielsen v4 (a).html")
    assert cpf not in subprocess.run(["git", "log", "--all", "-p"], cwd=remoto, capture_output=True, text=True, encoding="utf-8").stdout


def test_para_sem_mexer_quando_ha_outro_arquivo_alterado(tmp_path, capsys):
    remoto, repo = _montar(tmp_path)
    desk = tmp_path / "desk"
    desk.mkdir()
    (desk / "x Nielsen v4 y.html").write_text(f"CPF {_cpf()}", encoding="utf-8")
    (repo / DESIGNS / "leia-me.md").write_text("alterado a mao", encoding="utf-8")        # arquivo versionado modificado

    assert enviar_fichas.main(raiz=repo, desktop=desk, argv=[]) == 1
    assert "PAREI" in capsys.readouterr().out
    assert (desk / "x Nielsen v4 y.html").exists()                                        # nada foi movido
    assert enviar_fichas.RAMO not in _git(remoto, "branch", "--list")
