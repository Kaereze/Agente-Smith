"""Estado do envio: pedir e conferir o envio da NF, ligações, Enviar/Receber todas e caixas com problema."""

import datetime
import os
import re
import socket
import threading
import time

import app_dados as dados
import enviar_receber
import envio_nf
import ligacoes
import nf_achadas
import outlook_vivo
import rede_local
import saude
from config import PASTA_ESTADO
from estado_correio import _kw_ligacao
from log_util import configurar_logging
from sheets import STATUS_ROTULO_A1, nome_intervalo

logger = configurar_logging("app")



class EnvioMixin:
    """Métodos de Estado (app_servidor.py) movidos para cá em 29/10/2026; mesma lógica, mesmo `self`."""

    def registrar_nf_enviada(self, pedido, quem):
        """NF enviada pelo Painel: entra no pedido como emitida (todos os PCs veem). Resposta a um e-mail
        de quem não tem pedido pelo formulário não tem onde registrar."""
        if not pedido.get("aba"):
            return
        pc, quando = socket.gethostname(), dados.agora()
        linhas = [dados.evento(quando, quem, pc, pedido["aba"], pedido["carimbo"], pedido["email"], dados.NF, nf)
                  for nf in pedido.get("nfs", [])]
        linhas.append(dados.evento(quando, quem, pc, pedido["aba"], pedido["carimbo"], pedido["email"], dados.OBS,
                                   f"\"{pedido['assunto']}\" enviada ao hóspede ({pedido['para']}) pela caixa {pedido['conta_de']}"))
        self.backend.anexar_linhas(self.central, dados.ABA_TRATAMENTO, linhas)
        self.reler_tratamento()

    def caixas_com_problema(self):
        """Pro botão de caixas: por PC com Outlook sem enviar/receber, o aviso e as caixas com e-mail preso (27/10/2026)."""
        demo = bool(getattr(self, "demo", False))
        pcs = {p["pc"]: p for p in self.pcs()}
        por_pc = {}
        for p in saude.problemas(list(pcs.values())):
            if p.get("tipo") == "caixa" and p.get("pc"):
                por_pc.setdefault(p["pc"], []).append(p["texto"])
        este = socket.gethostname()
        enderecos = {pc: pcs[pc].get("rede") for pc in por_pc if pc != este and pcs.get(pc, {}).get("rede")}
        det = {} if demo else rede_local.perguntar_a_todos(self.segredo, enderecos, "caixas", {}, tempo=6)
        if este in por_pc and not demo:
            det[este] = self.rede_caixas({})
        saida = []
        for pc, textos in por_pc.items():
            d = det.get(pc) or {}
            saida.append({"pc": pc, "agente": pcs[pc].get("agente") or pc, "textos": textos, "outlook": pcs[pc].get("outlook", ""),
                          "caixas": [c for c in d.get("caixas", []) if c.get("presos")], "erro": d.get("erro", "")})
        return {"pcs": saida, "este_pc": este}

    def reiniciar_outlook(self, pc, quem):
        if getattr(self, "so_ver", False):
            return {"erro": "Modo só leitura: não reinicia nada"}
        este = socket.gethostname()
        todos = {p["pc"]: p for p in self.pcs()}
        if getattr(self, "demo", False):
            time.sleep(4)
            return {"ok": True, "segundos": 4.0, "saiu": 3, "presos": 0}
        if pc and pc != este and pc not in todos:
            return {"erro": "PC desconhecido"}
        if not pc or pc == este:
            r = self.rede_reiniciar_outlook({})
        else:
            endereco = todos[pc].get("rede")
            if not todos[pc].get("online") or not endereco:
                return {"erro": f"{todos[pc].get('agente') or pc} está desligado ou sem rede: peça para reiniciar lá"}
            try:
                r = rede_local.perguntar(self.segredo, endereco, "reiniciar_outlook", {}, tempo=outlook_vivo.REINICIO_TEMPO_REDE)
            except Exception as e:
                r = {"erro": f"o PC não respondeu pela rede ({type(e).__name__})"}
        logger.warning(f"🔁 Reinício do Outlook de {pc or este} pedido por {quem}: {r}")
        return r

    def _er_terminou(self, _pc):
        self.__dict__.setdefault("acordar", threading.Event()).set()   # a tela relê já; o espelho vem da vigia do conferente
        self.versao_tela += 1

    def _enviar_receber(self):
        if getattr(self, "_er", None) is None:
            demo = bool(getattr(self, "demo", False))

            def local():
                if demo:
                    time.sleep(1.5)
                    return {"ok": True, "segundos": 1.5, "saiu": 0, "presos": 0}
                return self.rede_enviar_receber({})

            def remoto(pc, endereco):
                if demo:
                    time.sleep(2 + (hash(pc) % 40) / 10)
                    return {"ok": True, "segundos": 3.0, "saiu": 0, "presos": 0}
                return rede_local.perguntar(self.segredo, endereco, "enviar_receber", {}, tempo=enviar_receber.TEMPO_REDE)
            self._er = enviar_receber.EnviarReceber(
                socket.gethostname(), local, remoto,
                lambda: [{**p, "rede": p.get("rede") or ("demo" if demo else "")} for p in self.pcs()],
                PASTA_ESTADO / "enviar_receber_tempos.json", ao_terminar=self._er_terminou)
        return self._er

    def enviar_receber_todas(self, quem):
        if getattr(self, "so_ver", False):
            return {"erro": "Modo só leitura: não pede nada aos PCs"}
        return self._enviar_receber().iniciar(quem)

    def definir_robo_ligado(self, ligado, quem):
        """Liga ou pausa o robô (27/10/2026, só o João): é a caixa "Robô ligado?" da aba Status, a mesma que o robô lê antes de
        cada rodada. Desligado = nada é copiado nem enviado (os pedidos esperam) e o "Enviar agora" fica travado."""
        if getattr(self, "so_ver", False):
            return {"ok": False, "motivo": "Modo só leitura: não liga nem pausa o robô"}
        valor = "TRUE" if ligado else "FALSE"
        if not getattr(self, "demo", False):
            self.backend.escrever(self.cfg["planilha_central_id"], [(f"{nome_intervalo(self.cfg['aba_status'])}!B1", valor)])
        self.status[STATUS_ROTULO_A1] = valor
        logger.warning(f"🔌 Robô {'LIGADO' if ligado else 'PAUSADO (desligado)'} no Painel por {quem}")
        self.versao_tela += 1
        return {"ok": True, "ligado": bool(ligado)}

    def _avisar_dono_envio(self, pc, corpo):
        """Avisa o PC dono pela rede. Sem caminho até ele (outra faixa de rede, firewall, desligado) = erro, e o pedido
        segue pela fila Envios_NF como sempre."""
        endereco = self._enderecos_rede().get(pc)
        if not endereco or not getattr(self, "segredo", None):
            raise RuntimeError("sem caminho direto até ele")
        r = rede_local.perguntar_a_todos(self.segredo, {pc: endereco}, "envio_nf", corpo,
                                         tempo=envio_nf.TEMPO_AVISO_DONO).get(pc, {})
        self._anotar_rede({pc: r})
        if "erro" in r:
            raise RuntimeError(r["erro"])
        return r

    def iniciar_nf_achadas(self):
        """Liga o fio que lê as notas novas das pastas do Dropbox e guarda o CPF/CNPJ do tomador (27/10/2026)."""
        if not (self.cfg.get("dropbox_notas") or {}).get("ativo"):
            return

        def ler(caminho):
            from conferente import texto_de_arquivo_dropbox
            return texto_de_arquivo_dropbox(caminho)
        self.nf_indice = nf_achadas.Indice(PASTA_ESTADO / "nf_achadas.json")
        nf_achadas.iniciar(self.cfg, self.nf_indice, ler, ao_novas=lambda: self.atualizar_notas_emails(forcar=True))

    def _nf_achadas(self, sol):
        """-> (sugestões de NF pelo documento, avisos). A tag ✅ não é prova: confere se o envio existe nos Itens Enviados."""
        est = self.estados.get(sol["chave"]) or dados.estado_inicial()
        nfs = [str(n) for n in est.get("nfs", [])]
        avisos = []
        enviados = list(self.enviados_correio)
        if nfs and enviados:
            sem = nf_achadas.sem_envio_confirmado(nfs, enviados, envio_nf.destinatarios(sol))
            if sem:
                avisos.append(f"Marcado como enviado, mas não achei o envio da NF {', '.join(sem)} nos Itens Enviados. "
                              "A resposta do hóspede com a nota anexada não conta como envio.")
        indice = getattr(self, "nf_indice", None)
        if indice is None:
            return [], avisos
        limite = (datetime.date.today() - datetime.timedelta(days=120)).isoformat()
        ligadas, outros = set(), {}
        for o in self.solicitacoes:
            if o["chave"] == sol["chave"] or (o.get("data") or "") < limite:
                continue
            for n in (self.estados.get(o["chave"]) or {}).get("nfs", []):
                ligadas.add((o.get("hotel", ""), str(n)))
            alvo = nf_achadas._alvo(o)
            for d in alvo["documentos"]:
                outros.setdefault(d, []).append(alvo)
        return nf_achadas.achadas_do_pedido(indice, sol, nfs, ligadas, outros, raiz=envio_nf.raiz_dropbox(self.cfg)), avisos

    def opcoes_envio(self, chave_sol):
        sol = next((s for s in self.solicitacoes if s["chave"] == chave_sol), None)
        if sol is None:
            raise KeyError("solicitação não encontrada")
        conta = self.cadastro.dados(sol["hotel"]).get("email", "")
        destino, motivo = self.envio_nf.destino_para(conta, aceitar_desligado=True)
        sugestoes = envio_nf.sugestoes_dropbox(sol, self.cfg)
        try:   # NF achadas pelo CPF/CNPJ dentro do PDF (27/10/2026); nunca anexa nem envia sozinha
            achadas, avisos_nf = self._nf_achadas(sol)
        except Exception:
            logger.exception("NF achadas")
            achadas, avisos_nf = [], []
        vistas = {x.get("rel") for x in sugestoes}
        sugestoes = sugestoes + [a for a in achadas if a["rel"] not in vistas]
        try:
            assinatura = envio_nf.assinatura_previa(conta, self._agente())
        except Exception:
            logger.exception("prévia da assinatura")
            assinatura = ""
        com_mensagem = envio_nf.assinatura_tem_mensagem(assinatura)
        selos = envio_nf.selos()
        return {"para": envio_nf.destinatarios(sol), "conta_de": conta, "destino": destino, "motivo": motivo,
                "este_pc": socket.gethostname(), "contas_locais": self.envio_nf.contas, "sugestoes": sugestoes, "avisos_nf": avisos_nf,
                "nome": sol["nome"], "hotel": sol["hotel"],
                "corpo": envio_nf.mensagem_padrao(self.cfg) if selos or not com_mensagem else "",
                "assinatura": assinatura, "assinatura_com_mensagem": com_mensagem and not selos,
                "selos": selos, "selo": envio_nf.selo_do_agente(self._agente())}

    def pedir_envio(self, corpo, quem):
        sol = next((s for s in self.solicitacoes if s["chave"] == corpo.get("chave")), None)
        if sol is None:
            raise KeyError("solicitação não encontrada")
        para, assunto = str(corpo.get("para", "")).strip(), str(corpo.get("assunto", "")).strip()
        if "@" not in para or not assunto:
            raise ValueError("preencha o destinatário e o assunto")
        conta = (corpo.get("conta_de") or self.cadastro.dados(sol["hotel"]).get("email", "")).strip().lower()
        import base64
        anexos = []
        for a in corpo.get("anexos") or []:
            if a.get("tipo") == "arquivo":
                anexos.append({"tipo": "arquivo", "nome": os.path.basename(a.get("nome", "nota.pdf")),
                               "conteudo": base64.b64decode(a.get("b64", ""))})
            elif a.get("tipo") == "dropbox" and a.get("rel"):
                anexos.append({"tipo": "dropbox", "rel": a["rel"], "nome": a.get("nome", "")})
        if not anexos:
            raise ValueError("anexe a nota fiscal")
        cc = ";".join(e.strip() for e in re.split(r"[;,]", str(corpo.get("cc", ""))) if "@" in e)
        selo = str(corpo.get("selo") or "")
        r = self.envio_nf.pedir(sol, para, assunto, conta, anexos, quem, corpo.get("corpo"), cc,
                                selo if envio_nf.caminho_selo(selo) else "", **_kw_ligacao(corpo))
        return self._marcar_ligacao_do_envio(r, corpo, quem, sol["hotel"], conta, para, assunto)

    # ---------- pedido por ligação (usuário, 22/10/2026) ----------
    def _gravar_ligacao(self, chave, acao, agente, hotel="", caixa="", para="", assunto=""):
        linha = ligacoes.evento(chave, acao, agente, hotel, caixa, para, assunto)
        self.backend.anexar_linhas(self.central, ligacoes.ABA, [linha])
        with self.lock:
            self.ligacoes_linhas = (self.ligacoes_linhas or [ligacoes.CABECALHO]) + [linha]
            self.ligacoes = ligacoes.dobrar(self.ligacoes_linhas)
            self.versao_tela = getattr(self, "versao_tela", 0) + 1

    def _marcar_ligacao_do_envio(self, r, corpo, quem, hotel, caixa, para, assunto):
        """Botão "Ligação" ligado na tela de escrever: marca o envio (chave = id ENV-…). O e-mail já está na fila; se a
        marca não gravar, o envio segue e a tela avisa pra marcar depois em Itens Enviados."""
        if not (r.get("ok") and corpo.get("ligacao") and r.get("id")):
            return r
        try:
            self._gravar_ligacao(r["id"], ligacoes.MARCAR, quem, hotel, caixa, para, assunto)
            logger.info(f"📞 {r['id']}: marcado como ligação ({hotel}, por {quem})")
        except Exception as e:
            logger.warning(f"⚠️ {r['id']}: não consegui gravar a marca de ligação ({e})")
            return {**r, "aviso_ligacao": "O e-mail vai sair, mas a marca de ligação não gravou. Marque depois em Itens Enviados (botão direito)."}
        return r

    def marcar_ligacao(self, id_email, marcar, agente):
        """Botão direito num e-mail de Itens Enviados: "Marcar como ligação" / "Tirar marca de ligação"."""
        with self.lock:
            e = next((x for x in self.enviados_correio if x.get("id") == id_email), None)
        if e is None:
            raise KeyError("e-mail enviado não encontrado (pode ter passado das 72 h)")
        chave = ligacoes.chave_do_enviado(e)
        if bool(marcar) == (chave in self.ligacoes):
            return {"ok": True, "ligacao": bool(marcar)}
        self._gravar_ligacao(chave, ligacoes.MARCAR if marcar else ligacoes.DESMARCAR, agente, e.get("hotel", ""),
                             e.get("caixa", ""), e.get("para", ""), e.get("assunto", ""))
        logger.info(f"📞 {chave}: {'marcado' if marcar else 'desmarcado'} como ligação em Itens Enviados, por {agente}")
        return {"ok": True, "ligacao": bool(marcar)}

    def _ligacoes_de_envios_falhos(self):
        """Envio marcado que falhou: o PC que marcou tira a marca (o reenvio é que conta)."""
        if getattr(self, "so_ver", False) or not self.ligacoes:
            return
        for chave in ligacoes.envios_falhos_a_desmarcar(self.ligacoes, self.envio_nf.fila, socket.gethostname()):
            m = self.ligacoes[chave]
            self._gravar_ligacao(chave, ligacoes.DESMARCAR, m["agente"], m["hotel"], m["caixa"], m["para"], m["assunto"])
            logger.info(f"📞 {chave}: o envio falhou — marca de ligação retirada (o reenvio é que conta)")

    def resumo_ligacoes(self):
        """Cartão Ligações da Visão geral; "de N envios" = envios do Painel que saíram hoje (a fila guarda 3 dias)."""
        hoje = datetime.date.today().isoformat()
        envios = sum(1 for e in list(getattr(self.envio_nf, "fila", {}).values())
                     if e.get("resultado") == envio_nf.ENVIADO and str(e.get("pedido_em", ""))[:10] == hoje
                     and not (e.get("pedido") or {}).get("acao"))
        return ligacoes.resumo(self.ligacoes, envios)

    def conferir_anexos(self, corpo):
        """Antes de enviar (usuário, 11/10/2026): abre cada PDF anexado e confere com o pedido (CPF/CNPJ, valor, nome,
        datas — a mesma regra do robô). -> {"avisos": [texto], "conferidas": n}. Só lê; não envia nada."""
        import base64
        import io
        import types
        from controle_nf import conferir_conteudo, documento_diferente, provas_da_solicitacao
        sol = next((s for s in self.solicitacoes if s["chave"] == corpo.get("chave")), None) if corpo.get("chave") else None
        if sol is None and corpo.get("id"):
            e = next((x for x in self.emails if x["id"] == corpo.get("id")), None)
            sol = self._solicitacao_do_email(e["de"]) if e else None
        if sol is None:
            return {"avisos": [], "conferidas": 0, "sem_pedido": True}
        provas = {**provas_da_solicitacao(types.SimpleNamespace(campos=sol.get("campos", []))), "nomes": sol.get("nomes", [])}
        raiz = envio_nf.raiz_dropbox(self.cfg)
        avisos, conferidas = [], 0
        for a in corpo.get("anexos") or []:
            nome = os.path.basename(str(a.get("nome") or a.get("rel") or "nota.pdf"))
            if not nome.lower().endswith(".pdf"):
                continue
            texto = ""
            try:
                from pypdf import PdfReader
                if a.get("tipo") == "arquivo":
                    leitor = PdfReader(io.BytesIO(base64.b64decode(a.get("b64", ""))))
                    texto = "\n".join((p.extract_text() or "") for p in leitor.pages[:3])
                elif a.get("tipo") == "dropbox" and a.get("rel"):
                    caminho = os.path.join(str(raiz), a["rel"]) if raiz else a["rel"]
                    from arquivos import so_na_nuvem
                    if os.path.exists(caminho) and not so_na_nuvem(caminho):   # só na nuvem: não baixa (regra do usuário)
                        texto = envio_nf._texto_da_nota_rapido(caminho, os.path.getmtime(caminho))
            except Exception as erro:
                logger.debug(f"conferir anexo {nome}: {erro}")
            resultado, prova = conferir_conteudo(provas, texto)
            if resultado == "sem_texto":
                continue   # PDF escaneado: não dá pra conferir aqui (o robô confere depois com OCR)
            conferidas += 1
            diferente = documento_diferente(provas, texto)
            if resultado == "nao_confere":
                avisos.append(f"{nome}: não parece ser a nota deste pedido ({prova})")
            elif diferente.startswith("⚠"):
                avisos.append(f"{nome}: {diferente[2:]}")
        return {"avisos": avisos, "conferidas": conferidas, "pedido": sol.get("nome", "")}

    def situacao_envio(self, id_envio):
        local = self.envio_nf.locais.get(id_envio)
        if local and local["estado"] != "enviando":
            return local
        fresca = envio_nf.dobrar_fila(self.backend.ler_abas(self.central, [envio_nf.ABA_FILA])[0].get(envio_nf.ABA_FILA, [[]]))
        return self.envio_nf.situacao(id_envio, fresca)
