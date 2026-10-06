"""Classifica as solicitações de um agente: o que falta para emitir, duplicadas e NF já emitida.

Só LEITURA: não grava na Central, não envia e-mail, não marca nada. O que ele faz é juntar num
retrato único por solicitação o que já existe espalhado — a fila do Painel (app_dados), a
conferência de NF do conferente (confirmar_nfs, que varre os Itens Enviados e as pastas do
Dropbox dos 4 PCs) e o tratamento dos campos (tratamento) — para o agente ver onde agir
ANTES de emitir.

    python src\\classificador.py                      agente deste PC, 45 dias
    python src\\classificador.py --agente Bernardo
    python src\\classificador.py --dias 90 --hotel BARRAVENTO
    python src\\classificador.py --sem-nf             pula Outlook/Dropbox (rápido)
    python src\\classificador.py --csv                grava em estado\\relatorios\\
"""
import argparse
import csv
import datetime
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_utf8 import garantir_utf8

garantir_utf8()

import app_dados as dados
from config import PASTA_ESTADO, caminho_chave_google, carregar_config
from log_util import configurar_logging
from sheets import BackendGoogle, ler_hoteis
from tratamento import normalizar

logger = configurar_logging("classificador")

DIARIA, CONSUMO, ESTACIONAMENTO = "diária", "consumo", "estacionamento"
COL_SERVICOS = "Informações necessárias na Nota Fiscal"
COL_DOCUMENTO = "Documento Tomador"
COL_NOME = "Nome Tomador"
COL_VALOR = "Valor da Nota Fiscal"
COL_DESCRICAO = "Descrição específica"
COL_CHECKIN = "Check-in da Hospedagem"
COL_CHECKOUT = "Check-out da Hospedagem"
COL_DIVIDIDA = "Nota Dividida"
COL_DIVIDIDA_QTD = "Dividida em quantas vezes"

# Acima disso o campo é erro de digitação ("119", "22"), não nota em 119 partes. A solicitação
# nunca fecharia como concluída porque situacao() exige uma NF por parte.
MAX_PARTES_PLAUSIVEL = 6

PEDIDO_SEPARADA = re.compile(r"\bsepara|\bdividi|\bem\s+dois\b|\bduas\s+not", re.IGNORECASE)


def _campo(sol, nome):
    alvo = normalizar(nome)
    for cab, valor in sol["campos"]:
        if normalizar(cab) == alvo:
            return str(valor).strip()
    return ""


def servicos(sol):
    """-> {'diária', 'consumo', ...} pelo campo de multi-escolha do formulário."""
    texto = normalizar(_campo(sol, COL_SERVICOS))
    achados = set()
    if "diaria" in texto:
        achados.add(DIARIA)
    if "consumo" in texto:
        achados.add(CONSUMO)
    if "estacionamento" in texto:
        achados.add(ESTACIONAMENTO)
    return achados


def _digitos(texto):
    return re.sub(r"\D", "", str(texto or ""))


def _digito_cpf(base):
    def calcular(parcial, peso_inicial):
        soma = sum(int(d) * p for d, p in zip(parcial, range(peso_inicial, 1, -1)))
        resto = (soma * 10) % 11
        return 0 if resto == 10 else resto
    d1 = calcular(base[:9], 10)
    d2 = calcular(base[:9] + str(d1), 11)
    return f"{d1}{d2}"


def _digito_cnpj(base):
    def calcular(parcial):
        pesos = [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2][-len(parcial):]
        resto = sum(int(d) * p for d, p in zip(parcial, pesos)) % 11
        return 0 if resto < 2 else 11 - resto
    d1 = calcular(base[:12])
    d2 = calcular(base[:12] + str(d1))
    return f"{d1}{d2}"


def documento(sol):
    """-> (tipo, digitos, valido). tipo: 'CPF' | 'CNPJ' | '' quando não dá para dizer."""
    d = _digitos(_campo(sol, COL_DOCUMENTO))
    if len(d) == 11:
        return "CPF", d, d[9:] == _digito_cpf(d) and len(set(d)) > 1
    if len(d) == 14:
        return "CNPJ", d, d[12:] == _digito_cnpj(d) and len(set(d)) > 1
    return "", d, False


def _valor_numerico(texto):
    """'R$ 1.234,56' -> 1234.56. None quando não é número."""
    t = re.sub(r"[^\d,.\-]", "", str(texto or ""))
    if not t:
        return None
    if "," in t:
        t = t.replace(".", "").replace(",", ".")
    try:
        return float(t)
    except ValueError:
        return None


