"""Teste da conexão com o Supabase: confere se conecta e MEDE quanto demora (dados fictícios, nada de hóspede).

    python ferramentas\\testar_supabase.py                 (usa %APPDATA%\\SolicitacoesNF\\chave-supabase.json)
    python ferramentas\\testar_supabase.py C:\\outro\\caminho\\chave-supabase.json

Antes: criar o projeto no Supabase, rodar `ferramentas\\supabase_tabelas.sql` no SQL Editor e guardar a chave (url + chave) no arquivo
acima. O arquivo fica FORA do repositório e este programa nunca mostra a chave. No fim apaga as linhas de teste.
"""
import os
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from central import banco_abas, supabase  # noqa: E402

LINHAS = 20     # linhas fictícias por gravação
RODADAS = 5     # quantas vezes mede cada coisa
ABA_TESTE = "TESTE_FILA"   # aba fictícia: nunca mexe na fila de verdade


class _GoogleVazio:   # a fila de teste só existe no banco
    def anexar_linhas(self, *a):
        pass

    def ler_abas(self, *a):
        return {}, {}


def medir(func):
    inicio = time.perf_counter()
    func()
    return time.perf_counter() - inicio


def resumo(nome, tempos):
    medio, pior = statistics.mean(tempos), max(tempos)
    print(f"  {nome:<34} médio {medio:5.2f} s · pior {pior:5.2f} s")
    return medio


def principal(argv):
    for saida in (sys.stdout, sys.stderr):   # o console do Windows (cp1252) quebraria nos ✅ e ❌
        if hasattr(saida, "reconfigure"):
            saida.reconfigure(encoding="utf-8", errors="replace")
    caminho = argv[1] if len(argv) > 1 else supabase.caminho_da_chave()
    try:
        banco = supabase.Banco.do_arquivo(caminho)
    except supabase.ErroBanco as e:
        print(f"❌ {e}")
        return 1
    pc = os.environ.get("COMPUTERNAME", "este-pc")
    ids = [f"teste-{pc}-{i}" for i in range(LINHAS)]
    try:
        print("1) Conectando e achando a tabela de teste...")
        banco.ler("painel_teste", limite=1)
        print("   ✅ conectou")
        print(f"2) Medindo ({RODADAS} vezes cada)...")
        gravar = [medir(lambda: banco.gravar("painel_teste", [{"id": i, "pc": pc, "valor": "fictício"} for i in ids], conflito="id"))
                  for _ in range(RODADAS)]
        ler = [medir(lambda: banco.ler("painel_teste", {"pc": f"eq.{pc}"})) for _ in range(RODADAS)]
        sinal = [medir(lambda: banco.sinal_de_vida(pc, "teste")) for _ in range(RODADAS)]
        resumo(f"gravar {LINHAS} linhas numa chamada", gravar)
        resumo("ler as linhas de volta", ler)
        resumo("sinal de vida (1 linha)", sinal)
        if banco.com_credencial:   # a fila de envio: o que o Painel vai usar de verdade (aba de teste, dados fictícios)
            fila = banco_abas.BackendComBanco(_GoogleVazio(), banco, {ABA_TESTE: {"modo": "banco", "cabecalho": ["Quando", "ID", "Evento", "PC", "Quem", "Dados (JSON)"]}},
                                              segundo_plano=False)
            linha = [["2026-01-01T00:00:00", f"ENV-TESTE-{i}", "PEDIDO", pc, "Teste", "{}"] for i in range(5)]
            gravar_fila = [medir(lambda: fila.anexar_linhas("-", ABA_TESTE, linha)) for _ in range(RODADAS)]
            ler_fila = [medir(lambda: fila.ler_abas("-", [ABA_TESTE])) for _ in range(RODADAS)]
            resumo("fila: gravar 5 eventos (por entrada do PC)", gravar_fila)
            resumo("fila: ler a fila inteira de teste", ler_fila)
            lidas = fila.ler_abas("-", [ABA_TESTE])[0][ABA_TESTE]
            print(f"  fila de teste lida de volta: {len(lidas) - 1} eventos (esperado {5 * RODADAS})")
        else:
            print("  (sem 'email' e 'senha' no arquivo da chave: a fila de envio não foi medida)")
    except supabase.ErroBanco as e:
        print(f"❌ {e}")
        if e.codigo in (404, 400):
            print("   Dica: a tabela ainda não existe. Rode ferramentas\\supabase_tabelas.sql no SQL Editor do Supabase.")
        if e.codigo in (401, 403):
            print("   Dica: a chave não foi aceita. Confira a chave PUBLICÁVEL, o 'email' e a 'senha' do arquivo e se o e-mail está em pcs_autorizados (supabase_fila.sql).")
        return 1
    finally:
        try:
            banco.apagar("painel_teste", {"pc": f"eq.{pc}"})
            banco.apagar("aba_linhas", {"aba": f"eq.{ABA_TESTE}"})
        except Exception:   # a limpeza não pode esconder o resultado
            pass
    print("3) Limpeza: linhas de teste apagadas.")
    print("Para comparar: a leitura da Central no Google levava em média ~5 s (pior ~60 s) nos registros deste PC.")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
