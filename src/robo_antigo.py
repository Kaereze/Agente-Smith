"""Convivência com o robô antigo (Apps Script via Gmail), que ainda atende alguns hotéis.

Um pedido é identificado pelo e-mail do hóspede + carimbo do formulário até o segundo,
que o robô antigo imprime no rodapé ("Enviado em: Fri Sep 25 2026 22:58:03 GMT-0300").
"""
import datetime
import json
import re

from arquivos import salvar_json
from log_util import configurar_logging
from tratamento import ler_data

logger = configurar_logging(__name__)

MESES = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
PADRAO = {"remetente": "redeandrade.notafiscal@gmail.com", "espera_minutos": 75, "dias_ativo": 3, "dias_caixa": 10}


def opcoes(cfg):
    return {**PADRAO, **{k: v for k, v in cfg.get("robo_antigo", {}).items() if not k.startswith("_")}}


def momento(carimbo, formato):
    """'25/09/2026 22:58:03' -> datetime"""
    data = ler_data(carimbo, formato)
    h = re.search(r"(\d{1,2}):(\d{2})(?::(\d{2}))?", carimbo or "")
    if not data or not h:
        return None
    return datetime.datetime(data.year, data.month, data.day, int(h.group(1)), int(h.group(2)), int(h.group(3) or 0))


def momento_do_email_antigo(texto):
    """'Fri Sep 25 2026 22:58:03 GMT-0300' -> datetime"""
    m = re.search(r"(\w{3}) (\d{1,2}) (\d{4}) (\d{2}):(\d{2}):(\d{2})", texto or "")
    if not m or m.group(1).lower() not in MESES:
        return None
    return datetime.datetime(int(m.group(3)), MESES[m.group(1).lower()], int(m.group(2)),
                             int(m.group(4)), int(m.group(5)), int(m.group(6)))


def chave(email, quando):
    return (str(email or "").strip().lower(), quando)


def _ate(iso, limite):
    try:
        return datetime.datetime.fromisoformat(iso) <= limite
    except (TypeError, ValueError):
        return False


def registrar_atividade(caminho, vistos, agora=None):
    """vistos = {hotel: pedido mais recente que o robô antigo marcou TRUE}. Data no futuro (carimbo lido no formato
    errado: 10/12 virou dezembro) não vale e sai do arquivo: deixaria o hotel "esperando o robô antigo" até lá."""
    limite = (agora or datetime.datetime.now()) + datetime.timedelta(days=1)
    try:
        atual = json.load(open(caminho, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        atual = {}
    atual = {h: iso for h, iso in atual.items() if _ate(iso, limite)}
    for hotel, quando in vistos.items():
        if quando and quando <= limite and (hotel not in atual or quando.isoformat() > atual[hotel]):
            atual[hotel] = quando.isoformat(timespec="seconds")
    salvar_json(caminho, atual)


def hoteis_ativos(caminho, agora, dias):
    try:
        atual = json.load(open(caminho, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return set()
    limite = agora - datetime.timedelta(days=dias)
    return {h for h, iso in atual.items() if datetime.datetime.fromisoformat(iso) >= limite}


def emails_do_robo_antigo(namespace, remetente, desde):
    """{(email_hospede, momento_do_pedido): 'dd/mm HH:MM'} das Caixas de Entrada deste Outlook."""
    achados = {}

    def varrer(pasta, profundidade=0):
        try:
            itens = pasta.Items
            itens.Sort("[ReceivedTime]", True)
            for item in itens:
                try:
                    recebido = item.ReceivedTime.replace(tzinfo=None)
                except Exception:
                    continue
                if recebido < desde:
                    break
                try:
                    if str(item.SenderEmailAddress or "").lower() != remetente:
                        continue
                    corpo = item.Body or ""
                except Exception:
                    continue
                por = re.search(r"Enviado por:\s*(\S+@\S+)", corpo)
                quando = momento_do_email_antigo((re.search(r"Enviado em:\s*(.+)", corpo) or [None, ""])[1])
                if por and quando:
                    achados[chave(por.group(1), quando)] = recebido.strftime("%d/%m %H:%M")
        except Exception:
            pass
        if profundidade < 1:
            try:
                for sub in pasta.Folders:
                    varrer(sub, profundidade + 1)
            except Exception:
                pass

    for conta in namespace.Accounts:
        try:
            varrer(conta.DeliveryStore.GetDefaultFolder(6))
        except Exception:
            continue
    return achados


def separar(pendentes, ativos, agora, espera_minutos):
    """-> (liberadas, aguardando). Em hotel onde o antigo está ativo, pedido recente espera a vez dele."""
    liberadas, aguardando = [], []
    limite = agora - datetime.timedelta(minutes=espera_minutos)
    for s in pendentes:
        quando = momento(s.carimbo, s.formato_data)
        if s.hotel.nome in ativos and quando and quando > limite:
            aguardando.append(s)
        else:
            liberadas.append(s)
    return liberadas, aguardando


def ja_mandadas_pelo_antigo(pendentes, enviados_antigo):
    """-> [(solicitacao, 'dd/mm HH:MM')]"""
    saida = []
    for s in pendentes:
        quando = momento(s.carimbo, s.formato_data)
        if quando and chave(s.email_hospede, quando) in enviados_antigo:
            saida.append((s, enviados_antigo[chave(s.email_hospede, quando)]))
    return saida
