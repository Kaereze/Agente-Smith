"""Um arquivo de log por programa (20/10/2026): o log disputado entre robô, conferente e Painel não gira mais."""
import log_util


def test_cada_programa_tem_o_seu_arquivo():
    assert log_util.arquivo_do_programa(r"C:\x\Solicitacoes NF\src\sincronizar.py") == "solicitacoes_nf.log"
    assert log_util.arquivo_do_programa("robo.py") == "solicitacoes_nf.log"
    assert log_util.arquivo_do_programa(r"src\main.py") == "solicitacoes_nf.log"
    assert log_util.arquivo_do_programa(r"src\conferente.py") == "conferente.log"
    assert log_util.arquivo_do_programa(r"src\app_servidor.py") == "painel.log"


def test_robo_conferente_e_painel_nunca_dividem_arquivo():
    arquivos = {log_util.arquivo_do_programa(s) for s in ("src/sincronizar.py", "src/conferente.py", "src/app_servidor.py")}
    assert len(arquivos) == 3


def test_outros_scripts_e_chamadas_sem_script():
    assert log_util.arquivo_do_programa(r"src\confirmar_nfs.py") == "confirmar_nfs.log"
    assert log_util.arquivo_do_programa("-c") == "outros.log"
    assert log_util.arquivo_do_programa("") == "outros.log"
    assert log_util.arquivo_do_programa("../../x y.py") == "xy.log"


def test_sob_pytest_continua_no_log_de_teste():
    assert log_util._rodando_sob_pytest()
