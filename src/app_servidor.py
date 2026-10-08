"""Painel Notas Fiscais: servidor HTTP só em 127.0.0.1 + janela do Edge em modo aplicativo.

    python src\\app_servidor.py --sem-janela   servidor em segundo plano (tarefa SolicitacoesNF_Painel, no logon)
    python src\\app_servidor.py                abre a janela; liga o servidor antes se ele não estiver rodando

O servidor fica no ar enquanto o PC estiver ligado e mantém os dados atualizados, então a
janela abre já carregada. O último estado também vai pro disco (painel_cache.pkl) pra
sobreviver a um reinício. Todos os PCs leem e gravam a mesma Planilha Central.
"""
import datetime
import json
import os
import pickle
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_utf8 import garantir_utf8

garantir_utf8()

import app_dados as dados
import atividade
import atualizador
import avisos_windows
import canceladas
import envio_nf
import espelho_emails
import rede_pcs
import fiscal_intelligence
import painel_metricas as metricas
from arquivos import salvar_json
from hoteis import CadastroHoteis
from app_envio import Envio
from config import PASTA_ESTADO, PASTA_PROJETO, caminho_chave_google, carregar_config, e_principal
from log_util import configurar_logging
from sheets import (LINHA_COMANDO, LINHA_PEDIDO, STATUS_ROTULO_A1, escrever_linhas_status, nome_do_hotel_pela_aba)
from tratamento import normalizar

logger = configurar_logging("app")

PORTA = 8765
PASTA_UI = PASTA_PROJETO / "app_ui"
CAMINHO_PREFS = PASTA_ESTADO / "app.json"
JANELA_ABERTA_SEGUNDOS = 90     # a janela pede dados a cada 15 s; sem pedido há 90 s = fechada
CAMINHO_CACHE = PASTA_ESTADO / "painel_cache.pkl"
CAMINHO_CANCELADAS = PASTA_ESTADO / "canceladas.json"
CANCELADAS_MINUTOS = 10
VERIFICAR_ATUALIZACAO_MINUTOS = 15
CAMINHO_VERSAO = PASTA_ESTADO / "versao_rodando.txt"
ATIVIDADE_CACHE_SEGUNDOS = 20
SALVAR_CACHE_SEGUNDOS = 120
VERSAO_CACHE = 1
NOTAS_EMAILS_SEGUNDOS = 120   # e-mail -> NF do Dropbox: recalculado a cada 2 min, fora da resposta da tela
ESTATICOS = {   # lista fechada: nada fora daqui é servido do disco
    "/icone.png": ("icone.png", "image/png"),
    "/favicon.ico": ("icone.ico", "image/x-icon"),
    "/graficos.js": ("graficos.js", "text/javascript; charset=utf-8"),
    "/painel.js": ("painel.js", "text/javascript; charset=utf-8"),
}
EDGE = [r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]


def nome_do_agente():
    try:
        nome = json.load(open(CAMINHO_PREFS, encoding="utf-8")).get("agente")
        if nome:
            return nome
    except (FileNotFoundError, ValueError):
        pass
    try:
        import identidade
        if identidade.ler().get("agente"):
            return identidade.ler()["agente"]
    except Exception:
        pass
    return os.environ.get("USERNAME", "?")


