"""Diagnóstico do espelho (só LÊ o Outlook, não marca lido, não move nada).

Uso (na pasta do projeto): .venv\\Scripts\\python.exe Automacoes\\diagnostico_espelho.py
Para cada conta do Outlook deste PC mostra a Caixa de Entrada: total, não lidos, e quantos o Painel mostra
(estado/espelho_emails.json) e por que os outros ficaram de fora (solicitação do robô, não é e-mail, respondido).
Criado em 14/10/2026: Outlook da Clara com 192 e Painel com menos.
"""
import collections
import json
import pathlib
import sys

RAIZ = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))

import espelho_emails as ee   # noqa: E402
import outlook_vivo           # noqa: E402


def main():
    try:
        estado = json.load(open(ee.CAMINHO_ESTADO, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        estado = {}
    no_espelho = set(estado.get("itens", {}))
    pedidos = {str(p.get("id", "")) for p in estado.get("pedidos_caixa", []) if isinstance(p, dict)}
    ns = outlook_vivo.aplicativo("diagnóstico do espelho").GetNamespace("MAPI")
    total = collections.Counter()
    print(f"{'conta':45} {'total':>6} {'n/lido':>6} {'Painel':>6} {'robô':>5} {'ñ-email':>7} {'fora':>5}")
    for conta in ns.Accounts:
        smtp = str(getattr(conta, "SmtpAddress", "") or "").lower()
        try:
            itens = conta.DeliveryStore.GetDefaultFolder(6).Items
        except Exception as e:
            print(f"{smtp:45} não abriu: {e}")
            continue
        c = collections.Counter()
        for item in itens:
            c["total"] += 1
            try:
                if getattr(item, "UnRead", False):
                    c["nao_lido"] += 1
                if getattr(item, "Class", 43) != 43:
                    c["nao_email"] += 1
                    continue
                i = ee.id_do_email(item.EntryID)
                if i in no_espelho:
                    c["painel"] += 1
                elif "Código de envio: NF-" in str(item.Body or "") or i in pedidos:
                    c["robo"] += 1
                else:
                    c["fora"] += 1
            except Exception:
                c["ilegivel"] += 1
        total.update(c)
        marca = "" if smtp.startswith("notafiscal@") else "  (não é caixa de hotel: o Painel não lê)"
        print(f"{smtp:45} {c['total']:6} {c['nao_lido']:6} {c['painel']:6} {c['robo']:5} {c['nao_email']:7} {c['fora']:5}{marca}")
    print(f"{'TOTAL':45} {total['total']:6} {total['nao_lido']:6} {total['painel']:6} {total['robo']:5} "
          f"{total['nao_email']:7} {total['fora']:5}")
    print("robô = solicitação do formulário (fica em Notas fiscais) · ñ-email = aviso/recibo/reunião · "
          "fora = o Painel considera respondido")


if __name__ == "__main__":
    main()
