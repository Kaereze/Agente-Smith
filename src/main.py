"""Envio: lê pendentes, envia, confirma em Itens Enviados e só então marca TRUE."""
import datetime
import os
import re
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from console_utf8 import garantir_utf8

garantir_utf8()

from controle_nf import abrir_registro
from historico import (ATENCAO, ERRO, NADA, ORIGEM_AGENDADO, ORIGEM_MANUAL, SUCESSO, Execucao,
                       JaEnviadas, explicar_aba_pulada, texto_simples)
from config import e_principal, PASTA_ESTADO, PASTA_LOGS, PASTA_SIMULACAO, ErroDeConfig, caminho_chave_google, carregar_config
import robo_antigo
from diario_envios import MINUTOS_ATE_DESISTIR, DiarioEnvios, idade_minutos, solicitacoes_da_entrada
from log_util import configurar_logging
from montar_email import montar_emails
from tratamento import normalizar
from sheets import (ErroPlanilha, gravar_status, interpretar_aba, ler_hoteis, ler_pendentes, marcar_enviados,
                    nome_do_hotel_pela_aba, registrar_central, robo_ligado)

logger = configurar_logging("main")

INTERVALO_CONFERENCIA_SEGUNDOS = 10


def _marcar_e_registrar(backend, cfg, solicitacoes, registrar=True):
    try:
        marcadas, nao_encontradas = marcar_enviados(backend, cfg, solicitacoes)
    except Exception as e:
        logger.error(f"❌ E-mail enviado, mas falhou ao marcar TRUE ({e}). "
                     f"O diário de envios guarda isso — a próxima execução marca sem reenviar.")
        return False
    logger.info(f"✅ {marcadas} solicitação(ões) marcada(s) como Enviado = TRUE.")
    if registrar:
        registrar_central(backend, cfg, solicitacoes)
    return True


def conferir_envios_anteriores(backend, outlook, cfg, diario, agora, ja_enviadas=None, log_exec=None):
    """Resolve o diário da execução anterior. Devolve (chaves bloqueadas, avisos)."""
    bloqueadas, avisos, confirmadas, codigos_confirmados = set(), [], [], []
    for entrada in diario.listar():
        solicitacoes = solicitacoes_da_entrada(entrada)
        chaves = {s.chave for s in solicitacoes}
        codigo = entrada["codigo"]
        criado_em = datetime.datetime.fromisoformat(entrada["criado_em"])
        try:
            if outlook.esta_nos_enviados(codigo, criado_em, destinatario=entrada.get("destinatario")):
                logger.info(f"🔁 E-mail {codigo} da execução anterior SAIU — marcando TRUE sem reenviar.")
                confirmadas.extend(solicitacoes)
                codigos_confirmados.append(codigo)
                if ja_enviadas is not None:
                    ja_enviadas.anotar(solicitacoes, codigo, entrada.get("destinatario", ""), criado_em)
                if log_exec is not None:
                    for hotel in dict.fromkeys(s.hotel.nome for s in solicitacoes):
                        log_exec.geral(ATENCAO, f"Um e-mail da execução anterior ({codigo}) tinha saído, mas não "
                                                f"estava marcado. Marquei TRUE sem reenviar.", hotel=hotel)
                bloqueadas |= chaves
            elif outlook.esta_na_caixa_saida(codigo, destinatario=entrada.get("destinatario")):
                minutos = idade_minutos(entrada, agora)
                aviso = f"E-mail {codigo} ({entrada['assunto']}) parado na Caixa de Saída há {minutos:.0f} min"
                logger.warning(f"⚠️ {aviso} — não vou reenviar essas solicitações. Confira o Outlook.")
                avisos.append(aviso)
                bloqueadas |= chaves
            elif idade_minutos(entrada, agora) < MINUTOS_ATE_DESISTIR:
                bloqueadas |= chaves
            else:
                logger.warning(f"⚠️ E-mail {codigo} não saiu (não está em Enviados nem na Caixa de Saída) — "
                               f"as {len(solicitacoes)} solicitação(ões) vão ser enviadas de novo.")
                diario.remover([codigo])
        except Exception as e:
            logger.warning(f"⚠️ Não consegui conferir o e-mail {codigo} ({e}) — segurando essas solicitações por agora.")
            bloqueadas |= chaves

    if confirmadas and _marcar_e_registrar(backend, cfg, confirmadas):
        diario.remover(codigos_confirmados)
    return bloqueadas, avisos