class Estado:
    """Cache em memória da Central. Uma leitura (batch) por atualização, pra caber na cota da API."""

    def __init__(self, backend, cfg, relogio=time.monotonic, servico_envio=None):
        self.backend, self.cfg, self.relogio = backend, cfg, relogio
        self.envio_nf = servico_envio or envio_nf.ServicoEnvio(backend, cfg, socket.gethostname(), self.registrar_nf_enviada)
        self.central = cfg["planilha_central_id"]
        self.lock = threading.Lock()
        self.abas_hotel, self.abas_lidas_em = {}, -1e9
        self.solicitacoes, self.estados, self.status = [], {}, {}
        self.atualizado_em, self.erro = None, ""
        self.cadastro = CadastroHoteis([])
        painel = cfg.get("painel", {})
        self.desde = datetime.date.fromisoformat(painel.get("desde", "2026-09-01"))
        self.fi_id, self.fi_minutos = painel.get("fiscal_intelligence_id", ""), int(painel.get("fi_minutos", 5))
        self.ignorar = list(painel.get("ignorar_hoteis", []))
        self.fi, self.fi_lido, self.fi_erro = None, -1e9, ""
        self.canceladas, self.canceladas_lidas, self.lendo_canceladas = [], -1e9, False
        self.cache_salvo = -1e9
        # rede de PCs: Outlook, versão, pedidos novos, comandos e atualização automática
        self.versao = envio_nf.versao_do_codigo() or atualizador.versao()   # lê o .git: nem todo PC tem git no PATH
        self.outlook, self.chaves_vistas, self.versao_registrada = None, None, False
        self.atualizacao = {"verificado_em": "", "motivo": "", "atras": 0}
        self.proxima_verificacao = time.monotonic() + 120
        self.comandos_em_execucao = set()
        self.atividade_cache = ([], -1e9)
        self.envio_nf.extras = self._extras_pc
        self.abas_emails, self.emails = [], []
        self.avisos = avisos_windows.Avisos()
        self.notas_emails, self.notas_emails_em = {}, -1e9   # {id do e-mail: [NF do Dropbox]} — calculado em segundo plano

    def _abas(self):
        if self.relogio() - self.abas_lidas_em > 600:
            marcador = normalizar(self.cfg.get("marcador_aba_respostas", "(respostas)"))
            ignoradas = {normalizar(a) for a in self.cfg.get("abas_ignoradas", [])}
            todas = self.backend.listar_abas(self.central)
            aba_cad = self.cfg["aba_cadastro_hoteis"]
            cad, _ = self.backend.ler_abas(self.central, [aba_cad])
            self.cadastro = CadastroHoteis(cad.get(aba_cad, []), self.cfg.get("apelidos_hoteis", {}),
                                           self.cfg.get("cadastro_colunas"))
            self.abas_hotel = {a: self.cadastro.canonico(nome_do_hotel_pela_aba(a)) or nome_do_hotel_pela_aba(a)
                               for a in todas if marcador in normalizar(a) and normalizar(a) not in ignoradas}
            self.abas_emails = [a for a in todas if a.startswith(espelho_emails.PREFIXO_ABA)]
            for aba, cab in ((dados.ABA_TRATAMENTO, dados.CABECALHO_TRATAMENTO), (envio_nf.ABA_FILA, envio_nf.CAB_FILA),
                             (envio_nf.ABA_ANEXOS, envio_nf.CAB_ANEXOS), (envio_nf.ABA_PCS, envio_nf.CAB_PCS),
                             (atividade.ABA, atividade.CABECALHO), (rede_pcs.ABA_COMANDOS, rede_pcs.CAB_COMANDOS)):
                if aba not in todas:
                    self.backend.criar_aba_log(self.central, aba, cab)
            if hasattr(self.backend, "garantir_colunas"):
                try:
                    self.backend.garantir_colunas(self.central, envio_nf.ABA_PCS, envio_nf.CAB_PCS)
                except Exception as e:
                    logger.warning(f"⚠️ Não consegui aumentar as colunas de {envio_nf.ABA_PCS} ({e})")
            self.abas_lidas_em = self.relogio()
        return self.abas_hotel

    def atualizar(self):
        try:
            abas = self._abas()
            status_aba = self.cfg["aba_status"]
            lidas, erros = self.backend.ler_abas(self.central, list(abas) + [dados.ABA_TRATAMENTO, status_aba,
                                                                              envio_nf.ABA_FILA, envio_nf.ABA_PCS,
                                                                              rede_pcs.ABA_COMANDOS] + self.abas_emails)
            solicitacoes = []
            for aba, hotel in abas.items():
                solicitacoes += dados.ler_solicitacoes(aba, hotel, lidas.get(aba, []), self.cfg)
            status = {str(l[0]).strip(): (str(l[1]) if len(l) > 1 else "") for l in lidas.get(status_aba, []) if l}
            emails = [e for aba in self.abas_emails for e in espelho_emails.ler_aba(lidas.get(aba, []))]
            with self.lock:
                self.solicitacoes = solicitacoes
                self.estados = dados.dobrar_eventos(lidas.get(dados.ABA_TRATAMENTO, [[]]))
                self.emails = emails
                self.status = status
                self.atualizado_em, self.erro = dados.agora(), ""
        except Exception as e:
            logger.warning(f"⚠️ Não consegui ler a planilha ({e})")
            self.erro = str(e)[:200]
            return
        try:
            self.envio_nf.tick(lidas, nome_do_agente())
        except Exception:
            logger.exception("fila de envio de NF")
        try:
            self._rede(lidas, solicitacoes)
        except Exception:
            logger.exception("rede de PCs")

    # ---------- rede de PCs ----------
    def _extras_pc(self):
        """Colunas E-H da linha deste PC em PCs_Painel."""
        outlook = {True: "aberto", False: "fechado"}.get(self.outlook, "?")
        # "'" na frente: a planilha lê "09119e6" como número (9.12E+09) e estragaria a versão
        return [outlook, "'" + self.versao, self.cfg.get("papel", ""), rede_pcs.ultima_conferencia()]

    def _rede(self, lidas, solicitacoes):
        pc, agente = socket.gethostname(), nome_do_agente()
        linhas = []
        if not self.versao_registrada:   # 1ª volta depois de ligar: registra se a versão mudou
            try:
                anterior = CAMINHO_VERSAO.read_text(encoding="utf-8").strip()
            except OSError:
                anterior = ""
            if anterior and anterior != self.versao:
                linhas.append(atividade.linha(atividade.ATUALIZADO, detalhe=f"de {anterior} para {self.versao}", agente=agente))
            CAMINHO_VERSAO.write_text(self.versao, encoding="utf-8")
            self.versao_registrada = True
        aberto = rede_pcs.outlook_aberto()
        if aberto is not None and aberto != self.outlook:
            if self.outlook is not None or not aberto:
                tipo = atividade.OUTLOOK_ABERTO if aberto else atividade.OUTLOOK_FECHADO
                linhas.append(atividade.linha(tipo, detalhe="o robô deste PC " + ("voltou a ler" if aberto else "parou de ler")
                                              + " os e-mails das caixas daqui", agente=agente))
            self.outlook = aberto
        # Pedido novo na planilha: só o principal registra (os outros veriam o mesmo e repetiriam)
        chaves = {s["chave"]: s for s in solicitacoes}
        if self.chaves_vistas is not None and e_principal(self.cfg):
            novas = [chaves[k] for k in chaves.keys() - self.chaves_vistas]
            linhas += [atividade.linha(atividade.NOVA_SOLICITACAO, s["hotel"], s["nome"],
                                       f"pedido de {s['carimbo']} · {s['email']}", agente="Robô") for s in novas[:30]]
            if len(novas) > 30:
                linhas.append(atividade.linha(atividade.NOVA_SOLICITACAO, detalhe=f"+{len(novas) - 30} pedidos novos", agente="Robô"))
        self.chaves_vistas = set(chaves)
        for id_c, comando, por in rede_pcs.pendentes(lidas.get(rede_pcs.ABA_COMANDOS, []), pc):
            if id_c not in self.comandos_em_execucao:
                self.comandos_em_execucao.add(id_c)
                threading.Thread(target=self._executar_comando, args=(id_c, comando, por), daemon=True).start()
        if self.cfg.get("painel", {}).get("atualizar_sozinho", True) and time.monotonic() >= self.proxima_verificacao:
            self.proxima_verificacao = time.monotonic() + VERIFICAR_ATUALIZACAO_MINUTOS * 60
            threading.Thread(target=self._verificar_atualizacao, args=(True,), daemon=True).start()
        atividade.registrar(self.backend, self.central, linhas)
        # Aviso do Windows: PC desligou, Outlook fechou ou conferência parou (principal: todos; os outros: só ele)
        for titulo, texto in self.avisos.mudancas(self.pcs(), pc, e_principal(self.cfg),
                                                  cfg_avisos=self.cfg.get("painel", {}).get("avisos")):
            avisos_windows.mostrar(titulo, texto)

    def _verificar_atualizacao(self, automatica, pedido_por=""):
        s = atualizador.situacao()
        motivo = atualizador.motivo_para_nao(s)
        self.atualizacao = {"verificado_em": datetime.datetime.now().isoformat(timespec="seconds"),
                            "motivo": motivo, "atras": s["atras"]}
        if atualizador.pode_atualizar(s):
            quem = "automática" if automatica else f"pedida por {pedido_por}"
            ok, texto = atualizador.atualizar()
            atividade.registrar(self.backend, self.central, [atividade.linha(
                atividade.ATUALIZADO if ok else atividade.FALHA,
                detalhe=f"atualização {quem} ({s['atras']} commit(s) novo(s)): {texto}", agente=nome_do_agente())])
            return texto
        return motivo

    def _executar_comando(self, id_c, comando, por):
        try:
            texto = self._verificar_atualizacao(False, por) if comando == "atualizar" else "comando desconhecido"
        except Exception as e:
            texto = f"falhou: {e}"
        try:
            self.backend.anexar_linhas(self.central, rede_pcs.ABA_COMANDOS,
                                       [rede_pcs.resposta(id_c, socket.gethostname(), comando, texto or "ok")])
        except Exception as e:
            logger.warning(f"⚠️ Não consegui responder o comando {id_c} ({e})")

    def pedir_comando(self, para, comando, por):
        if comando not in rede_pcs.COMANDOS:
            raise ValueError("comando desconhecido")
        pcs = {p["pc"].lower() for p in rede_pcs.ler_pcs(self.envio_nf.pcs_linhas)}
        if para != "TODOS" and para.lower() not in pcs:
            raise ValueError("PC desconhecido")
        self.backend.anexar_linhas(self.central, rede_pcs.ABA_COMANDOS, [rede_pcs.pedido(para, comando, por)])
        return {"ok": True}

    def pcs(self):
        return rede_pcs.ler_pcs(self.envio_nf.pcs_linhas)

    def atividade_resumo(self):
        linhas, lido = self.atividade_cache
        if time.monotonic() - lido > ATIVIDADE_CACHE_SEGUNDOS:
            linhas = self.backend.ler_abas(self.central, [atividade.ABA])[0].get(atividade.ABA, [])
            self.atividade_cache = (linhas, time.monotonic())
        return {"pcs": self.pcs(), "eventos": atividade.ler(linhas, 400), "este_pc": socket.gethostname(),
                "versao": self.versao, "atualizacao": self.atualizacao}

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

    def lista_emails(self):
        pcs = {p["pc"]: p for p in self.pcs()}
        saida = []
        for e in self.emails:
            sol = self._solicitacao_do_email(e["de"])
            dono = pcs.get(e["pc"], {})
            notas = self.notas_emails.get(e["id"], [])
            saida.append({**e, "pc_online": bool(dono.get("online")), "agente_pc": dono.get("agente", ""), "notas": notas,
                          "solicitacao": {"chave": sol["chave"], "hotel": sol["hotel"], "data": sol["data"]} if sol else None})
        return sorted(saida, key=lambda e: e["recebido"], reverse=True)

    def atualizar_notas_emails(self, forcar=False):
        """NF do Dropbox de cada e-mail espelhado (lê o Dropbox e às vezes o PDF: segundos). Roda no laço de fundo
        a cada NOTAS_EMAILS_SEGUNDOS; a lista de e-mails só consulta o resultado e responde na hora."""
        if not forcar and self.relogio() - self.notas_emails_em < NOTAS_EMAILS_SEGUNDOS:
            return
        self.notas_emails_em = self.relogio()
        mapa = {}
        for e in list(self.emails):
            try:
                mapa[e["id"]] = envio_nf.notas_do_email(e, self.cfg)
            except Exception as erro:
                logger.debug(f"NF do Dropbox pro e-mail {e['id']}: {erro}")
        self.notas_emails = mapa

    def _email(self, id_email):
        e = next((x for x in self.emails if x["id"] == id_email), None)
        if e is None:
            raise KeyError("e-mail não está mais na lista (pode ter sido respondido)")
        return e

    def opcoes_email(self, id_email):
        e = self._email(id_email)
        destino, motivo = self.envio_nf.destino_para(e["caixa"])
        sol = self._solicitacao_do_email(e["de"])
        sugestoes = envio_nf.sugestoes_dropbox(sol, self.cfg) if sol else []
        if not sugestoes:   # e-mail sem formulário (ex.: recepção repassando o pedido): a NF achada pelo nº/nome
            sugestoes = envio_nf.notas_do_email(e, self.cfg)
        assunto = e["assunto"] if e["assunto"].lower().startswith(("re:", "res:")) else "RE: " + e["assunto"]
        return {"para": [e["de"]], "conta_de": e["caixa"], "destino": destino, "motivo": motivo,
                "este_pc": socket.gethostname(), "contas_locais": self.envio_nf.contas, "sugestoes": sugestoes,
                "nome": e["nome"] or e["de"], "hotel": e["hotel"], "assunto": assunto, "corpo": "",
                "corpo_nf": envio_nf.mensagem_padrao(self.cfg), "assinatura": "", "assinatura_com_mensagem": False,
                "selos": envio_nf.selos(), "selo": envio_nf.selo_do_agente(nome_do_agente()), "email": e,
                "solicitacao": sol["chave"] if sol else ""}

    def responder_email(self, corpo, quem):
        e = self._email(str(corpo.get("id", "")))
        sol = self._solicitacao_do_email(e["de"]) or {"aba": "", "carimbo": "", "email": e["de"], "hotel": e["hotel"],
                                                       "nome": e["nome"] or e["de"]}
        para, assunto = str(corpo.get("para", "")).strip(), str(corpo.get("assunto", "")).strip()
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
        return self.envio_nf.pedir(sol, para, assunto, e["caixa"], anexos, quem, str(corpo.get("corpo", "")), cc,
                                   selo if envio_nf.caminho_selo(selo) else "", responder=e["id"])

    def opcoes_envio(self, chave_sol):
        sol = next((s for s in self.solicitacoes if s["chave"] == chave_sol), None)
        if sol is None:
            raise KeyError("solicitação não encontrada")
        conta = self.cadastro.dados(sol["hotel"]).get("email", "")
        destino, motivo = self.envio_nf.destino_para(conta)
        sugestoes = envio_nf.sugestoes_dropbox(sol, self.cfg)
        try:
            assinatura = envio_nf.assinatura_previa(conta, nome_do_agente())
        except Exception:
            logger.exception("prévia da assinatura")
            assinatura = ""
        com_mensagem = envio_nf.assinatura_tem_mensagem(assinatura)
        selos = envio_nf.selos()
        return {"para": envio_nf.destinatarios(sol), "conta_de": conta, "destino": destino, "motivo": motivo,
                "este_pc": socket.gethostname(), "contas_locais": self.envio_nf.contas, "sugestoes": sugestoes,
                "nome": sol["nome"], "hotel": sol["hotel"],
                "corpo": envio_nf.mensagem_padrao(self.cfg) if selos or not com_mensagem else "",
                "assinatura": assinatura, "assinatura_com_mensagem": com_mensagem and not selos,
                "selos": selos, "selo": envio_nf.selo_do_agente(nome_do_agente())}

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
        return self.envio_nf.pedir(sol, para, assunto, conta, anexos, quem, corpo.get("corpo"), cc,
                                   selo if envio_nf.caminho_selo(selo) else "")

    def situacao_envio(self, id_envio):
        local = self.envio_nf.locais.get(id_envio)
        if local and local["estado"] != "enviando":
            return local
        fresca = envio_nf.dobrar_fila(self.backend.ler_abas(self.central, [envio_nf.ABA_FILA])[0].get(envio_nf.ABA_FILA, [[]]))
        return self.envio_nf.situacao(id_envio, fresca)

    def reler_tratamento(self):
        lidas, _ = self.backend.ler_abas(self.central, [dados.ABA_TRATAMENTO])
        with self.lock:
            self.estados = dados.dobrar_eventos(lidas.get(dados.ABA_TRATAMENTO, [[]]))

    def registrar(self, agente, pc, chave_sol, acao, valor=""):
        sol = next((s for s in self.solicitacoes if s["chave"] == chave_sol), None)
        if sol is None:
            raise KeyError("solicitação não encontrada (a planilha pode ter mudado; atualize)")
        if acao == dados.ASSUMIR:
            self.reler_tratamento()
            dono = dados.quem_ganhou(self.estados, chave_sol)
            if dono and dono != agente:
                return {"ok": False, "motivo": f"Já está em tratamento por {dono}."}
        linha = dados.evento(dados.agora(), agente, pc, sol["aba"], sol["carimbo"], sol["email"], acao, valor)
        self.backend.anexar_linhas(self.central, dados.ABA_TRATAMENTO, [linha])
        self.reler_tratamento()
        if acao == dados.ASSUMIR:
            dono = dados.quem_ganhou(self.estados, chave_sol)
            if dono != agente:
                return {"ok": False, "motivo": f"{dono} assumiu um instante antes de você."}
        return {"ok": True}

    def fila(self, dias=None, desde=None):
        if dias:
            desde = (datetime.date.today() - datetime.timedelta(days=dias)).isoformat()
        try:
            controle = json.load(open(PASTA_ESTADO / "controle_nf.json", encoding="utf-8"))
        except (FileNotFoundError, ValueError):
            controle = {}
        with self.lock:
            return dados.montar_fila(self.solicitacoes, self.estados, dados.nfs_do_controle(controle), desde)

    def salvar_cache(self, forcar=False):
        """Último estado em disco: depois de reiniciar o PC a janela já abre com dados."""
        if not self.atualizado_em or (not forcar and self.relogio() - self.cache_salvo < SALVAR_CACHE_SEGUNDOS):
            return
        with self.lock:
            dados_cache = {"versao": VERSAO_CACHE, "solicitacoes": self.solicitacoes, "estados": self.estados,
                           "status": self.status, "atualizado_em": self.atualizado_em, "fi": self.fi,
                           "cadastro": self.cadastro, "abas_hotel": self.abas_hotel}
        try:
            CAMINHO_CACHE.parent.mkdir(parents=True, exist_ok=True)
            temporario = CAMINHO_CACHE.with_suffix(".tmp")
            temporario.write_bytes(pickle.dumps(dados_cache, protocol=pickle.HIGHEST_PROTOCOL))
            os.replace(temporario, CAMINHO_CACHE)
            self.cache_salvo = self.relogio()
        except OSError as e:
            logger.warning(f"⚠️ Não consegui salvar o cache do painel ({e})")

    def carregar_cache(self):
        try:
            c = pickle.loads(CAMINHO_CACHE.read_bytes())
        except (FileNotFoundError, OSError, pickle.UnpicklingError, EOFError, AttributeError, ImportError):
            return False
        if c.get("versao") != VERSAO_CACHE:
            return False
        self.solicitacoes, self.estados, self.status = c["solicitacoes"], c["estados"], c["status"]
        self.atualizado_em, self.fi, self.cadastro, self.abas_hotel = c["atualizado_em"], c["fi"], c["cadastro"], c["abas_hotel"]
        return True

    def atualizar_fi(self, forcar=False):
        """Fiscal Intelligence: o Mail Analytics grava 1x por dia, então reler a cada poucos minutos sobra."""
        if not self.fi_id or (not forcar and self.relogio() - self.fi_lido < self.fi_minutos * 60):
            return
        try:
            fi = fiscal_intelligence.ler(self.backend, self.fi_id, self.cadastro, self.desde, ignorar_hoteis=self.ignorar,
                                         lacunas_conhecidas=self.cfg.get("painel", {}).get("lacunas_conhecidas", {}),
                                         somam_fim_de_semana=self.cfg.get("painel", {}).get("somam_fim_de_semana"))
            with self.lock:
                self.fi, self.fi_erro = fi, ""
        except Exception as e:
            logger.warning(f"⚠️ Não consegui ler o Fiscal Intelligence ({e})")
            self.fi_erro = str(e)[:200]
        self.fi_lido = self.relogio()

    def atualizar_canceladas(self):
        """Arquivos (CANCELADA)/(SUBSTITUIDA) do Dropbox: a 1ª leitura dos PDFs leva minutos, então roda
        numa thread e as telas usam a última lista pronta."""
        if self.lendo_canceladas or self.relogio() - self.canceladas_lidas < CANCELADAS_MINUTOS * 60:
            return
        self.lendo_canceladas = True

        def ler():
            try:
                pastas = (self.cfg.get("dropbox_notas") or {}).get("pastas", [])
                cache = canceladas.ler_cache(CAMINHO_CANCELADAS)
                arquivos = canceladas.varrer(pastas, cache)
                canceladas.salvar_cache(CAMINHO_CANCELADAS, cache)
                with self.lock:
                    nomes, sols = list(self.cadastro.nomes()), list(self.solicitacoes)
                canceladas.atribuir_hoteis(arquivos, nomes, sols, self.cfg.get("apelidos_hoteis", {}),
                                           self.cfg.get("painel", {}).get("cnpj_hoteis", {}))
                with self.lock:
                    self.canceladas = arquivos
            except Exception:
                logger.exception("canceladas/substituídas do Dropbox")
            finally:
                self.canceladas_lidas, self.lendo_canceladas = self.relogio(), False

        threading.Thread(target=ler, daemon=True).start()

    def _periodo(self, ini, fim):
        hoje = datetime.date.today()
        ini = max(datetime.date.fromisoformat(ini) if ini else hoje.replace(day=1), self.desde)
        fim = min(datetime.date.fromisoformat(fim) if fim else hoje, hoje)
        return ini, max(fim, ini)

    def _ignorados(self):
        return {self.cadastro.canonico(h) or h for h in self.ignorar}

    def hoteis_por_agente(self):
        """[{hotel, agente}] do Cadastro_Hoteis (sem os ignorados): filtros de hotel e agente da caixa."""
        ign = self._ignorados()
        return [{"hotel": h, "agente": self.cadastro.dados(h).get("agente", "")} for h in self.cadastro.nomes() if h not in ign]

    def _fila_do_painel(self):
        ign = self._ignorados()
        return [s for s in self.fila(desde=self.desde.isoformat()) if s["hotel"] not in ign]

    def painel(self, ini, fim):
        ini, fim = self._periodo(ini, fim)
        hoje = datetime.date.today()
        fila = self._fila_do_painel()
        fi = self.fi or {"metricas": [], "fins_de_semana": {}, "saude": {}, "avisos": []}
        return {"ini": ini.isoformat(), "fim": fim.isoformat(), "desde": self.desde.isoformat(),
                "visao": metricas.visao_geral(fi["metricas"], fila, ini, fim, hoje, fi["fins_de_semana"], self.canceladas),
                "hoteis": metricas.tabela_hoteis(fi["metricas"], fila, ini, fim, hoje, self.cadastro, self._ignorados(),
                                                 self.canceladas),
                "saude": fi["saude"], "avisos": fi["avisos"], "fi_erro": self.fi_erro,
                "fi_lido_em": fi["lido_em"].isoformat(timespec="seconds") if fi.get("lido_em") else ""}

    def hotel(self, nome, ini, fim):
        ini, fim = self._periodo(ini, fim)
        fi = self.fi or {"metricas": [], "fins_de_semana": {}}
        return metricas.ficha_hotel(nome, fi["metricas"], self._fila_do_painel(), ini, fim,
                                    datetime.date.today(), fi["fins_de_semana"], self.cadastro, self.canceladas)

    def resumo_status(self):
        s = self.status
        return {"ligado": normalizar(s.get(STATUS_ROTULO_A1, "")) in ("true", "verdadeiro"),
                "ultima_execucao": s.get("Última execução com sucesso", ""),
                "resumo": s.get("Resumo da última execução", ""),
                "online": s.get("Robô online (último sinal)", ""),
                "comando": s.get("Comando", ""), "resposta": s.get("Resposta do robô", "")}


