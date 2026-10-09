"""BackendGoogle com um gspread falso: confere quantas chamadas cada operação gasta da cota."""
import cota_google
import sheets


class AbaFalsa:
    def __init__(self, titulo, linhas=100, colunas=20):
        self.title, self.id, self.row_count, self.col_count = titulo, 7, linhas, colunas
        self.limpou = 0
        self.anexadas = []

    def clear(self):
        self.limpou += 1

    def resize(self, rows, cols):
        self.row_count, self.col_count = rows, cols

    def append_rows(self, linhas, value_input_option):
        self.anexadas += linhas


class PlanilhaFalsa:
    def __init__(self):
        self.abas = {"Correio_PC": AbaFalsa("Correio_PC")}
        self.procuras = 0
        self.gravacoes = []
        self.pedidos = []

    def worksheet(self, nome):
        self.procuras += 1
        return self.abas[nome]

    def worksheets(self):
        return list(self.abas.values())

    def values_update(self, faixa, params, body):
        self.gravacoes.append((faixa, body["values"]))

    def batch_update(self, corpo):
        self.pedidos.append(corpo)


def backend(monkeypatch, tmp_path):
    monkeypatch.setattr(cota_google, "PASTA_CONSUMO", tmp_path)
    monkeypatch.setattr(sheets, "COTA", cota_google.Cota("painel"))
    monkeypatch.setattr(sheets, "_ABAS", {})
    monkeypatch.setattr(sheets, "_TAMANHOS", {})
    b = object.__new__(sheets.BackendGoogle)
    p = PlanilhaFalsa()
    b._cliente, b._planilhas = None, {"X": p}
    return b, p


def test_substituir_aba_grava_numa_escrita_e_apaga_as_sobras(monkeypatch, tmp_path):
    b, p = backend(monkeypatch, tmp_path)
    b.substituir_aba("X", "Correio_PC", [["ID", "De"], ["1", "a"], ["2", "b"], ["3", "c"]])
    assert p.abas["Correio_PC"].limpou == 1          # 1ª vez: não sabe o que tinha, limpa
    b.substituir_aba("X", "Correio_PC", [["ID", "De"], ["1", "a"]])
    assert p.abas["Correio_PC"].limpou == 1          # depois: uma escrita só, por cima
    faixa, valores = p.gravacoes[-1]
    assert faixa == "'Correio_PC'!A1:B4"
    assert valores[2:] == [["", ""], ["", ""]]       # as 2 linhas que sobraram viram vazio
    assert p.procuras == 1                           # achou a aba 1 vez só


def test_anexar_linhas_nao_procura_a_aba_toda_vez(monkeypatch, tmp_path):
    b, p = backend(monkeypatch, tmp_path)
    for i in range(5):
        b.anexar_linhas("X", "Correio_PC", [[str(i)]])
    assert p.procuras == 1 and len(p.abas["Correio_PC"].anexadas) == 5
    assert sheets.COTA.consumo()["leituras"] == 1 and sheets.COTA.consumo()["escritas"] == 5


def test_apagar_linhas_e_um_pedido_so(monkeypatch, tmp_path):
    b, p = backend(monkeypatch, tmp_path)
    b.apagar_linhas("X", "Correio_PC", 2, 10, novas=[["resumo", "1"]])
    assert len(p.pedidos) == 1
    tipos = [list(r)[0] for r in p.pedidos[0]["requests"]]
    assert tipos == ["deleteDimension", "insertDimension", "updateCells"]
    assert p.pedidos[0]["requests"][0]["deleteDimension"]["range"]["startIndex"] == 1
