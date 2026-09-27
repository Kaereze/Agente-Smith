r"""Gera um e-mail de exemplo (dados inventados) sem enviar.
Uso: python Automacoes\\gerar_exemplo_email.py [verde|classico]
"""
import datetime
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, "src"))

import controle_nf
from controle_nf import paragrafo_status, trocar_paragrafo_status
from modelos import Hotel, Solicitacao
import montar_email

visual = sys.argv[1] if len(sys.argv) > 1 else "verde"
controle_nf.VISUAL = visual
hotel = Hotel(aba="Solicitação Nota Fiscal (LUXOR) (respostas)", nome="LUXOR", operador="notafiscal@redeandradeluxor.com.br",
              planilha_id="exemplo", email_hotel="notafiscal@redeandradeluxor.com.br", agente="João")


def pedido(linha, carimbo, email, nome, campos, partes=1):
    return Solicitacao(hotel=hotel, linha=linha, carimbo=carimbo, email_hospede=email, nome_titulo=nome,
                       campos=campos, formato_data="brasileiro", partes_esperadas=partes)


lista = [
    pedido(812, "26/09/2026 08:14:32", "financeiro@transportesaurora.com.br", "TRANSPORTES AURORA LTDA", [
        ("Reserva no nome do tomador", "Não"), ("Razão social", "Transportes Aurora Ltda"),
        ("CNPJ", "12.345.678/0001-90"), ("Nome do hóspede", "Carlos Eduardo Mendes"),
        ("Data de entrada", "23/09/2026"), ("Data de saída", "26/09/2026"), ("Valor da hospedagem", "R$ 1.047,00"),
        ("E-mail para envio da nota", "financeiro@transportesaurora.com.br")]),
    pedido(813, "26/09/2026 09:02:10", "marina.alves@email.com", "Marina Alves Pereira", [
        ("Reserva no nome do tomador", "Sim"), ("Nome completo", "Marina Alves Pereira"), ("CPF", "123.456.789-00"),
        ("Data de entrada", "24/09/2026"), ("Data de saída", "26/09/2026"), ("Valor da hospedagem", "R$ 698,00"),
        ("Observação", "Emitir com o endereço da empresa, por favor")]),
    pedido(814, "26/09/2026 09:47:55", "compras@agrovale.com.br", "AGROVALE COMÉRCIO DE INSUMOS", [
        ("Razão social", "Agrovale Comércio de Insumos S.A."), ("CNPJ", "98.765.432/0001-10"),
        ("Nome do hóspede", "Rafael Souza Lima"), ("Data de entrada", "22/09/2026"), ("Data de saída", "26/09/2026"),
        ("Nota dividida", "Sim — em 2 notas"), ("Valor da hospedagem", "R$ 1.396,00")], partes=2),
]
cfg = {"limite_solicitacoes_por_email": 50, "modo": "PRODUCAO", "email_teste": "", "visual_email": visual}
email = montar_email.montar_emails(lista, cfg)[0]

# Mostra os selos como ficam DEPOIS que o conferente trabalha: 1 NF enviada, 1 tratativa, 1 aguardando
agora = datetime.datetime(2026, 9, 26, 10, 31).isoformat()
estados = [{"nfs": {"4821": {"data": agora, "prova": "CNPJ confere"}}},
           {"tratativas": {"x": {"data": agora}}},
           {"partes": 2}]
html = email.html
for s, estado in zip(lista, estados):
    html, _ = trocar_paragrafo_status(html, s.ref, paragrafo_status(s.ref, estado))

destino = os.path.join(RAIZ, "Docs", f"exemplo_email_{visual}.html")
os.makedirs(os.path.dirname(destino), exist_ok=True)
open(destino, "w", encoding="utf-8").write(html)
print("Assunto:", email.assunto)
print("Salvo em:", destino)
