"""Estado da rede entre os PCs: o que este PC responde aos outros e o que pergunta a eles."""

import datetime
import socket
import threading
import time

import atividade
import avisos_windows
import busca_outlook
import cota_google
import enviar_receber
import envio_pc_dono
import espelho_emails
import outlook_vivo
import rede_local
import rede_pcs
import saude
from config import e_principal, sem_outlook
from log_util import configurar_logging

logger = configurar_logging("app")

VERIFICAR_ATUALIZACAO_MINUTOS = 15
TELAS = {"visao": "Visão geral", "fila": "Notas fiscais", "correio": "E-mails", "log": "Log", "maquinas": "Máquinas"}   # pra Máquinas mostrar onde cada um está
SEM_REDE_SEGUNDOS = 300      # PC que não respondeu pela rede: 5 min usando a cópia, sem esperar
JANELA_ABERTA_SEGUNDOS = 90     # a janela pede dados a cada 15 s; sem pedido há 90 s = fechada
ATIVIDADE_CACHE_SEGUNDOS = 20



class RedeMixin:
    """Métodos de Estado (app_servidor.py) movidos para cá em 29/10/2026; mesma lógica, mesmo `self`."""

    # ---------- rede de PCs ----------
    def _extras_pc(self):
        """Colunas E-J da linha deste PC em PCs_Painel."""
        outlook = "sem Outlook" if sem_outlook(self.cfg) else (self.outlook or "?")
        leituras, escritas = cota_google.consumo_deste_pc()
        # "'" na frente: a planilha lê "09119e6" como número (9.12E+09) e estragaria a versão
        uso = getattr(self, "uso_ref", None)
        aberta = bool(uso and time.monotonic() - uso[0] < JANELA_ABERTA_SEGUNDOS)
        tela = TELAS.get(getattr(self, "vista_atual", ""), "")
        return [outlook, "'" + self.versao, self.cfg.get("papel", ""), rede_pcs.ultima_conferencia(),
                rede_local.endereco_deste_pc() if self.rede_ligada else "", f"'{leituras}/{escritas}",
                f"aberto|{tela}|{datetime.datetime.now():%H:%M}" if aberta else "fechado",
                saude.coluna(getattr(self, "saida_travada", 0), self._ultima_copia(), self._planilhas_sem_cadastro(),
                             self._ultimo_robo(), getattr(self, "ultimo_recebido", ""), getattr(self, "motivo_outlook", ""),
                             getattr(self, "caixas_senha", []))]

    def _rede(self, lidas, solicitacoes):
        if getattr(self, "so_ver", False):   # modo casa: só olha; não executa comando nem se registra como PC
            return
        pc, agente = socket.gethostname(), self._agente()
        linhas = []
        try:
            linhas += self._conferir_reinicio(agente)
        except Exception:
            logger.debug("conferir reinício", exc_info=True)
        try:
            linhas += self._conferencia_diaria(agente)
        except Exception:
            logger.debug("conferência diária", exc_info=True)
        if not self.versao_registrada:   # 1ª volta depois de ligar: registra se a versão mudou
            try:
                anterior = self._caminho_versao().read_text(encoding="utf-8").strip()
            except OSError:
                anterior = ""
            if anterior and anterior != self.versao:
                linhas.append(atividade.linha(atividade.ATUALIZADO, detalhe=f"de {anterior} para {self.versao}", agente=agente))
            self._caminho_versao().write_text(self.versao, encoding="utf-8")
            self.versao_registrada = True
        estado_outlook = None if sem_outlook(self.cfg) else rede_pcs.outlook_aberto()   # "aberto" | "sem janela" | "fechado" | None
        if estado_outlook is not None and estado_outlook != self.outlook:
            aberto = estado_outlook == "aberto"
            if self.outlook is not None or not aberto:
                tipo = atividade.OUTLOOK_ABERTO if aberto else atividade.OUTLOOK_FECHADO
                detalhe = ("o robô deste PC voltou a ler os e-mails das caixas daqui" if aberto else
                           "Outlook aberto sem janela: não baixa e-mail (o guardião vai abrir)" if estado_outlook == "sem janela"
                           else "o robô deste PC parou de ler os e-mails das caixas daqui")
                linhas.append(atividade.linha(tipo, detalhe=detalhe, agente=agente))
            self.outlook = estado_outlook
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
        for titulo, texto in self.avisos.outlook(self.pcs(), pc, e_principal(self.cfg)):   # Outlook parado (26/10/2026)
            avisos_windows.mostrar(titulo, texto)

    def pcs(self):
        return rede_pcs.ler_pcs(self.envio_nf.pcs_linhas)

    def atualizar_atividade(self, forcar=False):
        """Lê a aba Atividade_Robo do Google e guarda na memória. Chamado pelo laço do Painel, NUNCA pelo clique da tela."""
        _, lido = self.atividade_cache
        if not forcar and time.monotonic() - lido < ATIVIDADE_CACHE_SEGUNDOS:
            return
        linhas = self.backend.ler_abas(self.central, [atividade.ABA])[0].get(atividade.ABA, [])
        self.atividade_cache = (linhas, time.monotonic())

    def atividade_resumo(self):
        linhas, _ = self.atividade_cache   # só memória: o clique nunca espera o Google (29/10/2026); quem lê é o laço
        return {"pcs": self.pcs(), "eventos": atividade.ler(linhas, 400), "este_pc": socket.gethostname(),
                "versao": self.versao, "atualizacao": self.atualizacao}

    def _enderecos_rede(self, so_online=True):
        """PC que não respondeu pela rede nos últimos 5 min fica de fora (usuário, 15/10/2026: o e-mail e o histórico
        demoravam porque cada pedido esperava 12 s pelo PC da Clara, que está em outra faixa de rede): usa a cópia."""
        agora, fora = time.monotonic(), getattr(self, "_sem_rede", {})
        return {p["pc"]: p["rede"] for p in self.pcs() if p.get("rede") and (p["online"] or not so_online)
                and p["pc"] != socket.gethostname() and agora - fora.get(p["pc"], -1e9) > SEM_REDE_SEGUNDOS}

    def _anotar_rede(self, respostas):
        fora = self.__dict__.setdefault("_sem_rede", {})
        for pc, r in (respostas or {}).items():
            if "não respondeu pela rede" in str((r or {}).get("erro", "")):
                fora[pc] = time.monotonic()
            elif r and "erro" not in r:
                fora.pop(pc, None)

    # --- chamadas que chegam dos outros PCs (rede_local) ---
    def rede_buscar(self, corpo):
        if sem_outlook(getattr(self, "cfg", {})):   # PC só com o Painel: não tem caixa para pesquisar
            return {"resultados": [], "completo": True, "fonte": "sem_outlook", "pc": socket.gethostname()}
        indice = getattr(self, "indice", None)
        if indice is not None and not corpo.get("vivo") and indice.total():
            r = indice.buscar(corpo.get("q", ""), limite=min(int(corpo.get("limite") or busca_outlook.LIMITE_POR_PC), 200))
            return {"resultados": [{**x, "pc": socket.gethostname()} for x in r], "completo": self.montador.pronto,
                    "fonte": "indice", "pc": socket.gethostname()}
        import pythoncom
        pythoncom.CoInitialize()
        ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
        rapido = bool(corpo.get("so_enviados"))   # só os Itens Enviados, com limite de tempo curto
        r = busca_outlook.buscar(ns, self._caixas_de_hotel(), corpo.get("q", ""), socket.gethostname(),
                                 limite=min(int(corpo.get("limite") or busca_outlook.LIMITE_POR_PC), 200),
                                 tempo_maximo=min(float(corpo.get("tempo") or busca_outlook.TEMPO_MAXIMO), busca_outlook.TEMPO_MAXIMO),
                                 pastas=((5, "enviado"),) if rapido else busca_outlook.PASTAS)
        return {**r, "pc": socket.gethostname()}

    def rede_texto(self, corpo):
        """Texto inteiro de um e-mail das caixas deste PC: do espelho (já lido) ou direto do Outlook."""
        local = espelho_emails.item_local(str(corpo.get("id", ""))) if corpo.get("id") else {}
        if local and "texto" in local:
            return {"texto": local.get("texto", ""), "citado": local.get("citado", ""), "pc": socket.gethostname()}
        if not corpo.get("entry"):
            raise KeyError("e-mail não está mais no espelho deste PC")
        import pythoncom
        pythoncom.CoInitialize()
        ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
        return busca_outlook.abrir(ns, str(corpo["entry"]), self._caixas_de_hotel(), socket.gethostname())

    def rede_anexo(self, corpo):
        """Anexo de um e-mail das caixas deste PC (foto, PDF do hóspede) pra ver no Painel. Só leitura."""
        entry = str(corpo.get("entry") or "") or espelho_emails.item_local(str(corpo.get("id", ""))).get("entry_id", "")
        if not entry:
            raise KeyError("e-mail não está mais no espelho deste PC")
        import pythoncom
        pythoncom.CoInitialize()
        ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
        return {**busca_outlook.ler_anexo(ns, entry, self._caixas_de_hotel(), str(corpo.get("nome", ""))), "pc": socket.gethostname()}

    def rede_enviar(self, corpo):
        """Pedido do robô (PC principal, 15/10/2026): manda o e-mail do formulário da própria caixa do hotel, que
        está neste Outlook, para ela mesma (envio_pc_dono.enviar_aqui)."""
        import pythoncom
        pythoncom.CoInitialize()
        app = outlook_vivo.aplicativo()
        return envio_pc_dono.enviar_aqui(app, app.GetNamespace("MAPI"), corpo, self._caixas_de_hotel())

    def rede_conferir_envio(self, corpo):
        import pythoncom
        pythoncom.CoInitialize()
        return envio_pc_dono.conferir_aqui(outlook_vivo.aplicativo().GetNamespace("MAPI"), corpo, self._caixas_de_hotel())

    def rede_enviar_receber(self, _corpo):
        """Outro PC (ou este Painel) pede o Enviar/Receber deste Outlook (27/10/2026): roda e espera acabar."""
        if not outlook_vivo.pode_usar():
            return {"erro": "Outlook fechado neste PC"}
        import pythoncom
        pythoncom.CoInitialize()
        r = enviar_receber.rodar_aqui(outlook_vivo.aplicativo().GetNamespace("MAPI"))
        self.versao_tela += 1
        return r

    def rede_caixas(self, _corpo):
        """Outro PC (ou este Painel) pergunta quais caixas daqui têm e-mail preso (27/10/2026)."""
        return {"pc": socket.gethostname(), "caixas": list(getattr(self, "caixas_presas", []) or [])}

    def rede_reiniciar_outlook(self, _corpo):
        """Fecha à força e abre de novo o Outlook DESTE PC (27/10/2026: o que o João fazia à mão quando parava de enviar)."""
        import pythoncom
        pythoncom.CoInitialize()
        r = outlook_vivo.reiniciar()
        self.versao_tela += 1
        return r

    def rede_ping(self, _corpo):
        return {"pc": socket.gethostname(), "agente": self._agente(), "versao": self.versao}

    def rede_novidade(self, corpo):
        """O robô deste PC (ou o Painel de outro PC, repassando) gravou e-mail/NF novo na Central (21/10/2026): o laço
        relê já. Do robô daqui: repassa aos outros PCs uma vez (o repassado não é repassado de novo)."""
        acordar = self.__dict__.setdefault("acordar", threading.Event())
        if str((corpo or {}).get("o_que", "")) == "formulario":   # cópia rápida (23/10/2026): relê as abas dos hotéis já
            self.hoteis_lidos_em = -1e9
        acordar.set()
        if not (corpo or {}).get("repassado"):
            threading.Thread(target=self._repassar_novidade, args=(dict(corpo or {}),), daemon=True).start()
        return {"ok": True}

    def _repassar_novidade(self, corpo):
        enderecos = self._enderecos_rede()
        if not enderecos or not getattr(self, "segredo", None):
            return
        self._anotar_rede(rede_local.perguntar_a_todos(self.segredo, enderecos, "novidade",
                                                       {"o_que": str(corpo.get("o_que", ""))[:20], "repassado": True},
                                                       tempo=5))

    def rede_envio_nf(self, corpo):
        """Envio direto (21/10/2026): outro PC gravou um pedido para a caixa que está aqui e avisa na hora."""
        return self.envio_nf.receber_pela_rede(corpo)
