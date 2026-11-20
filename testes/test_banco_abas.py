"""Espelho da fila de envio no banco (20/11/2026): modo sombra (a planilha manda), modo banco (o banco manda) e a faxina.
Nenhum teste fala com a internet: o Google e o Supabase são falsos."""
import datetime
import importlib.util
import json
import time
from pathlib import Path

import pytest

from central import banco_abas
from central.banco_abas import BackendComBanco, TABELA
from central.supabase import ErroBanco
from emails import envio_nf

FILA, OUTRA = envio_nf.ABA_FILA, "Comandos_PC"
CAB = envio_nf.CAB_FILA
AGORA = datetime.datetime(2026, 11, 20, 12, 0, tzinfo=datetime.timezone.utc)


class GoogleFalso:
    def __init__(self):
        self.abas = {FILA: [list(CAB)], OUTRA: [["Quando"]]}
        self.chamadas, self.falha_ao_gravar = [], None

    def anexar_linhas(self, planilha_id, aba, linhas):
        self.chamadas.append(("anexar", aba))
        if self.falha_ao_gravar:
            raise self.falha_ao_gravar
        self.abas.setdefault(aba, []).extend(linhas)

    def ler_abas(self, planilha_id, nomes, faixas=None):
        self.chamadas.append(("ler", tuple(nomes)))
        return {n: [list(l) for l in self.abas.get(n, [])] for n in nomes}, {}

    def apagar_linhas(self, planilha_id, aba, inicio, fim, novas=None):
        self.chamadas.append(("apagar", aba, inicio, fim, novas))

    def listar_abas(self, planilha_id):
        return list(self.abas)


class BancoFalso:
    def __init__(self):
        self.linhas, self.proximo, self.falha_gravar, self.falha_ler, self.apagados = [], 1, None, None, []

    def gravar(self, tabela, linhas, conflito=None):
        assert tabela == TABELA
        if self.falha_gravar:
            raise self.falha_gravar
        for l in linhas:
            self.linhas.append({"id": self.proximo, **l})
            self.proximo += 1

    def ler_tudo(self, tabela, filtros=None, colunas="*", ordem=None, pagina=1000, teto=100000):
        if self.falha_ler:
            raise self.falha_ler
        aba = filtros["aba"].removeprefix("eq.")
        return [{"valores": l["valores"]} for l in sorted(self.linhas, key=lambda x: x["id"]) if l["aba"] == aba]

    def ler(self, tabela, filtros=None, colunas="*", limite=1000, ordem=None, desloc=0):
        aba = filtros["aba"].removeprefix("eq.")
        todas = [{"id": l["id"]} for l in sorted(self.linhas, key=lambda x: x["id"]) if l["aba"] == aba]
        return todas[desloc:desloc + limite]

    def apagar(self, tabela, filtros):
        self.apagados.append(filtros)
        if "id" in filtros:
            ids = {int(x) for x in filtros["id"].removeprefix("in.(").removesuffix(")").split(",")}
            self.linhas = [l for l in self.linhas if l["id"] not in ids]


def montar(modo, **kw):
    google, banco = GoogleFalso(), BancoFalso()
    kw.setdefault("segundo_plano", False)
    kw.setdefault("esperar", lambda s: None)
    kw.setdefault("relogio", lambda: AGORA)
    return BackendComBanco(google, banco, {FILA: {"modo": modo, "cabecalho": CAB}}, retencao_dias={FILA: 3}, **kw), google, banco


def pedido(id_envio="ENV-1"):
    return envio_nf.evento(AGORA, id_envio, envio_nf.PEDIDO, "PC-A", "Clara", {"para": "hospede@exemplo.com", "assunto": "NF"})


# ---- modo sombra ----
def test_sombra_grava_na_planilha_primeiro_e_copia_para_o_banco():
    b, google, banco = montar("sombra")
    b.anexar_linhas("C", FILA, [pedido()])
    assert google.abas[FILA][1][1] == "ENV-1"
    assert [l["valores"][1] for l in banco.linhas] == ["ENV-1"] and banco.linhas[0]["aba"] == FILA
    assert b.gravadas == 1 and b.falhas == 0


def test_sombra_le_da_planilha_e_nunca_consulta_o_banco():
    b, google, banco = montar("sombra")
    banco.falha_ler = ErroBanco("não deveria ler")
    b.anexar_linhas("C", FILA, [pedido()])
    lidas, erros = b.ler_abas("C", [FILA, OUTRA])
    assert erros == {} and lidas[FILA][1][1] == "ENV-1"
    assert google.chamadas[-1] == ("ler", (FILA, OUTRA))