def bloqueios(sol):
    """O que falta para o agente conseguir emitir. Lista vazia = dados completos."""
    faltas = []
    tipo, d, valido = documento(sol)
    if not d:
        faltas.append("sem CPF/CNPJ")
    elif not tipo:
        faltas.append(f"CPF/CNPJ com {len(d)} dígito(s)")
    elif not valido:
        faltas.append(f"{tipo} inválido")
    if not _campo(sol, COL_NOME) and not sol["nome"].strip():
        faltas.append("sem nome do tomador")
    # 'Valor da Nota Fiscal' é condicional no formulário: só aparece quando Nota Dividida = Sim.
    # Em pedido normal o valor vem do sistema do hotel, então vazio ali não é pendência.
    if normalizar(_campo(sol, COL_DIVIDIDA)) == "sim":
        valor = _campo(sol, COL_VALOR)
        if not valor:
            faltas.append("dividida sem dizer como dividir o valor")
        elif _valor_numerico(valor) is None:
            faltas.append("valor da divisão ilegível")
    if not sol["email"] and not sol["emails"]:
        faltas.append("sem e-mail")
    if not servicos(sol):
        faltas.append("sem tipo de serviço")
    return faltas


def _partes_declaradas(sol):
    """-> (partes, aviso). Trata o lixo digitado em 'Dividida em quantas vezes'."""
    bruto = _digitos(_campo(sol, COL_DIVIDIDA_QTD))
    if not bruto:
        return sol["partes"], ""
    pedido = int(bruto)
    if pedido > MAX_PARTES_PLAUSIVEL:
        return sol["partes"], f"'dividida em {pedido}' é implausível — nunca fecha como concluída"
    return sol["partes"], ""


def _periodo(sol):
    return f"{_campo(sol, COL_CHECKIN)}|{_campo(sol, COL_CHECKOUT)}"


def _tomador(sol):
    """Identidade do tomador para agrupar: documento quando há, senão o e-mail."""
    _, d, _ = documento(sol)
    return d or sol["email"] or normalizar(sol["nome"])


def agrupar(itens):
    """Marca duplicadas e complementares entre solicitações do mesmo tomador no mesmo hotel.

    Mesmos serviços + mesmo período = duplicada de verdade. Serviços diferentes (uma diária,
    outra consumo) = complementares: o hóspede quer a nota separada, não é duplicata.
    """
    grupos = {}
    for it in itens:
        grupos.setdefault((it["hotel"], _tomador(it["sol"])), []).append(it)
    for (_, tomador), grupo in grupos.items():
        if len(grupo) < 2 or not tomador:
            continue
        for it in grupo:
            irmas = [o for o in grupo if o is not it]
            it["irmas"] = len(irmas)
            mesmo_servico = [o for o in irmas
                             if o["servicos"] == it["servicos"] and _periodo(o["sol"]) == _periodo(it["sol"])]
            complementares = [o for o in irmas if o["servicos"] and o["servicos"] != it["servicos"]]
            if mesmo_servico:
                sem_periodo = _periodo(it["sol"]).strip("|") == ""
                it["marcas"].append(
                    f"possível DUPLICADA ({len(mesmo_servico) + 1}x mesmo serviço, sem check-in/out para comparar)"
                    if sem_periodo else
                    f"DUPLICADA ({len(mesmo_servico) + 1}x mesmo serviço e período)")
            if complementares:
                it["marcas"].append("nota separada (serviços diferentes no mesmo hóspede)")
    return itens


