"""Validações de dados do pedido de NFS-e de hospedagem (CPF, CNPJ numérico e alfanumérico, valores, datas, Id da DPS)."""
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
import re

CENT = Decimal('0.01')


def so_alfanum(texto: str) -> str:
    '''Tira pontos, barras e tracos e passa para maiusculo.'''
    return re.sub(r'[^0-9A-Za-z]', '', texto or '').upper()


def cpf_valido(texto: str) -> bool:
    cpf = re.sub(r'\D', '', texto or '')
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    for tamanho in (9, 10):
        soma = sum(int(cpf[i]) * (tamanho + 1 - i) for i in range(tamanho))
        dv = (soma * 10) % 11
        dv = 0 if dv == 10 else dv
        if dv != int(cpf[tamanho]):
            return False
    return True


def _dv_cnpj(base: str) -> int:
    '''Digito verificador do CNPJ. Letra vale o codigo ASCII menos 48.'''
    pesos = [2, 3, 4, 5, 6, 7, 8, 9]
    soma = 0
    for i, ch in enumerate(reversed(base)):
        soma += (ord(ch) - 48) * pesos[i % 8]
    resto = soma % 11
    return 0 if resto < 2 else 11 - resto


def cnpj_valido(texto: str) -> bool:
    cnpj = so_alfanum(texto)
    if len(cnpj) != 14 or not re.fullmatch(r'[0-9A-Z]{12}[0-9]{2}', cnpj):
        return False
    if cnpj == cnpj[0] * 14:
        return False
    d1 = _dv_cnpj(cnpj[:12])
    d2 = _dv_cnpj(cnpj[:12] + str(d1))
    return cnpj[12:] == f'{d1}{d2}'


def doc_tomador_valido(texto: str) -> tuple[bool, str]:
    '''Aceita CPF ou CNPJ. Devolve (valido, tipo).'''
    limpo = so_alfanum(texto)
    if len(limpo) == 11 and limpo.isdigit():
        return cpf_valido(limpo), 'CPF'
    if len(limpo) == 14:
        return cnpj_valido(limpo), 'CNPJ'
    return False, 'DESCONHECIDO'


def dinheiro(valor) -> Decimal:
    '''Converte para Decimal com 2 casas. Recusa float para nao perder centavo.'''
    if isinstance(valor, float):
        raise TypeError('use str ou Decimal, nao float')
    return Decimal(str(valor)).quantize(CENT, rounding=ROUND_HALF_UP)


def validar_estadia(checkin: date, checkout: date, qtd_diarias: int) -> list[str]:
    erros = []
    if checkout < checkin:
        erros.append('check-out anterior ao check-in')
    elif qtd_diarias != (checkout - checkin).days:
        erros.append('quantidade de diarias nao bate com as datas')
    if qtd_diarias < 1:
        erros.append('quantidade de diarias menor que 1')
    return erros


def total_nota(diaria_total, consumo, estacionamento) -> Decimal:
    '''Soma exata. diaria_total e o valor de todas as diarias juntas.'''
    partes = [dinheiro(diaria_total), dinheiro(consumo), dinheiro(estacionamento)]
    if any(p < 0 for p in partes):
        raise ValueError('valor negativo')
    total = sum(partes, Decimal('0.00'))
    if total <= 0:
        raise ValueError('valor total zero')
    return total


def valor_diaria_estimado(diaria_total, qtd_diarias: int) -> Decimal:
    '''Estimativa (RN-12). O valor oficial vem do QOps.'''
    return (dinheiro(diaria_total) / qtd_diarias).quantize(CENT, rounding=ROUND_HALF_UP)


def id_dps(cod_ibge: str, cnpj: str, serie: str, n_dps: int) -> str:
    '''Identificador da DPS: texto DPS, IBGE(7), tipo(1), inscricao(14), serie(5), numero(15).'''
    inscricao = so_alfanum(cnpj)
    if len(cod_ibge) != 7 or not cod_ibge.isdigit():
        raise ValueError('codigo IBGE deve ter 7 digitos')
    if len(inscricao) != 14:
        raise ValueError('CNPJ deve ter 14 caracteres')
    if not serie.isdigit() or len(serie) > 5 or not (1 <= int(serie) <= 99999):
        raise ValueError('serie invalida')
    if not (1 <= n_dps <= 999_999_999_999_999):
        raise ValueError('numero da DPS fora da faixa')
    ident = f'DPS{cod_ibge}2{inscricao}{int(serie):05d}{n_dps:015d}'
    assert len(ident) == 45
    return ident