def filtrar_somente_hoteis(hoteis, cfg):
    escolhidos = {normalizar(h) for h in cfg.get("somente_hoteis", []) if str(h).strip()}
    if not escolhidos:
        return hoteis
    filtrados = [h for h in hoteis if normalizar(h.nome) in escolhidos]
    logger.warning(f"⚠️ 'somente_hoteis' ligado no config.json — só estes hotéis: "
                   f"{', '.join(h.nome for h in filtrados) or '(nenhum encontrado!)'}. "
                   f"Esvazie a lista pra voltar a rodar todos.")
    return filtrados


def registrar_para_conferencia(emails, agora):
    if not emails:
        return
    try:
        with abrir_registro(PASTA_ESTADO / "controle_nf.json") as registro:
            for email in emails:
                registro.registrar_email(email, agora)
        logger.info(f"📌 {len(emails)} e-mail(s) anotado(s) pro conferente de NF.")
    except Exception as e:
        logger.warning(f"⚠️ Não consegui anotar os e-mails pro conferente de NF ({e}) — "
                       f"o envio está certo, só o ✅ automático não vai aparecer nesses e-mails.")


def _nome_arquivo_seguro(texto):
    return re.sub(r"[^\w.@-]+", "_", texto)


def salvar_simulacao(emails, agora, pasta=None):
    pasta = str(pasta or PASTA_SIMULACAO)
    os.makedirs(pasta, exist_ok=True)
    caminhos = []
    for i, email in enumerate(emails, start=1):
        nome = f"{agora:%Y%m%d_%H%M%S}_{i:02d}_{_nome_arquivo_seguro(email.operador)}.html"
        caminho = os.path.join(pasta, nome)
        with open(caminho, "w", encoding="utf-8") as f:
            f.write(email.html)
        caminhos.append(caminho)
        logger.info(f"📝 [SIMULAÇÃO] {email.assunto} -> {email.destinatario} "
                    f"({len(email.solicitacoes)} solicitações) salvo em {caminho}")
    return caminhos


def aguardar_confirmacoes(outlook, emails, desde, cfg, esperar=time.sleep, relogio=time.monotonic):
    """-> códigos que apareceram em Itens Enviados dentro do prazo."""
    limite = relogio() + int(cfg["outlook"]["espera_confirmacao_envio_segundos"])
    faltando = {e.codigo for e in emails}
    destino = {e.codigo: e.destinatario for e in emails}
    confirmados = set()
    while True:
        for codigo in sorted(faltando):
            try:
                if outlook.esta_nos_enviados(codigo, desde, destinatario=destino.get(codigo)):
                    confirmados.add(codigo)
            except Exception as e:
                logger.warning(f"⚠️ Erro ao procurar {codigo} em Itens Enviados: {e}")
        faltando -= confirmados
        if not faltando or relogio() >= limite:
            return confirmados
        esperar(INTERVALO_CONFERENCIA_SEGUNDOS)


def _hoteis_txt(email):
    return ", ".join(dict.fromkeys(s.hotel.nome for s in email.solicitacoes))


def ler_selecao(texto):
    """B13 da aba Status: "aba | 131, 132 | reenviar" -> {aba, linhas, reenviar}."""
    partes = [p.strip() for p in str(texto or "").split(" | ")]
    if len(partes) < 2 or not partes[0]:
        return None
    linhas = {int(n) for n in re.findall(r"\d+", partes[1])}
    if not linhas:
        return None
    return {"aba": partes[0], "linhas": linhas, "reenviar": len(partes) > 2 and "reenviar" in partes[2].lower()}