def classificar(backend, cfg, agente, dias=45, hotel=None, namespace=None, usar_nf=True):
    hoje = datetime.date.today()
    desde = (hoje - datetime.timedelta(days=dias)).isoformat()

    hoteis, _ = ler_hoteis(backend, dict(cfg, somente_hoteis=[]))
    meus = [h for h in hoteis if normalizar(h.agente) == normalizar(agente)]
    if hotel:
        meus = [h for h in meus if normalizar(hotel) in normalizar(h.nome)]
    if not meus:
        raise SystemExit(f"Nenhum hotel do agente '{agente}'" + (f" com '{hotel}' no nome." if hotel else "."))
    logger.info(f"🏨 {len(meus)} hotel(is) de {agente} · desde {desde}")

    lidas, _ = backend.ler_abas(cfg["planilha_central_id"], [h.aba for h in meus] + [dados.ABA_TRATAMENTO])
    solicitacoes = []
    for h in meus:
        for s in dados.ler_solicitacoes(h.aba, h.nome, lidas.get(h.aba, []), cfg):
            s["email_hotel"] = h.email_hotel
            solicitacoes.append(s)
    estados = dados.dobrar_eventos(lidas.get(dados.ABA_TRATAMENTO, [[]]))
    fila = dados.montar_fila(solicitacoes, estados, desde=desde)
    logger.info(f"📋 {len(fila)} solicitação(ões) no período")

    emitidas = {}
    if usar_nf:
        import confirmar_nfs
        logger.info("🔎 conferindo NF já emitida (Itens Enviados + Dropbox dos 4 PCs)...")
        for sol, numero, prova in confirmar_nfs.confirmar(backend, cfg, namespace, gravar=False):
            emitidas.setdefault(sol["chave"], []).append((numero, prova))

    itens = []
    for f in fila:
        marcas = []
        partes, aviso = _partes_declaradas(f)
        if aviso:
            marcas.append(aviso)
        achadas = emitidas.get(f["chave"], [])
        if achadas and not f["nfs"]:
            for numero, prova in achadas:
                marcas.append(f"NF {numero} JÁ EMITIDA, não marcada na Central — {prova}")
        descricao = _campo(f, COL_DESCRICAO)
        if descricao and PEDIDO_SEPARADA.search(descricao):
            marcas.append("hóspede pediu nota separada na descrição")
        itens.append({
            "sol": f, "hotel": f["hotel"], "servicos": servicos(f), "bloqueios": bloqueios(f),
            "marcas": marcas, "irmas": 0, "partes": partes,
            "nfs": list(dict.fromkeys(f["nfs"] + [n for n, _ in achadas])),
            "descricao": descricao,
        })
    return agrupar(itens)


