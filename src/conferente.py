"""Processo contínuo de cada PC.

Todos: acompanham Itens Enviados e o Dropbox e atualizam selo/tags dos e-mails de solicitação.
Só o principal: atende os comandos do menu da planilha e publica sinal de vida e cota de envio.
"""
import datetime
import logging
import msvcrt
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_utf8 import garantir_utf8

garantir_utf8()

from config import PASTA_ESTADO, ErroDeConfig, carregar_config, e_principal
from controle_nf import (CORES_CATEGORIAS, MINIMO_TEXTO_LEGIVEL, abrir_registro, assunto_com_contador, e_email_do_robo,
                         ler_assunto_nf, categorias_atualizadas, nfs_sem_prova, paragrafo_status, reconferir, resumo_email,
                         trocar_paragrafo_status)
from log_util import configurar_logging
import outlook_vivo

logger = configurar_logging("conferente")

CAMINHO_REGISTRO = PASTA_ESTADO / "controle_nf.json"
CLASSE_EMAIL = 43
MAX_ITENS_POR_CONTA = 3000
SOBREPOSICAO = datetime.timedelta(minutes=5)   # relê um pouco pra trás; aplicar é idempotente


def _data_outlook(valor):
    # Contas POP: SentOn/ReceivedTime vêm com a hora local marcada como UTC
    return valor.replace(tzinfo=None) if getattr(valor, "tzinfo", None) else valor


def _enderecos(item):
    enderecos = set()
    try:
        for r in item.Recipients:
            endereco = (r.Address or "").strip().lower()
            if "@" not in endereco:
                try:
                    endereco = r.AddressEntry.GetExchangeUser().PrimarySmtpAddress.lower()
                except Exception:
                    continue
            enderecos.add(endereco)
    except Exception:
        pass
    return enderecos


SCRIPT_OCR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Automacoes", "ler_pdf_ocr.ps1")
_textos_lidos = {}   # EntryID -> texto


def _texto_pdf(caminho):
    try:
        from pypdf import PdfReader
        return "\n".join((p.extract_text() or "") for p in PdfReader(caminho).pages[:5])
    except Exception:
        return ""


