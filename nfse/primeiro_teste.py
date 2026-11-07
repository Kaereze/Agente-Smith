"""Primeiro teste real com a PRODUÇÃO RESTRITA (ambiente de teste do governo). Roda no PC da empresa, na mão.

Uso (dentro da pasta do repositório):
    python -m nfse.primeiro_teste certificado --pfx C:\\caminho\\BOA_VIAGEM.pfx --cnpj-hotel 00000000000000
    python -m nfse.primeiro_teste assinatura  --pfx C:\\caminho\\BOA_VIAGEM.pfx
    python -m nfse.primeiro_teste conexao     --pfx C:\\caminho\\BOA_VIAGEM.pfx
    python -m nfse.primeiro_teste emitir      --pfx ... --dados nfse\\dados_teste.json --xsd C:\\xsd\\DPS_v1.00.xsd --algoritmo sha256
    python -m nfse.primeiro_teste consultar   --pfx ... --dps-id DPS...   (ou --chave 50 dígitos)
    python -m nfse.primeiro_teste cancelar    --pfx ... --chave ... --motivo "texto de 15 a 255 letras" --xsd C:\\xsd\\evento.xsd

A SENHA do certificado nunca vai na linha de comando: o programa lê da variável de ambiente NFSE_CERT_SENHA ou pergunta
no terminal (sem mostrar). Nunca escreva a senha em arquivo, chat ou commit.

Trava: só fala com a produção restrita (nfse/trava.py). Emitir e cancelar exigem você digitar a confirmação.
"""
import argparse
import getpass
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from . import assinatura, certificado, cliente, dps, trava

PASTA_SAIDA = Path("saida_nfse_teste")        # no .gitignore; só dados de teste
CODIGO_RECIFE = "2611606"
DPS_INEXISTENTE = "DPS" + CODIGO_RECIFE + "2" + "11222333000181" + "00001" + "000000000000001"   # só para testar a conexão

TABELA_ERROS = {
    200: "Deu certo.",
    201: "Nota criada (no ambiente de teste).",
    400: "O governo recusou os DADOS ou o XML. Leia a lista de erros (código, descrição) logo abaixo e corrija o dado, não o programa.",
    401: "Não autenticado. Confira se o certificado foi apresentado (finalidade 'Autenticação do Cliente').",
    403: "Certificado recusado: vencido, revogado, sem a finalidade certa, cadeia incompleta ou CNPJ sem cadastro no Emissor Nacional.",
    404: "Não existe (para consulta, isso é resposta normal e significa que ainda não foi emitido).",
    500: "Erro do lado do governo. NÃO repita o envio: consulte pelo Id da DPS antes de decidir.",
    501: "Endereço antigo, foi movido para o ADN.",
}
FALHAS_DE_CONEXAO = (
    "Falhou ANTES de chegar na API (handshake/TLS). Causas comuns: certificado sem 'Autenticação do Cliente', cadeia ICP-Brasil "
    "não instalada neste PC, relógio do PC errado, proxy/antivírus da empresa interceptando HTTPS, PC sem internet."
)


def _dizer(texto=""):
    print(texto)


def _senha():
    senha = os.environ.get("NFSE_CERT_SENHA")
    return senha if senha else getpass.getpass("Senha do certificado (não aparece na tela): ")


def _abrir_certificado(args):
    try:
        return certificado.carregar(args.pfx, _senha())
    except certificado.CertificadoInvalido as erro:
        _dizer(f"ERRO: {erro}")
        sys.exit(2)


def _guardar(nome, conteudo):
    PASTA_SAIDA.mkdir(exist_ok=True)
    caminho = PASTA_SAIDA / nome
    caminho.write_text(conteudo, encoding="utf-8")
    return caminho


