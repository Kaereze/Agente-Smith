"""Copia a Planilha Central do Google para o servidor central e confere linha a linha (API central, etapa 2, 24/11/2026).

    python ferramentas/copiar_central_para_servidor.py --servidor http://IP-DO-SERVIDOR:8770      copia
    python ferramentas/copiar_central_para_servidor.py --servidor http://... --conferir           só compara
    python ferramentas/copiar_central_para_servidor.py --arquivo central.sqlite                   copia para um arquivo (teste)
    python ferramentas/copiar_central_para_servidor.py --so-listar                                só mostra o que seria copiado

O token do servidor vem da variável CENTRAL_TOKEN (nunca como argumento: ficaria no histórico do terminal).

Segurança e cuidado:
- No Google ela só LÊ (chave de somente leitura): nunca grava nem apaga nada na planilha.
- Copia as abas internas do Painel (envios, correio, PCs, comandos...). As abas "(respostas)" dos formulários dos hotéis e o
  Cadastro_Hoteis (que a equipe edita na planilha) ficam no Google (regra em central/backend_roteado.py).
- Não escreve conteúdo de linha em lugar nenhum da tela nem do log: só nomes de aba e contagens (são dados de hóspedes).
- Se o servidor já tem abas, ela se recusa a copiar (para não passar por cima de dado que os PCs já gravaram lá); `--refazer` libera.
- A Central é escrita pelos PCs o tempo todo: abas "vivas" (Envios_NF, PCs_Painel...) podem diferir por linhas gravadas entre a
  cópia e a conferência. Rode a conferência logo após a cópia e, se só elas divergirem, repita.
"""
import argparse
import os
import sys

from central.backend_roteado import fica_no_google

LOTE_DE_ABAS = 8   # abas lidas por chamada ao Google: não segura tudo na memória nem passa dos 6 pedidos por minuto


def e_aba_interna(nome):
    """O que vai para o servidor: tudo menos o que fica no Google (formulários dos hotéis e Cadastro_Hoteis; a regra é do roteador)."""
    return not fica_no_google(nome)


def abas_a_copiar(origem, planilha_id, so=None):
    """Abas internas da Central, na ordem em que estão na planilha. `so` = nomes pedidos (os que não existem vão em `faltam`).
    -> (abas, faltam)"""
    existentes = [n for n in origem.listar_abas(planilha_id) if e_aba_interna(n)]
    if not so:
        return existentes, []
    return [n for n in existentes if n in so], [n for n in so if n not in existentes]


def _lotes(lista, tamanho):
    for i in range(0, len(lista), tamanho):
        yield lista[i:i + tamanho]


def _normal(linhas):
    """As linhas como o armazém as guarda: textos, sem célula vazia no fim, sem linha vazia no fim."""
    saida = []
    for linha in linhas:
        linha = [("" if c is None else str(c)) for c in linha]
        while linha and linha[-1] == "":
            linha.pop()
        saida.append(linha)
    while saida and saida[-1] == []:
        saida.pop()
    return saida


def copiar(origem, destino, planilha_id, abas):
    """Lê `abas` da origem (em lotes) e grava cada uma inteira no destino. -> {"copiadas": {aba: n_linhas}, "erros": {aba: motivo}}"""
    copiadas, erros = {}, {}
    for lote in _lotes(list(abas), LOTE_DE_ABAS):
        lidas, erros_da_leitura = origem.ler_abas(planilha_id, lote)
        erros.update({n: str(e)[:200] for n, e in erros_da_leitura.items()})
        for nome in lote:
            if nome not in lidas:
                erros.setdefault(nome, "não veio na leitura")
                continue
            linhas = _normal(lidas[nome])
            try:
                destino.substituir_aba(planilha_id, nome, linhas)
            except Exception as e:   # uma aba que falha não impede as outras: aparece no relatório
                erros[nome] = f"{type(e).__name__}: {str(e)[:150]}"
                continue
            copiadas[nome] = len(linhas)
    return {"copiadas": copiadas, "erros": erros}


def conferir(origem, destino, planilha_id, abas):
    """Compara origem e destino aba por aba, sem mostrar conteúdo.
    -> {"iguais": [aba], "diferentes": {aba: {"origem": n, "destino": n, "primeira_linha_diferente": n}}, "erros": {aba: motivo}}"""
    iguais, diferentes, erros = [], {}, {}
    for lote in _lotes(list(abas), LOTE_DE_ABAS):
        da_origem, erros_o = origem.ler_abas(planilha_id, lote)
        do_destino, erros_d = destino.ler_abas(planilha_id, lote)
        for nome in lote:
            if nome in erros_o or nome in erros_d or nome not in da_origem or nome not in do_destino:
                motivo = erros_o.get(nome) or erros_d.get(nome) or "não veio na leitura"
                lado = "origem" if nome in erros_o else "destino"
                erros[nome] = f"{lado}: {str(motivo)[:150]}"
                continue
            a, b = _normal(da_origem[nome]), _normal(do_destino[nome])
            if a == b:
                iguais.append(nome)
                continue
            primeira = next((i + 1 for i, (x, y) in enumerate(zip(a, b)) if x != y), min(len(a), len(b)) + 1)
            diferentes[nome] = {"origem": len(a), "destino": len(b), "primeira_linha_diferente": primeira}
    return {"iguais": iguais, "diferentes": diferentes, "erros": erros}


