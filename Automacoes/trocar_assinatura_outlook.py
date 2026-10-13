"""Troca a IMAGEM das assinaturas do Outlook deste PC pela assinatura nova do agente (usuário, 13/10/2026).

Mantém o texto de cada assinatura (mensagem da NF, link da pesquisa, "Atenciosamente,"): só a imagem muda.
Vale para as assinaturas escolhidas como padrão (e-mail novo e resposta) nas caixas notafiscal@ deste Outlook.
Antes de mexer, guarda uma cópia de cada pasta "<assinatura>_arquivos" em "<assinatura>_arquivos.antes-AAAAMMDD".
A imagem nova vem de app_ui/assinaturas/<agente>.png (a mesma do Painel).

Uso:  python Automacoes\\trocar_assinatura_outlook.py joao          (ou clara, cristian, bernardo)
      python Automacoes\\trocar_assinatura_outlook.py joao --ver    (só mostra o que faria)
O Outlook lê as assinaturas ao abrir: a nova aparece depois de fechar e abrir o Outlook.
"""
import datetime
import os
import re
import shutil
import struct
import sys
import winreg
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
PASTA_ASS = Path(os.environ["APPDATA"]) / "Microsoft" / "Signatures"
CHAVE_OUTLOOK = r"Software\Microsoft\Office\16.0\Outlook"
CONTAS = "9375CFF0413111d3B88A00104B2A6676"
LARGURA_PT = 390.0   # largura da imagem na assinatura (pontos); a altura segue a proporção da imagem nova


def _texto(valor):
    if isinstance(valor, bytes):
        return valor.decode("utf-16-le", errors="ignore").rstrip("\x00")
    return str(valor or "")


def assinaturas_em_uso():
    """{nome da assinatura: [contas]} das caixas notafiscal@ do perfil padrão do Outlook."""
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, CHAVE_OUTLOOK) as k:
        perfil = winreg.QueryValueEx(k, "DefaultProfile")[0]
    saida = {}
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"{CHAVE_OUTLOOK}\Profiles\{perfil}\{CONTAS}") as base:
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(base, i)
            except OSError:
                break
            i += 1
            with winreg.OpenKey(base, sub) as c:
                valores = {}
                for nome in ("Account Name", "New Signature", "Reply-Forward Signature"):
                    try:
                        valores[nome] = _texto(winreg.QueryValueEx(c, nome)[0])
                    except OSError:
                        valores[nome] = ""
            conta = valores["Account Name"].lower()
            if "notafiscal@" not in conta:
                continue
            for nome in {valores["New Signature"], valores["Reply-Forward Signature"]} - {""}:
                saida.setdefault(nome, []).append(conta)
    return saida


def tamanho_png(caminho):
    with open(caminho, "rb") as f:
        cab = f.read(24)
    return struct.unpack(">II", cab[16:24])


def trocar(agente, so_ver=False):
    nova = RAIZ / "app_ui" / "assinaturas" / f"{agente}.png"
    if not nova.exists():
        raise SystemExit(f"Não achei {nova}")
    w, h = tamanho_png(nova)
    altura_pt = round(LARGURA_PT * h / w, 2)
    largura_px, altura_px = round(LARGURA_PT * 4 / 3), round(altura_pt * 4 / 3)
    marca = datetime.date.today().strftime("%Y%m%d")
    em_uso = assinaturas_em_uso()
    if not em_uso:
        print("Nenhuma assinatura padrão nas caixas notafiscal@ deste Outlook.")
        return 0
    trocadas = 0
    for nome, contas in sorted(em_uso.items()):
        htm = PASTA_ASS / f"{nome}.htm"
        pasta = PASTA_ASS / f"{nome}_arquivos"
        if not pasta.exists():
            pasta = PASTA_ASS / f"{nome}_files"
        imagens = sorted(pasta.glob("image*.png")) + sorted(pasta.glob("image*.jpg")) if pasta.exists() else []
        if not htm.exists() or not imagens:
            print(f"  pulei: {nome} (sem .htm ou sem imagem)")
            continue
        print(f"  {nome}  ({', '.join(contas)})  -> {len(imagens)} imagem(ns)")
        if so_ver:
            continue
        copia = pasta.with_name(pasta.name + f".antes-{marca}")
        if not copia.exists():
            shutil.copytree(pasta, copia)
            shutil.copy2(htm, copia / htm.name)
        for img in imagens:
            if img.suffix.lower() == ".png":
                shutil.copyfile(nova, img)
            else:
                shutil.copyfile(nova, img.with_suffix(".png"))
        texto = htm.read_text(encoding="cp1252", errors="surrogateescape")
        texto = re.sub(r"(v:shape[^>]*style=')width:[\d.]+pt;\s*height:[\d.]+pt",
                       rf"\g<1>width:{LARGURA_PT}pt;height:{altura_pt}pt", texto)
        texto = re.sub(r'(<img[^>]*?)width=\d+([^>]*?)height=\d+', rf"\g<1>width={largura_px}\g<2>height={altura_px}", texto)
        texto = texto.replace(".jpg\"", ".png\"")
        htm.write_text(texto, encoding="cp1252", errors="surrogateescape")
        trocadas += 1
    print(f"{'Faria' if so_ver else 'Trocadas'}: {trocadas if not so_ver else len(em_uso)} assinatura(s). "
          "Feche e abra o Outlook para ver a nova.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    sys.exit(trocar(sys.argv[1].lower(), "--ver" in sys.argv))