def _mostrar_resposta(r):
    _dizer(f"  HTTP {r.status}: {TABELA_ERROS.get(r.status, 'código fora da tabela')}")
    corpo = r.json if isinstance(r.json, dict) else {}
    for lista in ("erros", "alertas"):
        for item in corpo.get(lista) or []:
            _dizer(f"  - {lista[:-1]} {item.get('codigo')}: {item.get('descricao')} {item.get('complemento') or ''}".rstrip())
    if isinstance(corpo.get("erro"), dict):
        e = corpo["erro"]
        _dizer(f"  - erro {e.get('codigo')}: {e.get('descricao')} {e.get('complemento') or ''}".rstrip())
    if not corpo and r.text.strip():
        _dizer(f"  (corpo não é JSON, {len(r.text)} letras; salvo em {_guardar('ultima_resposta.txt', r.text)})")


def _confirmar(frase):
    _dizer(f"\nPara continuar digite exatamente:  {frase}")
    return input("> ").strip() == frase


def cmd_certificado(args):
    cert = _abrir_certificado(args)
    _dizer(f"Certificado de: {cert.nome}")
    erros = 0
    for item in certificado.diagnostico(cert, cnpj_esperado=args.cnpj_hotel):
        _dizer(f"  [{item.nivel.upper():5}] {item.texto}")
        erros += item.nivel == "erro"
    _dizer("\nRESULTADO: " + ("há ERRO acima, resolva antes de seguir." if erros else "pode seguir para a etapa 'assinatura'."))
    return 1 if erros else 0


def _dados_de_exemplo():
    return dps.DadosDPS(
        prestador_cnpj="11222333000181", cod_municipio=CODIGO_RECIFE, serie="1", n_dps=1,
        dh_emi=datetime.now(timezone.utc).astimezone().replace(microsecond=0), competencia=datetime.now().date(),
        tomador_doc="11144477735", tomador_nome="MARCOS EXEMPLO", valor=dps.validacao.dinheiro("100.00"),
        descricao="TESTE DE ASSINATURA - HOSPEDAGEM 1 DIARIA, VALOR DA DIARIA: R$ 100,00", cod_trib_mun="501",
    )


def cmd_assinatura(args):
    """Offline: assina um DPS inventado com SHA-256 e com SHA-1 e confere as duas. Não manda nada para a internet."""
    cert = _abrir_certificado(args)
    xml = dps.montar_dps(_dados_de_exemplo())
    id_ = dps.id_da_dps(_dados_de_exemplo())
    for algoritmo in ("sha256", "sha1"):
        assinado = assinatura.assinar(xml, id_, cert, algoritmo)
        ok, motivo = assinatura.verificar(assinado)
        caminho = _guardar(f"dps_exemplo_{algoritmo}.xml", assinado)
        _dizer(f"  {algoritmo.upper():7} {'OK ' if ok else 'ERRO'} {motivo}  -> {caminho}")
    _dizer("\nIsto só prova que a conta de assinar está certa neste PC. Qual algoritmo o governo aceita (P-19) só o 'emitir' mostra.")
    return 0


def cmd_conexao(args):
    """Duas consultas que não gravam nada: convênio do município (ADN) e DPS que não existe (Sefin)."""
    cli = cliente.Cliente(_abrir_certificado(args))
    pedidos = (("ADN: município aderiu ao Emissor Nacional?", f"{cliente.ADN_PARAMETROS}/{CODIGO_RECIFE}/convenio", "GET"),
               ("Sefin: consulta de DPS que não existe (404 = conexão OK)", f"{cliente.SEFIN}/dps/{DPS_INEXISTENTE}", "GET"))
    falhas = 0
    for titulo, url, metodo in pedidos:
        _dizer(f"\n{titulo}\n  {metodo} {url}")
        try:
            r = cli.consultar(metodo, url)
        except cliente.ErroRede as erro:
            _dizer(f"  {erro}\n  {FALHAS_DE_CONEXAO}")
            falhas += 1
            continue
        _mostrar_resposta(r)
        if r.text.strip():
            _dizer(f"  resposta guardada em {_guardar('conexao_' + str(len(url)) + '.json', r.text)}")
        falhas += r.status in (401, 403)
    return 1 if falhas else 0


