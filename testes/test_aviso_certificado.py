from aviso_certificado import decidir

NOME = ("O servidor ao qual você está conectado está usando um certificado\rde segurança que não pode ser confirmado.\r\n\r\n"
        "O nome principal do destino está incorreto. ")


def test_so_o_nome_diferente_e_aceito():
    assert decidir(NOME) == "aceitar"
    assert decidir("The server you are connected to is using a security certificate that could not be verified. "
                   "The target principal name is incorrect.") == "aceitar"


def test_certificado_vencido_ou_nao_confiavel_nao_e_aceito():
    assert decidir(NOME + " O certificado expirou ou ainda não é válido.") == "suspeito"
    assert decidir("O certificado foi emitido por uma empresa que não é confiável.") == "suspeito"
    assert decidir("The certificate chain was issued by an authority that is not trusted.") == "suspeito"


def test_outras_janelas_sao_ignoradas():
    assert decidir("Deseja salvar as alterações?") == "outro"
