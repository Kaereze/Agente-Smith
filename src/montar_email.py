"""Assunto e HTML dos e-mails de solicitação. HTML com estilo inline: é o que o Outlook respeita."""
import datetime
import uuid
from html import escape

import controle_nf
from controle_nf import paragrafo_status
from modelos import EmailMontado
from tratamento import converter_data, normalizar

COR_PRIMARIA = "#00786c"
COR_CREME = "#d5bda1"
COR_TEXTO_TABELA = "#173f39"
COR_BORDA_TABELA = "#bfa27c"
FONTE = "font-family:Segoe UI,Arial,sans-serif;"
TAMANHO_MAXIMO_ASSUNTO = 200


def ordenar_para_email(solicitacoes):
    return sorted(solicitacoes, key=lambda s: (normalizar(s.hotel.nome), s.hotel.aba, s.linha))


def agrupar_por_operador(solicitacoes):
    grupos = {}
    for s in solicitacoes:
        grupos.setdefault(s.hotel.operador, []).append(s)
    return {op: ordenar_para_email(lista) for op, lista in sorted(grupos.items())}


def _dividir(lista, limite):
    return [lista[i:i + limite] for i in range(0, len(lista), limite)]


def _hoteis_em_ordem(solicitacoes):
    """-> [(hotel, quantidade)] na ordem de aparição"""
    contagem = {}
    for s in solicitacoes:
        contagem[s.hotel.nome] = contagem.get(s.hotel.nome, 0) + 1
    return list(contagem.items())


def assunto_individual(s):
    """'Solicitação NF - RONDONÓPOLIS - Nome do hóspede'"""
    return f"Solicitação NF - {s.hotel.nome} - {s.nome_titulo}"[:TAMANHO_MAXIMO_ASSUNTO]


def montar_assunto(solicitacoes, parte=1, total_partes=1):
    """'Solicitações NF (12) - Hotel A, Hotel B e mais 3'"""
    nomes = [nome for nome, _ in _hoteis_em_ordem(solicitacoes)]
    inicio = f"Solicitações NF ({len(solicitacoes)}) - "
    sufixo = f" [parte {parte}/{total_partes}]" if total_partes > 1 else ""

    usados = []
    for i, nome in enumerate(nomes):
        restantes = len(nomes) - i - 1
        candidato = ", ".join(usados + [nome])
        resto = f" e mais {restantes}" if restantes else ""
        if len(inicio + candidato + resto + sufixo) > TAMANHO_MAXIMO_ASSUNTO and usados:
            return inicio + ", ".join(usados) + f" e mais {len(nomes) - len(usados)}" + sufixo
        usados.append(nome)
    return inicio + ", ".join(usados) + sufixo


def _tabela_solicitacao(s, numero, total_hotel, formato_data):
    remetente = escape(s.email_hospede or "Não informado")
    enviado_em = escape(converter_data(s.carimbo, s.formato_data or formato_data) or "Não informado")
    linhas = []
    for i, (campo, valor) in enumerate(s.campos):
        linhas.append(
            f'<tr style="background-color:{COR_CREME};color:{COR_TEXTO_TABELA};">'
            f'<td style="padding:8px;border:1px solid {COR_BORDA_TABELA};width:35%;vertical-align:top;"><strong>{escape(campo)}</strong></td>'
            f'<td style="padding:8px;border:1px solid {COR_BORDA_TABELA};">{escape(str(valor))}</td></tr>'
        )
    return f"""
<div style="margin:18px 0 26px 0;">
  <p style="{FONTE}font-size:14px;margin:0 0 4px 0;color:{COR_PRIMARIA};">
    <strong>Solicitação {numero} de {total_hotel} — {escape(s.nome_titulo)}</strong></p>
  {paragrafo_status(s.ref, {"partes": s.partes_esperadas}) if s.ref else ""}
  <p style="{FONTE}font-size:12px;margin:0 0 6px 0;"><strong>Enviado por:</strong> {remetente}</p>
  <table style="border-collapse:collapse;{FONTE}font-size:13px;width:100%;">
    <thead><tr style="background-color:{COR_PRIMARIA};color:{COR_CREME};">
      <th style="padding:8px;text-align:left;border:1px solid {COR_PRIMARIA};">Campo</th>
      <th style="padding:8px;text-align:left;border:1px solid {COR_PRIMARIA};">Valor</th>
    </tr></thead>
    <tbody>{''.join(linhas)}</tbody>
  </table>
  <p style="{FONTE}font-size:12px;margin:6px 0 0 0;"><strong>Enviado em:</strong> {enviado_em}</p>
</div>"""