def _checar_antes_de_enviar(xml_assinado, cert, cnpj_prestador):
    trava.validar_xml_de_teste(xml_assinado)
    prestador = dps.validacao.so_alfanum(cnpj_prestador)
    if not cert.cnpj or cert.cnpj != prestador:
        _dizer(f"RECUSADO: CNPJ do certificado ({cert.cnpj or 'não achei'}) é diferente do prestador ({prestador}).")
        return False
    ok, motivo = assinatura.verificar(xml_assinado)
    if not ok:
        _dizer(f"RECUSADO: {motivo}")
    return ok


def cmd_emitir(args):
    cert = _abrir_certificado(args)
    dados = dps.de_json(args.dados)
    achados = dps.problemas(dados)
    if achados:
        _dizer("DADOS COM PROBLEMA:\n  - " + "\n  - ".join(achados))
        return 1
    xml = dps.montar_dps(dados)
    erros_xsd = dps.validar_xsd(xml, args.xsd)
    if erros_xsd:
        _dizer("O XSD OFICIAL RECUSOU O XML (o XSD manda; ajuste nfse/dps.py e anote no cofre):\n  - " + "\n  - ".join(erros_xsd))
        return 1
    id_ = dps.id_da_dps(dados)
    assinado = assinatura.assinar(xml, id_, cert, args.algoritmo)
    if not _checar_antes_de_enviar(assinado, cert, dados.prestador_cnpj):
        return 1
    _dizer(f"\nRESUMO PARA CONFERIR (produção restrita, não vale como nota)\n  Id da DPS : {id_}\n  Prestador : {dados.prestador_cnpj}"
           f"\n  Tomador   : {dados.tomador_nome} ({dados.tomador_doc})\n  Valor     : R$ {dados.valor}\n  Descrição : {dados.descricao}"
           f"\n  Assinatura: {args.algoritmo.upper()}\n  Guardado  : {_guardar('dps_enviado.xml', assinado)}")
    if not _confirmar("EMITIR TESTE"):
        _dizer("Cancelado. Nada foi enviado.")
        return 0
    cli = cliente.Cliente(cert)
    try:
        ja = cli.consultar("GET", f"{cliente.SEFIN}/dps/{id_}")
    except cliente.ErroRede as erro:
        _dizer(f"Não consegui nem consultar antes de enviar ({erro}). Nada foi enviado.")
        return 1
    if ja.status == 200:
        _dizer("Esse Id de DPS JÁ virou nota. Não envio de novo (evita duplicidade). Use 'consultar'.")
        _mostrar_resposta(ja)
        return 1
    try:
        r = cli.enviar(f"{cliente.SEFIN}/nfse", {"dpsXmlGZipB64": cliente.compactar(assinado)})
    except cliente.ErroRede as erro:
        _dizer(f"{erro}\nNÃO sei se a nota foi criada. NÃO envie de novo: rode 'consultar --dps-id {id_}'.")
        return 1
    _mostrar_resposta(r)
    _guardar("resposta_emissao.json", r.text)
    if r.status == 201 and isinstance(r.json, dict):
        _dizer(f"\nCHAVE DE ACESSO: {r.json.get('chaveAcesso')}")
        if r.json.get("nfseXmlGZipB64"):
            _dizer(f"NFS-e (XML) guardada em {_guardar('nfse_emitida.xml', cliente.descompactar(r.json['nfseXmlGZipB64']))}")
        _dizer(f"Anote no cofre: algoritmo {args.algoritmo.upper()} foi ACEITO (fecha P-19).")
        return 0
    _dizer("Se o erro falar de assinatura/Signature, rode de novo com --algoritmo sha1 (ou sha256) e anote o resultado (P-19).")
    return 1


def cmd_consultar(args):
    cli = cliente.Cliente(_abrir_certificado(args))
    if args.chave:
        url = f"{cliente.SEFIN}/nfse/{args.chave}"
    elif args.dps_id:
        url = f"{cliente.SEFIN}/dps/{args.dps_id}"
    else:
        _dizer("Informe --chave (50 dígitos) ou --dps-id.")
        return 2
    try:
        r = cli.consultar("GET", url)
    except cliente.ErroRede as erro:
        _dizer(f"{erro}\n{FALHAS_DE_CONEXAO}")
        return 1
    _mostrar_resposta(r)
    if r.status == 200 and isinstance(r.json, dict) and r.json.get("nfseXmlGZipB64"):
        _dizer(f"NFS-e (XML) guardada em {_guardar('nfse_consultada.xml', cliente.descompactar(r.json['nfseXmlGZipB64']))}")
    return 0 if r.status in (200, 404) else 1


