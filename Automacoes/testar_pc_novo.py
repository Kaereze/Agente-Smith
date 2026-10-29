"""Teste final de um PC novo (29/10/2026): chave, Planilha Central e conversa com os outros PCs. Só LÊ; nada é gravado.

    .venv\\Scripts\\python.exe Automacoes\\testar_pc_novo.py

Mostra OK / aviso / falha por etapa. Nunca mostra a chave nem o segredo da rede.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import envio_nf  # noqa: E402
import rede_local  # noqa: E402
import rede_pcs  # noqa: E402
from config import caminho_chave_google, carregar_config, sem_outlook  # noqa: E402

CAMPOS_CHAVE = ("type", "client_email", "private_key", "private_key_id", "project_id")


def ok(texto):
    print(f"   OK  {texto}")


def aviso(texto):
    print(f"   --  {texto}")


def falha(texto):
    print(f"   !!  {texto}")


def conferir_chave(caminho):
    try:
        dados = json.load(open(caminho, encoding="utf-8"))
    except (OSError, ValueError):
        falha(f"Não achei ou não consegui ler a chave do Google em {caminho}")
        return False
    faltam = [c for c in CAMPOS_CHAVE if not dados.get(c)]
    if dados.get("type") != "service_account" or faltam:
        falha(f"A chave não parece completa (faltam: {', '.join(faltam) or 'tipo errado'}). Baixe de novo no Google Cloud.")
        return False
    ok(f"Chave do Google válida (conta {dados['client_email']})")
    return True


def conferir_segredo(caminho):
    pasta = Path(caminho).parent / rede_local.ARQUIVO_SEGREDO_REDE
    if pasta.exists():
        if rede_local._segredo_do_arquivo(caminho):
            ok("segredo-rede.txt válido (o PC fala com os outros 4 PCs)")
        else:
            falha("segredo-rede.txt existe, mas está errado (precisa ter 64 caracteres de 0-9 e a-f). Gere de novo no PC do João.")
            return False
    else:
        aviso("Sem segredo-rede.txt: se esta chave for diferente da dos outros PCs, a pesquisa e o texto dos e-mails não chegam. "
              "O resto funciona pela Planilha Central.")
    return True


def main():
    print("==================== TESTE DO PC NOVO ====================")
    try:
        cfg = carregar_config()
    except Exception as e:   # noqa: BLE001
        falha(f"Configuração com problema: {e}")
        return 1
    ok(f"Papel deste PC: {cfg.get('papel')}" + ("  (sem Outlook, só o Painel)" if sem_outlook(cfg) else ""))
    caminho = caminho_chave_google(cfg)
    if not (conferir_chave(caminho) and conferir_segredo(caminho)):
        return 1

    from sheets import BackendGoogle
    try:
        dados, erros = BackendGoogle(caminho, somente_leitura=True).ler_abas(cfg["planilha_central_id"], [envio_nf.ABA_PCS])
    except Exception as e:   # noqa: BLE001
        falha(f"Não consegui ler a Planilha Central ({str(e)[:140]}). A planilha precisa estar compartilhada com a conta de serviço.")
        return 1
    if envio_nf.ABA_PCS not in dados:
        falha(f"Não consegui ler a aba {envio_nf.ABA_PCS}: {erros}")
        return 1
    ok("Planilha Central lida")

    pcs = [p for p in rede_pcs.ler_pcs(dados[envio_nf.ABA_PCS]) if p["online"]]
    ok(f"{len(pcs)} PC(s) ligado(s) agora na rede da equipe")
    segredo = rede_local.segredo_da_chave(caminho)
    for p in pcs:
        nome = f"{p['agente'] or '?'} ({p['pc']})"
        if not p["rede"]:
            aviso(f"{nome}: sem endereço de rede publicado (Painel recém-aberto?)")
            continue
        try:
            r = rede_local.perguntar(segredo, p["rede"], "ping", {}, tempo=5)
            ok(f"{nome}: respondeu (versão {r.get('versao', '?')})")
        except Exception as e:   # noqa: BLE001
            aviso(f"{nome}: não respondeu ({type(e).__name__}). Firewall da porta 8766, PC em outra rede, ou segredo diferente.")
    print("\nPronto. Os avisos (--) não impedem o Painel de abrir; as falhas (!!) precisam ser resolvidas.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