def test_sombra_banco_fora_do_ar_nao_derruba_o_envio_e_conta_a_falha():
    esperas = []
    b, google, banco = montar("sombra", esperar=esperas.append)
    banco.falha_gravar = ErroBanco("sem resposta do banco")
    b.anexar_linhas("C", FILA, [pedido()])   # não levanta
    assert len(google.abas[FILA]) == 2
    assert b.falhas == 1 and "banco/Envios_NF" in b.ultimo_erro and esperas == [2, 6]


def test_sombra_erro_da_planilha_sobe_e_o_banco_nao_recebe_nada():
    b, google, banco = montar("sombra")
    google.falha_ao_gravar = RuntimeError("429")
    with pytest.raises(RuntimeError):
        b.anexar_linhas("C", FILA, [pedido()])
    assert banco.linhas == []


def test_sombra_faxina_apaga_na_planilha_por_posicao_e_no_banco_por_idade():
    b, google, banco = montar("sombra")
    b.apagar_linhas("C", FILA, 2, 12)
    assert google.chamadas[-1] == ("apagar", FILA, 2, 12, None)
    assert banco.apagados == [{"aba": f"eq.{FILA}", "criado": "lt.2026-11-17T12:00:00Z"}]


# ---- modo banco ----
def test_banco_grava_no_banco_primeiro_e_a_planilha_recebe_a_copia():
    b, google, banco = montar("banco")
    b.anexar_linhas("C", FILA, [pedido()])
    assert len(banco.linhas) == 1 and google.abas[FILA][1][1] == "ENV-1"


def test_banco_fora_do_ar_o_erro_sobe_e_nada_vai_para_a_planilha():
    b, google, banco = montar("banco")
    banco.falha_gravar = ErroBanco("sem resposta do banco")
    with pytest.raises(ErroBanco):
        b.anexar_linhas("C", FILA, [pedido()])
    assert len(google.abas[FILA]) == 1   # só o cabeçalho


def test_banco_le_a_fila_do_banco_com_cabecalho_e_o_resto_do_google_numa_chamada_so():
    b, google, banco = montar("banco")
    b.anexar_linhas("C", FILA, [pedido("ENV-1")])
    b.anexar_linhas("C", FILA, [envio_nf.evento(AGORA, "ENV-1", envio_nf.ASSUMIDO, "PC-B", "Clara", {})])
    lidas, erros = b.ler_abas("C", [OUTRA, FILA, "Status"])
    assert erros == {} and lidas[FILA][0] == CAB and len(lidas[FILA]) == 3
    assert google.chamadas[-1] == ("ler", (OUTRA, "Status"))   # a fila saiu da chamada ao Google
    dobrada = envio_nf.dobrar_fila(lidas[FILA])                # o resto do Painel entende a fila do banco igual à da planilha
    assert dobrada["ENV-1"]["assumido_por"] == "PC-B" and dobrada["ENV-1"]["pedido"]["para"] == "hospede@exemplo.com"


def test_banco_so_com_a_fila_nao_chama_o_google_para_ler():
    b, google, _ = montar("banco")
    lidas, _ = b.ler_abas("C", [FILA])
    assert lidas[FILA] == [CAB] and not any(c[0] == "ler" for c in google.chamadas)


def test_banco_erro_de_leitura_vira_erro_da_aba_e_o_resto_e_lido():
    b, google, banco = montar("banco")
    banco.falha_ler = ErroBanco("o banco respondeu 503")
    lidas, erros = b.ler_abas("C", [OUTRA, FILA])
    assert OUTRA in lidas and FILA not in lidas and "banco" in erros[FILA] and "503" in erros[FILA]


def test_banco_faxina_apaga_exatamente_as_linhas_das_posicoes_lidas():
    b, google, banco = montar("banco")
    for i in range(5):
        b.anexar_linhas("C", FILA, [pedido(f"ENV-{i}")])
    b.apagar_linhas("C", FILA, 2, 5)   # as 3 primeiras linhas de dados
    assert [l["valores"][1] for l in banco.linhas] == ["ENV-3", "ENV-4"]
    assert not any(c[0] == "apagar" for c in google.chamadas)


# ---- o que não é da fila, e o modo casa ----
def test_aba_nao_ligada_passa_direto_para_a_planilha_e_o_resto_do_backend_tambem():
    b, google, banco = montar("banco")
    b.anexar_linhas("C", OUTRA, [["x"]])
    assert banco.linhas == [] and google.abas[OUTRA][-1] == ["x"]
    assert b.listar_abas("C") == [FILA, OUTRA]   # método que o espelho não conhece: vai para o Google


