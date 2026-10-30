"""Tabela de rotas da API do Painel (30/10/2026): o que cada endereço faz, num lugar só.

O servidor (`app_servidor.criar_handler`) cuida do que é de HTTP: Host, token, arquivos da tela, JSON, gzip, códigos de erro.
Aqui fica só "este endereço chama aquilo". Para criar uma rota nova, é uma linha em `GET` ou em `POST`.

Cada função recebe o contexto `c` (o que o servidor sabe: `estado`, `cfg`, `pc`, `envio`, `agente()`...) e:
- GET:  `q`, um dicionário com o primeiro valor de cada parâmetro da URL
- POST: `corpo`, o JSON enviado pela tela
e devolve o que vai para a tela, ou `(corpo, codigo_http)` quando precisa de um código diferente de 200.

Este módulo não importa `app_servidor` (ele roda como `__main__`); o que depende dele chega pelo contexto.
"""
import datetime

from log_util import configurar_logging
from sheets import LINHA_COMANDO, LINHA_PEDIDO

logger = configurar_logging("app")

# GET que a tela pede o tempo todo: se não mudou desde a última resposta, o servidor manda só {"__igual": true}
COMPARAR = frozenset({"/api/estado", "/api/emails", "/api/correio"})

# POST que o modo casa (só visualização) ainda aceita
POST_NO_MODO_CASA = frozenset({"/api/agente", "/api/atualizar"})


# ---------------------------------------------------------------- GET

def _estado(c, q):
    dias = int(q.get("dias", "45") or 0)
    c.estado.vista_atual = q.get("vista", "")
    e = c.estado
    return {
        "agente": c.agente(), "pc": c.pc, "erro": e.erro, "operadores": c.operadores_deste_pc(),
        "atualizado_em": e.atualizado_em.isoformat(timespec="seconds") if e.atualizado_em else "",
        "atualizar_segundos": int(c.cfg.get("app", {}).get("atualizar_segundos", 15)),
        "status": e.resumo_status(), "fila": e.fila_da_tela(dias), "pcs": e.pcs(),
        "caixa_pcs": e.resumo_caixa(), "saude": e.problemas_de_saude(),
        "hoteis": e.hoteis_por_agente(), "ligacoes": e.resumo_ligacoes(),
        "demo": bool(getattr(e, "demo", False)), "pagina": c.marca_pagina(), "so_ver": bool(getattr(e, "so_ver", False)),
        "admin": c.e_admin(), "tema": c.ler_prefs().get("tema", ""),
    }


def _envio(c, q):
    def ler_status():
        aba = c.cfg["aba_status"]
        linhas = c.estado.backend.ler_abas(c.estado.central, [aba])[0].get(aba, [])
        return {str(l[0]).strip(): (str(l[1]) if len(l) > 1 else "") for l in linhas if l}
    return c.envio.situacao(ler_status)


def _relatorio_semana(c, q):
    try:
        return c.estado.relatorio_semana(int(q.get("deslocamento", q.get("semana", "0")) or 0), q.get("tipo", "semana"))
    except Exception as e:
        logger.warning(f"⚠️ Relatório da semana: {e}")
        return {"erro": f"não consegui ler a planilha do Mail Analytics ({str(e)[:120]})"}


GET = {
    "/api/versao": lambda c, q: {"v": c.estado.marca_tela()},
    "/api/estado": _estado,
    "/api/envio": _envio,
    "/api/envio_nf/opcoes": lambda c, q: c.estado.opcoes_envio(q.get("chave", "")),
    "/api/envio_nf/status": lambda c, q: c.estado.situacao_envio(q.get("id", "")),
    "/api/nf_cobre": lambda c, q: c.estado.nf_cobre(q.get("id", "")),
    "/api/caixas": lambda c, q: c.estado.caixas_com_problema(),
    "/api/enviar_receber/status": lambda c, q: c.estado._enviar_receber().status(q.get("id", "")),
    "/api/painel": lambda c, q: c.estado.painel(q.get("ini"), q.get("fim")),
    "/api/hotel": lambda c, q: c.estado.hotel(q.get("nome", ""), q.get("ini"), q.get("fim")),
    "/api/relatorio_semana": _relatorio_semana,
    "/api/cadastro/faltando": lambda c, q: {"faltando": c.estado.cadastro_faltando(),
                                            "agentes": sorted({p["agente"] for p in c.estado.pcs() if p.get("agente")})},
    "/api/atividade": lambda c, q: c.estado.atividade_resumo(),
    "/api/emails": lambda c, q: {"emails": c.estado.lista_emails(), "este_pc": c.pc},
    "/api/correio": lambda c, q: c.estado.lista_correio(),
    "/api/correio/conversa": lambda c, q: c.estado.conversa(q.get("de", "")),
    "/api/correio/texto": lambda c, q: c.estado.texto_email(q.get("id", ""), q.get("pc", ""), q.get("entry", "")),
    "/api/correio/anexo": lambda c, q: c.estado.anexo_email(q.get("id", ""), q.get("pc", ""), q.get("entry", ""), q.get("nome", "")),
    "/api/correio/buscar": lambda c, q: c.estado.buscar_outlook(q.get("q", ""), q.get("vivo", "") == "1"),
    "/api/email/opcoes": lambda c, q: c.estado.opcoes_email(q.get("id", "")),
    "/api/email/novo": lambda c, q: c.estado.opcoes_email_novo(q.get("conta", "")),
}


