"""Compara a fila de envio da planilha (Envios_NF) com a cópia no banco (Supabase): serve para decidir se o modo "sombra" está certo.

    python ferramentas\\comparar_fila_banco.py

Lê a planilha (só leitura) e o banco, e diz quantas linhas faltam no banco e quantas sobram. Só vale a partir do momento em que o
banco começou a receber (linhas mais velhas da planilha são ignoradas). Mostra só QUANDO, ID, EVENTO e PC: nunca o conteúdo do pedido
(e-mail e assunto do hóspede). Pode rodar de qualquer PC que tenha a chave do Google e a do Supabase (também o de casa).
"""
import collections
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from central import supabase  # noqa: E402
from central.banco_abas import TABELA  # noqa: E402
from central.sheets import BackendGoogle  # noqa: E402
from config import caminho_chave_google, carregar_config  # noqa: E402
from emails import envio_nf  # noqa: E402


def linha_comparavel(valores):
    v = [str(x) for x in valores] + [""] * (6 - len(valores))
    return tuple(v[:6])


def comparar(da_planilha, do_banco):
    """-> (faltam no banco, sobram no banco, quantas linhas da planilha entram na conta). Ignora o que é mais velho que a 1ª linha do banco."""
    banco = collections.Counter(linha_comparavel(l) for l in do_banco)
    if not banco:
        return [], [], 0
    desde = min(k[0] for k in banco)
    planilha = collections.Counter(linha_comparavel(l) for l in da_planilha if str(l[0]) >= desde)
    faltam = list((planilha - banco).elements())
    sobram = list((banco - planilha).elements())
    return faltam, sobram, sum(planilha.values())


def principal():
    for saida in (sys.stdout, sys.stderr):
        if hasattr(saida, "reconfigure"):
            saida.reconfigure(encoding="utf-8", errors="replace")
    cfg = carregar_config()
    try:
        banco = supabase.Banco.do_arquivo(supabase.caminho_da_chave(cfg))
        do_banco = [l["valores"] for l in banco.ler_tudo(TABELA, {"aba": f"eq.{envio_nf.ABA_FILA}"}, colunas="valores", ordem="id.asc")]
    except supabase.ErroBanco as e:
        print(f"❌ {e}")
        return 1
    dados, erros = BackendGoogle(caminho_chave_google(cfg), somente_leitura=True).ler_abas(cfg["planilha_central_id"], [envio_nf.ABA_FILA])
    if erros or envio_nf.ABA_FILA not in dados:
        print(f"❌ Não consegui ler a planilha: {erros}")
        return 1
    da_planilha = dados[envio_nf.ABA_FILA][1:]
    faltam, sobram, contadas = comparar(da_planilha, do_banco)
    print(f"Planilha: {len(da_planilha)} linhas ({contadas} desde que o banco começou). Banco: {len(do_banco)} linhas.")
    if not do_banco:
        print("O banco ainda está vazio: ligue o modo sombra (config.local.json > banco > abas) em algum PC do trabalho e espere haver envios.")
        return 0
    print(f"Faltam no banco: {len(faltam)}   ·   Sobram no banco: {len(sobram)}")
    for rotulo, lista in (("Falta no banco", faltam), ("Sobra no banco", sobram)):
        for k in lista[:5]:
            print(f"  {rotulo}: {k[0]} · {k[1]} · {k[2]} · {k[3]}")
    if not faltam and not sobram:
        print("✅ Igual: o banco acompanha a planilha.")
    return 0 if not faltam else 2


if __name__ == "__main__":
    sys.exit(principal())