def criar_handler(estado, cfg, token, ultimo_uso, envio=None):
    pc = socket.gethostname()
    hosts_ok = {f"127.0.0.1:{PORTA}", f"localhost:{PORTA}"}
    envio = envio or Envio(ao_terminar=estado.atualizar)
    operadores = [k for k in cfg.get("agentes", {}) if not str(k).startswith("_")]

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def _json(self, corpo, codigo=200):
            dados_ = json.dumps(corpo, ensure_ascii=False, default=str).encode("utf-8")
            self.send_response(codigo)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(dados_)))
            self.end_headers()
            self.wfile.write(dados_)

        def _autorizado(self):
            # Host fixo barra DNS rebinding; token barra POST vindo de outra página aberta no navegador
            return self.headers.get("Host") in hosts_ok and self.headers.get("X-Token") == token

        def do_GET(self):
            ultimo_uso[0] = time.monotonic()
            if self.headers.get("Host") not in hosts_ok:
                return self._json({"erro": "host"}, 403)
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                html = (PASTA_UI / "index.html").read_text(encoding="utf-8").replace("__TOKEN__", token)
                corpo = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                return self.wfile.write(corpo)
            selo = re.fullmatch(r"/assinaturas/([a-z0-9]+)\.png", url.path)
            if selo and envio_nf.caminho_selo(selo.group(1)):
                corpo = envio_nf.caminho_selo(selo.group(1)).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                return self.wfile.write(corpo)
            estatico = ESTATICOS.get(url.path)
            if estatico:
                arquivo, tipo = estatico
                corpo = (PASTA_UI / arquivo).read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", tipo)
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Content-Length", str(len(corpo)))
                self.end_headers()
                return self.wfile.write(corpo)
            if not self._autorizado():
                return self._json({"erro": "não autorizado"}, 403)
            if url.path == "/api/estado":
                dias = int(parse_qs(url.query).get("dias", ["45"])[0] or 0)
                return self._json({
                    "agente": nome_do_agente(), "pc": pc, "erro": estado.erro, "operadores": operadores,
                    "atualizado_em": estado.atualizado_em.isoformat(timespec="seconds") if estado.atualizado_em else "",
                    "atualizar_segundos": int(cfg.get("app", {}).get("atualizar_segundos", 15)),
                    "status": estado.resumo_status(), "fila": estado.fila(dias), "pcs": estado.pcs(),
                    "hoteis": estado.hoteis_por_agente(),
                })
            if url.path == "/api/envio":
                def ler_status():
                    aba = cfg["aba_status"]
                    linhas = estado.backend.ler_abas(estado.central, [aba])[0].get(aba, [])
                    return {str(l[0]).strip(): (str(l[1]) if len(l) > 1 else "") for l in linhas if l}
                return self._json(envio.situacao(ler_status))
            q = {k: v[0] for k, v in parse_qs(url.query).items()}
            try:
                if url.path == "/api/envio_nf/opcoes":
                    return self._json(estado.opcoes_envio(q.get("chave", "")))
                if url.path == "/api/envio_nf/status":
                    return self._json(estado.situacao_envio(q.get("id", "")))
                if url.path == "/api/painel":
                    return self._json(estado.painel(q.get("ini"), q.get("fim")))
                if url.path == "/api/hotel":
                    return self._json(estado.hotel(q.get("nome", ""), q.get("ini"), q.get("fim")))
                if url.path == "/api/atividade":
                    return self._json(estado.atividade_resumo())
                if url.path == "/api/emails":
                    return self._json({"emails": estado.lista_emails(), "este_pc": pc})
                if url.path == "/api/email/opcoes":
                    return self._json(estado.opcoes_email(q.get("id", "")))
            except KeyError as e:
                return self._json({"erro": str(e).strip("'\"")}, 404)
            except ValueError as e:
                return self._json({"erro": f"parâmetro inválido: {e}"}, 400)
            return self._json({"erro": "não encontrado"}, 404)

        def do_POST(self):
            ultimo_uso[0] = time.monotonic()
            if not self._autorizado():
                return self._json({"erro": "não autorizado"}, 403)
            tamanho = int(self.headers.get("Content-Length") or 0)
            try:
                corpo = json.loads(self.rfile.read(tamanho) or b"{}")
            except ValueError:
                return self._json({"erro": "JSON inválido"}, 400)
            path = urlparse(self.path).path
            try:
                if path == "/api/acao":
                    r = estado.registrar(nome_do_agente(), pc, corpo["chave"], corpo["acao"], corpo.get("valor", ""))
                    return self._json(r)
                if path == "/api/agente":
                    nome = str(corpo.get("nome", "")).strip()[:40]
                    if nome not in operadores:
                        return self._json({"ok": False, "motivo": "operador desconhecido"}, 400)
                    salvar_json(CAMINHO_PREFS, {"agente": nome})
                    return self._json({"ok": True})
                if path == "/api/enviar":
                    if e_principal(carregar_config()):   # aqui mesmo: rápido e com log direto da memória
                        if not envio.iniciar_local(nome_do_agente()):
                            return self._json({"ok": False, "motivo": "Já tem um envio em andamento."})
                        return self._json({"ok": True, "modo": "local"})
                    quando = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
                    escrever_linhas_status(estado.backend, cfg, {LINHA_COMANDO: "ENVIAR",
                                                                 LINHA_PEDIDO: f"{nome_do_agente()} (Painel) | {quando}"})
                    envio.iniciar_remoto()
                    return self._json({"ok": True, "modo": "remoto"})
                if path == "/api/envio_nf":
                    return self._json(estado.pedir_envio(corpo, nome_do_agente()))
                if path == "/api/email/responder":
                    return self._json(estado.responder_email(corpo, nome_do_agente()))
                if path == "/api/comando":
                    return self._json(estado.pedir_comando(str(corpo.get("para", "")), str(corpo.get("comando", "")),
                                                           f"{nome_do_agente()} ({pc})"))
                if path == "/api/atualizar":
                    estado.atualizar()
                    estado.atualizar_fi(forcar=True)
                    return self._json({"ok": not estado.erro, "motivo": estado.erro})
            except KeyError as e:
                return self._json({"ok": False, "motivo": str(e).strip("'\"")}, 409)
            except ValueError as e:
                return self._json({"ok": False, "motivo": str(e)}, 400)
            except Exception as e:
                logger.exception("erro na API")
                return self._json({"ok": False, "motivo": f"Erro ao gravar na planilha: {e}"}, 500)
            return self._json({"erro": "não encontrado"}, 404)

    return Handler