def test_modo_casa_somente_leitura_nunca_grava_no_banco():
    b, google, banco = montar("sombra", somente_leitura=True)
    b.anexar_linhas("C", FILA, [pedido()])
    b.apagar_linhas("C", FILA, 2, 3)
    assert banco.linhas == [] and banco.apagados == []
    assert ("anexar", FILA) in google.chamadas   # o backend do Google decide (no modo casa ele ignora)


def test_em_segundo_plano_as_copias_saem_na_ordem_sem_travar_quem_grava():
    b, google, banco = montar("sombra", segundo_plano=True)
    for i in range(20):
        b.anexar_linhas("C", FILA, [pedido(f"ENV-{i:02d}")])
    limite = time.time() + 5
    while b.gravadas < 20 and time.time() < limite:
        time.sleep(0.01)
    assert [l["valores"][1] for l in banco.linhas] == [f"ENV-{i:02d}" for i in range(20)]


# ---- ligar pela configuração ----
def test_envolver_sem_config_devolve_o_mesmo_backend():
    google = GoogleFalso()
    assert banco_abas.envolver(google, {}) is google
    assert banco_abas.envolver(google, {"banco": {"abas": {}}}) is google


def test_envolver_ignora_aba_desconhecida_e_modo_invalido():
    google = GoogleFalso()
    assert banco_abas.envolver(google, {"banco": {"abas": {"Tratamento": "banco", FILA: "tanto-faz"}}}) is google


def test_envolver_sem_arquivo_da_chave_segue_so_com_a_planilha(tmp_path):
    google = GoogleFalso()
    cfg = {"banco": {"abas": {FILA: "sombra"}}, "supabase": {"caminho_chave": str(tmp_path / "nao-existe.json")}}
    assert banco_abas.envolver(google, cfg) is google


def test_envolver_com_arquivo_liga_o_espelho_e_respeita_o_modo_casa(tmp_path):
    chave = tmp_path / "chave-supabase.json"
    chave.write_text(json.dumps({"url": "https://abcdefghijkl.supabase.co", "chave": "sb_publishable_chave_falsa_de_teste_123456",
                                 "email": "pc@exemplo.com", "senha": "x"}), encoding="utf-8")
    google = GoogleFalso()
    cfg = {"banco": {"abas": {FILA: "sombra"}}, "supabase": {"caminho_chave": str(chave)}}
    b = banco_abas.envolver(google, cfg, somente_leitura=True, segundo_plano=False)
    assert isinstance(b, BackendComBanco) and b.modo_de(FILA) == "sombra" and b.resumo()["abas"] == {FILA: "sombra"}


# ---- comparação planilha x banco e ligação nos programas ----
RAIZ = Path(__file__).resolve().parents[1]


def _ferramenta():
    spec = importlib.util.spec_from_file_location("comparar_fila_banco", RAIZ / "ferramentas" / "comparar_fila_banco.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_comparar_acha_o_que_falta_e_o_que_sobra_e_ignora_o_que_e_mais_velho_que_o_banco():
    comparar = _ferramenta().comparar
    velha = ["2026-11-10T08:00:00", "ENV-0", "PEDIDO", "PC-A", "Clara", "{}"]
    a, b, c = (["2026-11-20T09:00:00", f"ENV-{i}", "PEDIDO", "PC-A", "Clara", "{}"] for i in (1, 2, 3))
    faltam, sobram, contadas = comparar([velha, a, b], [a, c])
    assert faltam == [tuple(b)] and sobram == [tuple(c)] and contadas == 2   # a velha (antes do banco começar) não conta
    assert comparar([a], [a]) == ([], [], 1)
    assert comparar([a], []) == ([], [], 0)   # banco vazio: nada a comparar


def test_o_painel_e_o_robo_passam_o_backend_pelo_espelho_e_o_robo_sem_segundo_plano():
    servidor = (RAIZ / "src" / "app_servidor.py").read_text(encoding="utf-8")
    robo = (RAIZ / "src" / "main.py").read_text(encoding="utf-8")
    assert servidor.count("banco_abas.envolver(") == 2 and "somente_leitura=True" in servidor.split("banco_abas.envolver(")[1]
    assert "banco_abas.envolver(" in robo and "segundo_plano=False" in robo   # o robô termina e fecha: a cópia sai na hora
    config = json.loads((RAIZ / "config.json").read_text(encoding="utf-8"))
    assert config["banco"] == {"abas": {}}   # entrega: tudo desligado até o João ligar, PC por PC, no config.local.json
