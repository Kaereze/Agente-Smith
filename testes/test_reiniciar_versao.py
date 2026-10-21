import atualizador

OK = {"atras": 0, "frente": 0, "limpo": True, "erro": ""}


def test_reinicia_quando_pasta_esta_na_frente_do_que_roda():
    assert atualizador.precisa_reiniciar(OK, "aa7624d 14/10", "29267a6")


def test_nao_reinicia_quando_ja_roda_a_versao_da_pasta():
    assert not atualizador.precisa_reiniciar(OK, "29267a6", "29267a6c0ffee")


def test_nao_reinicia_sem_versao_ou_com_erro_ou_atrasado():
    assert not atualizador.precisa_reiniciar(OK, "", "29267a6")
    assert not atualizador.precisa_reiniciar(OK, "aa7624d", "")
    assert not atualizador.precisa_reiniciar(dict(OK, erro="sem rede"), "aa7624d", "29267a6")
    assert not atualizador.precisa_reiniciar(dict(OK, atras=2), "aa7624d", "29267a6")


# ---------- só documentação não reinicia (21/10/2026) ----------
def test_so_documentos():
    assert atualizador.so_documentos(["Segundo Cérebro/1 Diário/2026-10-21.md", "CHANGELOG.md", "README.md"])
    assert atualizador.so_documentos(["Segundo Cérebro/6 Documentos/Apresentacao/Projeto.pdf"])
    assert not atualizador.so_documentos(["CHANGELOG.md", "src/envio_nf.py"])
    assert not atualizador.so_documentos(["app_ui/painel.js"])
    assert not atualizador.so_documentos(["config.json"])
    assert not atualizador.so_documentos([])                     # não sabe o que mudou: reinicia


def _git_falso(monkeypatch, arquivos):
    chamadas, reinicios = [], []

    def git(*args, timeout=60):
        chamadas.append(args)
        if args[:2] == ("rev-parse", "--abbrev-ref"):
            return "main"
        if args[:1] == ("rev-parse",):
            return "f00dbabe"
        if "diff" in args:
            return "\n".join(arquivos)
        return ""
    monkeypatch.setattr(atualizador, "_git", git)
    monkeypatch.setattr(atualizador, "versao", lambda: "abc 21/10")
    monkeypatch.setattr(atualizador, "pedir_reinicio", lambda: reinicios.append(1) or "reinício pedido")
    monkeypatch.setattr(atualizador.subprocess, "run", lambda *a, **k: reinicios.append("pip"))
    return chamadas, reinicios


def test_atualizacao_so_de_documentacao_nao_reinicia(monkeypatch):
    chamadas, reinicios = _git_falso(monkeypatch, ["Segundo Cérebro/0 Comece aqui/00 Início.md", "CHANGELOG.md"])
    ok, texto, reiniciou = atualizador.atualizar()
    assert ok and not reiniciou and not reinicios and "sem reiniciar" in texto
    assert ("merge", "--ff-only", "f00dbabe") in chamadas        # exatamente o commit conferido


def test_atualizacao_com_codigo_reinicia_como_sempre(monkeypatch):
    chamadas, reinicios = _git_falso(monkeypatch, ["CHANGELOG.md", "src/envio_nf.py"])
    ok, texto, reiniciou = atualizador.atualizar()
    assert ok and reiniciou and reinicios == ["pip", 1]
    assert ("merge", "--ff-only", "origin/main") in chamadas


def test_painel_adota_a_versao_so_se_ja_rodava_a_da_pasta(monkeypatch, tmp_path):
    import app_servidor
    monkeypatch.setattr(app_servidor, "CAMINHO_VERSAO", tmp_path / "versao_rodando.txt")
    monkeypatch.setattr(app_servidor.envio_nf, "versao_do_codigo", lambda: "f00dbab")
    e = object.__new__(app_servidor.Estado)
    e.versao = "abc1234"
    e._adotar_versao_sem_reiniciar("abc1234")                     # rodava o da pasta: vira o novo, sem reinício
    assert e.versao == "f00dbab" and (tmp_path / "versao_rodando.txt").read_text(encoding="utf-8") == "f00dbab"
    e.versao = "0ld0000"
    e._adotar_versao_sem_reiniciar("abc1234")                     # reinício pendente de antes: não mascara
    assert e.versao == "0ld0000"
