"""Montagem do DPS (Declaração de Prestação de Serviço) e do pedido de cancelamento — RASCUNHO.

ATENÇÃO (P-34): os nomes e a ordem das tags abaixo vêm do que se conhece do leiaute nacional v1.00, mas o XSD OFICIAL
não está no projeto ainda. Por isso:
- `validar_xsd` é OBRIGATÓRIO antes de assinar e enviar (RN-80). `primeiro_teste.py emitir` não funciona sem `--xsd`.
- Se o XSD recusar, o XSD manda: ajuste aqui e registre a diferença no cofre.
- Os campos do que ainda é dúvida de negócio (consumo/estacionamento dentro da nota: P-01/P-24/P-26) NÃO são montados
  aqui: a descrição vem pronta de fora e é conferida por gente.

O XML sai compacto (sem quebra de linha entre tags), com UM namespace só (o da raiz), porque `assinatura.py` depende disso.
"""
import json
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from xml.sax.saxutils import escape

from . import validacao

NS_NFSE = "http://www.sped.fazenda.gov.br/nfse"
VERSAO_LAYOUT = "1.00"          # P-layout: 1.00 ou 1.01, por configuração (RN-87)
VER_APLIC = "PAINEL-NFSE-0.1"
TP_AMB = 2                      # produção restrita; a trava confere de novo antes de enviar


class DadosInvalidos(Exception):
    """Lista de problemas em `args[0]`."""


@dataclass
class DadosDPS:
    prestador_cnpj: str
    cod_municipio: str            # IBGE de 7 dígitos (Recife = 2611606)
    serie: str
    n_dps: int
    dh_emi: datetime              # com fuso
    competencia: date
    tomador_doc: str              # CPF ou CNPJ
    tomador_nome: str
    descricao: str
    valor: Decimal
    cod_trib_nac: str = "090101"  # hospedagem
    cod_trib_mun: str = ""        # ex.: "501" nos hotéis de Recife (P-29)
    nbs: str = "103031100"
    op_simp_nac: int = 1          # 1 = não optante, 2 = MEI, 3 = ME/EPP (conferir no XSD)
    reg_esp_trib: int = 0
    aliquota_iss: Decimal = None  # só quando o município/regime pede (hotel do Simples não leva)
    trib_issqn: int = 1
    tp_ret_issqn: int = 1


def de_json(caminho):
    """Lê o arquivo de dados de teste (ver nfse/exemplo_dados_teste.json)."""
    with open(caminho, encoding="utf-8") as f:
        d = json.load(f)
    return DadosDPS(
        prestador_cnpj=d["prestador_cnpj"], cod_municipio=d["cod_municipio"], serie=str(d["serie"]), n_dps=int(d["n_dps"]),
        dh_emi=datetime.fromisoformat(d["dh_emi"]), competencia=date.fromisoformat(d["competencia"]),
        tomador_doc=d["tomador_doc"], tomador_nome=d["tomador_nome"], descricao=d["descricao"],
        valor=validacao.dinheiro(d["valor"]), cod_trib_nac=d.get("cod_trib_nac", "090101"), cod_trib_mun=d.get("cod_trib_mun", ""),
        nbs=d.get("nbs", "103031100"), op_simp_nac=int(d.get("op_simp_nac", 1)), reg_esp_trib=int(d.get("reg_esp_trib", 0)),
        aliquota_iss=validacao.dinheiro(d["aliquota_iss"]) if d.get("aliquota_iss") not in (None, "") else None,
    )


def problemas(d):
    """Conferências antes de montar. Lista vazia = pode seguir. Nunca adivinha: faltou, avisa."""
    erros = []
    if not validacao.cnpj_valido(d.prestador_cnpj):
        erros.append("CNPJ do prestador inválido")
    ok_doc, tipo = validacao.doc_tomador_valido(d.tomador_doc)
    if not ok_doc:
        erros.append(f"documento do tomador inválido ({tipo})")
    if not (d.cod_municipio.isdigit() and len(d.cod_municipio) == 7):
        erros.append("código do município deve ter 7 dígitos")
    if not d.tomador_nome.strip():
        erros.append("nome do tomador vazio")
    if not (15 <= len(d.descricao.strip()) <= 2000):
        erros.append("descrição do serviço fora do tamanho (15 a 2000 letras)")
    if d.dh_emi.tzinfo is None:
        erros.append("data/hora de emissão sem fuso horário")
    if d.valor <= 0:
        erros.append("valor deve ser maior que zero")
    if len(d.cod_trib_nac) != 6 or not d.cod_trib_nac.isdigit():
        erros.append("código de tributação nacional deve ter 6 dígitos")
    try:
        validacao.id_dps(d.cod_municipio, d.prestador_cnpj, d.serie, d.n_dps)
    except (ValueError, AssertionError) as erro:
        erros.append(f"Id da DPS: {erro}")
    return erros


