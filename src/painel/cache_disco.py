"""Leitura segura do cache em disco (painel_cache.pkl).

Fase 1, 05/11/2026: lê só estes tipos. Um arquivo trocado por outro com código dentro não roda nada: é recusado
(o Painel então lê tudo de novo do Google, como sempre fez sem cache)."""
import io
import pickle

TIPOS_DO_CACHE = {("datetime", "datetime"), ("datetime", "date"), ("datetime", "timezone"), ("datetime", "timedelta"),
                  ("central.hoteis", "CadastroHoteis"), ("notas.modelos", "Hotel"), ("notas.modelos", "Solicitacao"),
                  ("collections", "OrderedDict"), ("collections", "defaultdict"), ("builtins", "set"), ("builtins", "frozenset")}


class _LeitorDoCache(pickle.Unpickler):
    def find_class(self, modulo, nome):
        if (modulo, nome) not in TIPOS_DO_CACHE:
            raise pickle.UnpicklingError(f"tipo fora da lista no cache: {modulo}.{nome}")
        return super().find_class(modulo, nome)


def ler_cache_seguro(dados):
    return _LeitorDoCache(io.BytesIO(dados)).load()