def _pendentes_da_selecao(backend, cfg, selecao, log_exec):
    """Com 'reenviar', inclui linhas que já têm TRUE."""
    cfg_sem_filtro = dict(cfg, somente_hoteis=[])
    hoteis, erros = ler_hoteis(backend, cfg_sem_filtro)
    hotel = next((h for h in hoteis if h.aba == selecao["aba"]), None)
    if hotel is None:
        motivo = next((e for e in erros if e.startswith(selecao["aba"])), f"{selecao['aba']}: aba não encontrada")
        log_exec.geral(ERRO, "Envio separado não feito. " + explicar_aba_pulada(motivo)[1],
                       hotel=nome_do_hotel_pela_aba(selecao["aba"]))
        return [], [motivo]
    dados, erros_leitura = backend.ler_abas(hotel.planilha_id, [hotel.aba])
    if hotel.aba in erros_leitura:
        log_exec.geral(ERRO, "Não consegui ler a aba do hotel. " + texto_simples(Exception(erros_leitura[hotel.aba])),
                       hotel=hotel.nome)
        return [], [hotel.aba]
    pendentes, erro = interpretar_aba(hotel, dados.get(hotel.aba, []), cfg,
                                      incluir_linhas=selecao["linhas"] if selecao["reenviar"] else None)
    if erro:
        log_exec.geral(ERRO, explicar_aba_pulada(f"{hotel.aba}: {erro}")[1], hotel=hotel.nome)
        return [], [erro]
    escolhidas = [s for s in pendentes if s.linha in selecao["linhas"]]
    faltaram = sorted(selecao["linhas"] - {s.linha for s in escolhidas})
    if faltaram:
        log_exec.geral(ATENCAO, f"As linhas {', '.join(map(str, faltaram))} não foram enviadas: já estão com TRUE "
                                f"(marque 'reenviar' pra mandar de novo) ou estão vazias.", hotel=hotel.nome)
    return escolhidas, []


def _convivencia_robo_antigo(backend, cfg, outlook, pendentes, ja_enviadas, log_exec, agora):
    """Dá a vez ao robô antigo (Apps Script) e marca TRUE no que ele já mandou, sem reenviar."""
    op = robo_antigo.opcoes(cfg)
    ativos = robo_antigo.hoteis_ativos(PASTA_ESTADO / "robo_antigo.json", agora, op["dias_ativo"])
    pendentes, aguardando = robo_antigo.separar(pendentes, ativos, agora, op["espera_minutos"])
    if aguardando:
        hoteis = sorted({s.hotel.nome for s in aguardando})
        logger.info(f"⏳ {len(aguardando)} solicitação(ões) recente(s) esperando a vez do robô antigo "
                    f"(até {op['espera_minutos']} min): {', '.join(hoteis)}")
    if not pendentes:
        return pendentes
    try:
        if getattr(outlook, "namespace", None) is None and hasattr(outlook, "conectar"):
            outlook.conectar()
        desde = agora - datetime.timedelta(days=op["dias_caixa"])
        enviados = robo_antigo.emails_do_robo_antigo(outlook.namespace, op["remetente"].lower(), desde)
    except Exception as e:
        logger.warning(f"⚠️ Não consegui olhar as caixas atrás de e-mails do robô antigo ({e}) — sigo sem essa conferência.")
        return pendentes
    ja = robo_antigo.ja_mandadas_pelo_antigo(pendentes, enviados)
    if ja:
        feitas = [s for s, _ in ja]
        logger.warning(f"🤝 {len(feitas)} solicitação(ões) já enviada(s) pelo robô antigo (Gmail) — marcando TRUE sem reenviar.")
        if _marcar_e_registrar(backend, cfg, feitas, registrar=False):
            for s, quando in ja:
                ja_enviadas.anotar([s], "ROBO-ANTIGO", op["remetente"], agora)
                log_exec.geral(ATENCAO, f"Já tinha sido enviada pelo robô antigo (Gmail) em {quando} "
                                        f"({s.nome_titulo}). Não reenviei: só marquei TRUE.", hotel=s.hotel.nome)
        ids = {id(s) for s in feitas}
        pendentes = [s for s in pendentes if id(s) not in ids]
    return pendentes