# ---------------------------------------------------------------- POST

def _tema(c, corpo):   # tema por PC (claro, escuro ou o do Windows), lembrado depois de reiniciar
    tema = str(corpo.get("tema", ""))
    if tema not in c.temas_ok:
        return {"ok": False, "motivo": "tema desconhecido"}, 400
    c.salvar_pref("tema", tema)
    return {"ok": True}


def _agente(c, corpo):
    nome = str(corpo.get("nome", "")).strip()[:40]
    if nome not in c.operadores:
        return {"ok": False, "motivo": "operador desconhecido"}, 400
    if nome not in c.operadores_deste_pc(recarregar=True):
        return {"ok": False, "motivo": f"O usuário {nome} só pode ser usado no PC dele."}, 403
    c.salvar_pref("agente", nome)
    return {"ok": True}


def _enviar(c, corpo):
    if c.e_principal(c.carregar_config()):   # aqui mesmo: rápido e com log direto da memória
        if not c.envio.iniciar_local(c.agente()):
            return {"ok": False, "motivo": "Já tem um envio em andamento."}
        return {"ok": True, "modo": "local"}
    quando = datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")
    c.escrever_linhas_status(c.estado.backend, c.cfg, {LINHA_COMANDO: "ENVIAR", LINHA_PEDIDO: f"{c.agente()} (Painel) | {quando}"})
    c.envio.iniciar_remoto()
    return {"ok": True, "modo": "remoto"}


def _robo_ligado(c, corpo):
    if not c.e_admin():
        return {"ok": False, "motivo": "Só o João liga ou pausa o robô, no PC dele."}, 403
    return c.estado.definir_robo_ligado(bool(corpo.get("ligado")), c.agente())


def _atualizar(c, corpo):
    c.estado.atualizar()
    c.estado.atualizar_fi(forcar=True)
    return {"ok": not c.estado.erro, "motivo": c.estado.erro}


POST = {
    "/api/acao": lambda c, b: c.estado.registrar(c.agente(), c.pc, b["chave"], b["acao"], b.get("valor", "")),
    "/api/tema": _tema,
    "/api/agente": _agente,
    "/api/enviar": _enviar,
    "/api/envio_nf": lambda c, b: c.estado.pedir_envio(b, c.agente()),
    "/api/cadastro/adicionar": lambda c, b: c.estado.adicionar_cadastro(b, c.agente()),
    "/api/envio_nf/conferir": lambda c, b: c.estado.conferir_anexos(b),
    "/api/email/responder": lambda c, b: c.estado.responder_email(b, c.agente()),
    "/api/email/novo": lambda c, b: c.estado.enviar_email_novo(b, c.agente()),
    "/api/correio/evento": lambda c, b: c.estado.evento_correio([str(i) for i in b.get("ids", [])], str(b.get("acao", "")), c.agente()),
    "/api/correio/excluir": lambda c, b: c.estado.excluir_email(str(b.get("id", "")), c.agente(), b),
    "/api/correio/urgencia": lambda c, b: c.estado.marcar_urgencia(str(b.get("id", "")), str(b.get("marcar", "")), c.agente()),
    "/api/correio/mover_nf": lambda c, b: c.estado.mover_email_nf(str(b.get("id", "")), c.agente()),
    "/api/correio/concluir": lambda c, b: c.estado.concluir_conversa(str(b.get("id", "")), c.agente()),
    "/api/robo/ligado": _robo_ligado,
    "/api/outlook/reiniciar": lambda c, b: c.estado.reiniciar_outlook(str(b.get("pc", "")), c.agente()),
    "/api/enviar_receber": lambda c, b: c.estado.enviar_receber_todas(c.agente()),
    "/api/ligacao": lambda c, b: c.estado.marcar_ligacao(str(b.get("id", "")), bool(b.get("marcar")), c.agente()),
    "/api/correio/encaminhar": lambda c, b: c.estado.encaminhar_email(b, c.agente()),
    "/api/comando": lambda c, b: c.estado.pedir_comando(str(b.get("para", "")), str(b.get("comando", "")), f"{c.agente()} ({c.pc})"),
    "/api/atualizar": _atualizar,
}
