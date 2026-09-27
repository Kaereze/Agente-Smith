"""
Peças falsas pros testes — nenhum teste usa Google nem Outlook de verdade.

PlanilhaFalsa imita o BackendGoogle (guarda as abas num dicionário).
OutlookFalso imita o OutlookNF (Caixa de Saída e Itens Enviados em listas).
"""
import copy
import datetime
import json
import os
import sys

import pytest
from gspread.utils import a1_to_rowcol

PASTA_PROJETO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(PASTA_PROJETO, "src"))

CENTRAL = "PLANILHA_CENTRAL"
ESTRELA = "Solicitação Nota Fiscal (Estrela Centro) (respostas)"
ARACAJU = "Solicitação Nota Fiscal (Aracaju) (respostas)"
BARRA = "Nota Fiscal (Barra) (respostas)"
CABECALHO_HOTEL = ["Carimbo de data/hora", "Endereço de e-mail", "Hotel", "Nome do Hóspede", "CPF", "CEP",
                   "Data de Check-in", "Nota Dividida", "IMPORTANTE", "Preenchimento intuitivo", "Enviado"]


def linha_hotel(n, hotel="Hotel", cpf="1234567890", enviado="FALSE"):
    return [f"9/{(n % 28) + 1}/2026 10:{n % 60:02d}:00", f"hospede{n}@x.com", hotel, f"Hóspede Número {n} Silva",
            cpf, "1310000", "9/3/2026", "Não", "ok", "5", enviado]


class PlanilhaFalsa:
    def __init__(self):
        self.planilhas = {CENTRAL: {}}
        self.abas_com_erro = set()
        self.falhas_escrita = 0          # quantas próximas escritas vão dar erro
        self.escritas = 0

    def aba(self, nome, planilha=CENTRAL):
        return self.planilhas.setdefault(planilha, {})[nome]

    def listar_abas(self, planilha_id):
        return list(self.planilhas.get(planilha_id, {}))

    def ler_abas(self, planilha_id, nomes):
        dados, erros = {}, {}
        for nome in nomes:
            abas = self.planilhas.get(planilha_id, {})
            if nome in self.abas_com_erro or nome not in abas:
                erros[nome] = f"Unable to parse range: {nome}"
            else:
                dados[nome] = copy.deepcopy(abas[nome])
        return dados, erros

    def escrever(self, planilha_id, atualizacoes):
        if self.falhas_escrita:
            self.falhas_escrita -= 1
            raise RuntimeError("503 Google fora do ar (simulado)")
        for faixa, valor in atualizacoes:
            aba, celula = faixa.rsplit("!", 1)
            aba = aba[1:-1].replace("''", "'")
            linha, coluna = a1_to_rowcol(celula)
            tabela = self.planilhas[planilha_id][aba]
            while len(tabela) < linha:
                tabela.append([])
            while len(tabela[linha - 1]) < coluna:
                tabela[linha - 1].append("")
            if isinstance(valor, str) and valor.startswith("'"):
                valor = valor[1:]  # igual ao Google: o apóstrofo só força texto, não aparece na célula
            tabela[linha - 1][coluna - 1] = "TRUE" if valor is True else ("FALSE" if valor is False else valor)
        self.escritas += 1

    def criar_aba_status(self, planilha_id, nome, linhas):
        self.planilhas[planilha_id][nome] = [["TRUE" if v is True else "FALSE" if v is False else v for v in l]
                                             for l in linhas]

    def criar_aba_log(self, planilha_id, nome, cabecalho):
        self.planilhas[planilha_id][nome] = [list(cabecalho)]

    def inserir_no_topo(self, planilha_id, aba, linhas):
        tabela = self.planilhas[planilha_id][aba]
        tabela[1:1] = [list(l) for l in linhas]

    def anexar_linhas(self, planilha_id, aba, linhas):
        self.planilhas.setdefault(planilha_id, {}).setdefault(aba, []).extend(linhas)