def executar(cfg, backend, outlook, esperar=time.sleep, agora=None, relogio=time.monotonic, log_exec=None,
             selecao=None):
    agora = agora or datetime.datetime.now()
    modo = cfg["modo"]
    log_exec = log_exec or Execucao(ORIGEM_MANUAL, "", modo, agora)
    por_pedido = log_exec.origem != ORIGEM_AGENDADO   # a pedido de alguém: sempre deixa rastro no log
    logger.info("=" * 60)
    logger.info(f"🤖 Solicitações NF — início ({modo}) · {log_exec.origem} · {log_exec.quem}")

    if modo != "SIMULACAO" and not robo_ligado(backend, cfg):
        logger.info("⏸️ Robô DESLIGADO no painel (aba Status, 'Robô ligado?'). Nada feito.")
        gravar_status(backend, cfg, False, "Desligado pelo painel — nada enviado", agora)
        if por_pedido:
            log_exec.geral(ERRO, "Nada foi enviado: o robô está DESLIGADO na aba Status (caixa 'Robô ligado?').")
        return 0

    if selecao:
        pendentes, erros_abas = _pendentes_da_selecao(backend, cfg, selecao, log_exec)
    else:
        hoteis, erros_cadastro = ler_hoteis(backend, cfg)
        logger.info(f"🏨 {len(hoteis)} aba(s) de respostas ligada(s) a um agente.")
        hoteis = filtrar_somente_hoteis(hoteis, cfg)
        pendentes, erros_abas = ler_pendentes(backend, cfg, hoteis)
        erros_abas = erros_cadastro + erros_abas
        if por_pedido:
            for erro_aba in erros_abas:
                aba, frase = explicar_aba_pulada(erro_aba)
                log_exec.geral(ATENCAO, frase, hotel=nome_do_hotel_pela_aba(aba))
    logger.info(f"📋 {len(pendentes)} solicitação(ões) pendente(s) lida(s).")

    avisos = [f"aba com erro: {e}" for e in erros_abas]
    diario = DiarioEnvios(PASTA_ESTADO / "envios_pendentes.json")
    ja_enviadas = JaEnviadas(PASTA_ESTADO / "ja_enviadas.json")
    outlook_conectado = False

    if modo == "PRODUCAO" and diario.listar():
        outlook.conectar()
        outlook_conectado = True
        bloqueadas, avisos_diario = conferir_envios_anteriores(backend, outlook, cfg, diario, agora,
                                                               ja_enviadas, log_exec)
        avisos += avisos_diario
        antes = len(pendentes)
        pendentes = [s for s in pendentes if s.chave not in bloqueadas]
        if antes != len(pendentes):
            logger.info(f"🔒 {antes - len(pendentes)} solicitação(ões) já tratada(s) pela execução anterior — não reenviadas.")

    # Sem TRUE mas já confirmado em Enviados (a marcação falhou antes): só marca.
    reenviar = bool(selecao and selecao["reenviar"])
    if modo == "PRODUCAO" and not reenviar:
        ja = [s for s in pendentes if ja_enviadas.contem(s)]
        if ja:
            logger.warning(f"🛟 {len(ja)} solicitação(ões) sem TRUE já constam como enviadas — marcando TRUE sem reenviar.")
            if _marcar_e_registrar(backend, cfg, ja, registrar=False):
                log_exec.reparo(ja, ja_enviadas.registros)
            pendentes = [s for s in pendentes if not ja_enviadas.contem(s)]

    if modo == "PRODUCAO" and not selecao and pendentes:
        pendentes = _convivencia_robo_antigo(backend, cfg, outlook, pendentes, ja_enviadas, log_exec, agora)

    if not pendentes:
        resumo = "Nada pendente" + (f" ({'; '.join(avisos)})" if avisos else "")
        logger.info(f"✅ {resumo}.")
        if modo != "SIMULACAO":
            gravar_status(backend, cfg, True, resumo, agora)
        if por_pedido and not log_exec.linhas:
            log_exec.geral(NADA, "Não havia nenhuma solicitação pendente pra enviar.")
        return 0

    emails = montar_emails(pendentes, cfg)
    teto = int(cfg.get("max_emails_por_execucao", 150))
    if len(emails) > teto:   # cota do servidor; o resto fica sem TRUE e vai na próxima
        logger.warning(f"🚦 {len(emails)} e-mails nesta rodada — envio {teto} agora e o resto na próxima (cota do servidor).")
        emails = emails[:teto]
    logger.info(f"✉️ {len(emails)} e-mail(s) montado(s) pra {len({e.operador for e in emails})} operador(es).")

    if modo == "SIMULACAO":
        salvar_simulacao(emails, agora)
        logger.info("✅ Simulação concluída — nada enviado, planilha não mexida.")
        return 0

    if not outlook_conectado:
        outlook.conectar()

    inicio_envio = datetime.datetime.now()
    enviados, falhas_envio = [], []
    for posicao, email in enumerate(emails):
        logger.info(f"📤 Enviando {email.codigo} -> {email.destinatario} | {len(email.solicitacoes)} solicitação(ões) | {_hoteis_txt(email)}")
        if modo == "PRODUCAO":
            diario.anotar(email, agora)
        try:
            outlook.enviar(email)
            enviados.append(email)
        except Exception as e:
            logger.error(f"❌ Falha ao enviar {email.codigo} pra {email.destinatario}: {e}")
            falhas_envio.append(email)
            log_exec.email(email, ERRO, "Não foi enviado. " + texto_simples(e) +
                           " As linhas continuam sem TRUE e vão de novo na próxima execução.", ok=False)
            try:
                outlook.conectar()
            except Exception as e2:
                logger.error(f"❌ Outlook não voltou ({e2}) — parando os envios. O resto vai na próxima execução.")
                for resto in emails[posicao + 1:]:
                    log_exec.email(resto, ERRO, "Não foi enviado: o Outlook parou de responder no meio do envio. "
                                                "Vai na próxima execução.", ok=False)
                break

    if modo == "TESTE":
        registrar_para_conferencia(enviados, agora)
        for email in enviados:
            log_exec.email(email, SUCESSO, "Teste: enviado só pro e-mail de teste. A planilha NÃO foi marcada "
                                           "(essas solicitações continuam pendentes).", ok=True)
        resumo = (f"TESTE: {len(enviados)} e-mail(s) com {sum(len(e.solicitacoes) for e in enviados)} "
                  f"solicitação(ões) enviados pra {cfg['email_teste']} (nada marcado TRUE)")
        if falhas_envio:
            resumo += f"; {len(falhas_envio)} falharam"
        logger.info(f"✅ {resumo}")
        gravar_status(backend, cfg, not falhas_envio, resumo, agora)
        return 0 if not falhas_envio else 1

    confirmados = aguardar_confirmacoes(outlook, enviados, inicio_envio, cfg, esperar, relogio)
    sem_confirmacao = [e for e in enviados if e.codigo not in confirmados]
    for e in sem_confirmacao:
        logger.warning(f"⚠️ {e.codigo} ainda não apareceu em Itens Enviados — linhas continuam FALSE; "
                       f"a próxima execução confere (e não reenvia se já tiver saído).")
        log_exec.email(e, ATENCAO, "O Outlook aceitou o e-mail, mas ele ainda não apareceu em Itens Enviados "
                                   "(pode estar na Caixa de Saída). Nada foi marcado. A próxima execução confere "
                                   "antes de reenviar, então não vai duplicar.", ok=False)

    emails_ok = [e for e in enviados if e.codigo in confirmados]
    for e in emails_ok:
        ja_enviadas.anotar(e.solicitacoes, e.codigo, e.destinatario, agora)   # antes do TRUE, de propósito
    registrar_para_conferencia(emails_ok, agora)
    solicitacoes_ok = [s for e in emails_ok for s in e.solicitacoes]
    marcou = True
    if solicitacoes_ok:
        marcou = _marcar_e_registrar(backend, cfg, solicitacoes_ok)
        if marcou:
            diario.remover(confirmados)
    for e in emails_ok:
        if marcou:
            log_exec.email(e, SUCESSO, ("Reenviado a pedido (Envio Separado). " if reenviar else "") +
                           "Enviado e confirmado na pasta Itens Enviados. As linhas foram marcadas como enviadas (TRUE).",
                           ok=True)
        else:
            log_exec.email(e, ATENCAO, "O e-mail saiu (confirmado em Itens Enviados), mas não consegui marcar TRUE na "
                                       "planilha. A próxima execução marca sozinha, sem reenviar.", ok=True)

    total_ok = len(solicitacoes_ok)
    resumo = f"{len(confirmados)} e-mail(s) enviado(s), {total_ok} solicitação(ões) marcada(s) TRUE"
    if sem_confirmacao:
        resumo += f"; {len(sem_confirmacao)} e-mail(s) aguardando confirmação"
    if falhas_envio:
        resumo += f"; {len(falhas_envio)} e-mail(s) falharam"
    if not marcou:
        resumo += "; FALHA ao marcar TRUE (resolve sozinho na próxima)"
    if avisos:
        resumo += f"; avisos: {'; '.join(avisos)}"

    sucesso = not falhas_envio and not sem_confirmacao and marcou
    (logger.info if sucesso else logger.warning)(("✅ " if sucesso else "⚠️ ") + resumo)
    gravar_status(backend, cfg, sucesso, resumo, agora)
    return 0 if sucesso else 1