def tags_pendentes(namespace, cfg, dias=45):
    """O que mudaria nas categorias (tags) dos e-mails de solicitação deste Outlook.

    SÓ categorias: de propósito não chama conferente.atualizar_consolidados(), que reescreve
    Subject e HTMLBody junto. Nada de pasta, leitura, movimentação ou envio.
    -> ([(item, de, para, porque)], ignorados_fora_deste_outlook)
    """
    import json

    from conferente import CAMINHO_REGISTRO, _conta_por_smtp, _e_email_de_solicitacao, _procurar_consolidado
    from controle_nf import CATEGORIA_DIVIDIDA, categorias_atualizadas, pede_nota_dividida, resumo_email

    try:
        registro = json.load(open(CAMINHO_REGISTRO, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        registro = {}
    por_ref = registro.get("solicitacoes", {})

    mudancas, fora = [], 0
    vistos = set()
    for codigo, dados_email in (registro.get("emails") or {}).items():
        conta = _conta_por_smtp(namespace, dados_email.get("destinatario", ""))
        if conta is None:
            fora += 1
            continue
        item = None
        if dados_email.get("entry_id_recebido"):
            try:
                item = namespace.GetItemFromID(dados_email["entry_id_recebido"], conta.DeliveryStore.StoreID)
                if codigo not in (item.Body or ""):
                    item = None
            except Exception:
                item = None
        if item is None:
            item = _procurar_consolidado(conta.DeliveryStore.GetDefaultFolder(6), codigo)   # olFolderInbox
        if item is None:
            continue
        solicitacoes = [por_ref[r] for r in dados_email.get("refs", []) if r in por_ref]
        if not solicitacoes:
            continue
        feitas, total, tem_tratativa = resumo_email(solicitacoes)
        atual = item.Categories or ""
        novo = categorias_atualizadas(atual, feitas, total, tem_tratativa)
        vistos.add(item.EntryID)
        if novo != atual:
            mudancas.append((item, atual, novo, f"{feitas}/{total} NF concluída(s)"))

    # Nota dividida: mesma regra do conferente (controle_nf.pede_nota_dividida), categoria permanente.
    remetente_antigo = str(cfg.get("robo_antigo", {}).get("remetente", "")).lower()
    desde = datetime.datetime.now() - datetime.timedelta(days=dias)
    for conta in namespace.Accounts:
        try:
            itens = conta.DeliveryStore.GetDefaultFolder(6).Items
            itens.Sort("[ReceivedTime]", True)
        except Exception:
            continue
        for item in itens:
            try:
                if item.ReceivedTime.replace(tzinfo=None) < desde:
                    break
            except Exception:
                continue
            try:
                if not _e_email_de_solicitacao(item, remetente_antigo):
                    continue
                atuais = [c.strip() for c in re.split(r"[;,]", item.Categories or "") if c.strip()]
                if CATEGORIA_DIVIDIDA in atuais or not pede_nota_dividida(item.Body or ""):
                    continue
                atual = item.Categories or ""
                mudancas.append((item, atual, ", ".join(atuais + [CATEGORIA_DIVIDIDA]), "pede nota dividida"))
            except Exception:
                continue
    return mudancas, fora


def aplicar_tags(namespace, mudancas):
    """Grava só o campo Categories. Save() do item, sem tocar em mais nada."""
    from conferente import garantir_categorias

    garantir_categorias(namespace)
    gravadas, falhas = 0, []
    for item, _, novo, _ in mudancas:
        try:
            item.Categories = novo
            item.Save()
            gravadas += 1
        except Exception as e:
            falhas.append(str(e))
    return gravadas, falhas


def _prioridade(it):
    """Pronta para emitir e sem ruído = no fim da lista. O que precisa de olho humano, no topo."""
    tem_dup = any("DUPLICADA" in m for m in it["marcas"])
    tem_emitida = any("JÁ EMITIDA" in m for m in it["marcas"])
    return (not tem_emitida, not tem_dup, not it["bloqueios"], it["sol"]["data"])


def relatorio(itens, agente, dias):
    pendentes = [it for it in itens if it["sol"]["situacao"] != dados.CONCLUIDA]
    linhas = [f"\n{'=' * 100}",
              f" CLASSIFICAÇÃO — {agente} · últimos {dias} dias · {len(itens)} solicitação(ões), "
              f"{len(pendentes)} em aberto",
              f" Só leitura: nada foi gravado na Central e nenhum e-mail foi enviado.",
              f"{'=' * 100}"]

    emitidas = [it for it in pendentes if any("JÁ EMITIDA" in m for m in it["marcas"])]
    duplicadas = [it for it in pendentes if any("DUPLICADA" in m for m in it["marcas"])]
    separadas = [it for it in pendentes if any("separada" in m for m in it["marcas"])]
    travadas = [it for it in pendentes if it["bloqueios"]]
    prontas = [it for it in pendentes if not it["bloqueios"] and not it["marcas"]]

    linhas += ["", " RESUMO",
               f"   NF já emitida mas não marcada na Central .... {len(emitidas):4}   <- resolver primeiro",
               f"   Duplicadas (mesmo serviço e período) ........ {len(duplicadas):4}",
               f"   Nota separada / dividida .................... {len(separadas):4}",
               f"   Travadas por dado faltando .................. {len(travadas):4}",
               f"   Prontas para emitir ......................... {len(prontas):4}"]

    faltas = {}
    for it in travadas:
        for b in it["bloqueios"]:
            faltas[b] = faltas.get(b, 0) + 1
    if faltas:
        linhas += ["", " O QUE MAIS FALTA"]
        linhas += [f"   {n:4}  {b}" for b, n in sorted(faltas.items(), key=lambda x: -x[1])]

    por_hotel = {}
    for it in pendentes:
        por_hotel.setdefault(it["hotel"], []).append(it)
    linhas += ["", " POR HOTEL (em aberto)"]
    for h, grupo in sorted(por_hotel.items(), key=lambda x: -len(x[1])):
        trava = sum(1 for i in grupo if i["bloqueios"])
        linhas.append(f"   {len(grupo):4} em aberto · {trava:3} travadas · {h}")

    linhas += ["", f"{'=' * 100}", " DETALHE (o que precisa de olho humano primeiro)", f"{'=' * 100}"]
    for it in sorted(pendentes, key=_prioridade)[:60]:
        s = it["sol"]
        tipo, d, _ = documento(s)
        linhas.append(f"\n  {s['data']} · {s['hotel']} · linha {s['linha']} · {s['situacao']}")
        linhas.append(f"     {s['nome'][:45]:45} {tipo} {d or '-'}")
        dividida = f"dividida em {it['partes']} ({_campo(s, COL_VALOR) or 'sem valor'})" \
            if normalizar(_campo(s, COL_DIVIDIDA)) == "sim" else "inteira"
        linhas.append(f"     serviços: {', '.join(sorted(it['servicos'])) or '-'}"
                      f" · {dividida}"
                      f" · NF: {', '.join(it['nfs']) or '-'}")
        for b in it["bloqueios"]:
            linhas.append(f"     ⚠️  falta: {b}")
        for m in it["marcas"]:
            linhas.append(f"     ❗ {m}")
        if it["descricao"]:
            linhas.append(f"     nota do hóspede: {it['descricao'][:160]}")
    if len(pendentes) > 60:
        linhas.append(f"\n  ... e mais {len(pendentes) - 60} em aberto (use --csv para a lista inteira)")
    return "\n".join(linhas)


def gravar_csv(itens, agente):
    pasta = PASTA_ESTADO / "relatorios"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"classificacao_{normalizar(agente).replace(' ', '_')}_{datetime.date.today():%Y-%m-%d}.csv"
    with open(caminho, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["Data", "Hotel", "Aba", "Linha", "Situação", "Nome", "Tipo doc", "Documento",
                    "Serviços", "Valor", "Partes", "NFs", "Falta", "Marcas", "Descrição"])
        for it in sorted(itens, key=_prioridade):
            s = it["sol"]
            tipo, d, _ = documento(s)
            w.writerow([s["data"], s["hotel"], s["aba"], s["linha"], s["situacao"], s["nome"], tipo, d,
                        ", ".join(sorted(it["servicos"])), _campo(s, COL_VALOR), it["partes"],
                        ", ".join(it["nfs"]), " | ".join(it["bloqueios"]), " | ".join(it["marcas"]),
                        it["descricao"]])
    return caminho


def main():
    p = argparse.ArgumentParser(description="Classifica as solicitações de um agente (só leitura).")
    p.add_argument("--agente", default=None, help="padrão: o agente deste PC")
    p.add_argument("--dias", type=int, default=45)
    p.add_argument("--hotel", default=None, help="filtra por parte do nome do hotel")
    p.add_argument("--sem-nf", action="store_true", help="pula a conferência de NF (bem mais rápido)")
    p.add_argument("--csv", action="store_true", help="grava a lista inteira em estado\\relatorios\\")
    p.add_argument("--tags", action="store_true",
                   help="organiza as categorias dos e-mails de solicitação (prévia; grava só com --aplicar)")
    p.add_argument("--aplicar", action="store_true", help="com --tags: grava as categorias no Outlook")
    args = p.parse_args()

    cfg = carregar_config()

    if args.tags:
        import win32com.client
        ns = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        mudancas, fora = tags_pendentes(ns, cfg, args.dias)
        print(f"\n{'APLICANDO' if args.aplicar else 'PRÉVIA — nada gravado'}: "
              f"{len(mudancas)} e-mail(s) com categoria a mudar"
              + (f" · {fora} consolidado(s) de caixa que não está neste Outlook" if fora else ""))
        porque = {}
        for _, _, _, motivo in mudancas:
            porque[motivo] = porque.get(motivo, 0) + 1
        for motivo, n in sorted(porque.items(), key=lambda x: -x[1]):
            print(f"   {n:5}  {motivo}")
        for item, atual, novo, motivo in mudancas[:25]:
            print(f"\n   {(item.Subject or '')[:78]}")
            print(f"      de:   {atual or '(sem categoria)'}")
            print(f"      para: {novo}")
        if len(mudancas) > 25:
            print(f"\n   ... e mais {len(mudancas) - 25}")
        if args.aplicar:
            gravadas, falhas = aplicar_tags(ns, mudancas)
            print(f"\n✅ {gravadas} e-mail(s) recategorizado(s)." +
                  (f" {len(falhas)} falha(s): {falhas[:3]}" if falhas else ""))
        else:
            print("\nPara gravar: acrescente --aplicar")
        return
    agente = args.agente or cfg.get("agente") or cfg.get("agente_principal")
    backend = BackendGoogle(caminho_chave_google(cfg), somente_leitura=True)

    namespace = None
    if not args.sem_nf:
        try:
            import win32com.client
            namespace = win32com.client.Dispatch("Outlook.Application").GetNamespace("MAPI")
        except Exception as e:
            logger.warning(f"⚠️ Outlook indisponível ({e}); confiro só o Dropbox")

    itens = classificar(backend, cfg, agente, args.dias, args.hotel, namespace, usar_nf=not args.sem_nf)
    print(relatorio(itens, agente, args.dias))
    if args.csv:
        print(f"\nCSV: {gravar_csv(itens, agente)}")


if __name__ == "__main__":
    main()