class OutlookFalso:
    def __init__(self):
        self.enviados = []           # e-mails que "saíram"
        self.caixa_saida = []        # e-mails presos
        self.prender_na_saida = False
        self.falhar_envios = set()   # índices (1, 2, ...) de envio que dão erro
        self.outlook_morre_apos_falha = False
        self.tentativas_envio = 0
        self.conexoes = 0

    def conectar(self):
        self.conexoes += 1
        if self.outlook_morre_apos_falha and self.tentativas_envio in self.falhar_envios:
            raise RuntimeError("Outlook fechado (simulado)")

    def enviar(self, email):
        self.tentativas_envio += 1
        if self.tentativas_envio in self.falhar_envios:
            raise RuntimeError("O Outlook foi fechado durante o envio (simulado)")
        (self.caixa_saida if self.prender_na_saida else self.enviados).append(email)

    def esta_nos_enviados(self, codigo, desde, destinatario=None):
        return any(e.codigo == codigo for e in self.enviados)

    def esta_na_caixa_saida(self, codigo, destinatario=None):
        return any(e.codigo == codigo for e in self.caixa_saida)

    def solicitacoes_enviadas(self):
        return [s.chave for e in self.enviados for s in e.solicitacoes]


class Relogio:
    def __init__(self):
        self.t = 0.0

    def agora(self):
        return self.t

    def esperar(self, segundos):
        self.t += segundos


@pytest.fixture
def cfg():
    with open(os.path.join(PASTA_PROJETO, "config.json"), encoding="utf-8") as f:
        c = json.load(f)
    c.update(modo="PRODUCAO", email_teste="teste@x.com", planilha_central_id=CENTRAL, somente_hoteis=[], destino_envio="agente",
             registro_central={"ativo": True, "planilha_id": "REGISTROS", "aba": "Registros"},
             agentes={"João": "notafiscal1@andradehoteis.com.br", "Clara": "notafiscal2@andradehoteis.com.br",
                      "Cristian": "notafiscal3@andradehoteis.com.br", "Bernardo": "notafiscal4@andradehoteis.com.br"})
    return c


@pytest.fixture
def planilha():
    p = PlanilhaFalsa()
    # igual ao Cadastro_Hoteis real: sem cabeçalho; A = hotel, B = e-mail do hotel, C = agente
    p.planilhas[CENTRAL]["Cadastro_Hoteis"] = [
        ["ESTRELA CENTRO", "notafiscal@estrela.com.br", "João"],
        ["ARACAJU", "notafiscal@aracaju.com.br", "Clara"],
        ["BARRA", "notafiscal@barra.com.br", "João"],
        ["JERI", "notafiscal@jeri.com.br", "Bernardo"],
    ]
    p.planilhas[CENTRAL]["Status"] = [["Robô ligado?", "TRUE"], ["Última execução com sucesso", ""],
                                      ["Resumo da última execução", ""], ["Última tentativa", ""],
                                      ["Modo", ""], ["Máquina", ""]]
    p.planilhas[CENTRAL][ESTRELA] = [CABECALHO_HOTEL, linha_hotel(1, "Estrela"), linha_hotel(2, "Estrela", enviado="TRUE"),
                                     linha_hotel(3, "Estrela", enviado="")]
    p.planilhas[CENTRAL][ARACAJU] = [CABECALHO_HOTEL, linha_hotel(4, "Aracaju")]
    p.planilhas[CENTRAL][BARRA] = [CABECALHO_HOTEL, linha_hotel(5, "Barra")]
    p.planilhas["REGISTROS"] = {"Registros": [CABECALHO_HOTEL]}
    return p


@pytest.fixture
def outlook():
    return OutlookFalso()


@pytest.fixture(autouse=True)
def pastas_temporarias(tmp_path, monkeypatch):
    """Diário de envios e simulação vão pra uma pasta temporária, nunca pras pastas reais."""
    import main
    monkeypatch.setattr(main, "PASTA_ESTADO", tmp_path / "estado")
    monkeypatch.setattr(main, "PASTA_SIMULACAO", tmp_path / "simulacao")
    return tmp_path


AGORA = datetime.datetime(2026, 9, 24, 10, 0, 0)