OCUPADO = 3   # exit code quando a trava está com outra execução


def rodar(codigo_se_ocupado=0, origem=None, quem=None, selecao=None):
    from lock_execucao import adquirir_lock, liberar_lock
    from outlook import OutlookNF
    from sheets import BackendGoogle

    agendado = "--agendado" in sys.argv
    origem = origem or (ORIGEM_AGENDADO if agendado else ORIGEM_MANUAL)
    quem = quem or ("Robô (horário programado)" if agendado else f"{os.environ.get('USERNAME', '?')} (no computador)")

    try:
        cfg = carregar_config()
    except ErroDeConfig as e:
        logger.error(f"❌ {e}")
        return 1

    if not e_principal(cfg):
        logger.warning("⛔ Este PC está como conferente (config.local.json) — o envio só roda no PC principal.")
        return 0
    if not adquirir_lock():
        return codigo_se_ocupado
    backend = None
    log_exec = Execucao(origem, quem, cfg["modo"])
    try:
        backend = BackendGoogle(caminho_chave_google(cfg), somente_leitura=cfg["modo"] == "SIMULACAO")
        return executar(cfg, backend, OutlookNF(cfg), log_exec=log_exec, selecao=selecao)
    except Exception as e:
        if isinstance(e, ErroPlanilha):
            logger.error(f"❌ {e}")
        else:
            logger.exception(f"❌ Erro inesperado: {e}")
        log_exec.geral(ERRO, "A execução parou antes de terminar. " + texto_simples(e) +
                             " O que não foi confirmado continua pendente e vai na próxima.")
        if backend is not None and cfg["modo"] != "SIMULACAO":
            gravar_status(backend, cfg, False, f"ERRO: {e}")
        return 1
    finally:
        if cfg["modo"] != "SIMULACAO":
            log_exec.gravar(backend, cfg, PASTA_LOGS)
        liberar_lock()


if __name__ == "__main__":
    sys.exit(rodar())
