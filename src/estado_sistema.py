"""Estado do sistema: versão e atualização, comandos entre PCs, saúde e os vigias em segundo plano."""

import datetime
import socket
import threading
import time

import atividade
import atualizador
import envio_nf
import indice_emails
import outlook_vivo
import rede_pcs
import saude
from config import PASTA_ESTADO, e_principal
from log_util import configurar_logging

logger = configurar_logging("app")


DROPBOX_OLHAR_SEGUNDOS = 10   # pasta de notas do Dropbox: mudou = NF nova, refaz a lista e as NFs dos e-mails já
REINICIO_PENDENTE_MIN = 5          # código novo na pasta e o Painel ainda no velho por mais que isso: pede o reinício de novo


class SistemaMixin:
    """Métodos de Estado (app_servidor.py) movidos para cá em 29/10/2026; mesma lógica, mesmo `self`."""

    def _ultimo_robo(self):
        """Quando o robô de envio (main.py, a cada 10 min no principal) terminou por último: aba Status (coluna B)."""
        if not e_principal(self.cfg):
            return ""
        q = str((self.status or {}).get("ultima_execucao", "")).strip()
        try:
            return datetime.datetime.strptime(q[:19], "%d/%m/%Y %H:%M:%S").isoformat(timespec="seconds")
        except ValueError:
            return ""

    def problemas_de_saude(self):
        """Faixa de saúde: o que os PCs publicam + o atraso do Mail Analytics (do relatório guardado)."""
        lista = saude.problemas(self.pcs())
        lista += saude.pedidos_sem_envio(list(getattr(self, "solicitacoes", []) or []))   # pedido parado (15/10/2026)
        rel = getattr(self, "_ultimo_relatorio", None)
        if rel:
            lista += saude.mail_analytics_atrasado(rel.get("ultimo_dia"), datetime.date.today())
        return lista

    def _ultima_copia(self):
        """Quando a cópia dos hotéis deu certo pela última vez (só o PC principal copia)."""
        if not e_principal(self.cfg):
            return ""
        try:
            return (PASTA_ESTADO / "ultima_copia.txt").read_text(encoding="utf-8").strip()[:19]
        except OSError:
            return ""

    def iniciar_indice(self):
        """Índice local dos e-mails deste PC (pesquisa instantânea, 20/10/2026): monta aos poucos numa linha de fundo."""
        try:
            self.indice = indice_emails.Indice()
        except Exception as e:
            logger.warning(f"⚠️ Índice de e-mails não abriu ({e}) — a pesquisa continua direto no Outlook")
            return
        self.montador = indice_emails.Montador(self.indice)

        def rodar():
            import pythoncom
            pythoncom.CoInitialize()
            while True:
                pausa = 120
                try:
                    if outlook_vivo.pode_usar():   # nunca cria um Outlook escondido; o guardião do conferente abre
                        ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
                        pausa = self.montador.passo(ns, self._caixas_de_hotel())
                except Exception as e:
                    logger.debug(f"índice de e-mails: {e}")
                    pausa = 60
                time.sleep(pausa)
        threading.Thread(target=rodar, daemon=True, name="indice_emails").start()

    def vigiar_caixa_de_saida(self):
        """A cada 2 min conta os e-mails parados há mais de 10 min na Caixa de Saída do Outlook deste PC (só lê)."""
        def rodar():
            import pythoncom
            pythoncom.CoInitialize()
            while True:
                try:
                    if not outlook_vivo.pode_usar():   # nunca cria um Outlook escondido; o guardião do conferente abre
                        time.sleep(120)
                        continue
                    ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
                    limite = datetime.datetime.now() - datetime.timedelta(minutes=saude.SAIDA_TRAVADA_MIN)
                    vistos, presos = set(), 0
                    self.ultimo_recebido = saude.ultimo_recebido(ns) or getattr(self, "ultimo_recebido", "")
                    try:   # por que o Outlook parou (26/10/2026): Trabalhar Offline, janela de senha, certificado
                        self.motivo_outlook = saude.motivo_outlook(ns)
                        self.caixas_senha = saude.caixas_pedindo_senha() if self.motivo_outlook == "senha" else []
                    except Exception:
                        self.motivo_outlook = ""
                        self.caixas_senha = []
                    for pasta in [ns.GetDefaultFolder(4)] + [c.DeliveryStore.GetDefaultFolder(4) for c in ns.Accounts]:
                        try:
                            if pasta.EntryID in vistos:
                                continue
                            vistos.add(pasta.EntryID)
                            for item in pasta.Items:
                                quando = item.LastModificationTime
                                if datetime.datetime(quando.year, quando.month, quando.day, quando.hour, quando.minute) < limite:
                                    presos += 1
                        except Exception:
                            continue
                    if presos and presos != getattr(self, "saida_travada", 0):
                        logger.warning(f"⚠️ Caixa de Saída do Outlook: {presos} e-mail(s) parado(s) há mais de "
                                       f"{saude.SAIDA_TRAVADA_MIN} min")
                    self.saida_travada = presos
                    try:
                        self.caixas_presas = saude.presos_por_conta(ns)   # por conta, pro botão "caixas com problema"
                    except Exception:
                        self.caixas_presas = []
                except Exception:
                    logger.debug("Caixa de Saída", exc_info=True)
                time.sleep(120)

        threading.Thread(target=rodar, daemon=True).start()

    def _conferencia_diaria(self, agente):
        """Teste diário automático (usuário, 11/10/2026): 1 vez por dia, depois das 8h, o PC principal confere a
        cópia dos hotéis, o robô de envio, a Caixa de Saída, o Outlook e o robô de cada PC, a versão e o Mail
        Analytics, e deixa o resultado no Log. Os mesmos problemas aparecem na hora na faixa de saúde."""
        hoje = datetime.date.today().isoformat()
        if not e_principal(self.cfg) or datetime.datetime.now().strftime("%H:%M") < "08:00" or                 getattr(self, "_conferido_em", "") == hoje:
            return []
        self._conferido_em = hoje
        try:
            self.relatorio_semana(0)   # lê o Mail Analytics (só leitura) pra saber se ele está em dia
        except Exception as e:
            logger.warning(f"⚠️ Conferência diária: não li a planilha do Mail Analytics ({e})")
        problemas = self.problemas_de_saude()
        if problemas:
            texto = f"conferência diária: {len(problemas)} problema(s) — " + " · ".join(p["texto"] for p in problemas)[:180]
            logger.warning(f"⚠️ Conferência diária: {len(problemas)} problema(s)")
            return [atividade.linha(atividade.FALHA, detalhe=texto, agente=agente)]
        logger.info("✅ Conferência diária: tudo funcionando")
        return [atividade.linha(atividade.ATUALIZADO, detalhe="conferência diária: tudo funcionando ✓ (cópia, envio, "
                                "Caixa de Saída, Outlook, robôs, versões e Mail Analytics)", agente=agente)]

    def _conferir_reinicio(self, agente):
        """O código na pasta mudou e este Painel ainda roda o velho (o reinício não aconteceu): depois de
        REINICIO_PENDENTE_MIN avisa no Log e pede o reinício de novo, 1 vez por versão (11/10/2026)."""
        if time.monotonic() < getattr(self, "_proximo_conferir_versao", 0):
            return []
        self._proximo_conferir_versao = time.monotonic() + 60
        na_pasta = envio_nf.versao_do_codigo()
        if not na_pasta or not self.versao or na_pasta.startswith(self.versao[:7]):
            self._versao_nova_desde = None
            return []
        desde = getattr(self, "_versao_nova_desde", None)
        if desde is None or desde[0] != na_pasta:
            self._versao_nova_desde = (na_pasta, time.monotonic(), False)
            return []
        if desde[2] or time.monotonic() - desde[1] < REINICIO_PENDENTE_MIN * 60:
            return []
        self._versao_nova_desde = (na_pasta, desde[1], True)
        logger.warning(f"⚠️ Código novo na pasta ({na_pasta}), mas este Painel ainda roda o {self.versao}: pedindo o reinício de novo")
        try:
            como = atualizador.pedir_reinicio()
        except Exception as e:
            como = f"o Agendador recusou ({str(e)[:80]})"
        return [atividade.linha(atividade.FALHA, detalhe=f"código {na_pasta} baixado, mas o PC continuava no {self.versao}: {como}",
                                agente=agente)]

    def _verificar_atualizacao(self, automatica, pedido_por=""):
        s = atualizador.situacao(so_etiquetadas=automatica)   # automática: só versão com etiqueta (canal de teste, 27/10/2026)
        motivo = atualizador.motivo_para_nao(s)
        self.atualizacao = {"verificado_em": datetime.datetime.now().isoformat(timespec="seconds"),
                            "motivo": motivo, "atras": s["atras"]}
        if atualizador.pode_atualizar(s):
            quem = "automática" if automatica else f"pedida por {pedido_por}"
            na_pasta_antes = envio_nf.versao_do_codigo()
            ok, texto, reiniciou = atualizador.atualizar(so_etiquetadas=automatica)
            if ok and not reiniciou:   # só documentação: o código que roda é o mesmo da versão nova
                self._adotar_versao_sem_reiniciar(na_pasta_antes)
            atividade.registrar(self.backend, self.central, [atividade.linha(
                atividade.ATUALIZADO if ok else atividade.FALHA,
                detalhe=f"atualização {quem} ({s['atras']} commit(s) novo(s)): {texto}", agente=self._agente())])
            return texto
        na_pasta = envio_nf.versao_do_codigo()
        if not automatica and atualizador.precisa_reiniciar(s, self.versao, na_pasta):   # pedido: só reinicia
            como = atualizador.so_reiniciar()
            texto = f"código {na_pasta[:7]} já estava na pasta, o Painel rodava {self.versao.split(' ')[0]}: {como}"
            atividade.registrar(self.backend, self.central, [atividade.linha(
                atividade.ATUALIZADO, detalhe=f"atualização pedida por {pedido_por}: {texto}", agente=self._agente())])
            return texto
        return motivo

    def _adotar_versao_sem_reiniciar(self, na_pasta_antes):
        """Atualização só de documentação (21/10/2026): passa a valer a versão nova sem reiniciar, pra a faixa de saúde
        e o _conferir_reinicio não pedirem reinício. Só se este Painel já rodava o código da pasta: com um reinício
        pendente de antes (código novo baixado e não reiniciado), fica como está e o _conferir_reinicio cuida."""
        nova = envio_nf.versao_do_codigo()
        if not nova or not na_pasta_antes or not self.versao or not na_pasta_antes.startswith(self.versao[:7]):
            return
        self.versao = nova
        try:
            self._caminho_versao().write_text(nova, encoding="utf-8")
        except OSError:
            logger.debug("versao_rodando.txt", exc_info=True)

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

    def marca_tela(self):
        """Muda quando a tela tem dado novo pra buscar (velocidade 3, 21/10/2026): leitura da Central, NF do Dropbox ou
        envio que terminou. A tela pergunta isto a cada 3 s e só relê quando muda."""
        envio = getattr(self, "envio_nf", None)
        locais = list(getattr(envio, "locais", {}).values())
        feitos = sum(1 for v in locais if (v or {}).get("estado") in ("enviado", "falhou"))
        return f"{getattr(self, 'versao_tela', 0)}.{len(locais)}.{feitos}"

    def olhar_dropbox(self):
        """Pasta de notas do Dropbox mudou (NF nova)? Refaz a lista e as NFs dos e-mails na hora (21/10/2026; antes a
        lista valia 5 min e as NFs dos e-mails 2 min). -> True quando mudou."""
        if time.monotonic() - self.dropbox_olhado < DROPBOX_OLHAR_SEGUNDOS:
            return False
        self.dropbox_olhado = time.monotonic()
        marca = envio_nf.marca_das_pastas(self.cfg)
        antes, self.marca_dropbox = self.marca_dropbox, marca
        if antes is None or marca == antes:
            return False
        envio_nf.listar_notas_dropbox(self.cfg, forcar=True)
        self.atualizar_notas_emails(forcar=True)
        self.versao_tela += 1
        logger.info("🧾 NF nova no Dropbox — NFs dos e-mails refeitas")
        return True
