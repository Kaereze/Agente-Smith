"""Modelos de dados: Hotel, Solicitacao, EmailMontado."""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hotel:
    aba: str            # nome da aba com as respostas desse hotel
    nome: str           # nome do hotel como aparece no e-mail
    operador: str       # e-mail do operador que recebe
    planilha_id: str    # planilha onde a aba mora
    email_hotel: str = ""  # conta do hotel (coluna B do Cadastro_Hoteis) — de onde saem as NFs
    agente: str = ""       # nome do agente (coluna C do Cadastro_Hoteis) — aparece no Log de Envios


@dataclass
class Solicitacao:
    hotel: Hotel
    linha: int                  # número da linha na planilha (1 = cabeçalho)
    carimbo: str                # "Carimbo de data/hora" do Forms, como veio da planilha
    email_hospede: str
    nome_titulo: str            # nome usado no título do bloco (mesma regra do assunto antigo)
    campos: list                # [(campo, valor)] já tratados, sem vazios/ocultos
    linha_bruta: list = field(default_factory=list)   # valores originais (pra aba Registros)
    assinatura: str = ""        # "impressão digital" da linha inteira (sem a coluna Enviado)
    formato_data: str = ""      # "americano"/"brasileiro" — descoberto por aba (dados colados vêm diferentes)
    # Pro conferente (controle_nf.py) saber quando a NF foi enviada:
    emails_contato: list = field(default_factory=list)  # todos os e-mails do formulário
    nomes: list = field(default_factory=list)           # nomes/razão social (pra casar "NF 1212 - NOME")
    partes_esperadas: int = 1                           # nota dividida em N -> espera N NFs
    data_pedido: str = ""                               # AAAA-MM-DD
    ref: str = ""                                       # identificador no e-mail consolidado (código-NN)

    @property
    def chave(self):
        """Identidade da solicitação — NÃO usa o número da linha, porque alguém pode ordenar/apagar linhas…"""
        return (self.hotel.planilha_id, self.hotel.aba, self.carimbo, self.email_hospede, self.assinatura)


@dataclass
class EmailMontado:
    operador: str               # destinatário real
    destinatario: str           # pra onde vai de fato (no modo TESTE, o e-mail de teste)
    assunto: str
    html: str
    codigo: str                 # código único que aparece no rodapé — usado pra confirmar o envio
    solicitacoes: list
