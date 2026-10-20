"""Travas de entrega: guarda do git (Claude Code) e checagem antes do commit."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "ferramentas"))
import checar_commit  # noqa: E402
import guarda_git  # noqa: E402


def test_guarda_libera_a_entrega_normal():
    for cmd in ["git push origin main main:Bernardo main:Christian main:clara", "git status", "git log --oneline -5",
                "git checkout -- src/envio_nf.py", "git restore --staged estado/x.json", "git branch -d velha",
                "git commit -m 'reset --hard no texto'"]:
        assert guarda_git.motivo(cmd) is None, cmd


def test_guarda_bloqueia_o_que_apaga_trabalho():
    for cmd in ["git push --force origin main", "git push -f origin main", "git push origin +main",
                "git push --force-with-lease", "git push origin --delete clara", "git push origin :clara",
                "git reset --hard HEAD~1", "git clean -fd", "git clean -xf", "git branch -D clara",
                "git checkout .", "git checkout -- .", "git restore .",
                'cd "/c/x" && git reset --hard origin/main', 'git -C "Solicitacoes NF" push --force']:
        assert guarda_git.motivo(cmd), cmd


def test_commit_barra_dado_do_robo_e_credencial():
    arquivos = {"src/ok.py": "x = 1", "estado/diario.json": "{}", "logs/robo.log": "", "config.local.json": "{}",
                "chave_google.json": "{}", "src/vaza.py": 'K = "' + "ghp_" + "a" * 30 + '"'}
    achados = checar_commit.problemas(list(arquivos), arquivos.get)
    assert not any(a.startswith("src/ok.py") for a in achados)
    for rel in ["estado/diario.json", "logs/robo.log", "config.local.json", "chave_google.json", "src/vaza.py"]:
        assert any(a.startswith(rel) for a in achados), rel
    assert not any("a" * 30 in a for a in achados)   # o valor nunca aparece


def test_commit_barra_cpf_de_hospede_de_verdade(tmp_path):
    (tmp_path / "backup_central_20261019_120000.json").write_text('{"cpf": "275.314.860-04"}', encoding="utf-8")
    reais = checar_commit.cpfs_reais(tmp_path)
    arquivos = {"testes/test_x.py": 'CPF = "27531486004"', "testes/test_y.py": 'CPF = "123.456.789-09"  # exemplo'}
    achados = checar_commit.problemas(list(arquivos), arquivos.get, reais)
    assert len(achados) == 1 and achados[0].startswith("testes/test_x.py") and "27531486004" not in achados[0]


def test_sem_estado_a_trava_de_cpf_nao_roda(tmp_path):
    assert checar_commit.cpfs_reais(tmp_path) == set()


def test_commit_limpo_passa():
    assert checar_commit.problemas(["README.md", "src/main.py"], lambda rel: "texto comum") == []