def abrir_janela():
    """Abre o app (app_janela.py, pywebview). Sem pywebview instalado, cai pro Edge em modo aplicativo."""
    try:
        import webview  # noqa: F401
        pythonw = PASTA_PROJETO / ".venv" / "Scripts" / "pythonw.exe"
        subprocess.Popen([str(pythonw), str(PASTA_PROJETO / "src" / "app_janela.py")], cwd=str(PASTA_PROJETO))
        return
    except ImportError:
        pass
    edge = next((p for p in EDGE if os.path.exists(p)), None)
    url = f"http://127.0.0.1:{PORTA}/"
    if edge is None:
        import webbrowser
        return webbrowser.open(url)
    perfil = PASTA_ESTADO / "app_edge"   # perfil separado: a janela não se mistura com o Edge do usuário
    subprocess.Popen([edge, f"--app={url}", f"--user-data-dir={perfil}", "--window-size=1440,900",
                      "--no-first-run", "--no-default-browser-check"])


def porta_livre():
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", PORTA)) != 0


def main():
    sem_janela = "--sem-janela" in sys.argv
    if sem_janela:   # religado logo após matar o anterior: a porta pode levar uns segundos pra soltar
        limite = time.monotonic() + 10
        while not porta_livre() and time.monotonic() < limite:
            time.sleep(0.5)
    if not porta_livre():
        if not sem_janela:
            abrir_janela()
        return 0

    from sheets import BackendGoogle
    cfg = carregar_config()
    estado = Estado(BackendGoogle(caminho_chave_google(cfg)), cfg)
    if estado.carregar_cache():
        logger.info(f"📦 Último estado carregado do disco ({estado.atualizado_em:%d/%m %H:%M}) — atualizando em seguida.")
    token = secrets.token_urlsafe(24)
    ultimo_uso = [-1e9]
    servidor = ThreadingHTTPServer(("127.0.0.1", PORTA), criar_handler(estado, cfg, token, ultimo_uso))
    app = cfg.get("app", {})
    em_uso, em_fundo = int(app.get("atualizar_segundos", 15)), int(app.get("atualizar_segundos_fundo", 60))

    def laco():
        """Fica rodando enquanto o PC estiver ligado. Janela aberta: relê rápido; fechada: devagar (cota da API)."""
        while True:
            estado.atualizar()
            estado.atualizar_notas_emails()
            estado.atualizar_fi()
            estado.atualizar_canceladas()
            estado.salvar_cache()
            inicio = time.monotonic()
            while True:
                aberta = time.monotonic() - ultimo_uso[0] < JANELA_ABERTA_SEGUNDOS
                if time.monotonic() - inicio >= (em_uso if aberta else em_fundo):
                    break
                time.sleep(1)

    threading.Thread(target=laco, daemon=True).start()
    logger.info(f"🖥️ Painel Notas Fiscais no ar em http://127.0.0.1:{PORTA}/ · agente {nome_do_agente()}")
    if not sem_janela:
        abrir_janela()
    servidor.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