def montar_html(operador, solicitacoes, codigo, parte=1, total_partes=1,
                formato_data="americano", aviso_teste=None, agora=None):
    agora = agora or datetime.datetime.now()
    resumo = _hoteis_em_ordem(solicitacoes)

    linhas_resumo = "".join(
        f'<tr style="background-color:{COR_CREME};color:{COR_TEXTO_TABELA};"><td style="padding:6px 10px;border:1px solid {COR_BORDA_TABELA};">{escape(nome)}</td>'
        f'<td style="padding:6px 10px;border:1px solid {COR_BORDA_TABELA};text-align:right;">{qtd}</td></tr>'
        for nome, qtd in resumo
    )

    blocos, hotel_atual, lista_hotel = [], None, []

    def fechar_bloco():
        if not lista_hotel:
            return
        tabelas = "".join(_tabela_solicitacao(s, i, len(lista_hotel), formato_data)
                          for i, s in enumerate(lista_hotel, start=1))
        blocos.append(
            f'<h2 style="{FONTE}font-size:17px;color:{COR_CREME};background:{COR_PRIMARIA};'
            f'padding:10px 14px;margin:30px 0 0 0;border-left:6px solid {COR_CREME};">'
            f'{escape(hotel_atual)} <span style="font-weight:normal;font-size:13px;">'
            f'({len(lista_hotel)} solicitaç{"ão" if len(lista_hotel) == 1 else "ões"})</span></h2>'
            + tabelas)

    for s in solicitacoes:
        if s.hotel.nome != hotel_atual:
            fechar_bloco()
            hotel_atual, lista_hotel = s.hotel.nome, []
        lista_hotel.append(s)
    fechar_bloco()

    faixa_teste = ""
    if aviso_teste:
        faixa_teste = (f'<p style="{FONTE}background:#fff3cd;border:1px solid #e0b100;padding:10px;">'
                       f'<strong>MODO TESTE</strong> — em produção este e-mail iria para '
                       f'<strong>{escape(aviso_teste)}</strong>. Nada foi marcado como enviado na planilha.</p>')

    titulo_parte = f" — parte {parte} de {total_partes}" if total_partes > 1 else ""
    return f"""<html><body style="{FONTE}color:#222;">
{faixa_teste}
<h1 style="{FONTE}font-size:20px;color:{COR_PRIMARIA};margin:0 0 4px 0;">Solicitações de Nota Fiscal{titulo_parte}</h1>
<p style="{FONTE}font-size:12px;color:#666;margin:0 0 16px 0;">
  Operador: {escape(operador)} · Gerado em {agora.strftime('%d/%m/%Y %H:%M')} · {len(solicitacoes)} solicitação(ões)</p>

<table style="border-collapse:collapse;{FONTE}font-size:13px;min-width:320px;">
  <thead><tr style="background-color:{COR_PRIMARIA};color:{COR_CREME};">
    <th style="padding:6px 10px;text-align:left;border:1px solid #ddd;">Hotel</th>
    <th style="padding:6px 10px;text-align:right;border:1px solid #ddd;">Solicitações</th>
  </tr></thead>
  <tbody>{linhas_resumo}
    <tr style="font-weight:bold;background:{COR_CREME};color:{COR_TEXTO_TABELA};"><td style="padding:6px 10px;border:1px solid {COR_BORDA_TABELA};">Total</td>
    <td style="padding:6px 10px;border:1px solid {COR_BORDA_TABELA};text-align:right;">{len(solicitacoes)}</td></tr>
  </tbody>
</table>
{''.join(blocos)}
<p style="{FONTE}font-size:11px;color:#999;margin-top:30px;border-top:1px solid #eee;padding-top:8px;">
  E-mail gerado automaticamente pelo robô Solicitações NF. Código de envio: {codigo}</p>
</body></html>"""


