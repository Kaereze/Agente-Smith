"""Identidade do PC (src/identidade.py): votação contas do Outlook × Cadastro_Hoteis."""
from identidade import resolver

CAD = [(f"H{i}", f"nf{i}@joao.com", "João") for i in range(12)] + [(f"C{i}", f"nf{i}@clara.com", "Clara") for i in range(8)]


def test_pc_do_joao():
    agente, conf, _, _ = resolver([f"nf{i}@joao.com" for i in range(12)] + ["pessoal@gmail.com"], CAD)
    assert agente == "João" and conf == 100


def test_outlook_ainda_carregando_recusa_e_tenta_de_novo():
    agente, _, _, retentavel = resolver(["nf1@joao.com", "nf2@joao.com"], CAD)
    assert agente is None and retentavel


def test_pc_com_contas_de_dois_agentes_nao_e_atribuido():
    agente, _, motivo, retentavel = resolver([f"nf{i}@joao.com" for i in range(8)] + [f"nf{i}@clara.com" for i in range(6)], CAD)
    assert agente is None and not retentavel and "mais de um agente" in motivo
