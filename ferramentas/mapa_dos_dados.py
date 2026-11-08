"""Gera o mapa dos dados do Painel (Segundo Cérebro, "6 Documentos/Mapa dos dados.md") a partir do catálogo src/sistema/armazem.py.

    python ferramentas/mapa_dos_dados.py

O catálogo é a fonte: o documento nunca fica velho. Um teste (testes/test_armazem.py) falha se o documento deixar de listar algum arquivo.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from sistema import armazem  # noqa: E402

DESTINO = RAIZ / "Segundo Cérebro (Agente Smith)" / "6 Documentos" / "Mapa dos dados.md"


def texto():
    linhas = ["---", "tipo: documento", 'pasta: "6 Documentos"', 'pai: "[[00 Início]]"', "prioridade: P0", "tags: [cerebro/documentos, lgpd, dados]", "---",
              "# Mapa dos dados", "",
              "> Gerado de `src/sistema/armazem.py` por `ferramentas/mapa_dos_dados.py`. **Não edite à mão**: mude o catálogo e rode a ferramenta.",
              "> Tudo fica em `estado/` de cada PC, fora do GitHub. \"Pessoal\" = tem nome, CPF/CNPJ, e-mail ou texto de hóspede.", "",
              "| Arquivo | Para que serve | Pessoal | Quanto tempo fica | Quem escreve |", "|---|---|---|---|---|"]
    for d in [*armazem.DADOS.values(), *armazem.BACKUPS]:
        linhas.append(f"| `{d.arquivo}` | {d.para_que} | {'**sim**' if d.pessoal else 'não'} | {d.guarda} | `{d.quem}` |")
    linhas += ["", "## Onde mexer", "- Arquivo novo em `estado/`: declare em `src/sistema/armazem.py` e peça o caminho com `armazem.caminho(...)`. O teste barra caminho montado à mão.",
               "- Pedido de titular (ver ou apagar dados de uma pessoa): `ferramentas/pedido_titular.py` e [[Dados de hóspedes (LGPD)]].",
               "- Quem abriu o quê: `estado/acessos/AAAA-MM.jsonl` (`src/privacidade/acessos.py`), 12 meses, sem nome nem CPF.", ""]
    return "\n".join(linhas)


if __name__ == "__main__":
    DESTINO.write_text(texto(), encoding="utf-8")
    print("escrito:", DESTINO.name, "·", len(armazem.DADOS) + len(armazem.BACKUPS), "dados")