# Visual "verde" (config visual_email = "verde"): fundo escuro, tudo em <table> pro Outlook não quebrar o layout
V, C, V2, C2, LINHA = "#173f39", "#d5bda1", "#1f4b44", "#a8977f", "#2d5b53"


def _tabela_solicitacao_verde(s, numero, total_hotel, formato_data):
    remetente = escape(s.email_hospede or "Não informado")
    enviado_em = escape(converter_data(s.carimbo, s.formato_data or formato_data) or "Não informado")
    linhas = "".join(
        f'<tr><td style="{FONTE}font-size:12px;color:{C2};padding:7px 12px;border-top:1px solid {LINHA};'
        f'width:38%;vertical-align:top;">{escape(campo)}</td>'
        f'<td style="{FONTE}font-size:13px;color:{C};padding:7px 12px;border-top:1px solid {LINHA};">'
        f'{escape(str(valor))}</td></tr>'
        for campo, valor in s.campos)
    return f"""
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:0 0 14px 0;">
  <tr><td style="background:{V2};border-left:4px solid {C};padding:14px 16px;">
    <p style="{FONTE}font-size:11px;letter-spacing:2px;text-transform:uppercase;color:{C2};margin:0 0 3px 0;">
      Solicitação {numero} de {total_hotel}</p>
    <p style="{FONTE}font-size:16px;font-weight:bold;color:{C};margin:0 0 8px 0;">{escape(s.nome_titulo)}</p>
    {paragrafo_status(s.ref, {"partes": s.partes_esperadas}) if s.ref else ""}
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin-top:4px;">
      {linhas}
    </table>
    <p style="{FONTE}font-size:11px;color:{C2};margin:10px 0 0 0;">
      Pedido feito em <strong style="color:{C};">{enviado_em}</strong> por <strong style="color:{C};">{remetente}</strong></p>
  </td></tr>
</table>"""


