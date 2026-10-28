import limpeza


def _arquivo(caminho, bytes_):
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_bytes(b"x" * bytes_)


def test_limpa_so_o_cache_e_guarda_tema_e_preferencias(tmp_path):
    base = tmp_path / "app_webview" / "EBWebView" / "Default"
    _arquivo(base / "Cache" / "Cache_Data" / "f_000001", 600)
    _arquivo(base / "Code Cache" / "js" / "a", 300)
    _arquivo(base / "GPUCache" / "data_0", 100)
    _arquivo(base / "Service Worker" / "CacheStorage" / "x", 50)
    _arquivo(base / "Local Storage" / "leveldb" / "000003.log", 40)   # tema e preferências do Painel
    _arquivo(base / "IndexedDB" / "x" / "db", 30)
    _arquivo(base / "Preferences", 20)
    _arquivo(tmp_path / "app_edge" / "Default" / "Cache" / "d", 500)
    _arquivo(tmp_path / "app.json", 10)   # dado do Painel
    liberado = limpeza.limpar_cache_da_janela(tmp_path, minimo=1)
    assert liberado == 600 + 300 + 100 + 50 + 500
    for ficou in ("Local Storage/leveldb/000003.log", "IndexedDB/x/db", "Preferences"):
        assert (base / ficou).exists()
    assert (tmp_path / "app.json").exists()
    assert not (base / "Cache").exists() and not (tmp_path / "app_edge" / "Default" / "Cache").exists()


def test_cache_pequeno_nao_e_mexido(tmp_path):
    _arquivo(tmp_path / "app_webview" / "Default" / "Cache" / "a", 1000)
    assert limpeza.limpar_cache_da_janela(tmp_path, minimo=10_000) == 0
    assert (tmp_path / "app_webview" / "Default" / "Cache" / "a").exists()


def test_sem_pasta_de_perfil_nao_quebra(tmp_path):
    assert limpeza.limpar_cache_da_janela(tmp_path) == 0
    assert limpeza.aparar_registros(tmp_path / "nao_existe") == 0


def test_registros_so_apaga_copia_girada_grande(tmp_path):
    _arquivo(tmp_path / "saida_console_sincronizar.txt", 400)     # ativo: nunca
    _arquivo(tmp_path / "saida_console_sincronizar.txt.1", 200)   # girado mas pequeno: fica
    _arquivo(tmp_path / "saida_console_sincronizar.txt.2", 1600)  # girado e grande: sai
    _arquivo(tmp_path / "painel.log.3", 1600)
    _arquivo(tmp_path / "painel.log", 5000)                       # ativo grande: o logging gira, não eu
    assert limpeza.aparar_registros(tmp_path, teto=100) == 1600 + 1600
    assert sorted(p.name for p in tmp_path.iterdir()) == ["painel.log", "saida_console_sincronizar.txt",
                                                          "saida_console_sincronizar.txt.1"]


def test_maiores_pastas_mostra_so_nome_e_tamanho(tmp_path):
    _arquivo(tmp_path / "app_webview" / "EBWebView" / "WidevineCdm" / "x", 3_000_000)
    _arquivo(tmp_path / "app_webview" / "EBWebView" / "Default" / "History", 1_000_000)
    achadas = limpeza.maiores_pastas(tmp_path, 2)
    assert achadas[0][1] == 3 and achadas[0][0].endswith("WidevineCdm")
    assert all(isinstance(n, int) for _, n in achadas)
