"""Console em UTF-8 (acentos e emojis no Windows)."""
import sys


def garantir_utf8():
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            # fluxo sem suporte a reconfigure (ex.: capturado por um test runner) — segue sem forçar, não é um…
            pass
