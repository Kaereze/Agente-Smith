"""Confere, caixa por caixa, a Caixa de Entrada do Outlook DESTE PC contra o que o Painel espelhou (29/10/2026). Só LÊ.

    .venv\\Scripts\\python.exe Automacoes\\conferir_contagem_outlook.py

O número azul do Outlook ao lado de "Caixa de Entrada" é o de NÃO LIDOS; o total é tudo o que está na pasta. O Painel guarda
os dois. Aqui aparecem lado a lado, com a soma, e a linha fica marcada quando diferem. Só mostra nomes de caixas e números.
O Outlook precisa estar aberto com janela.
"""
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

PREFIXO_CAIXA = "notafiscal@"


def comparar(outlook, painel):
    """outlook, painel: {caixa: (não lidos, total)}. -> [(caixa, (nl, tot) do Outlook, (nl, tot) do Painel, bate)] ordenado."""
    saida = []
    for caixa in sorted(set(outlook) | set(painel)):
        o, p = outlook.get(caixa), painel.get(caixa, (0, 0))
        saida.append((caixa, o, p, o == p if o is not None else False))
    return saida


def somar(linhas, lado):
    """lado 1 = Outlook, 2 = Painel. -> (soma de não lidos, soma do total)."""
    valores = [l[lado] for l in linhas if l[lado] is not None]
    return sum(v[0] for v in valores), sum(v[1] for v in valores)


def contar_outlook():
    import outlook_vivo
    import pythoncom
    if not outlook_vivo.pode_usar():
        raise SystemExit("O Outlook não está aberto com janela. Abra o Outlook e rode de novo.")
    pythoncom.CoInitialize()
    ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
    saida = {}
    for conta in ns.Accounts:
        caixa = str(conta.SmtpAddress or "").strip().lower()
        if not caixa.startswith(PREFIXO_CAIXA):
            continue
        try:
            pasta = conta.DeliveryStore.GetDefaultFolder(6)
            saida[caixa] = (int(pasta.UnReadItemCount), int(pasta.Items.Count))
        except Exception as e:   # noqa: BLE001
            print(f"   !!  Não abri a Caixa de Entrada de {caixa}: {type(e).__name__}")
    return saida


def contar_painel():
    import envio_nf  # noqa: F401  (carrega a configuração do projeto)
    import espelho_emails as ee
    from config import caminho_chave_google, carregar_config
    from sheets import BackendGoogle
    cfg = carregar_config()
    aba = ee.nome_aba(socket.gethostname())
    dados, _ = BackendGoogle(caminho_chave_google(cfg), somente_leitura=True).ler_abas(cfg["planilha_central_id"], [aba])
    linhas = dados.get(aba) or []
    if not linhas:
        raise SystemExit(f"O Painel ainda não publicou o espelho deste PC (aba {aba}).")
    i = {n: k for k, n in enumerate(linhas[0])}
    saida = {}
    for l in linhas[1:]:
        l = list(l) + [""] * len(i)
        if not l[0] or l[i["Pasta"]] != "entrada":
            continue
        nl, tot = saida.get(str(l[i["Caixa"]]).strip().lower(), (0, 0))
        saida[str(l[i["Caixa"]]).strip().lower()] = (nl + (str(l[i["Lido Outlook"]]).upper() == "FALSE"), tot + 1)
    return saida


def main():
    print("========== CAIXA DE ENTRADA: OUTLOOK x PAINEL ==========")
    linhas = comparar(contar_outlook(), contar_painel())
    print(f"{'caixa':32} {'Outlook nao lidos/total':>24} {'Painel nao lidos/total':>24}")
    for caixa, o, p, bate in linhas:
        o_txt = f"{o[0]}/{o[1]}" if o else "-"
        print(f"{caixa.split('@')[1].replace('redeandrade', '').replace('.com.br', ''):32} {o_txt:>24} {p[0]}/{p[1]:<22} {'OK' if bate else '<-- DIFERENTE'}")
    so, st = somar(linhas, 1)
    sp, pt = somar(linhas, 2)
    print(f"\nSOMA  Outlook: {so} nao lidos, {st} no total   |   Painel: {sp} nao lidos, {pt} no total")
    diferentes = [l for l in linhas if not l[3]]
    print("TUDO IGUAL." if not diferentes else f"{len(diferentes)} caixa(s) diferente(s): o Painel ainda nao alcancou o Outlook, ou o contrario.")
    return 0 if not diferentes else 2


if __name__ == "__main__":
    sys.exit(main())