def relatorio_da_copia(r):
    linhas = [f"Copiadas {len(r['copiadas'])} aba(s), {sum(r['copiadas'].values())} linha(s) no total."]
    linhas += [f"  ✗ {n}: {m}" for n, m in sorted(r["erros"].items())]
    return "\n".join(linhas)


def relatorio_da_conferencia(r):
    linhas = [f"Conferência: {len(r['iguais'])} aba(s) iguais, {len(r['diferentes'])} diferentes, {len(r['erros'])} com erro."]
    linhas += [f"  ≠ {n}: origem {d['origem']} linha(s), servidor {d['destino']}; 1ª diferença na linha {d['primeira_linha_diferente']}"
               for n, d in sorted(r["diferentes"].items())]
    linhas += [f"  ✗ {n}: {m}" for n, m in sorted(r["erros"].items())]
    return "\n".join(linhas)


def copiar_e_conferir(origem, destino, planilha_id, abas, refazer=False, escrever=print):
    """A cópia inteira: recusa se o destino já tem abas (a menos que `refazer`), copia e confere. -> código de saída (0 = tudo igual)"""
    if destino.listar_abas(planilha_id) and not refazer:
        escrever("O servidor já tem abas. Para não passar por cima do que os PCs já gravaram lá, nada foi copiado. "
                 "Use --refazer só se tiver certeza.")
        return 2
    resultado = copiar(origem, destino, planilha_id, abas)
    escrever(relatorio_da_copia(resultado))
    r = conferir(origem, destino, planilha_id, abas)
    escrever(relatorio_da_conferencia(r))
    return 0 if not resultado["erros"] and not r["diferentes"] and not r["erros"] else 1


def _destino(args):
    if args.arquivo:
        from servidor_central.armazem import Armazem
        return Armazem(args.arquivo)
    token = os.environ.get("CENTRAL_TOKEN", "")
    if not token:
        sys.exit("Defina a variável CENTRAL_TOKEN com o token do servidor (não use argumento: ele ficaria no histórico).")
    from central.backend_api import BackendAPI
    return BackendAPI(args.servidor, token, tempo=120)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Copia a Planilha Central do Google para o servidor central e confere.")
    onde = ap.add_mutually_exclusive_group()
    onde.add_argument("--servidor", help="endereço do servidor central, ex.: http://10.0.0.5:8770")
    onde.add_argument("--arquivo", help="grava num arquivo SQLite local (teste, sem servidor)")
    ap.add_argument("--conferir", action="store_true", help="só compara, não copia")
    ap.add_argument("--so-listar", action="store_true", help="só mostra quais abas seriam copiadas")
    ap.add_argument("--refazer", action="store_true", help="copia mesmo que o servidor já tenha abas")
    ap.add_argument("--abas", help="só estas abas, separadas por vírgula")
    args = ap.parse_args(argv)
    if not args.so_listar and not (args.servidor or args.arquivo):
        ap.error("diga para onde: --servidor ou --arquivo (ou use --so-listar)")

    from config import carregar_config, caminho_chave_google
    from central.sheets import BackendGoogle
    cfg = carregar_config()
    planilha = cfg["planilha_central_id"]
    origem = BackendGoogle(caminho_chave_google(cfg), somente_leitura=True)   # chave que só lê: o Google nunca é alterado
    pedidas = [a.strip() for a in args.abas.split(",")] if args.abas else None
    abas, faltam = abas_a_copiar(origem, planilha, pedidas)
    for nome in faltam:
        print(f"  ? aba não encontrada (ou é de formulário): {nome}")
    print(f"{len(abas)} aba(s) interna(s) da Central.")

    if args.so_listar:
        lidas = {}
        for lote in _lotes(abas, LOTE_DE_ABAS):
            lidas.update(origem.ler_abas(planilha, lote)[0])
        for nome in abas:
            print(f"  {nome}: {len(_normal(lidas.get(nome, [])))} linha(s)")
        return 0

    destino = _destino(args)
    if args.conferir:
        r = conferir(origem, destino, planilha, abas)
        print(relatorio_da_conferencia(r))
        return 0 if not r["diferentes"] and not r["erros"] else 1

    return copiar_e_conferir(origem, destino, planilha, abas, refazer=args.refazer)


if __name__ == "__main__":
    sys.exit(main())