def montar_html_verde(operador, solicitacoes, codigo, parte=1, total_partes=1,
                      formato_data="americano", aviso_teste=None, agora=None):
    agora = agora or datetime.datetime.now()
    resumo = _hoteis_em_ordem(solicitacoes)
    total = len(solicitacoes)

    blocos, hotel_atual, lista_hotel = [], None, []

    def fechar_bloco():
        if not lista_hotel:
            return
        n = len(lista_hotel)
        blocos.append(
            f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:22px 0 12px 0;">'
            f'<tr><td style="background:{C};padding:10px 16px;">'
            f'<span style="{FONTE}font-size:16px;font-weight:bold;color:{V};">{escape(hotel_atual)}</span>'
            f'<span style="{FONTE}font-size:12px;color:{V};"> · {n} solicitaç{"ão" if n == 1 else "ões"}</span>'
            f'</td></tr></table>'
            + "".join(_tabela_solicitacao_verde(s, i, n, formato_data) for i, s in enumerate(lista_hotel, start=1)))

    for s in solicitacoes:
        if s.hotel.nome != hotel_atual:
            fechar_bloco()
            hotel_atual, lista_hotel = s.hotel.nome, []
        lista_hotel.append(s)
    fechar_bloco()

    faixa_teste = ""
    if aviso_teste:
        faixa_teste = (f'<p style="{FONTE}font-size:13px;color:{C};border:1px dashed {C};padding:10px 14px;margin:0 0 16px 0;">'
                       f'<strong>MODO TESTE</strong> — em produção este e-mail iria para <strong>{escape(aviso_teste)}</strong>. '
                       f'Nada foi marcado como enviado na planilha.</p>')
    resumo_hoteis = "".join(
        f'<tr><td style="{FONTE}font-size:13px;color:{C};padding:6px 12px;border-top:1px solid {LINHA};">{escape(nome)}</td>'
        f'<td style="{FONTE}font-size:13px;color:{C};padding:6px 12px;border-top:1px solid {LINHA};text-align:right;">{qtd}</td></tr>'
        for nome, qtd in resumo) if len(resumo) > 1 else ""
    titulo_parte = f" · parte {parte} de {total_partes}" if total_partes > 1 else ""
    hotel_titulo = resumo[0][0] if len(resumo) == 1 else f"{len(resumo)} hotéis"

    return f"""<html><body style="margin:0;padding:0;background:{V};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" bgcolor="{V}" style="background:{V};border-collapse:collapse;">
<tr><td align="center" style="padding:28px 14px;">
<table role="presentation" width="680" cellpadding="0" cellspacing="0" style="max-width:680px;width:100%;border-collapse:collapse;">
<tr><td>
  {faixa_teste}
  <p style="{FONTE}font-size:11px;letter-spacing:4px;text-transform:uppercase;color:{C2};margin:0 0 6px 0;">Rede Andrade · Solicitações NF</p>
  <p style="{FONTE}font-size:24px;font-weight:bold;color:{C};margin:0 0 4px 0;">Solicitações de Nota Fiscal{titulo_parte}</p>
  <p style="{FONTE}font-size:13px;color:{C2};margin:0 0 18px 0;">{escape(hotel_titulo)} · {agora.strftime('%d/%m/%Y %H:%M')}</p>

  <table role="presentation" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:0 0 6px 0;">
    <tr><td style="background:{C};padding:12px 22px;text-align:center;">
      <span style="{FONTE}font-size:30px;font-weight:bold;color:{V};line-height:1;">{total}</span><br>
      <span style="{FONTE}font-size:11px;color:{V};">solicitaç{"ão" if total == 1 else "ões"} de nota fiscal</span>
    </td></tr>
  </table>
  {f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;margin:10px 0 0 0;">{resumo_hoteis}</table>' if resumo_hoteis else ""}

  {''.join(blocos)}

  <p style="{FONTE}font-size:12px;color:{C2};margin:22px 0 0 0;line-height:1.6;">
    Ao enviar a nota ao hóspede, use o assunto <strong style="color:{C};">NF 1234 - NOME</strong> com o arquivo anexado:
    o robô reconhece o envio e marca a solicitação aqui como <strong style="color:{C};">NF enviada</strong>.</p>
  <p style="{FONTE}font-size:10px;color:{C2};margin:18px 0 0 0;border-top:1px solid {LINHA};padding-top:10px;">
    E-mail gerado automaticamente pelo robô Solicitações NF · para {escape(operador)} · Código de envio: {codigo}</p>
</td></tr></table>
</td></tr></table>
</body></html>"""


def novo_codigo():
    return "NF-" + uuid.uuid4().hex[:10].upper()


def montar_emails(solicitacoes, cfg):
    """agrupar_email = "solicitacao": um e-mail por solicitação; "hotel": um por operador, em partes."""
    emails = []
    controle_nf.VISUAL = cfg.get("visual_email", "classico")
    montar = montar_html_verde if controle_nf.VISUAL == "verde" else montar_html
    limite = cfg["limite_solicitacoes_por_email"]
    modo_teste = cfg["modo"] == "TESTE"
    uma_por_email = cfg.get("agrupar_email", "hotel") == "solicitacao"
    for operador, lista in agrupar_por_operador(solicitacoes).items():
        partes = [[s] for s in lista] if uma_por_email else _dividir(lista, limite)
        for i, parte in enumerate(partes, start=1):
            codigo = novo_codigo()
            for n, s in enumerate(parte, start=1):
                s.ref = f"{codigo}-{n:02d}"
            assunto = (assunto_individual(parte[0]) if uma_por_email else montar_assunto(parte, i, len(partes)))
            if modo_teste:
                assunto = "[TESTE] " + assunto
            emails.append(EmailMontado(
                operador=operador,
                destinatario=cfg["email_teste"] if modo_teste else operador,
                assunto=assunto,
                html=montar(operador, parte, codigo, 1 if uma_por_email else i, 1 if uma_por_email else len(partes),
                                 cfg.get("formato_data_planilha", "americano"),
                                 aviso_teste=operador if modo_teste else None),
                codigo=codigo,
                solicitacoes=parte,
            ))
    return emails