def id_da_dps(d):
    return validacao.id_dps(d.cod_municipio, d.prestador_cnpj, d.serie, d.n_dps)


def _tag(nome, valor):
    return f"<{nome}>{escape(str(valor))}</{nome}>"


def _doc(tag_cnpj_cpf_valor):
    limpo = validacao.so_alfanum(tag_cnpj_cpf_valor)
    return _tag("CPF", limpo) if len(limpo) == 11 else _tag("CNPJ", limpo)


def montar_dps(d):
    """XML do DPS SEM assinatura (str). Levanta DadosInvalidos se `problemas` achar algo."""
    achados = problemas(d)
    if achados:
        raise DadosInvalidos(achados)
    id_ = id_da_dps(d)
    cserv = _tag("cTribNac", d.cod_trib_nac) + (_tag("cTribMun", d.cod_trib_mun) if d.cod_trib_mun else "")
    cserv += _tag("xDescServ", d.descricao.strip()) + _tag("cNBS", d.nbs)
    trib_mun = _tag("tribISSQN", d.trib_issqn) + _tag("tpRetISSQN", d.tp_ret_issqn)
    if d.aliquota_iss is not None:
        trib_mun = _tag("tribISSQN", d.trib_issqn) + _tag("pAliq", d.aliquota_iss) + _tag("tpRetISSQN", d.tp_ret_issqn)
    inf = (_tag("tpAmb", TP_AMB) + _tag("dhEmi", d.dh_emi.replace(microsecond=0).isoformat()) + _tag("verAplic", VER_APLIC)
           + _tag("serie", int(d.serie)) + _tag("nDPS", d.n_dps) + _tag("dCompet", d.competencia.isoformat()) + _tag("tpEmit", 1)
           + _tag("cLocEmi", d.cod_municipio)
           + "<prest>" + _doc(d.prestador_cnpj) + "<regTrib>" + _tag("opSimpNac", d.op_simp_nac) + _tag("regEspTrib", d.reg_esp_trib)
           + "</regTrib></prest>"
           + "<toma>" + _doc(d.tomador_doc) + _tag("xNome", d.tomador_nome.strip()) + "</toma>"
           + "<serv><locPrest>" + _tag("cLocPrestacao", d.cod_municipio) + "</locPrest><cServ>" + cserv + "</cServ></serv>"
           + "<valores><vServPrest>" + _tag("vServ", d.valor) + "</vServPrest><trib><tribMun>" + trib_mun + "</tribMun></trib></valores>")
    return f'<DPS xmlns="{NS_NFSE}" versao="{VERSAO_LAYOUT}"><infDPS Id="{id_}">{inf}</infDPS></DPS>'


def montar_pedido_cancelamento(chave, cnpj_autor, motivo_codigo, motivo_texto, dh_evento, n_pedido=1):
    """XML do pedido de cancelamento (evento 101101), sem assinatura — RASCUNHO, mesmo aviso do topo.

    Motivo: 15 a 255 letras (RN-84). O código do motivo (1, 2…) ainda não foi confirmado: P-21.
    """
    if not (chave.isdigit() and len(chave) == 50):
        raise DadosInvalidos(["chave de acesso deve ter 50 dígitos"])
    if not validacao.cnpj_valido(cnpj_autor):
        raise DadosInvalidos(["CNPJ do autor inválido"])
    if not (15 <= len(motivo_texto.strip()) <= 255):
        raise DadosInvalidos(["motivo deve ter de 15 a 255 letras"])
    id_ = f"PRE{chave}101101"
    inf = (_tag("tpAmb", TP_AMB) + _tag("verAplic", VER_APLIC) + _tag("dhEvento", dh_evento.replace(microsecond=0).isoformat())
           + _doc(cnpj_autor) + _tag("chNFSe", chave) + _tag("nPedRegEvento", f"{n_pedido:03d}")
           + "<e101101>" + _tag("xDesc", "Cancelamento de NFS-e") + _tag("cMotivo", motivo_codigo) + _tag("xMotivo", motivo_texto.strip())
           + "</e101101>")
    return f'<pedRegEvento xmlns="{NS_NFSE}" versao="{VERSAO_LAYOUT}"><infPedReg Id="{id_}">{inf}</infPedReg></pedRegEvento>'


def validar_xsd(xml, caminho_xsd):
    """Valida contra o XSD oficial. Precisa do pacote lxml (pip install lxml). Devolve lista de erros (vazia = válido)."""
    try:
        from lxml import etree
    except ImportError:
        raise RuntimeError("para validar o XSD instale o lxml:  pip install lxml") from None
    esquema = etree.XMLSchema(etree.parse(str(caminho_xsd)))
    documento = etree.fromstring(xml.encode("utf-8"))
    esquema.validate(documento)
    return [f"linha {e.line}: {e.message}" for e in esquema.error_log]
