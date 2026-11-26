"""Mede a "poluição" do visual do Painel (19/11/2026, repaginação): quantos tamanhos de texto, cantos, espaçamentos, cores,
camadas e regras forçadas o CSS tem. Só lê arquivos (app_ui/**/*.css). Rode: python ferramentas/medir_design.py [--json]

O teste testes/test_medidas_design.py usa estas contas como "catraca": o número só pode DESCER. Quando uma etapa da
repaginação reduzir um valor, abaixe o teto lá. Metas ficam em METAS (a tabela da Auditoria de usabilidade)."""
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
UI = RAIZ / "app_ui"
METAS = {"tamanhos_de_texto": 7, "raios_de_canto": 4, "espacamentos_gap": 7, "cores_hex": 30, "importantes": 50, "camadas_z": 6}


def _css():
    # só o CSS do Painel: fontes.css (fontes embutidas) e o tokens.css (a própria régua) ficam de fora da conta; o tema_claro.css também
    # (26/11/2026): é gerado por ferramentas/gerar_tema_claro.py a partir do CSS escrito à mão, que já é medido aqui
    arquivos = [f for f in UI.rglob("*.css") if f.name not in ("fontes.css", "tokens.css", "tema_claro.css")]
    return arquivos, "\n".join(f.read_text(encoding="utf-8", errors="ignore") for f in arquivos)


def medir():
    arquivos, css = _css()
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)   # comentário não conta
    return {
        "tamanhos_de_texto": len(set(re.findall(r"font-size:\s*([\d.]+)px", css))),
        "raios_de_canto": len(set(re.findall(r"border-radius:\s*([\d.]+)px", css))),
        "espacamentos_gap": len(set(re.findall(r"\bgap:\s*([\d.]+)px", css))),
        "cores_hex": len({c.lower() for c in re.findall(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b", css)}),
        "importantes": css.count("!important"),
        "camadas_z": len(set(re.findall(r"z-index:\s*(-?\d+)", css))),
        "arquivos_css": len(arquivos),
        "linhas_css": sum(len(f.read_text(encoding="utf-8", errors="ignore").splitlines()) for f in arquivos),
    }


if __name__ == "__main__":
    m = medir()
    if "--json" in sys.argv:
        print(json.dumps(m, ensure_ascii=False, indent=1))
    else:
        for k, v in m.items():
            meta = f"  (meta {METAS[k]})" if k in METAS else ""
            print(f"{k:22} {v:>6}{meta}")
