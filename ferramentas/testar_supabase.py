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
from central import supabase  # noqa: E402

LINHAS = 20     # linhas fictícias por gravação
RODADAS = 5     # quantas vezes mede cada coisa


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
    except supabase.ErroBanco as e:
        print(f"❌ {e}")
        if e.codigo in (404, 400):
            print("   Dica: a tabela ainda não existe. Rode ferramentas\\supabase_tabelas.sql no SQL Editor do Supabase.")
        if e.codigo in (401, 403):
            print("   Dica: a chave não foi aceita. Confira se é a chave PUBLICÁVEL (anon) do projeto, sem espaço sobrando.")
        return 1
    finally:
        try:
            banco.apagar("painel_teste", {"pc": f"eq.{pc}"})
        except Exception:   # a limpeza não pode esconder o resultado
            pass
    print("3) Limpeza: linhas de teste apagadas.")
    print("Para comparar: a leitura da Central no Google levava em média ~5 s (pior ~60 s) nos registros deste PC.")
    return 0


if __name__ == "__main__":
    sys.exit(principal(sys.argv))
