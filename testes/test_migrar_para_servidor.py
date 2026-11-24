"""Cópia da Central do Google para o servidor central e conferência (API central, etapa 2). Só dados inventados."""
import threading

import pytest

from central import migrar_para_servidor as mig
from central.backend_api import BackendAPI
from servidor_central import servidor
from servidor_central.armazem import Armazem

P = "central-teste"
SEGREDO = "Fulano Inventado 000.000.000-00"


class SoLeitura(Armazem):
    """A origem: igual ao Google, mas se alguém tentar gravar o teste grita (a cópia nunca pode alterar o Google)."""

    def __init__(self, abas):
        super().__init__()
        for nome, linhas in abas.items():
            super().substituir_aba(P, nome, linhas)
        self.travada = True

    def _proibido(self, *a, **k):
        raise AssertionError("a cópia tentou GRAVAR na origem")

    def __getattribute__(self, nome):
        if nome in ("escrever", "criar_aba_status", "criar_aba_log", "inserir_no_topo", "substituir_aba", "garantir_colunas",
                    "anexar_linhas", "apagar_linhas", "apagar_aba") and object.__getattribute__(self, "__dict__").get("travada"):
            return object.__getattribute__(self, "_proibido")
        return super().__getattribute__(nome)


def _central():
    return SoLeitura({
        "Envios_NF": [["id", "estado"], ["ENV-1", "enviado"], [], ["ENV-3", "aguardando", "", "x"]],
        "PCs_Painel": [["pc", "agente"], ["DESKTOP-A", "Clara"]],
        "Cadastro_Hoteis": [["hotel", "caixa"], [SEGREDO, "x@exemplo.com"]],
        "Vazia": [],
        "Solicitação Nota Fiscal (HOTEL A) (respostas)": [["Carimbo"], ["01/01/2026"]],
        "Nota Fiscal (Biton) (respostas)": [["Carimbo"]],
    })


def test_so_as_abas_internas_sao_copiadas_e_as_de_formulario_ficam_no_google():
    abas, faltam = mig.abas_a_copiar(_central(), P)
    assert abas == ["Envios_NF", "PCs_Painel", "Cadastro_Hoteis", "Vazia"] and faltam == []


def test_pedir_so_algumas_abas_e_avisar_das_que_nao_existem():
    abas, faltam = mig.abas_a_copiar(_central(), P, ["PCs_Painel", "Solicitação Nota Fiscal (HOTEL A) (respostas)", "Nada"])
    assert abas == ["PCs_Painel"] and faltam == ["Solicitação Nota Fiscal (HOTEL A) (respostas)", "Nada"]


def test_copia_e_conferencia_ficam_iguais_inclusive_linha_vazia_no_meio_e_aba_vazia():
    origem, destino = _central(), Armazem()
    abas, _ = mig.abas_a_copiar(origem, P)
    saidas = []
    assert mig.copiar_e_conferir(origem, destino, P, abas, escrever=saidas.append) == 0
    assert destino.listar_abas(P) == abas and destino.ler_abas(P, ["Vazia"])[0]["Vazia"] == []
    lidas = destino.ler_abas(P, ["Envios_NF"])[0]["Envios_NF"]
    assert lidas == [["id", "estado"], ["ENV-1", "enviado"], [], ["ENV-3", "aguardando", "", "x"]]   # a linha 3 vazia continua no lugar
    assert "4 aba(s) iguais" in saidas[-1]


def test_a_copia_nunca_grava_na_origem():
    origem, destino = _central(), Armazem()
    mig.copiar_e_conferir(origem, destino, P, mig.abas_a_copiar(origem, P)[0], escrever=lambda t: None)   # gritaria se gravasse


def test_conferencia_acha_a_aba_que_mudou_e_diz_a_linha_sem_mostrar_o_conteudo():
    origem, destino = _central(), Armazem()
    abas, _ = mig.abas_a_copiar(origem, P)
    mig.copiar(origem, destino, P, abas)
    destino.escrever(P, [("'Cadastro_Hoteis'!A2", "OUTRO NOME")])
    r = mig.conferir(origem, destino, P, abas)
    assert list(r["diferentes"]) == ["Cadastro_Hoteis"] and r["diferentes"]["Cadastro_Hoteis"]["primeira_linha_diferente"] == 2
    texto = mig.relatorio_da_conferencia(r)
    assert "Cadastro_Hoteis" in texto and SEGREDO not in texto and "OUTRO NOME" not in texto


def test_conferencia_acha_linha_a_mais_no_servidor():
    origem, destino = _central(), Armazem()
    abas, _ = mig.abas_a_copiar(origem, P)
    mig.copiar(origem, destino, P, abas)
    destino.anexar_linhas(P, "PCs_Painel", [["DESKTOP-B", "Bernardo"]])
    r = mig.conferir(origem, destino, P, abas)
    assert r["diferentes"]["PCs_Painel"] == {"origem": 2, "destino": 3, "primeira_linha_diferente": 3}


def test_servidor_que_ja_tem_abas_nao_e_sobrescrito_sem_refazer():
    origem, destino = _central(), Armazem()
    destino.criar_aba_log(P, "Envios_NF", ["gravado pelos PCs"])
    saidas = []
    assert mig.copiar_e_conferir(origem, destino, P, ["Envios_NF"], escrever=saidas.append) == 2
    assert destino.ler_abas(P, ["Envios_NF"])[0]["Envios_NF"] == [["gravado pelos PCs"]]
    assert "nada foi copiado" in saidas[0]
    assert mig.copiar_e_conferir(origem, destino, P, ["Envios_NF"], refazer=True, escrever=saidas.append) == 0


def test_uma_aba_que_falha_nao_impede_as_outras_e_aparece_no_relatorio():
    origem = _central()

    class DestinoQueFalha(Armazem):
        def substituir_aba(self, planilha_id, aba, linhas):
            if aba == "PCs_Painel":
                raise RuntimeError("disco cheio")
            return super().substituir_aba(planilha_id, aba, linhas)
    destino = DestinoQueFalha()
    r = mig.copiar(origem, destino, P, ["Envios_NF", "PCs_Painel", "Vazia"])
    assert set(r["copiadas"]) == {"Envios_NF", "Vazia"} and "disco cheio" in r["erros"]["PCs_Painel"]


def test_aba_que_some_da_origem_aparece_como_erro_na_copia():
    origem, destino = _central(), Armazem()
    r = mig.copiar(origem, destino, P, ["Envios_NF", "Sumiu"])
    assert "Envios_NF" in r["copiadas"] and "Sumiu" in r["erros"]


def test_copia_pela_rede_para_o_servidor_de_verdade():
    srv = servidor.servir(Armazem(), "t" * 32, porta=0, endereco="127.0.0.1")
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        destino = BackendAPI(f"http://127.0.0.1:{srv.server_address[1]}", "t" * 32)
        origem = _central()
        abas, _ = mig.abas_a_copiar(origem, P)
        assert mig.copiar_e_conferir(origem, destino, P, abas, escrever=lambda t: None) == 0
        assert destino.ler_abas(P, ["PCs_Painel"])[0]["PCs_Painel"] == [["pc", "agente"], ["DESKTOP-A", "Clara"]]
    finally:
        srv.shutdown()
        srv.server_close()


def test_sem_token_na_variavel_a_ferramenta_nao_tenta_o_servidor(monkeypatch):
    monkeypatch.delenv("CENTRAL_TOKEN", raising=False)
    args = type("A", (), {"arquivo": None, "servidor": "http://127.0.0.1:1"})()
    with pytest.raises(SystemExit):
        mig._destino(args)
