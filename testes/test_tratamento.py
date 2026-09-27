from tratamento import campos_para_email, completar_zeros, converter_data, tipo_documento


def test_cpf_com_zero_comido():
    assert completar_zeros("1234567890", "cpf") == "01234567890"
    assert completar_zeros("012.345.678-90", "cpf") == "01234567890"


def test_cnpj_e_cep():
    assert completar_zeros("1234567000199", "cnpj") == "01234567000199"
    assert completar_zeros("1310000", "cep") == "01310000"


def test_coluna_cpf_cnpj_decide_pelo_tamanho():
    assert completar_zeros("1234567890", "cpf_cnpj") == "01234567890"
    assert completar_zeros("1234567000199", "cpf_cnpj") == "01234567000199"


def test_numero_em_notacao_cientifica():
    assert completar_zeros("1,23456789E+10", "cpf") == "12345678900"


def test_texto_livre_nao_e_mexido():
    assert completar_zeros("Passaporte AB123", "cpf") == "Passaporte AB123"
    assert completar_zeros("123456789012345", "cpf") == "123456789012345"


def test_tipo_documento_pelo_nome_da_coluna():
    assert tipo_documento("CPF do hóspede") == "cpf"
    assert tipo_documento("CPF/CNPJ") == "cpf_cnpj"
    assert tipo_documento("CEP") == "cep"
    assert tipo_documento("Recepção") is None  # contém "cep" mas não é CEP


def test_data_americana_vira_brasileira():
    assert converter_data("9/3/2026") == "03/09/2026"
    assert converter_data("12/25/2026 14:05:31") == "25/12/2026 14:05:31"
    assert converter_data("2026-09-03") == "03/09/2026"
    assert converter_data("3/9/2026", "brasileiro") == "03/09/2026"


def test_data_invalida_fica_igual():
    assert converter_data("13/25/2026") == "13/25/2026"
    assert converter_data("amanhã") == "amanhã"


def test_campos_vazios_e_ocultos_somem():
    cab = ["Carimbo de data/hora", "Nome", "Observação", "Enviado", "CPF"]
    linha = ["9/3/2026 10:00:00", "Ana", "   ", "FALSE", "1234567890"]
    campos = campos_para_email(cab, linha, ["Enviado", "Carimbo de data/hora"])
    assert campos == [("Nome", "Ana"), ("CPF", "01234567890")]


def test_cep_incompleto_nao_vira_documento_inventado():
    assert completar_zeros("40030", "cep") == "40030"          # hóspede digitou incompleto
    assert completar_zeros("1234567", "cpf") == "1234567"
    assert completar_zeros("123456789", "cpf") == "00123456789"  # 2 zeros comidos: ainda completa


def test_formato_de_data_descoberto_pela_aba():
    from tratamento import detectar_formato_data
    assert detectar_formato_data(["05/10/2025", "26/10/2025 12:36:33"]) == "brasileiro"
    assert detectar_formato_data(["5/28/2026", "6/1/2026"]) == "americano"
    assert detectar_formato_data(["05/10/2025"], "americano") == "americano"   # sem pista: usa o config


def test_pc_sem_config_local_nunca_envia(tmp_path, monkeypatch):
    """Clone novo sem config.local.json fica como conferente (não copia, não envia, não atende o menu)."""
    import json
    import config
    base = json.load(open(config.CAMINHO_CONFIG, encoding="utf-8"))
    cfg_arq = tmp_path / "config.json"
    cfg_arq.write_text(json.dumps(base), encoding="utf-8")
    monkeypatch.setattr(config, "CAMINHO_CONFIG", cfg_arq)
    monkeypatch.setattr(config, "CAMINHO_CONFIG_LOCAL", tmp_path / "config.local.json")
    monkeypatch.setattr(config, "CAMINHO_MAQUINA", tmp_path / "maquina.json")
    assert not config.e_principal(config.carregar_config(cfg_arq))
    (tmp_path / "config.local.json").write_text('{"papel": "principal", "outlook": {"tentativas_conexao": 2}}', encoding="utf-8")
    cfg = config.carregar_config(cfg_arq)
    assert config.e_principal(cfg) and cfg["outlook"]["tentativas_conexao"] == 2


def test_pc_do_agente_principal_vira_principal_sozinho(tmp_path, monkeypatch):
    import json
    import config
    monkeypatch.setattr(config, "CAMINHO_CONFIG_LOCAL", tmp_path / "nao_existe.json")
    monkeypatch.setattr(config, "CAMINHO_MAQUINA", tmp_path / "maquina.json")
    cfg_arq = tmp_path / "config.json"
    base = json.load(open(config.CAMINHO_CONFIG, encoding="utf-8"))
    base["agente_principal"] = "João"
    cfg_arq.write_text(json.dumps(base), encoding="utf-8")
    monkeypatch.setattr(config, "CAMINHO_CONFIG", cfg_arq)
    (tmp_path / "maquina.json").write_text('{"agente": "Joao"}', encoding="utf-8")
    assert config.carregar_config(cfg_arq)["papel"] == "principal"
    (tmp_path / "maquina.json").write_text('{"agente": "Clara"}', encoding="utf-8")
    assert config.carregar_config(cfg_arq)["papel"] == "conferente"
    (tmp_path / "maquina.json").write_text('{"agente": "João", "conflito": "trocou"}', encoding="utf-8")
    assert config.carregar_config(cfg_arq)["papel"] == "conferente"
