"""Cadastro único de hotéis: casa os nomes que cada fonte usa com o nome do Cadastro_Hoteis.

"São Francisco" (aba da Central), "SÃO FRANCISCO" (Mail Analytics) e um apelido do config
viram o mesmo hotel.
"""
from tratamento import normalizar


class CadastroHoteis:
    def __init__(self, linhas_cadastro, apelidos=None, colunas=None):
        col = colunas or {}
        i_nome, i_email, i_agente = (ord(str(col.get(k, d)).upper()) - 65
                                     for k, d in (("hotel", "A"), ("email_hotel", "B"), ("agente", "C")))
        self.hoteis = {}
        for l in linhas_cadastro:
            cel = lambda i: str(l[i]).strip() if len(l) > i else ""
            nome = cel(i_nome)
            if not nome or normalizar(cel(i_agente)) in ("agente", "operador") or normalizar(nome) == "nome":
                continue
            self.hoteis.setdefault(normalizar(nome), {"nome": nome, "email": cel(i_email).lower(), "agente": cel(i_agente)})
        self._sem_espaco = {k.replace(" ", ""): k for k in self.hoteis}
        self.apelidos = {normalizar(k): normalizar(v) for k, v in (apelidos or {}).items() if not str(k).startswith("_")}

    def canonico(self, nome):
        """Nome do Cadastro_Hoteis | None se nenhuma forma do nome casar."""
        n = normalizar(nome)
        n = self.apelidos.get(n, n)
        if n in self.hoteis:
            return self.hoteis[n]["nome"]
        chave = self._sem_espaco.get(n.replace(" ", ""))
        return self.hoteis[chave]["nome"] if chave else None

    def dados(self, nome_canonico):
        return self.hoteis.get(normalizar(nome_canonico), {})

    def nomes(self):
        return sorted(h["nome"] for h in self.hoteis.values())
