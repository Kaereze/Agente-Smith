"""Estado do correio: o espelho do Outlook dos 4 PCs, busca, ações sobre e-mails e conferência de NF."""

import datetime
import json
import os
import re
import socket
import threading
import time

import avisos_windows
import busca_outlook
import correio
import app_dados as dados
import envio_nf
import espelho_emails
import hospedes
import ligacoes
import nf_achadas
import nf_cobre
import outlook_vivo
import rede_local
import saude
from arquivos import salvar_json
from log_util import configurar_logging

logger = configurar_logging("app")
NOTAS_EMAILS_SEGUNDOS = 120   # e-mail -> NF do Dropbox: recalculado a cada 2 min, fora da resposta da tela
ENVIADOS_RAPIDO_SEGUNDOS = 1.0   # consulta rápida nos Itens Enviados do Outlook quando o índice ainda não tem o envio do hóspede


def _kw_ligacao(corpo):
    """Botão Ligação ligado na tela de escrever: o pedido de envio leva ligacao=True (categoria LIGAÇÃO no Outlook).
    Desligado: nenhum argumento a mais."""
    return {"ligacao": True} if (corpo or {}).get("ligacao") else {}


class CorreioMixin:
    """Métodos de Estado (app_servidor.py) movidos para cá em 29/10/2026; mesma lógica, mesmo `self`."""

    # ---------- aba E-mails ----------
    def _solicitacao_do_email(self, de):
        """Pedido do formulário mais recente desse mesmo e-mail (se houver). Índice por e-mail, refeito só quando
        a lista de pedidos muda: varrer 3,6 mil pedidos para cada e-mail deixava a tela lenta."""
        lista = self.solicitacoes
        if getattr(self, "_indice_emails", (None,))[0] is not lista:
            indice = {}
            for s in lista:
                for x in {str(e).lower() for e in [s["email"]] + s.get("emails", []) if e}:
                    atual = indice.get(x)
                    if atual is None or (s["data"], s["carimbo"]) > (atual["data"], atual["carimbo"]):
                        indice[x] = s
            self._indice_emails = (lista, indice)
        return self._indice_emails[1].get((de or "").lower())

    def _alertas_documento(self):
        """{e-mail do hóspede: alerta} das NFs que saíram pra outro CPF/CNPJ (pedidos dos últimos 45 dias)."""
        corte = (datetime.date.today() - datetime.timedelta(days=45)).isoformat()
        saida = {}
        with self.lock:
            sols, estados = list(self.solicitacoes), self.estados
        for s in sols:
            est = estados.get(s["chave"])
            if not est or not est["obs"] or (s["data"] and s["data"] < corte):
                continue
            urgentes, _ = dados.alertas_documento(est)
            if urgentes:
                for x in {str(e).lower() for e in [s["email"]] + s.get("emails", []) if e}:
                    saida[x] = f"NF {urgentes[0]['nf']}: {urgentes[0]['texto']}"
        return saida

    def _notas_do_pedido(self, sol, nfs):
        """Textos dos PDFs (índice das pastas do Dropbox) das NF já ligadas ao pedido: [(nº, nome do arquivo, texto)].
        O CPF/CNPJ da nota tem que ser o do pedido: a numeração das notas se repete entre hotéis."""
        indice = getattr(self, "nf_indice", None)
        if indice is None:
            return []
        docs = set(nf_achadas._alvo(sol)["documentos"])
        return [(e.get("nf"), e.get("nome", ""), e.get("texto", "")) for _c, e in indice.itens()
                if e.get("nf") in nfs and not e.get("sem_texto") and (not docs or e.get("doc") in docs)]

    def _pedidos_com_nf_por_email(self):
        """{e-mail do hóspede: (pedido, [nº das NF])} dos pedidos dos últimos 45 dias que já têm NF."""
        corte = (datetime.date.today() - datetime.timedelta(days=45)).isoformat()
        with self.lock:
            sols, estados = list(self.solicitacoes), self.estados
        mapa = {}
        for s in sols:
            nfs = [str(n) for n in (estados.get(s["chave"]) or {}).get("nfs", [])]
            if not nfs or (s.get("data") or "") < corte:
                continue
            for x in {str(e).lower() for e in [s["email"]] + s.get("emails", []) if e}:
                if x not in mapa or (s["data"], s["carimbo"]) > (mapa[x][0]["data"], mapa[x][0]["carimbo"]):
                    mapa[x] = (s, nfs)
        return mapa

    def _alertas_nova_nota(self):
        """{e-mail do hóspede: "Pede nova nota (NF 2186): ..."} — o e-mail novo pede algo (datas, serviço, CPF/CNPJ,
        descrição) que a NF já enviada não cobre (27/10/2026). Só marca urgência; nada é movido nem apagado. Aqui lê só a prévia
        do e-mail (a tela confere o texto inteiro ao abrir)."""
        mapa = self._pedidos_com_nf_por_email()
        if not mapa or getattr(self, "nf_indice", None) is None:
            return {}
        saida, vistos = {}, {}
        with self.lock:
            emails = list(self.emails)
        for r in emails:
            de = (r.get("de") or "").lower()
            if r["pasta"] != espelho_emails.ENTRADA or {"formulario", "aviso"} & set(r.get("classes", [])) or de not in mapa:
                continue
            if r["quando"] <= vistos.get(r["de"], ""):
                continue
            sol, nfs = mapa[de]
            textos = [t for _n, _p, t in self._notas_do_pedido(sol, nfs)]
            if not textos:
                continue
            vistos[r["de"]] = r["quando"]
            motivo = nf_cobre.motivo_curto(nf_cobre.analisar(r.get("previa", ""), textos), nfs)
            if motivo:
                saida[r["de"]] = motivo
            else:
                saida.pop(r["de"], None)
        return saida

    def _textos_do_hospede(self, e):
        """Texto novo + citado de TODOS os e-mails do hóspede na lista (o histórico inteiro), do mais velho ao mais novo."""
        cache = self.__dict__.setdefault("_textos_email", {})
        textos = []
        irmaos = sorted((x for x in list(self.emails) if x["pasta"] == espelho_emails.ENTRADA
                         and (x.get("de") or "").lower() == (e.get("de") or "").lower()), key=lambda x: x["quando"])
        for x in irmaos:
            if x["id"] not in cache:
                try:
                    t = self.texto_email(x["id"])
                    cache[x["id"]] = (t.get("texto", ""), t.get("citado", ""))
                except Exception:
                    cache[x["id"]] = (x.get("previa", ""), "")
            textos += list(cache[x["id"]])
        return textos

    def nf_cobre(self, id_email):
        """Caixa "NF" do e-mail aberto (27/10/2026): (1) a NF já enviada x o que o hóspede pede agora; (2) o HISTÓRICO INTEIRO do
        hóspede (todas as mensagens, com a parte citada) x as notas prontas nas pastas, achadas pelo CPF/CNPJ."""
        e = self._email(id_email)
        saida = {"nfs": []}
        achado = self._pedidos_com_nf_por_email().get((e.get("de") or "").lower())
        nfs = []
        if achado:
            sol, nfs = achado
            try:
                texto = self.texto_email(id_email).get("texto", "") or e.get("previa", "")
            except Exception:
                texto = e.get("previa", "")
            notas = self._notas_do_pedido(sol, nfs)
            analise = nf_cobre.analisar(texto, [t for _n, _p, t in notas])
            enviados = list(self.enviados_correio)
            sem = nf_achadas.sem_envio_confirmado(nfs, enviados, envio_nf.destinatarios(sol)) if enviados else []
            saida = {**analise, "nfs": [{"nf": n, "pdf": next((p for nn, p, _t in notas if nn == n), "")} for n in nfs],
                     "avisos_envio": sem, "sugere_concluir": analise["cobre"] is True and not sem,
                     "motivo_urgencia": nf_cobre.motivo_curto(analise, nfs)}
        indice = getattr(self, "nf_indice", None)
        if indice is not None:
            try:
                textos = self._textos_do_hospede(e)
                docs = set()
                for t in textos:
                    docs |= nf_achadas.documentos_do_texto(t)
                sol = achado[0] if achado else self._solicitacao_do_email(e["de"])
                if sol:
                    docs |= set(nf_achadas._alvo(sol)["documentos"])
                prontas = nf_achadas.notas_por_documento(indice, docs, raiz=envio_nf.raiz_dropbox(self.cfg), ja_ligadas=nfs, com_texto=True) if docs else []
                itens = nf_cobre.pedido_do_historico(textos)
                if prontas and itens:
                    saida["prontas"] = [{"nf": n["nf"], "pdf": n["nome"]} for n in prontas]
                    saida["historico"] = nf_cobre.comparar_historico(itens, [{"nf": n["nf"], "texto": n["texto"]} for n in prontas])
            except Exception:
                logger.exception("histórico do hóspede x notas prontas")
        return saida

    def mover_email_nf(self, id_email, agente):
        """Botão direito > "Tirar da caixa de entrada" (27/10/2026): ESTE e-mail, mesmo já respondido, vai para a pasta
        "NF enviada" da caixa do hotel, no Outlook do PC dono. A Caixa de Entrada é só dos que ainda esperam resposta.
        Nada é apagado; sempre um clique da pessoa (com "Desfazer" de 10 s na tela)."""
        e = self._email(id_email)
        sol = {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"], "nome": e["nome"] or e["de"]}
        r = self.envio_nf.pedir(sol, "", e["assunto"], e["caixa"], [], agente, responder=e["id"], acao=envio_nf.MOVER_NF)
        if not r.get("ok"):
            return r
        linha = espelho_emails.evento(e["id"], "EXCLUIR", agente)   # some da entrada pra equipe toda, na hora
        self.backend.anexar_linhas(self.central, espelho_emails.ABA_EVENTOS, [linha])
        self.eventos_linhas = (self.eventos_linhas or [espelho_emails.CAB_EVENTOS]) + [linha]
        self._montar_correio()
        logger.info(f"📁 Tirar da entrada: e-mail de {e['de']} indo para \"{envio_nf.PASTA_NF_ENVIADA}\" (pedido de {agente})")
        return r

    def concluir_conversa(self, id_email, agente):
        """Botão Concluir (27/10/2026): move a conversa inteira do hóspede (os e-mails dele na entrada) para a pasta "NF enviada"
        da caixa do hotel, no Outlook do PC dono. Sempre um clique da pessoa; nada é apagado."""
        e0 = self._email(id_email)
        conversa = [x for x in self.entrada_correio if x["de"] == e0["de"]] or [e0]
        linhas, feitos, falhas = [], 0, set()
        for e in conversa:
            sol = {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"], "nome": e["nome"] or e["de"]}
            r = self.envio_nf.pedir(sol, "", e["assunto"], e["caixa"], [], agente, responder=e["id"], acao=envio_nf.MOVER_NF)
            if r.get("ok"):
                feitos += 1
                linhas.append(espelho_emails.evento(e["id"], "EXCLUIR", agente))   # some da entrada pra equipe toda, na hora
            else:
                falhas.add(str(r.get("motivo", ""))[:120])
        if linhas:
            self.backend.anexar_linhas(self.central, espelho_emails.ABA_EVENTOS, linhas)
            self.eventos_linhas = (self.eventos_linhas or [espelho_emails.CAB_EVENTOS]) + linhas
            self._montar_correio()
        logger.info(f"📁 Concluir: {feitos} e-mail(s) de {e0['de']} indo para \"{envio_nf.PASTA_NF_ENVIADA}\" (pedido de {agente})")
        return {"ok": feitos > 0, "movidos": feitos, "motivo": "; ".join(sorted(f for f in falhas if f))}

    def _montar_correio(self):
        eventos = espelho_emails.dobrar_eventos(self.eventos_linhas + self.eventos_pendentes)
        entrada, enviados, _ = correio.juntar(self.emails, eventos, datetime.datetime.now(), self._alertas_documento(),
                                              self._alertas_nova_nota())
        convs = correio.conversas([e for e in entrada if e.get("pendente", True)])   # conversa = esperando resposta
        with self.lock:
            self.eventos_correio, self.entrada_correio, self.enviados_correio, self.convs = eventos, entrada, enviados, convs

    def _lido_no_outlook(self):
        """Abriu (ou "Não lido") no Painel -> o PC dono da caixa marca igual no Outlook dele (usuário, 11/10/2026).
        Cada PC só mexe nos e-mails das próprias caixas; cada clique é levado 1 vez só (lido_aplicado.json), até
        24 h depois (PC que estava desligado leva quando ligar). Só muda a marca de lido, nada mais no e-mail."""
        if getattr(self, "demo", False) or getattr(self, "so_ver", False) or getattr(self, "_lido_rodando", False) \
                or not outlook_vivo.pode_usar():
            return
        pc = socket.gethostname()
        if not hasattr(self, "_lido_aplicado"):
            try:
                self._lido_aplicado = json.load(open(self.LIDO_APLICADO, encoding="utf-8"))
            except (FileNotFoundError, ValueError):
                self._lido_aplicado = {}
        with self.lock:
            eventos = espelho_emails.dobrar_eventos(self.eventos_linhas + self.eventos_pendentes)
            meus = [e for e in self.emails if e["pc"] == pc and e["pasta"] == espelho_emails.ENTRADA]
        corte = max(self.LIDO_OUTLOOK_DESDE,
                    (datetime.datetime.now() - datetime.timedelta(hours=24)).isoformat(timespec="seconds"))
        tarefas = []
        for e in meus:
            ev = eventos.get(e["id"]) or {}
            q = ev.get("lido_mudou_em", "")
            if q and q >= corte and self._lido_aplicado.get(e["id"]) != q:
                tarefas.append((e["id"], bool(ev.get("lido")), q))
        if not tarefas:
            return
        self._lido_rodando = True

        def rodar():
            try:
                import pythoncom
                pythoncom.CoInitialize()
                ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
                for i, lido, q in tarefas:
                    entry = espelho_emails.entry_do_email(i)
                    try:
                        if entry:
                            item = ns.GetItemFromID(entry)
                            if bool(item.UnRead) == lido:
                                item.UnRead = not lido
                                item.Save()
                                logger.info(f"📬 Outlook: marcado como {'lido' if lido else 'não lido'} (pedido pelo Painel) · "
                                            f"{str(item.Subject or '')[:60]}")
                    except Exception as erro:
                        logger.debug(f"lido no Outlook ({i}): {erro}")
                    self._lido_aplicado[i] = q
                corte_local = (datetime.datetime.now() - datetime.timedelta(hours=48)).isoformat(timespec="seconds")
                self._lido_aplicado = {k: v for k, v in self._lido_aplicado.items() if v >= corte_local}
                salvar_json(self.LIDO_APLICADO, self._lido_aplicado)
            except Exception:
                logger.exception("lido no Outlook")
            finally:
                self._lido_rodando = False

        threading.Thread(target=rodar, daemon=True).start()

    def _avisar_urgencias(self):
        """Aviso do Windows só quando um e-mail das caixas DESTE PC entra em Urgência (usuário, 08/10/2026)."""
        minhas = [c for c in self.convs if socket.gethostname() in c["pcs"]]
        novas, self.urgencias_avisadas = (correio.novas_urgencias(minhas, self.urgencias_avisadas or set())
                                          if self.urgencias_avisadas is not None else ([], {c["de"] for c in minhas if c["urgente"]}))
        cfg_av = {**avisos_windows.PADRAO, **(self.cfg.get("painel", {}).get("avisos") or {})}
        if not novas or not cfg_av["ativo"] or not (cfg_av["das"] <= datetime.datetime.now().strftime("%H:%M") < cfg_av["ate"]):
            return
        if len(novas) == 1:
            c = novas[0]
            motivo = (c["ultimo"].get("motivo_urgencia") or "urgência").lower()
            avisos_windows.mostrar("Urgência", f"{c['nome']} ({', '.join(c['hoteis'])}): {motivo}.")
        else:
            avisos_windows.mostrar("Urgência", f"{len(novas)} e-mails entraram em Urgência nas suas caixas.")

    def _pcs_por_nome(self):
        return {p["pc"]: p for p in self.pcs()}

    def lista_correio(self):
        """Caixa de Entrada, Urgência e Itens Enviados dos 4 PCs juntos (1 linha por hóspede)."""
        pcs = self._pcs_por_nome()
        with self.lock:
            convs, enviados = list(self.convs), list(self.enviados_correio)
        saida = []
        for c in convs:
            sol = self._solicitacao_do_email(c["de"])
            notas = [n for i in c["ids"] for n in self.notas_emails.get(i, [])]
            saida.append({**c, "notas": list({n.get("rel", n.get("nome")): n for n in notas}.values()),
                          "pcs_online": [pc for pc in c["pcs"] if pcs.get(pc, {}).get("online")],
                          "agentes": [pcs.get(pc, {}).get("agente", "") for pc in c["pcs"]],
                          "solicitacao": {"chave": sol["chave"], "hotel": sol["hotel"], "data": sol["data"]} if sol else None})
        espelhos = {}
        for e in self.emails:   # quando cada PC atualizou o espelho por último (PC desligado = espelho parado)
            espelhos[e["pc"]] = max(espelhos.get(e["pc"], ""), e["atualizado"])
        with self.lock:
            entrada = list(getattr(self, "entrada_correio", []))
        por_de = {c["de"]: c for c in saida}
        emails = [{**e, "pc_online": bool(pcs.get(e["pc"], {}).get("online")), "agente": pcs.get(e["pc"], {}).get("agente", ""),
                   "total_conversa": por_de.get(e["de"], {}).get("total", 1),
                   "prazo": por_de.get(e["de"], {}).get("prazo"),
                   "notas": self.notas_emails.get(e["id"], []),
                   "solicitacao": por_de.get(e["de"], {}).get("solicitacao")} for e in entrada]
        marcadas = self.ligacoes
        enviados = [{**e, "ligacao": ligacoes.chave_do_enviado(e) in marcadas} for e in enviados]
        return {"conversas": saida, "emails": emails, "enviados": enviados, "contagem": correio.contagem(convs, entrada),
                "pcs": [{"pc": p["pc"], "agente": p["agente"], "online": p["online"], "espelho": espelhos.get(p["pc"], ""),
                         "rede": bool(p.get("rede"))} for p in pcs.values()],
                "este_pc": socket.gethostname()}

    def lista_emails(self):
        """Compatibilidade (tela antiga): e-mails da entrada, 1 por linha."""
        return [{**e, "recebido": e["quando"]} for e in getattr(self, "entrada_correio", [])]

    def atualizar_notas_emails(self, forcar=False):
        """NF do Dropbox de cada e-mail espelhado (lê o Dropbox e às vezes o PDF: segundos). Roda no laço de fundo
        a cada NOTAS_EMAILS_SEGUNDOS; a lista de e-mails só consulta o resultado e responde na hora."""
        if not forcar and self.relogio() - self.notas_emails_em < NOTAS_EMAILS_SEGUNDOS:
            return
        self.notas_emails_em = self.relogio()
        mapa = {}
        for e in list(self.emails):
            if e["pasta"] != espelho_emails.ENTRADA:
                continue
            try:
                local = espelho_emails.item_local(e["id"]) if e["pc"] == socket.gethostname() else {}
                mapa[e["id"]] = envio_nf.notas_do_email({**e, "texto": local.get("texto") or e.get("previa", "")}, self.cfg)
            except Exception as erro:
                logger.debug(f"NF do Dropbox pro e-mail {e['id']}: {erro}")
        try:   # NF achadas pelo CPF/CNPJ (do pedido ou escrito no e-mail): vale também para e-mail sem formulário
            for i, itens in self._notas_por_documento().items():
                atuais = mapa.get(i, [])
                mapa[i] = atuais + [n for n in itens if n["rel"] not in {x.get("rel") for x in atuais}]
        except Exception:
            logger.exception("NF achadas por documento")
        self.notas_emails = mapa

    def _documentos_do_email(self, e, sol, buscar):
        """CPF/CNPJ do e-mail: os do pedido do formulário + os escritos no texto (guardados; o texto vem do Outlook do PC dono,
        então só se busca para e-mail candidato, no máximo `buscar` por vez)."""
        docs = set(nf_achadas._alvo(sol)["documentos"]) if sol else set()
        cache = self.__dict__.setdefault("_docs_do_email", {})
        if e["id"] not in cache and buscar[0] > 0:
            buscar[0] -= 1
            try:
                local = espelho_emails.item_local(e["id"]) if e["pc"] == socket.gethostname() else {}
                dados_texto = {"texto": local["texto"], "citado": local.get("citado", "")} if local.get("texto") else self.texto_email(e["id"])
            except Exception:
                return docs, False   # PC dono sem rede agora: tenta na próxima volta
            # o CPF/CNPJ muitas vezes só está na parte citada ("Mostrar mensagens anteriores") de uma resposta
            self.__dict__.setdefault("_textos_email", {})[e["id"]] = (dados_texto.get("texto", ""), dados_texto.get("citado", ""))
            cache[e["id"]] = (nf_achadas.documentos_do_texto(dados_texto.get("texto", "")) |
                              nf_achadas.documentos_do_texto(dados_texto.get("citado", "")) | nf_achadas.documentos_do_texto(e.get("previa", "")))
        return docs | cache.get(e["id"], set()), e["id"] in cache

    def _notas_por_documento(self):
        """{id do e-mail: [NF das pastas cujo CPF/CNPJ é o do e-mail]} — GATILHO (27/10/2026): nota nova na pasta aparece na etiqueta
        "NF pronta" do e-mail do hóspede, com ou sem formulário. Só lê; nunca envia nem move nada."""
        indice = getattr(self, "nf_indice", None)
        if indice is None:
            return {}
        agora = datetime.datetime.now()
        desde = (agora - datetime.timedelta(hours=nf_achadas.NOTA_PRONTA_HORAS)).timestamp()
        recentes = [(c, e) for c, e in indice.itens() if e.get("doc") and not e.get("sem_texto") and e.get("mtime", 0) >= desde]
        if not recentes:
            return {}
        palavras = set().union(*(nf_achadas.palavras_do_nome(e.get("nome", "")) for _c, e in recentes))
        corte = (agora - datetime.timedelta(days=15)).isoformat()
        buscar, saida, raiz = [8], {}, envio_nf.raiz_dropbox(self.cfg)
        entradas = [x for x in list(self.emails) if x["pasta"] == espelho_emails.ENTRADA]
        por_remetente = {}
        for x in entradas:
            por_remetente.setdefault((x.get("de") or "").lower(), []).append(x["id"])
        for e in sorted(entradas, key=lambda x: x["quando"], reverse=True):
            if e["quando"] < corte or {"formulario", "aviso"} & set(e.get("classes", [])):
                continue
            sol = self._solicitacao_do_email(e["de"])
            ja = [str(n) for n in ((self.estados.get(sol["chave"]) or {}).get("nfs", []) if sol else [])]
            cache = self.__dict__.get("_docs_do_email", {})
            candidato = bool(sol) or e["id"] in cache or bool(
                palavras & set(nf_achadas._palavras_texto(f"{e.get('nome', '')} {e.get('de', '')} {e.get('assunto', '')} {e.get('previa', '')}")))
            if not candidato:
                continue
            docs, _ = self._documentos_do_email(e, sol, buscar)
            for outro in por_remetente.get((e.get("de") or "").lower(), []):   # a resposta herda o documento do e-mail original
                docs = docs | self.__dict__.get("_docs_do_email", {}).get(outro, set())
            if docs:
                achadas = nf_achadas.notas_por_documento(indice, docs, agora, raiz, ja)
                if achadas:
                    saida[e["id"]] = achadas
        return saida

    def _email(self, id_email):
        e = next((x for x in self.emails if x["id"] == id_email and x["pasta"] != espelho_emails.RESPOSTA), None)
        if e is None:
            raise KeyError("e-mail não está mais na lista (pode ter sido respondido ou excluído)")
        return e

    def _caixas_de_hotel(self):
        """{caixa: hotel} de todos os hotéis do cadastro (a busca/leitura pela rede só abre essas caixas)."""
        saida = {}
        for h in self.cadastro.nomes():
            caixa = str(self.cadastro.dados(h).get("email", "")).strip().lower()
            if "@" in caixa:
                saida[caixa] = saida.get(caixa, "") + (" / " if caixa in saida else "") + h
        return saida

    # --- o que a tela pede ---
    def texto_email(self, id_email="", pc="", entry=""):
        """Texto inteiro, pedido ao vivo pro PC dono (nada fica guardado aqui). PC dono desligado: a cópia da
        aba CorreioTexto_<PC> (só existe enquanto o e-mail está sem resposta)."""
        if id_email and not pc:
            pc = self._email(id_email)["pc"]
        if pc == socket.gethostname():
            return {**self.rede_texto({"id": id_email, "entry": entry}), "origem": "este PC"}
        endereco = self._enderecos_rede().get(pc)
        if endereco and self.segredo:
            r = rede_local.perguntar_a_todos(self.segredo, {pc: endereco}, "texto", {"id": id_email, "entry": entry}, tempo=6).get(pc, {})
            self._anotar_rede({pc: r})
            if "erro" not in r:
                return {**r, "origem": "ao vivo"}
        if not id_email:
            raise KeyError(f"o PC {pc} não respondeu pela rede agora — tente de novo em instantes")
        return {**self._texto_da_planilha(pc, id_email), "origem": "cópia (PC dono sem rede)"}

    def anexo_email(self, id_email="", pc="", entry="", nome=""):
        """Anexo pedido ao vivo pro PC dono (nada fica guardado). PC dono desligado: não tem como (só ele tem o Outlook)."""
        if not nome:
            raise ValueError("nome do anexo")
        if id_email and not pc:
            pc = self._email(id_email)["pc"]
        if pc == socket.gethostname() or not pc:
            return self.rede_anexo({"id": id_email, "entry": entry, "nome": nome})
        endereco = self._enderecos_rede().get(pc)
        if not (endereco and self.segredo):
            raise KeyError("o PC dono desse e-mail está desligado ou sem rede agora: o anexo só pode ser aberto por lá")
        r = rede_local.perguntar_a_todos(self.segredo, {pc: endereco}, "anexo", {"id": id_email, "entry": entry, "nome": nome},
                                         tempo=45).get(pc, {})
        self._anotar_rede({pc: r})
        if "erro" in r:
            raise KeyError(f"o PC dono não mandou o anexo: {r['erro']}")
        return r

    def _texto_da_planilha(self, pc, id_email):
        e = self._email(id_email)
        versao, textos = self.textos_cache.get(pc, ("", {}))
        if versao != e.get("versao_texto") or id_email not in textos:
            aba = espelho_emails.nome_aba_textos(pc)
            textos = espelho_emails.ler_textos(self.backend.ler_abas(self.central, [aba])[0].get(aba, []))
            self.textos_cache[pc] = (e.get("versao_texto"), textos)
        texto, citado = textos.get(id_email, ("", ""))
        return {"texto": texto or e.get("previa", ""), "citado": citado, "pc": pc}

    def buscar_outlook(self, termo, vivo=False):
        """Pergunta aos PCs ligados (este incluído) ao mesmo tempo. Cada um responde pelo índice local (milissegundos);
        vivo=True (botão "Procurar também no Outlook"): direto no Outlook de cada um, como antes de 20/10/2026."""
        termo = busca_outlook.limpar_termo(termo)
        if len(termo) < 3:
            return {"resultados": [], "pcs": {}, "termo": termo}
        respostas = {}
        enderecos = self._enderecos_rede()
        import threading as _t
        local = {}
        fio = _t.Thread(target=lambda: local.update(r=self._buscar_local(termo, vivo)))
        fio.start()
        if enderecos and self.segredo:
            respostas = rede_local.perguntar_a_todos(self.segredo, enderecos, "buscar", {"q": termo, "vivo": vivo},
                                                     tempo=8 if vivo else 4)
            self._anotar_rede(respostas)
        fio.join(busca_outlook.TEMPO_MAXIMO + 3)
        respostas[socket.gethostname()] = local.get("r", {"erro": "o Outlook deste PC não respondeu a tempo"})
        pcs = self._pcs_por_nome()
        for p in pcs.values():
            if p["pc"] not in respostas:
                respostas[p["pc"]] = {"erro": "desligado" if not p["online"] else "sem rede agora (usa a cópia)" if p.get("rede")
                                      else "sem endereço de rede (atualize o Painel dele)"}
        resultados = [r for resp in respostas.values() for r in resp.get("resultados", [])]
        resultados.sort(key=lambda r: r["quando"], reverse=True)
        situacao = {pc: ({"ok": True, "achados": len(r.get("resultados", [])), "completo": r.get("completo", True),
                          "fonte": r.get("fonte", "outlook")}
                         if "erro" not in r else {"ok": False, "erro": r["erro"]}) for pc, r in respostas.items()}
        if self._falta_envio_do_hospede(termo, vivo, resultados, situacao):
            achados = self._enviados_rapido(termo, enderecos)
            ids = {r["id"] for r in resultados}
            resultados += [r for r in achados if r["id"] not in ids]
            resultados.sort(key=lambda r: r["quando"], reverse=True)
        return {"resultados": resultados, "pcs": situacao, "termo": termo, "vivo": bool(vivo),
                "agentes": {p["pc"]: p["agente"] for p in pcs.values()}}

    @staticmethod
    def _falta_envio_do_hospede(termo, vivo, resultados, situacao):
        """Pesquisa por endereço de hóspede (22/10/2026) e nenhum e-mail ENVIADO apareceu, com algum PC respondendo pelo
        índice ainda incompleto (ou direto do Outlook sem pasta de enviados): vale a consulta rápida nos Itens Enviados."""
        if vivo or "@" not in termo or any(r.get("pasta") == "enviado" for r in resultados):
            return False
        return any(s.get("ok") and not (s.get("fonte") == "indice" and s.get("completo", True)) for s in situacao.values())

    def _enviados_rapido(self, termo, enderecos):
        """Consulta só nos Itens Enviados do Outlook de cada PC, com limite de ~1 s. Guarda 60 s (o mesmo endereço
        digitado de novo não repete). Qualquer falha = sem extra: o resultado normal já está na tela."""
        cache = self.__dict__.setdefault("_enviados_rapido_cache", {})
        agora = time.monotonic()
        if termo in cache and agora - cache[termo][0] < 60:
            return cache[termo][1]
        corpo = {"q": termo, "vivo": True, "so_enviados": True, "tempo": ENVIADOS_RAPIDO_SEGUNDOS, "limite": 20}
        achados, local = [], {}
        fio = threading.Thread(target=lambda: local.update(r=self._buscar_local_rapido(corpo)))
        fio.start()
        try:
            if enderecos and getattr(self, "segredo", None):
                resp = rede_local.perguntar_a_todos(self.segredo, enderecos, "buscar", corpo, tempo=ENVIADOS_RAPIDO_SEGUNDOS + 1.5)
                achados += [x for r in resp.values() for x in r.get("resultados", [])]
        except Exception:
            logger.debug("enviados rápido pela rede", exc_info=True)
        fio.join(ENVIADOS_RAPIDO_SEGUNDOS + 2)
        achados += (local.get("r") or {}).get("resultados", [])
        achados = [x for x in achados if x.get("pasta") == "enviado"]
        cache[termo] = (agora, achados)
        return achados

    def _buscar_local_rapido(self, corpo):
        try:
            return self.rede_buscar(corpo)
        except Exception:
            logger.debug("enviados rápido neste PC", exc_info=True)
            return {}

    def _buscar_local(self, termo, vivo=False):
        try:
            return self.rede_buscar({"q": termo, "vivo": vivo})
        except Exception as e:
            return {"erro": f"Outlook deste PC: {e}"}

    def _hospedes(self):
        """Hóspede único (e-mail ou CPF/CNPJ): {endereço: [pedidos do mesmo hóspede]}. Refeito só quando a lista de
        pedidos muda (como o índice por e-mail)."""
        lista = self.solicitacoes
        if getattr(self, "_indice_hospedes", (None,))[0] is not lista:
            grupo = hospedes.grupos(lista)
            membros, por_endereco = {}, {}
            for s in lista:
                membros.setdefault(grupo[s["chave"]], []).append(s)
            for s in lista:
                for x in hospedes.enderecos(s):
                    por_endereco.setdefault(x, set()).add(grupo[s["chave"]])
            self._indice_hospedes = (lista, {x: [s for g in gs for s in membros[g]] for x, gs in por_endereco.items()})
        return self._indice_hospedes[1]

    def conversa(self, de):
        """Tudo do hóspede na tela: e-mails sem resposta (todos os PCs), o que saiu pra ele nas últimas 24 h, os
        pedidos do formulário dele e as NFs já enviadas (pelo registro, conferido no PDF pelo robô).
        Hóspede único (Etapa 2): entram também os pedidos feitos com outro e-mail e o mesmo CPF/CNPJ."""
        de = (de or "").strip().lower()
        pedidos = self._hospedes().get(de, [])
        ligados = sorted({x for s in pedidos for x in hospedes.enderecos(s)} - {de})[:5]
        with self.lock:
            recebidos = [e for e in getattr(self, "entrada_correio", []) if e["de"] == de]
            enviados = [e for e in self.enviados_correio if de in [x.strip() for x in e["para"].split(",")]]
            fila = [s for s in dados.montar_fila(pedidos, self.estados)]
        pcs = self._pcs_por_nome()
        linha_do_tempo = ([{"tipo": "recebido", **e} for e in recebidos] + [{"tipo": "enviado", **e} for e in enviados] +
                          [{"tipo": "formulario", "quando": s["data"], "chave": s["chave"], "hotel": s["hotel"],
                            "nome": s["nome"], "situacao": s["situacao"], "nfs": s["nfs"], "envios": s["envios"],
                            "email": s["email"], "alerta_doc": s["alerta_doc"]}
                           for s in fila])
        linha_do_tempo.sort(key=lambda x: x["quando"], reverse=True)
        nfs_enviadas = [{"nfs": env["nfs"], "para": env["para"], "quando": env["quando"], "hotel": s["hotel"]}
                        for s in fila for env in s["envios"]]
        return {"de": de, "nome": next((e["nome"] for e in recebidos if e["nome"]), fila[0]["nome"] if fila else de),
                "linha_do_tempo": linha_do_tempo, "nfs_enviadas": nfs_enviadas, "enderecos": ligados,
                "pcs": {pc: {"online": p["online"], "agente": p["agente"]} for pc, p in pcs.items()}}

    def evento_correio(self, ids, acao, agente):
        """Lido / não lido (equipe toda). Gravado junto com os outros na próxima volta (1 escrita só)."""
        if acao not in ("LIDO", "NAO_LIDO"):
            raise ValueError("ação desconhecida")
        pc = socket.gethostname()
        with self.lock:
            na_tela = {x["id"]: x["lido"] for x in getattr(self, "entrada_correio", [])}   # o que aparece (vem do Outlook)
            for i in ids[:200]:
                atual = na_tela.get(i, self.eventos_correio.get(i, {}).get("lido", False))
                if atual != (acao == "LIDO"):
                    self.eventos_pendentes.append(espelho_emails.evento(str(i), acao, agente, pc))
        self._montar_correio()
        try:   # e-mail das caixas deste PC: já marca no Outlook (sem esperar a próxima volta)
            self._lido_no_outlook()
        except Exception:
            logger.debug("lido no Outlook", exc_info=True)
        return {"ok": True}

    def _gravar_eventos_pendentes(self):
        with self.lock:
            pendentes, self.eventos_pendentes = self.eventos_pendentes, []
        if not pendentes:
            return
        try:
            self.backend.anexar_linhas(self.central, espelho_emails.ABA_EVENTOS, pendentes)
            self.eventos_linhas = (self.eventos_linhas or [espelho_emails.CAB_EVENTOS]) + pendentes
        except Exception as e:
            logger.warning(f"⚠️ Não consegui gravar lido/não lido ({e}) — tento na próxima volta")
            with self.lock:
                self.eventos_pendentes = pendentes + self.eventos_pendentes

    def excluir_email(self, id_email, agente, extra=None):
        """Some na hora pra equipe toda; o PC dono move pra Itens Excluídos do Outlook dele (o "Desfazer" de 10 s
        fica na tela: só depois dele o pedido chega aqui)."""
        try:
            e = self._email(id_email)
        except KeyError:
            # Resultado de pesquisa (ou e-mail antigo): só está no índice do PC dono, não no espelho da equipe. O PC dono exclui pelo
            # EntryID depois de conferir no índice dele; não há linha do espelho para sumir, então não há evento para a equipe.
            extra = extra or {}
            entry, caixa = str(extra.get("entry", "")).strip(), str(extra.get("caixa", "")).strip().lower()
            if not (entry and caixa and caixa in self._caixas_de_hotel()):
                raise
            sol = {"aba": "", "carimbo": "", "email": str(extra.get("de", "")), "hotel": str(extra.get("hotel", "")),
                   "nome": str(extra.get("nome") or extra.get("de") or "")}
            return self.envio_nf.pedir(sol, "", str(extra.get("assunto", ""))[:300], caixa, [], agente, responder=id_email,
                                       acao=envio_nf.EXCLUIR, entry=entry)
        sol = {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"], "nome": e["nome"] or e["de"]}
        r = self.envio_nf.pedir(sol, "", e["assunto"], e["caixa"], [], agente, responder=e["id"], acao=envio_nf.EXCLUIR)
        if not r.get("ok"):
            return r
        linha = espelho_emails.evento(e["id"], "EXCLUIR", agente)
        self.backend.anexar_linhas(self.central, espelho_emails.ABA_EVENTOS, [linha])
        self.eventos_linhas = (self.eventos_linhas or [espelho_emails.CAB_EVENTOS]) + [linha]
        self._montar_correio()
        return r

    def marcar_urgencia(self, id_email, marcar, agente):
        """Botão direito (usuário, 20/10/2026): vale na hora pra equipe (Eventos_Correio) e o PC dono põe a categoria no
        Outlook, que é onde fica guardado (o evento some na faxina de 3 dias; a categoria não)."""
        if marcar not in ("urgente", "normal"):
            raise ValueError("marcar: urgente ou normal")
        e = self._email(id_email)
        sol = {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"], "nome": e["nome"] or e["de"]}
        r = self.envio_nf.pedir(sol, "", e["assunto"], e["caixa"], [], agente, mensagem=marcar, responder=e["id"],
                                acao=envio_nf.URGENCIA)
        if not r.get("ok"):
            return r
        linha = espelho_emails.evento(e["id"], "URGENTE" if marcar == "urgente" else "NAO_URGENTE", agente)
        self.backend.anexar_linhas(self.central, espelho_emails.ABA_EVENTOS, [linha])
        self.eventos_linhas = (self.eventos_linhas or [espelho_emails.CAB_EVENTOS]) + [linha]
        self._montar_correio()
        return r

    def encaminhar_email(self, corpo, quem):
        e = self._email(str(corpo.get("id", "")))
        para = ";".join(x.strip() for x in re.split(r"[;,]", str(corpo.get("para", ""))) if "@" in x)
        if not para:
            raise ValueError("preencha pra quem encaminhar")
        assunto = e["assunto"] if e["assunto"].lower().startswith(("enc:", "fw:", "fwd:")) else "ENC: " + e["assunto"]
        sol = {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"], "nome": e["nome"] or e["de"]}
        selo = str(corpo.get("selo") or "")   # assinatura padrão também no encaminhar (13/10/2026)
        return self.envio_nf.pedir(sol, para, assunto, e["caixa"], [], quem, str(corpo.get("corpo", "")),
                                   selo=selo if envio_nf.caminho_selo(selo) else "", responder=e["id"], acao=envio_nf.ENCAMINHAR)

    def opcoes_email(self, id_email):
        e = self._email(id_email)
        destino, motivo = self.envio_nf.destino_para(e["caixa"], aceitar_desligado=True)
        sol = self._solicitacao_do_email(e["de"])
        sugestoes = envio_nf.sugestoes_dropbox(sol, self.cfg) if sol else []
        if not sugestoes:   # e-mail sem formulário (ex.: recepção repassando o pedido): a NF achada pelo nº/nome
            sugestoes = envio_nf.notas_do_email(e, self.cfg)
        vistas = {x.get("rel") for x in sugestoes}   # + as achadas pelo CPF/CNPJ (gatilho da nota nova)
        sugestoes = sugestoes + [n for n in self.notas_emails.get(e["id"], []) if n.get("rel") not in vistas]
        assunto = e["assunto"] if e["assunto"].lower().startswith(("re:", "res:")) else "RE: " + e["assunto"]
        return {"para": [e["de"]], "conta_de": e["caixa"], "destino": destino, "motivo": motivo,
                "este_pc": socket.gethostname(), "contas_locais": self.envio_nf.contas, "sugestoes": sugestoes,
                "nome": e["nome"] or e["de"], "hotel": e["hotel"], "assunto": assunto, "corpo": "",
                "corpo_nf": envio_nf.mensagem_padrao(self.cfg), "assinatura": "", "assinatura_com_mensagem": False,
                "selos": envio_nf.selos(), "selo": envio_nf.selo_do_agente(self._agente()), "email": e,
                "solicitacao": sol["chave"] if sol else ""}

    def contas_de_hotel(self):
        """Caixas notafiscal@ dos 4 PCs -> [{"conta", "hotel", "agente", "pc", "destino"}], as deste PC primeiro.
        É o "De" do Novo e-mail (usuário, 13/10/2026): sai pela caixa do hotel, pelo Outlook do PC dono."""
        hotel_da_conta = {}
        for h in self.cadastro.nomes():
            email = str(self.cadastro.dados(h).get("email", "")).strip().lower()
            if email:
                hotel_da_conta[email] = h
        este = socket.gethostname()
        vistas, saida = set(), []
        for p in sorted(self.pcs(), key=lambda x: x["pc"] != este):
            for c in p.get("contas_lista", []):
                if c.startswith("notafiscal@") and c not in vistas:
                    vistas.add(c)
                    saida.append({"conta": c, "hotel": hotel_da_conta.get(c, saude.nome_da_caixa(c)),
                                  "agente": p.get("agente", ""), "pc": p["pc"], "online": bool(p.get("online"))})
        return saida

    def opcoes_email_novo(self, conta=""):
        """Opções do Novo e-mail: escolher a caixa do hotel, escrever para quem quiser (modelo: solicitação de dados)."""
        contas = self.contas_de_hotel()
        if not contas:
            raise KeyError("nenhuma caixa de hotel nos PCs da equipe (aba PCs_Painel)")
        escolhida = next((c for c in contas if c["conta"] == conta.lower()), contas[0])
        destino, motivo = self.envio_nf.destino_para(escolhida["conta"], aceitar_desligado=True)
        return {"novo": True, "para": [], "conta_de": escolhida["conta"], "destino": destino, "motivo": motivo,
                "este_pc": socket.gethostname(), "contas_locais": self.envio_nf.contas, "contas": contas,
                "sugestoes": [], "nome": "", "hotel": escolhida["hotel"], "assunto": "", "corpo": "",
                "corpo_nf": envio_nf.mensagem_padrao(self.cfg), "assinatura": "", "assinatura_com_mensagem": False, "selos": envio_nf.selos(),
                "selo": envio_nf.selo_do_agente(self._agente())}

    def enviar_email_novo(self, corpo, quem):
        """Novo e-mail ao hóspede: sai da caixa do hotel escolhida, sem ligar a nenhuma solicitação (não marca NF)."""
        conta = str(corpo.get("conta_de", "")).strip().lower()
        contas = {c["conta"]: c for c in self.contas_de_hotel()}
        if conta not in contas:
            raise ValueError("escolha a caixa do hotel de onde o e-mail sai")
        para, assunto = str(corpo.get("para", "")).strip(), str(corpo.get("assunto", "")).strip()
        texto = str(corpo.get("corpo", "")).strip()
        if "@" not in para or not assunto:
            raise ValueError("preencha o destinatário e o assunto")
        if not texto:
            raise ValueError("escreva a mensagem")
        import base64
        anexos = [{"tipo": "arquivo", "nome": os.path.basename(a.get("nome", "anexo.pdf")),
                   "conteudo": base64.b64decode(a.get("b64", ""))}
                  for a in corpo.get("anexos") or [] if a.get("tipo") == "arquivo"]
        cc = ";".join(x.strip() for x in re.split(r"[;,]", str(corpo.get("cc", ""))) if "@" in x)
        selo = str(corpo.get("selo") or "")
        sol = {"aba": "", "carimbo": "", "email": para, "hotel": contas[conta]["hotel"], "nome": para}
        logger.info(f"✉️ Novo e-mail de {conta} para {para}: \"{assunto}\" — por {quem}")
        r = self.envio_nf.pedir(sol, para, assunto, conta, anexos, quem, str(corpo.get("corpo", "")), cc,
                                selo if envio_nf.caminho_selo(selo) else "", livre=True, **_kw_ligacao(corpo))
        return self._marcar_ligacao_do_envio(r, corpo, quem, sol["hotel"], conta, para, assunto)

    def responder_email(self, corpo, quem):
        e = self._email(str(corpo.get("id", "")))
        para, assunto = str(corpo.get("para", "")).strip(), str(corpo.get("assunto", "")).strip()
        # formulário do Emissor Automático (20/10/2026): o pedido é o do hóspede do Para, não o do remetente (o Emissor)
        do_form = self._solicitacao_do_email(para.lower()) if "formulario" in (e.get("classes") or []) and "@" in para else None
        sol = do_form or self._solicitacao_do_email(e["de"]) or {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"],
                                                                 "nome": e["nome"] or e["de"]}
        if "@" not in para or not assunto:
            raise ValueError("preencha o destinatário e o assunto")
        import base64
        anexos = []
        for a in corpo.get("anexos") or []:
            if a.get("tipo") == "arquivo":
                anexos.append({"tipo": "arquivo", "nome": os.path.basename(a.get("nome", "nota.pdf")),
                               "conteudo": base64.b64decode(a.get("b64", ""))})
            elif a.get("tipo") == "dropbox" and a.get("rel"):
                anexos.append({"tipo": "dropbox", "rel": a["rel"], "nome": a.get("nome", "")})
        if not anexos and not str(corpo.get("corpo", "")).strip():
            raise ValueError("escreva a resposta ou anexe a nota")
        cc = ";".join(x.strip() for x in re.split(r"[;,]", str(corpo.get("cc", ""))) if "@" in x)
        selo = str(corpo.get("selo") or "")
        r = self.envio_nf.pedir(sol, para, assunto, e["caixa"], anexos, quem, str(corpo.get("corpo", "")), cc,
                                selo if envio_nf.caminho_selo(selo) else "", responder=e["id"], **_kw_ligacao(corpo))
        return self._marcar_ligacao_do_envio(r, corpo, quem, e["hotel"] or sol["hotel"], e["caixa"], para, assunto)
