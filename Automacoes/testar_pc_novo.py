"""Teste final de um PC novo (29/10/2026): chave, Planilha Central e conversa com os outros PCs. Só LÊ; nada é gravado.
Desde 05/11/2026 também confere a segurança: cifra da rede, relógio, firewall, BitLocker, ajustes e usuários do Windows.
REGRA: toda segurança nova entra aqui E em Automacoes/coracao.ps1 na mesma entrega (pedido do João).

    .venv\\Scripts\\python.exe Automacoes\\testar_pc_novo.py

Mostra OK / aviso / falha por etapa. Nunca mostra a chave nem o segredo da rede.
"""
import email.utils
import json
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from emails import envio_nf  # noqa: E402
from rede import rede_local  # noqa: E402
from rede import rede_pcs  # noqa: E402
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


LIMITE_RELOGIO_S = 10   # a rede entre os PCs só aceita pedido com até 30 s de diferença; acima de 10 já é risco


def deslocamento_do_relogio(data_http, agora=None):
    """Segundos que o relógio deste PC está adiantado (+) ou atrasado (-) em relação ao cabeçalho Date de um site. None se ilegível."""
    try:
        return (agora or time.time()) - email.utils.parsedate_to_datetime(data_http).timestamp()
    except (TypeError, ValueError):
        return None


def conferir_relogio():
    try:
        with urllib.request.urlopen(urllib.request.Request("https://www.google.com", method="HEAD"), timeout=6) as r:
            desvio = deslocamento_do_relogio(r.headers.get("Date"))
    except Exception:   # noqa: BLE001
        aviso("Não consegui conferir o relógio (sem internet?). Ele precisa estar certo: a rede entre os PCs recusa pedido com mais de 30 s de diferença.")
        return
    if desvio is None:
        aviso("Não consegui ler a hora do servidor para conferir o relógio.")
    elif abs(desvio) > LIMITE_RELOGIO_S:
        falha(f"Relógio {'adiantado' if desvio > 0 else 'atrasado'} {abs(desvio):.0f} s. Ligue 'Definir horário automaticamente' no Windows "
              "(senão a rede entre os PCs recusa os pedidos deste).")
    else:
        ok(f"Relógio certo (diferença de {abs(desvio):.0f} s)")


def _powershell(comando):
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", comando], capture_output=True, text=True, timeout=30)
        return r.stdout.strip()
    except Exception:   # noqa: BLE001
        return ""


def conferir_cifra(segredo):
    if not rede_local.CIFRA_DISPONIVEL:
        falha("Falta a biblioteca de cifra (cryptography). Rode INSTALAR_OU_ATUALIZAR.bat de novo.")
        return False
    try:
        c = rede_local.cifrar(segredo, b"teste", b"a")
        assert rede_local.decifrar(segredo, c, b"a") == b"teste"
    except Exception:   # noqa: BLE001
        falha("A cifra da rede não funcionou neste PC.")
        return False
    ok("Cifra da rede entre os PCs funcionando" + ("  (a rede já exige cifra)" if rede_local.EXIGIR_CIFRA else ""))
    return True


def conferir_seguranca_do_windows():
    if _powershell('if (Get-NetFirewallRule -DisplayName "Painel Fiscal - rede entre os PCs" -ErrorAction SilentlyContinue) {"sim"}') == "sim":
        ok("Firewall liberado para a rede entre os PCs (porta 8766, só rede local)")
    else:
        aviso("Firewall ainda não liberado: rode Automacoes/liberar_rede.ps1 (pede senha de administrador uma vez).")
    protecao = _powershell("(Get-BitLockerVolume -MountPoint $env:SystemDrive -ErrorAction SilentlyContinue).ProtectionStatus")
    if protecao == "On":
        ok("BitLocker ligado (disco cifrado)")
    elif protecao == "Off":
        aviso("BitLocker DESLIGADO: peça ao TI para ligar (a chave do Google e os dados ficam no disco).")
    else:
        aviso("Não consegui ver o BitLocker (precisa de administrador). Confirme com o TI que o disco está cifrado.")
    usuarios = _powershell("(Get-LocalUser | Where-Object Enabled).Count")
    if usuarios.isdigit() and int(usuarios) > 1:
        aviso(f"{usuarios} usuários ativos no Windows deste PC: quem entra com outro usuário não vê a chave, mas anote para a Fase 2 (token do Painel).")
    elif usuarios.isdigit():
        ok("Um só usuário ativo no Windows")


def conferir_ajustes():
    import ajustes
    erros = ajustes.erros()
    if erros:
        aviso(f"ajustes.json com {len(erros)} valor(es) inválido(s); o Painel usa o de fábrica nesses.")
    else:
        ok("Ajustes em ordem (ou sem ajustes.json: vale o de fábrica)")


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
    conferir_cifra(rede_local.segredo_da_chave(caminho))
    conferir_relogio()
    conferir_seguranca_do_windows()
    conferir_ajustes()

    from central.sheets import BackendGoogle
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
