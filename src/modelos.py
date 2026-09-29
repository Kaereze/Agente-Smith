from dataclasses import dataclass, field


@dataclass(frozen=True)
class Hotel:
    aba: str
    nome: str
    operador: str
    planilha_id: str
    email_hotel: str = ""
    agente: str = ""


@dataclass
class Solicitacao:
    hotel: Hotel
    linha: int
    carimbo: str
    email_hospede: str
    nome_titulo: str
    campos: list                                   # [(campo, valor)] já prontos pro e-mail
    linha_bruta: list = field(default_factory=list)
    assinatura: str = ""                           # hash da linha sem a coluna Enviado
    formato_data: str = ""                         # "americano" | "brasileiro", detectado por aba
    emails_contato: list = field(default_factory=list)
    nomes: list = field(default_factory=list)
    partes_esperadas: int = 1                      # nota dividida em N -> N NFs
    data_pedido: str = ""                          # AAAA-MM-DD
    ref: str = ""                                  # "<código do e-mail>-NN"

    @property
    def chave(self):
        """Não usa o número da linha: a planilha pode ser reordenada."""
        return (self.hotel.planilha_id, self.hotel.aba, self.carimbo, self.email_hospede, self.assinatura)


@dataclass
class EmailMontado:
    operador: str
    destinatario: str      # no modo TESTE, o email_teste
    assunto: str
    html: str
    codigo: str            # vai no rodapé; é por ele que o envio é confirmado em Itens Enviados
    solicitacoes: list
