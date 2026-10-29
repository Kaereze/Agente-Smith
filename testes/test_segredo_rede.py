"""Segredo da rede entre os PCs (29/10/2026): arquivo segredo-rede.txt ao lado da chave vale mais que o cálculo pela chave."""
import json

import rede_local


def _chave(pasta, nome="chave-api.json", id_="abc123", privada="PRIVADA-FICTICIA"):
    caminho = pasta / nome
    caminho.write_text(json.dumps({"private_key_id": id_, "private_key": privada}), encoding="utf-8")
    return caminho


def test_sem_arquivo_o_segredo_continua_o_mesmo_de_sempre(tmp_path):
    esperado = rede_local._segredo_calculado(_chave(tmp_path))
    assert rede_local.segredo_da_chave(tmp_path / "chave-api.json") == esperado and len(esperado) == 32


def test_pc_com_chave_nova_fala_com_os_antigos_usando_o_arquivo(tmp_path):
    antigo = tmp_path / "joao"
    novo = tmp_path / "ingrid"
    antigo.mkdir(), novo.mkdir()
    chave_antiga = _chave(antigo, id_="id-antigo", privada="privada-antiga")
    chave_nova = _chave(novo, id_="id-novo", privada="privada-nova")
    assert rede_local.segredo_da_chave(chave_antiga) != rede_local.segredo_da_chave(chave_nova)     # sem o arquivo: não se entendem
    assert rede_local.gerar_arquivo_segredo(chave_antiga, novo / rede_local.ARQUIVO_SEGREDO_REDE)
    assert rede_local.segredo_da_chave(chave_nova) == rede_local.segredo_da_chave(chave_antiga)     # com o arquivo: mesmo segredo


def test_o_arquivo_gerado_nao_leva_a_chave_privada(tmp_path):
    chave = _chave(tmp_path, privada="TEXTO-SECRETO-DA-CHAVE")
    destino = tmp_path / "saida" / rede_local.ARQUIVO_SEGREDO_REDE
    destino.parent.mkdir()
    assert rede_local.gerar_arquivo_segredo(chave, destino)
    conteudo = destino.read_text(encoding="utf-8")
    assert "TEXTO-SECRETO" not in conteudo and len(conteudo) == 64 and bytes.fromhex(conteudo)


def test_arquivo_malformado_e_ignorado(tmp_path):
    chave = _chave(tmp_path)
    for lixo in ("", "isto nao e hexadecimal", "abcd", "zz" * 32):
        (tmp_path / rede_local.ARQUIVO_SEGREDO_REDE).write_text(lixo, encoding="utf-8")
        assert rede_local.segredo_da_chave(chave) == rede_local._segredo_calculado(chave)


def test_assinatura_entre_os_dois_pcs_passa_com_o_arquivo(tmp_path):
    antigo = tmp_path / "a"
    novo = tmp_path / "n"
    antigo.mkdir(), novo.mkdir()
    chave_antiga = _chave(antigo, id_="i1", privada="p1")
    chave_nova = _chave(novo, id_="i2", privada="p2")
    rede_local.gerar_arquivo_segredo(chave_antiga, novo / rede_local.ARQUIVO_SEGREDO_REDE)
    quando = "1000"
    assinatura = rede_local.assinar(rede_local.segredo_da_chave(chave_nova), quando, "/rede/ping", b"{}")
    assert rede_local.assinatura_ok(rede_local.segredo_da_chave(chave_antiga), quando, "/rede/ping", b"{}", assinatura, agora=1010.0)


def test_sem_chave_e_sem_arquivo_o_segredo_e_vazio(tmp_path):
    assert rede_local.segredo_da_chave(tmp_path / "nao-existe.json") == b""
