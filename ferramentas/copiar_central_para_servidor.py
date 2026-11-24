"""Copia a Planilha Central do Google para o servidor central e confere (API central, etapa 2).

    python ferramentas/copiar_central_para_servidor.py --so-listar
    python ferramentas/copiar_central_para_servidor.py --servidor http://IP:8770

Detalhes e cuidados: src/central/migrar_para_servidor.py. O token vem da variável CENTRAL_TOKEN.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "src"))
from central.migrar_para_servidor import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