def _texto_ocr(caminho):
    """OCR nativo do Windows via Automacoes/ler_pdf_ocr.ps1, para PDF que é imagem."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", SCRIPT_OCR, caminho],
                           capture_output=True, timeout=120, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return r.stdout.decode("utf-8", errors="replace")
    except Exception as e:
        logger.debug(f"OCR falhou ({e})")
        return ""


def texto_da_nota(item):
    """Texto de todos os anexos PDF/XML do e-mail, em cache por EntryID."""
    chave = item.EntryID
    if chave in _textos_lidos:
        return _textos_lidos[chave]
    pasta = tempfile.mkdtemp(prefix="nf_")
    partes = []
    try:
        for i, anexo in enumerate(item.Attachments):
            nome = (anexo.FileName or "").lower()
            if not nome.endswith((".pdf", ".xml")):
                continue
            caminho = os.path.join(pasta, f"anexo{i}{os.path.splitext(nome)[1]}")
            anexo.SaveAsFile(caminho)
            partes.append(_ler_arquivo_de_nota(caminho))
    except Exception as e:
        logger.warning(f"⚠️ Não consegui abrir o anexo de \"{item.Subject}\" ({e}).")
    finally:
        shutil.rmtree(pasta, ignore_errors=True)
    _textos_lidos[chave] = "\n".join(partes)
    return _textos_lidos[chave]


def _ler_arquivo_de_nota(caminho):
    if caminho.lower().endswith(".xml"):
        with open(caminho, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    texto = _texto_pdf(caminho)
    if len(texto.strip()) < MINIMO_TEXTO_LEGIVEL:
        texto = _texto_ocr(caminho) or texto
    return texto


def texto_de_arquivo_dropbox(caminho_original):
    """Lê uma cópia temporária: o arquivo original do Dropbox nunca é aberto nem tocado."""
    pasta = tempfile.mkdtemp(prefix="nf_dropbox_")
    try:
        copia = os.path.join(pasta, "nota" + os.path.splitext(caminho_original)[1].lower())
        shutil.copyfile(caminho_original, copia)
        return _ler_arquivo_de_nota(copia)
    except Exception as e:
        logger.debug(f"Não consegui ler {caminho_original} ({e})")
        return ""
    finally:
        shutil.rmtree(pasta, ignore_errors=True)


MAX_NOTAS_DROPBOX_POR_VOLTA = 60
_proxima_dropbox = 0.0


def _nome_da_fonte(pasta):
    """'...\\PC 2 - CLARA\\Notas Fiscais Hóspedes\\2026 - CLARA' -> 'PC 2 - CLARA'"""
    return next((p for p in pasta.replace("/", "\\").split("\\") if p.upper().startswith("PC ")), os.path.basename(pasta))


def varrer_dropbox(registro, cfg, agora):
    """Somente leitura. -> quantas solicitações ganharam ✅"""
    global _proxima_dropbox
    conf = cfg.get("dropbox_notas") or {}
    if not conf.get("ativo") or time.monotonic() < _proxima_dropbox:
        return 0
    mais_antiga = registro.data_mais_antiga_aberta()
    if not mais_antiga:
        return 0
    limite = max(datetime.datetime.fromisoformat(mais_antiga) - datetime.timedelta(days=1),
                 agora - datetime.timedelta(days=int(cfg["conferencia"]["dias_maximos"])))

    novos = []
    for pasta in conf.get("pastas", []):
        fonte = _nome_da_fonte(pasta)
        try:
            with os.scandir(pasta) as entradas:   # sem recursão, de propósito
                for e in entradas:
                    if not e.is_file() or not e.name.lower().endswith((".pdf", ".xml")):
                        continue
                    modificado = datetime.datetime.fromtimestamp(e.stat().st_mtime)
                    if modificado < limite:
                        continue
                    marca = modificado.isoformat(timespec="seconds")
                    if registro.dropbox.get(e.path) == marca:
                        continue
                    nf = ler_assunto_nf(os.path.splitext(e.name)[0])
                    if not nf:
                        registro.dropbox[e.path] = marca
                        continue
                    novos.append((modificado, e.path, nf, fonte, marca))
        except OSError as e:
            logger.warning(f"⚠️ Não consegui olhar a pasta do Dropbox {pasta} ({e}).")

    novos.sort(reverse=True)
    mudancas = 0
    for modificado, caminho, nf, fonte, marca in novos[:MAX_NOTAS_DROPBOX_POR_VOLTA]:
        ref = registro.aplicar_nota_dropbox(caminho, nf, modificado,
                                            lambda c=caminho: texto_de_arquivo_dropbox(c), fonte)
        registro.dropbox[caminho] = marca
        if ref:
            sol = registro.solicitacoes[ref]
            logger.info(f"✅ NF {nf[0]} (Dropbox, {fonte}) · {sol['hotel']} · {sol['nome']} — "
                        f"{sol['nfs'][nf[0]]['prova']}")
            mudancas += 1
    faltam = len(novos) - MAX_NOTAS_DROPBOX_POR_VOLTA
    if faltam > 0:
        logger.info(f"📂 Dropbox: faltam {faltam} nota(s) pra ler — continuo na próxima volta.")
    else:
        _proxima_dropbox = time.monotonic() + 60 * int(conf.get("intervalo_minutos", 5))
    corte = limite.isoformat(timespec="seconds")
    for caminho in [c for c, m in registro.dropbox.items() if m < corte]:
        del registro.dropbox[caminho]
    return mudancas


def _anexos(item):
    try:
        return [a.FileName for a in item.Attachments]
    except Exception:
        return []


def varrer_enviados(namespace, registro, cfg, agora):
    """Aplica os enviados novos de todas as contas. -> quantos mudaram alguma solicitação"""
    mais_antiga = registro.data_mais_antiga_aberta()
    if not mais_antiga:
        return 0
    conf = cfg["conferencia"]
    limite = max(datetime.datetime.fromisoformat(mais_antiga) - datetime.timedelta(days=1),
                 agora - datetime.timedelta(days=int(conf["dias_maximos"])))
    extensoes = conf["extensoes_anexo_nf"]
    mudancas = 0

    for conta in namespace.Accounts:
        smtp = (conta.SmtpAddress or "").strip().lower()
        try:
            pasta = conta.DeliveryStore.GetDefaultFolder(5)   # olFolderSentMail
            itens = pasta.Items
            itens.Sort("[SentOn]", True)
        except Exception as e:
            logger.warning(f"⚠️ Não consegui abrir Itens Enviados de {smtp}: {e}")
            continue

        marca = registro.varredura.get(smtp)
        corte = max(limite, datetime.datetime.fromisoformat(marca) - SOBREPOSICAO) if marca else limite
        mais_novo = datetime.datetime.fromisoformat(marca) if marca else None
        for i, item in enumerate(itens):
            if i >= MAX_ITENS_POR_CONTA:
                break
            try:
                if getattr(item, "Class", CLASSE_EMAIL) != CLASSE_EMAIL:
                    continue
                enviado_em = _data_outlook(item.SentOn)
                if enviado_em < corte:
                    break
                if mais_novo is None or enviado_em > mais_novo:
                    mais_novo = enviado_em
                if registro.ja_processado(item.EntryID):
                    continue
                resultado = registro.aplicar_envio({
                    "entry_id": item.EntryID, "conta": smtp, "destinatarios": _enderecos(item),
                    "assunto": item.Subject or "", "data": enviado_em, "anexos": _anexos(item),
                }, extensoes, ler_texto=lambda item=item: texto_da_nota(item))
            except Exception as e:
                logger.debug(f"Item ilegível em {smtp}: {e}")
                continue
            if resultado:
                ref, tipo = resultado
                sol = registro.solicitacoes[ref]
                prova = ""
                if tipo == "nf":
                    nf = next((d for d in sol["nfs"].values() if d["entry_id"] == item.EntryID), {})
                    prova = f" — {'confira: ' if nf.get('conferir') else ''}{nf.get('prova', '')}"
                logger.info(f"{'✅ NF' if tipo == 'nf' else '💬 Tratativa'} · {sol['hotel']} · {sol['nome']} "
                            f"· \"{item.Subject}\" ({ref}){prova}")
                mudancas += 1
        if mais_novo:
            registro.varredura[smtp] = mais_novo.isoformat(timespec="seconds")
    return mudancas


def reconferir_antigas(namespace, registro):
    """Relê notas marcadas antes da conferência por conteúdo existir; desfaz o ✅ se não baterem."""
    mudancas = 0
    for ref, numero, entry_id in nfs_sem_prova(registro):
        try:
            texto = texto_da_nota(namespace.GetItemFromID(entry_id))
        except Exception as e:
            logger.debug(f"Não achei o e-mail da NF {numero} pra reconferir ({e})")
            continue
        resultado, prova = reconferir(registro, ref, numero, texto)
        sol = registro.solicitacoes[ref]
        if resultado == "nao_confere":
            logger.warning(f"↩️ NF {numero} NÃO é de {sol['nome']} ({sol['hotel']}) — desfiz o ✅. ({prova})")
        else:
            logger.info(f"🔎 NF {numero} reconferida pra {sol['nome']}: {resultado} — {prova}")
        mudancas += 1
    return mudancas


def _conta_por_smtp(namespace, smtp):
    for conta in namespace.Accounts:
        if (conta.SmtpAddress or "").strip().lower() == smtp:
            return conta
    return None


def _procurar_consolidado(pasta, codigo, profundidade=0):
    """Busca pelo código do rodapé, incluindo subpastas (a equipe move os e-mails)."""
    try:
        itens = pasta.Items
        itens.Sort("[ReceivedTime]", True)
        for i, item in enumerate(itens):
            if i >= 300:
                break
            try:
                if codigo in (item.Body or "") and e_email_do_robo(item.Subject, item.Body, codigo):
                    return item
            except Exception:
                continue
    except Exception:
        pass
    if profundidade < 2:
        try:
            for sub in pasta.Folders:
                achado = _procurar_consolidado(sub, codigo, profundidade + 1)
                if achado is not None:
                    return achado
        except Exception:
            pass
    return None


def _esta_aberto(outlook, item):
    try:
        for janela in outlook.Inspectors:
            if janela.CurrentItem.EntryID == item.EntryID:
                return True
    except Exception:
        pass
    return False


def atualizar_consolidados(outlook, namespace, registro):
    """Reescreve selo, contador do assunto e categorias dos e-mails recebidos marcados pra atualizar."""
    atualizados = 0
    for codigo, dados in registro.emails.items():
        if not dados.get("precisa_atualizar"):
            continue
        conta = _conta_por_smtp(namespace, dados["destinatario"])
        if conta is None:
            if not dados.get("avisado_fora"):
                logger.warning(f"⚠️ {codigo} foi pra {dados['destinatario']}, que não está neste Outlook — "
                               f"o selo ✅ só aparece se o conferente rodar na máquina dessa caixa.")
                dados["avisado_fora"] = True
            continue

        item = None
        if dados.get("entry_id_recebido"):
            try:
                item = namespace.GetItemFromID(dados["entry_id_recebido"], conta.DeliveryStore.StoreID)
                if codigo not in (item.Body or "") or not e_email_do_robo(item.Subject, item.Body, codigo):
                    item = None
            except Exception:
                item = None
        if item is None:
            item = _procurar_consolidado(conta.DeliveryStore.GetDefaultFolder(6), codigo)   # olFolderInbox
        if item is None:
            logger.info(f"ℹ️ Ainda não achei o consolidado {codigo} na caixa de {dados['destinatario']} "
                        f"(pode não ter chegado) — tento de novo na próxima volta.")
            continue
        dados["entry_id_recebido"] = item.EntryID

        if _esta_aberto(outlook, item):   # salvar com o inspector aberto gera conflito de versão
            logger.info(f"ℹ️ {codigo} está aberto numa janela — atualizo quando fechar.")
            continue

        solicitacoes = [registro.solicitacoes[r] for r in dados["refs"] if r in registro.solicitacoes]
        corpo = item.HTMLBody
        sem_marcador = 0
        for ref in dados["refs"]:
            if ref not in registro.solicitacoes:
                continue
            corpo, achou = trocar_paragrafo_status(corpo, ref, paragrafo_status(ref, registro.solicitacoes[ref]))
            sem_marcador += 0 if achou else 1
        feitas, total, tem_tratativa = resumo_email(solicitacoes)
        item.HTMLBody = corpo
        item.Subject = assunto_com_contador(item.Subject, feitas, total)
        item.Categories = categorias_atualizadas(item.Categories, feitas, total, tem_tratativa)
        item.Save()
        dados["precisa_atualizar"] = False
        atualizados += 1
        aviso = f" ({sem_marcador} bloco(s) sem marcador — e-mail antigo?)" if sem_marcador else ""
        logger.info(f"📝 {codigo} atualizado: {feitas}/{total} ✅{aviso}")
    return atualizados


def garantir_categorias(namespace):
    try:
        existentes = {c.Name for c in namespace.Categories}
        for nome, cor in CORES_CATEGORIAS.items():
            if nome not in existentes:
                namespace.Categories.Add(nome, cor)
    except Exception as e:
        logger.debug(f"Não consegui criar as categorias coloridas ({e}) — o texto aparece do mesmo jeito.")


NOTAS_DIVIDIDAS_SEGUNDOS = 10 * 60
ESPELHO_EMAILS_SEGUNDOS = 2 * 60   # aba E-mails do Painel: pendentes das caixas deste PC
CONFIRMAR_NFS_SEGUNDOS = 2 * 60   # NF enviada / tratativa / e-mail do hóspede chegam na fila de todos em ~2 min
VIGIA_SEGUNDOS = 20               # vigia_outlook: só olha; e-mail novo antecipa a conferência e o espelho
MIN_ENTRE_CONFERENCIAS = 30       # conferência completa leva ~15 s: no máximo uma a cada 30 s por PC
_ja_olhados = set()


def _e_email_de_solicitacao(item, remetente_antigo):
    try:
        corpo = item.Body or ""
        return ("Código de envio: NF-" in corpo) or str(item.SenderEmailAddress or "").lower() == remetente_antigo
    except Exception:
        return False


def marcar_notas_divididas(namespace, cfg, dias=45, so_conta=None):
    """Categoria "Nota dividida" nos e-mails de solicitação (dos dois robôs) que pedem mais de uma nota."""
    from controle_nf import CATEGORIA_DIVIDIDA, pede_nota_dividida
    remetente_antigo = str(cfg.get("robo_antigo", {}).get("remetente", "redeandrade.notafiscal@gmail.com")).lower()
    desde = datetime.datetime.now() - datetime.timedelta(days=dias)
    marcados = 0
    for conta in namespace.Accounts:
        if so_conta and (conta.SmtpAddress or "").lower() != so_conta:
            continue
        try:
            itens = conta.DeliveryStore.GetDefaultFolder(6).Items
            itens.Sort("[ReceivedTime]", True)
        except Exception:
            continue
        for item in itens:
            try:
                if item.ReceivedTime.replace(tzinfo=None) < desde:
                    break
                chave = item.EntryID
            except Exception:
                continue
            if chave in _ja_olhados:
                continue
            _ja_olhados.add(chave)
            if not _e_email_de_solicitacao(item, remetente_antigo):
                continue
            atuais = [c.strip() for c in re.split(r"[;,]", item.Categories or "") if c.strip()]
            if CATEGORIA_DIVIDIDA in atuais or not pede_nota_dividida(item.Body or ""):
                continue
            item.Categories = ", ".join(atuais + [CATEGORIA_DIVIDIDA])
            item.Save()
            marcados += 1
            logger.info(f"🔀 Nota dividida: '{(item.Subject or '')[:70]}' ({conta.SmtpAddress})")
    return marcados


def uma_volta(outlook, namespace, cfg, agora=None):
    import controle_nf
    controle_nf.VISUAL = cfg.get("visual_email", "classico")
    agora = agora or datetime.datetime.now()
    with abrir_registro(CAMINHO_REGISTRO) as registro:
        if not registro.emails:
            return 0, 0
        mudancas = varrer_enviados(namespace, registro, cfg, agora)
        mudancas += reconferir_antigas(namespace, registro)
        mudancas += varrer_dropbox(registro, cfg, agora)
        mudancas += registro.igualar_gemeas()
        atualizados = atualizar_consolidados(outlook, namespace, registro)
    return mudancas, atualizados


def _travar_instancia_unica():
    """-> arquivo travado (manter aberto enquanto o processo vive) | None se já há outro."""
    os.makedirs(PASTA_ESTADO, exist_ok=True)
    arquivo = open(PASTA_ESTADO / "_conferente.lock", "a+b")
    try:
        msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
        return arquivo
    except OSError:
        arquivo.close()
        return None


# --- Comandos do menu da planilha (aba Status) ---
TICK_SEGUNDOS = 10
SINAL_ONLINE_SEGUNDOS = 5 * 60
PEDIDO_EXPIRA = datetime.timedelta(minutes=30)


def _agora_txt():
    return datetime.datetime.now().strftime("%d/%m %H:%M")


IDENTIDADE_SEGUNDOS = 6 * 60 * 60


def _identificar(cfg):
    try:
        import pythoncom
        import identidade
        from config import caminho_chave_google
        from sheets import BackendGoogle
        pythoncom.CoInitialize()
        ns = outlook_vivo.aplicativo().GetNamespace("MAPI")
        dados = identidade.detectar(cfg, ns, BackendGoogle(caminho_chave_google(cfg), somente_leitura=True))
        papel = carregar_config()["papel"]
        logger.info(f"🪪 Este PC: {dados.get('agente') or '?'} → papel {papel}")
    except Exception as e:
        logger.warning(f"⚠️ Não consegui identificar este PC agora ({e}) — mantenho o que já sabia.")


class _SoConferente(Exception):
    pass


def publicar_sinal(backend, cfg):
    from sheets import LINHA_CONFIG, LINHA_ONLINE, config_publica, escrever_linhas_status
    escrever_linhas_status(backend, cfg, {
        LINHA_CONFIG: config_publica(cfg),
        LINHA_ONLINE: datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
    })


def publicar_cota(backend, namespace, cfg):
    if backend is None:
        return
    from cota_envio import medir
    from sheets import LINHA_COTA, escrever_linhas_status
    escrever_linhas_status(backend, cfg, {LINHA_COTA: medir(namespace, cfg)})


def _ler_selecao_status(backend, cfg):
    from sheets import LINHA_SELECAO
    dados, _ = backend.ler_abas(cfg["planilha_central_id"], [cfg["aba_status"]])
    linhas = dados.get(cfg["aba_status"], [])
    return linhas[LINHA_SELECAO - 1][1] if len(linhas) >= LINHA_SELECAO and len(linhas[LINHA_SELECAO - 1]) > 1 else ""


class AndamentoNaPlanilha(logging.Handler):
    """Handler de logging que espelha o log numa célula da aba Status (o menu mostra ao vivo)."""
    INTERVALO = 4
    MAX_LINHAS = 150
    IGNORAR = ("urllib3", "google", "gspread", "requests")

    def __init__(self, backend, cfg, linha=None):
        super().__init__(logging.INFO)
        self.backend, self.cfg, self.linha = backend, cfg, linha
        self.linhas, self.ultima_gravacao, self.gravando = [], 0.0, False

    def emit(self, record):
        if record.name.startswith(self.IGNORAR) or set(record.getMessage()) <= {"="}:
            return
        self.linhas.append(f"{datetime.datetime.fromtimestamp(record.created):%H:%M:%S}  {record.getMessage()}")
        self.linhas = self.linhas[-self.MAX_LINHAS:]
        if time.monotonic() - self.ultima_gravacao >= self.INTERVALO:
            self.gravar()

    def gravar(self):
        if self.gravando:   # o retry da própria gravação loga: evita recursão
            return
        self.gravando = True
        try:
            from sheets import LINHA_ANDAMENTO, escrever_linhas_status
            escrever_linhas_status(self.backend, self.cfg, {self.linha or LINHA_ANDAMENTO: "\n".join(self.linhas)})
            self.ultima_gravacao = time.monotonic()
        except Exception:
            pass
        finally:
            self.gravando = False


def atender_conferencia(backend, cfg, quem):
    """Comando CONFERIR_COPIA."""
    from sheets import LINHA_COMANDO, LINHA_CONFERENCIA, LINHA_RESPOSTA, escrever_linhas_status
    import conferir_copia
    escrever_linhas_status(backend, cfg, {LINHA_COMANDO: "CONFERINDO", LINHA_CONFERENCIA: "",
                                          LINHA_RESPOSTA: f"🔍 Conferindo a cópia (pedido por {quem or '?'} · {_agora_txt()})"})
    andamento = AndamentoNaPlanilha(backend, cfg, linha=LINHA_CONFERENCIA)
    logging.getLogger().addHandler(andamento)
    try:
        _, resumo = conferir_copia.rodar_com_trava()
    except Exception as e:
        logger.error(f"❌ A conferência parou com erro: {e}")
        resumo = f"A conferência parou com erro: {e}"
    finally:
        logging.getLogger().removeHandler(andamento)
        andamento.gravar()
    escrever_linhas_status(backend, cfg, {LINHA_COMANDO: "", LINHA_RESPOSTA: f"🔍 {resumo} · terminou {_agora_txt()}"})
    return True


def atender_pedido(backend, cfg):
    """Despacha o comando da aba Status. -> True se havia um comando."""
    from historico import ORIGEM_CLAUDIO, ORIGEM_SEPARADO
    from sheets import LINHA_COMANDO, LINHA_RESPOSTA, LINHA_SELECAO, escrever_linhas_status, ler_comando
    comando, quem, quando = ler_comando(backend, cfg)
    if comando == "CONFERIR_COPIA":
        return atender_conferencia(backend, cfg, quem)
    if comando not in ("ENVIAR", "ENVIAR_SEPARADO"):
        return False
    if quando and datetime.datetime.now(datetime.timezone.utc) - quando > PEDIDO_EXPIRA:
        escrever_linhas_status(backend, cfg, {
            LINHA_COMANDO: "",
            LINHA_RESPOSTA: f"⌛ O pedido de {quando.astimezone():%d/%m %H:%M} expirou (o robô estava desligado). "
                            f"Clique em ⚡ Ativar Claudio de novo.",
        })
        return True

    import main as robo_envio
    selecao = None
    if comando == "ENVIAR_SEPARADO":
        texto = _ler_selecao_status(backend, cfg)
        selecao = robo_envio.ler_selecao(texto)
        if selecao is None:
            escrever_linhas_status(backend, cfg, {LINHA_COMANDO: "", LINHA_SELECAO: "",
                                                  LINHA_RESPOSTA: "⚠️ Envio separado sem hotel/linhas escolhidos — nada enviado."})
            return True
    origem = ORIGEM_SEPARADO if selecao else ORIGEM_CLAUDIO
    logger.info(f"⚡ {origem} pedido por {quem or '?'}" + (f" — {selecao['aba']} linhas {sorted(selecao['linhas'])}" if selecao else ""))
    from sheets import LINHA_ANDAMENTO
    escrever_linhas_status(backend, cfg, {LINHA_COMANDO: "EM ANDAMENTO", LINHA_ANDAMENTO: "",
                                          LINHA_RESPOSTA: f"🚀 Enviando... (pedido por {quem or '?'} · {_agora_txt()})"})
    andamento = AndamentoNaPlanilha(backend, cfg)
    logging.getLogger().addHandler(andamento)
    logger.info(f"📨 Pedido recebido de {quem or '?'} — começando.")
    try:
        codigo = robo_envio.rodar(codigo_se_ocupado=robo_envio.OCUPADO, origem=origem, quem=quem or "?",
                                  selecao=selecao)
    except Exception as e:
        codigo, erro = 1, e
        logger.error(f"❌ O envio parou com erro: {e}")
    else:
        erro = None
    finally:
        logging.getLogger().removeHandler(andamento)
        andamento.gravar()
    if codigo == robo_envio.OCUPADO:
        resposta = "⏳ Já tinha um envio rodando nesta máquina (Agendador). Espere alguns minutos e confira de novo."
    else:
        dados, _ = backend.ler_abas(cfg["planilha_central_id"], [cfg["aba_status"]])
        linhas = dados.get(cfg["aba_status"], [])
        resumo = (linhas[2][1] if len(linhas) > 2 and len(linhas[2]) > 1 else "") or (str(erro) if erro else "")
        resposta = f"{'✅' if codigo == 0 else '⚠️'} {resumo} · terminou {_agora_txt()}"
    escrever_linhas_status(backend, cfg, {LINHA_COMANDO: "", LINHA_SELECAO: "", LINHA_RESPOSTA: resposta})
    logger.info(f"⚡ {origem} terminou: {resposta}")
    return True


def main():
    uma_vez = "--uma-vez" in sys.argv
    try:
        cfg = carregar_config()
    except ErroDeConfig as e:
        logger.error(f"❌ {e}")
        return 1
    trava = _travar_instancia_unica()
    if trava is None:
        logger.info("ℹ️ Já tem um conferente rodando nesta máquina — este sai.")
        return 0
    import cota_google
    cota_google.configurar("conferente_principal" if e_principal(cfg) else "conferente")
    outlook_vivo.iniciar_guardiao()   # usuário, 13/10/2026: Outlook obrigatoriamente aberto (com janela) com o PC ligado

    import pythoncom
    from config import caminho_chave_google
    from sheets import BackendGoogle, garantir_rotulos_status

    intervalo = int(cfg["conferencia"]["intervalo_segundos"])
    logger.info(f"👀 Conferente de NF ligado (Itens Enviados a cada {intervalo}s; "
                f"pedidos do menu ⚡ Ativar Claudio a cada {TICK_SEGUNDOS}s).")
    categorias_ok = False
    backend = None
    proxima_conferencia = proximo_sinal = proxima_identidade = proxima_dividida = 0.0
    proxima_confirmacao = time.monotonic() + 60
    proximo_espelho, espelho, contagem = time.monotonic() + 30, None, None
    proximo_vigia, vigia, ultima_completa = time.monotonic() + 40, None, -1e9
    dropbox_antes = None   # marca das pastas de notas: mudou = NF nova (etiqueta "NF emitida" no e-mail do hóspede)
    proxima_faxina = time.monotonic() + 5 * 60   # faxina da Central: 1x por dia, só no principal (faxina.py)
    while True:
        agora = time.monotonic()
        try:
            cfg = carregar_config()   # hot reload
        except ErroDeConfig as e:
            logger.error(f"❌ {e}")

        if agora >= proxima_identidade:
            _identificar(cfg)
            proxima_identidade = agora + IDENTIDADE_SEGUNDOS
            cfg = carregar_config()

        try:
            if not e_principal(cfg):
                raise _SoConferente
            if backend is None:
                backend = BackendGoogle(caminho_chave_google(cfg))
                garantir_rotulos_status(backend, cfg)
            if agora >= proximo_sinal:
                publicar_sinal(backend, cfg)
                proximo_sinal = agora + SINAL_ONLINE_SEGUNDOS
            if atender_pedido(backend, cfg):
                proxima_conferencia = 0.0
            if agora >= proxima_faxina:
                proxima_faxina = agora + 60 * 60
                try:
                    import faxina
                    faxina.rodar(backend, cfg)
                except Exception as e:
                    logger.warning(f"⚠️ Faxina da Central não rodou ({e}) — tento de novo em 1 h.")
        except _SoConferente:
            pass
        except Exception as e:
            logger.warning(f"⚠️ Não consegui falar com a planilha ({e}) — tento de novo em {TICK_SEGUNDOS}s.")
            backend = None

        if agora >= proxima_conferencia:
            try:
                pythoncom.CoInitialize()
                outlook = outlook_vivo.aplicativo()
                namespace = outlook.GetNamespace("MAPI")
                if not categorias_ok:
                    garantir_categorias(namespace)
                    categorias_ok = True
                uma_volta(outlook, namespace, cfg)
                if agora >= proxima_dividida:
                    marcar_notas_divididas(namespace, cfg)
                    proxima_dividida = agora + NOTAS_DIVIDIDAS_SEGUNDOS
            except Exception as e:
                logger.warning(f"⚠️ Volta do conferente falhou ({e}) — tento de novo em {intervalo}s.")
            try:
                if e_principal(cfg):
                    publicar_cota(backend, namespace, cfg)
            except Exception as e:
                logger.warning(f"⚠️ Não consegui medir a cota de envio ({e}).")
            proxima_conferencia = time.monotonic() + intervalo

        try:   # a cada volta (10 s): aviso de certificado do Outlook (nome do servidor diferente) trava a fila de envio
            import aviso_certificado
            aviso_certificado.responder_avisos()
        except Exception as erro:
            logger.debug(f"aviso de certificado: {erro}")

        if agora >= proximo_vigia:
            # Vigia (20 s): só olha o Outlook. E-mail novo enviado/recebido -> conferência e espelho agora.
            try:
                pythoncom.CoInitialize()
                namespace = outlook_vivo.aplicativo().GetNamespace("MAPI")
                import vigia_outlook
                vigia = vigia or vigia_outlook.Vigia()
                novos = vigia.novidades(namespace)
                import envio_nf
                marca = envio_nf.marca_das_pastas(cfg)
                if dropbox_antes is not None and marca != dropbox_antes:
                    envio_nf.listar_notas_dropbox(cfg, forcar=True)
                    logger.info("🧾 NF nova no Dropbox — conferindo os e-mails dos hóspedes agora")
                    proximo_espelho = min(proximo_espelho, max(agora, ultima_completa + MIN_ENTRE_CONFERENCIAS))
                dropbox_antes = marca
                if any(novos.values()):
                    logger.info(f"👁️ Outlook: {novos['enviado']} enviado(s), {novos['recebido']} recebido(s) novo(s)"
                                f"{' e ' + str(novos.get('saiu', 0)) + ' saiu(saíram) da Caixa de Entrada' if novos.get('saiu') else ''}"
                                f" — conferindo agora")
                    quando = max(agora, ultima_completa + MIN_ENTRE_CONFERENCIAS)
                    proxima_confirmacao = min(proxima_confirmacao, quando)
                    proximo_espelho = min(proximo_espelho, quando)
            except Exception as e:
                logger.debug(f"vigia do Outlook: {e}")
            proximo_vigia = time.monotonic() + VIGIA_SEGUNDOS

        if agora >= proxima_confirmacao or agora >= proximo_espelho:
            try:
                pythoncom.CoInitialize()
                namespace = outlook_vivo.aplicativo().GetNamespace("MAPI")
            except Exception as e:
                logger.warning(f"⚠️ Outlook indisponível ({e}) — confiro de novo em 2 min.")
                namespace = None
                proxima_confirmacao = agora + CONFIRMAR_NFS_SEGUNDOS
                proximo_espelho = agora + ESPELHO_EMAILS_SEGUNDOS
            if namespace is not None and agora >= proxima_confirmacao:
                # NFs de todas as solicitações da Central -> aba Tratamento (o painel de todos os PCs vê).
                # Cada PC confere o próprio Outlook; o Dropbox é compartilhado, então só o principal lê.
                try:
                    import confirmar_nfs
                    confirmar_nfs.rodar(namespace, cfg, usar_dropbox=e_principal(cfg))
                except Exception as e:
                    logger.warning(f"⚠️ Confirmação de NFs falhou ({e}) — tento de novo em 10 min.")
                proxima_confirmacao = time.monotonic() + CONFIRMAR_NFS_SEGUNDOS
                ultima_completa = time.monotonic()
            if namespace is not None and agora >= proximo_espelho:
                # E-mails de hóspedes sem resposta das caixas daqui -> aba Emails_<PC> (o Painel de todos vê)
                try:
                    import espelho_emails
                    if espelho is None:
                        espelho = espelho_emails.Espelho(BackendGoogle(caminho_chave_google(cfg)), cfg)
                    espelho.volta(namespace)
                except Exception as e:
                    logger.warning(f"⚠️ Espelho de e-mails falhou ({e}) — tento de novo em 2 min.")
                    espelho = None
                try:   # fim de semana de João e Cristian contado pelo Painel (o Mail Analytics só grava na segunda)
                    import contagem_painel
                    if espelho is not None:
                        contagem = contagem or contagem_painel.Contagem()
                        contagem.talvez(namespace, espelho._caixas_do_outlook(namespace, espelho._caixas()),
                                        contagem_painel.agente_deste_pc(), espelho.backend, espelho.central)
                except Exception as e:
                    logger.warning(f"⚠️ Contagem do fim de semana falhou ({e})")
                proximo_espelho = time.monotonic() + ESPELHO_EMAILS_SEGUNDOS

        if uma_vez:
            return 0
        time.sleep(TICK_SEGUNDOS)


if __name__ == "__main__":
    sys.exit(main())