def cmd_cancelar(args):
    cert = _abrir_certificado(args)
    agora = datetime.now(timezone.utc).astimezone()
    try:
        xml = dps.montar_pedido_cancelamento(args.chave, cert.cnpj, args.motivo_codigo, args.motivo, agora)
    except dps.DadosInvalidos as erro:
        _dizer("PEDIDO COM PROBLEMA:\n  - " + "\n  - ".join(erro.args[0]))
        return 1
    erros_xsd = dps.validar_xsd(xml, args.xsd)
    if erros_xsd:
        _dizer("O XSD OFICIAL RECUSOU O PEDIDO:\n  - " + "\n  - ".join(erros_xsd))
        return 1
    assinado = assinatura.assinar(xml, f"PRE{args.chave}101101", cert, args.algoritmo)
    if not _checar_antes_de_enviar(assinado, cert, cert.cnpj):
        return 1
    _dizer(f"\nCANCELAR a nota de teste {args.chave}\n  Motivo: {args.motivo}\n  Guardado: {_guardar('pedido_cancelamento.xml', assinado)}")
    if not _confirmar("CANCELAR TESTE"):
        _dizer("Cancelado. Nada foi enviado.")
        return 0
    try:
        r = cliente.Cliente(cert).enviar(f"{cliente.SEFIN}/nfse/{args.chave}/eventos",
                                         {"pedidoRegistroEventoXmlGZipB64": cliente.compactar(assinado)})
    except cliente.ErroRede as erro:
        _dizer(f"{erro}\nNÃO sei se o cancelamento valeu. Rode 'consultar --chave {args.chave}' antes de tentar de novo.")
        return 1
    _mostrar_resposta(r)
    _guardar("resposta_cancelamento.json", r.text)
    return 0 if r.status in (200, 201) else 1


def montar_parser():
    p = argparse.ArgumentParser(prog="python -m nfse.primeiro_teste", description=__doc__.split("\n\n")[0])
    sub = p.add_subparsers(dest="comando", required=True)

    def com_pfx(nome, ajuda, funcao):
        s = sub.add_parser(nome, help=ajuda)
        s.add_argument("--pfx", required=True, help="caminho do certificado .pfx/.p12 (a senha é pedida à parte)")
        s.set_defaults(funcao=funcao)
        return s

    com_pfx("certificado", "confere validade, CNPJ e finalidade (offline)", cmd_certificado).add_argument("--cnpj-hotel", default=None)
    com_pfx("assinatura", "assina um DPS inventado com SHA-256 e SHA-1 (offline)", cmd_assinatura)
    com_pfx("conexao", "duas consultas que não gravam nada (online, só teste)", cmd_conexao)
    e = com_pfx("emitir", "emite UMA nota de teste, com confirmação digitada", cmd_emitir)
    e.add_argument("--dados", required=True)
    e.add_argument("--xsd", required=True, help="XSD oficial do DPS (obrigatório)")
    e.add_argument("--algoritmo", choices=sorted(assinatura.ALGORITMOS), default="sha256")
    c = com_pfx("consultar", "consulta nota ou DPS", cmd_consultar)
    c.add_argument("--chave")
    c.add_argument("--dps-id")
    x = com_pfx("cancelar", "cancela uma nota de TESTE, com confirmação digitada", cmd_cancelar)
    x.add_argument("--chave", required=True)
    x.add_argument("--motivo", required=True)
    x.add_argument("--motivo-codigo", default="1", help="código do motivo (P-21: conferir no XSD/manual)")
    x.add_argument("--xsd", required=True, help="XSD oficial do evento (obrigatório)")
    x.add_argument("--algoritmo", choices=sorted(assinatura.ALGORITMOS), default="sha256")
    return p


def main(argv=None):
    args = montar_parser().parse_args(argv)
    return args.funcao(args)


if __name__ == "__main__":
    sys.exit(main())
