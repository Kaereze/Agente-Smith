"""Ajustes (04/11/2026, pedido do João): tempos, limites, textos e assinaturas num ajustes.json só do PC do administrador."""
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

import ajustes
from ajustes_tabela import ENTRADAS, GRUPOS

RAIZ = Path(__file__).resolve().parents[1]
POR_CHAVE = {e[0]: e for e in ENTRADAS}


@pytest.fixture
def arquivo(tmp_path, monkeypatch):
    """Aponta o ajustes.json para uma pasta de teste e devolve uma função que grava o conteúdo e recarrega."""
    caminho = tmp_path / "ajustes.json"
    monkeypatch.setattr(ajustes, "CAMINHO", caminho)
    monkeypatch.setitem(ajustes.ESTADO, "valores", None)

    def gravar(conteudo):
        caminho.write_text(conteudo if isinstance(conteudo, str) else json.dumps(conteudo, ensure_ascii=False), encoding="utf-8")
        ajustes.carregar(forcar=True)
    yield gravar
    ajustes.ESTADO["valores"] = None


def test_sem_arquivo_vale_o_de_fabrica(arquivo):
    assert ajustes.erros() == []
    assert ajustes.valor("recarregar.limite_segundos") == 10 and ajustes.valor("google.chamada_limite_segundos") == 30
    assert ajustes.diferencas() == []


def test_valor_do_arquivo_vence_e_o_resto_fica_de_fabrica(arquivo):
    arquivo({"recarregar": {"limite_segundos": 15}, "tela": {"k_volta_segundos": 4.5}})
    assert ajustes.valor("recarregar.limite_segundos") == 15 and ajustes.valor("tela.k_volta_segundos") == 4.5
    assert ajustes.valor("google.tentativa_segundos") == 15 and ajustes.erros() == []
    assert {d[0] for d in ajustes.diferencas()} == {"tela.k_volta_segundos", "recarregar.limite_segundos"}


def test_valor_fora_do_aceito_volta_ao_de_fabrica_e_explica(arquivo):
    arquivo({"recarregar": {"limite_segundos": 999}, "google": {"tentativa_segundos": "dez"}, "saude": {"sem_email_horas": True}})
    assert ajustes.valor("recarregar.limite_segundos") == 10 and ajustes.valor("google.tentativa_segundos") == 15 and ajustes.valor("saude.sem_email_horas") == 3
    texto = "\n".join(ajustes.erros())
    assert "recarregar.limite_segundos" in texto and "fora do aceito (de 5 a 30)" in texto
    assert "google.tentativa_segundos" in texto and "precisa ser um número" in texto and "saude.sem_email_horas" in texto


def test_tempo_da_tela_aceita_decimal_e_contagem_nao(arquivo):
    arquivo({"recarregar": {"limite_segundos": 10.5}, "janela": {"resposta_segundos": 4.5}, "tela": {"atualizar_pc_resultado_segundos": 5, "k_volta_segundos": 6.0}})
    assert ajustes.valor("recarregar.limite_segundos") == 10.5                                  # tempo em segundos: 10.5 vale
    assert ajustes.valor("tela.k_volta_segundos") == 6 and isinstance(ajustes.valor("tela.k_volta_segundos"), int)
    assert ajustes.valor("tela.atualizar_pc_resultado_segundos") == 5.0
    assert ajustes.valor("janela.resposta_segundos") == 3 and any("número inteiro" in e for e in ajustes.erros())   # os demais seguem inteiros


def test_chave_com_erro_de_digitacao_e_json_quebrado_avisam_sem_derrubar(arquivo):
    arquivo({"recarregar": {"limite_segundo": 12}, "grupo_que_nao_existe": {"x": 1}, "_LEIA_ME": "texto", "tela": {"_ajuda": "texto"}})
    texto = "\n".join(ajustes.erros())
    assert 'a chave "recarregar.limite_segundo" não existe' in texto and 'o grupo "grupo_que_nao_existe" não existe' in texto
    assert "_LEIA_ME" not in texto and "_ajuda" not in texto                       # as linhas de explicação são ignoradas
    arquivo('{ "recarregar": { "limite_segundos": 12, }')                           # vírgula sobrando
    assert ajustes.valor("recarregar.limite_segundos") == 10
    assert "erro de digitação" in ajustes.erros()[0] and "linha 1" in ajustes.erros()[0]


def test_prioridade_media_precisa_ser_menor_que_a_alta(arquivo):
    arquivo({"filtro": {"prioridade_alta_a_partir_de": 5, "prioridade_media_a_partir_de": 8}})
    assert (ajustes.valor("filtro.prioridade_alta_a_partir_de"), ajustes.valor("filtro.prioridade_media_a_partir_de")) == (10, 4)
    assert "precisa ser menor" in "\n".join(ajustes.erros())
    arquivo({"filtro": {"prioridade_alta_a_partir_de": 20, "prioridade_media_a_partir_de": 8}})
    assert (ajustes.valor("filtro.prioridade_alta_a_partir_de"), ajustes.valor("filtro.prioridade_media_a_partir_de")) == (20, 8) and ajustes.erros() == []


def test_assinaturas_somam_as_de_fabrica_e_null_tira(arquivo):
    arquivo({"assinaturas": {
        "textos": {"ana": {"nome": "Ana Souza", "linhas": ["ANA SOUZA", "FINANCEIRO"]}, "afonso": None},
        "nomes": {"joao": "João Carlos", "cristian": None},
        "ordem": ["ana", "joao"]}})
    textos = ajustes.valor("assinaturas.textos")
    assert textos == {"ana": {"nome": "Ana Souza", "linhas": ["ANA SOUZA", "FINANCEIRO"]}} and ajustes.erros() == []
    assert ajustes.valor("assinaturas.nomes") == {"joao": "João Carlos"} and ajustes.valor("assinaturas.ordem") == ["ana", "joao"]
    arquivo({"assinaturas": {"textos": {"Ana Maria": {"nome": "x", "linhas": ["y"]}}}})
    assert "só pode ter letras minúsculas e números" in "\n".join(ajustes.erros()) and "afonso" in ajustes.valor("assinaturas.textos")
    arquivo({"assinaturas": {"textos": {"ana": {"nome": "Ana"}}}})
    assert 'precisa de "nome" e de 1 a 8 "linhas"' in "\n".join(ajustes.erros())


def test_cor_e_lista_de_textos_sao_conferidas(arquivo):
    arquivo({"email": {"cor_primaria": "#112233", "cor_creme": "vermelho", "remetentes_automaticos": ["no-reply", "aviso@"], "dominios_automaticos": "booking"}})
    assert ajustes.valor("email.cor_primaria") == "#112233" and ajustes.valor("email.cor_creme") == "#d5bda1"
    assert ajustes.valor("email.remetentes_automaticos") == ["no-reply", "aviso@"] and "booking.com" in ajustes.valor("email.dominios_automaticos")
    assert "#rrggbb" in "\n".join(ajustes.erros()) and "lista de textos" in "\n".join(ajustes.erros())


def test_prazos_somam_aos_de_fabrica_e_nao_aceitam_zero(arquivo):
    arquivo({"email": {"prazo_horas": {"pedido": 72}}})
    assert ajustes.valor("email.prazo_horas") == {"corrigir": 24, "cobranca": 24, "pedido": 72}
    arquivo({"email": {"prazo_horas": {"pedido": 0}}})
    assert ajustes.valor("email.prazo_horas")["pedido"] == 48 and "maior que zero" in "\n".join(ajustes.erros())


def test_valor_devolvido_e_copia_e_chave_desconhecida_e_erro_de_quem_programa(arquivo):
    ajustes.valor("assinaturas.ordem").append("lixo")
    assert "lixo" not in ajustes.valor("assinaturas.ordem")
    with pytest.raises(KeyError):
        ajustes.valor("tela.nao_existe")


# ---------- a tabela e o código ----------

def test_tabela_esta_inteira_e_dentro_do_proprio_limite():
    chaves = [e[0] for e in ENTRADAS]
    assert len(chaves) == len(set(chaves)) and len(chaves) >= 150
    for chave, padrao, minimo, maximo, texto, tipo in ENTRADAS:
        assert chave.split(".")[0] in GRUPOS and re.fullmatch(r"[a-z0-9_]+\.[a-z0-9_]+", chave), chave
        assert len(texto) > 15, chave
        if tipo in (None, "decimal") and isinstance(padrao, (int, float)) and not isinstance(padrao, bool):
            assert minimo <= padrao <= maximo, (chave, minimo, padrao, maximo)
            limpo, motivo = ajustes._conferir(chave, padrao, minimo, maximo, tipo, padrao)
            assert motivo is None and limpo == padrao, chave
    for grupo in GRUPOS:
        assert any(c.startswith(grupo + ".") for c in chaves), f"grupo vazio: {grupo}"


def _fontes(pasta, sufixos):
    return {p: p.read_text(encoding="utf-8") for p in pasta.rglob("*") if p.suffix in sufixos and "__pycache__" not in p.parts}


def test_toda_chave_usada_no_codigo_existe_e_toda_chave_da_tabela_tem_uso():
    usadas = set()
    for texto in _fontes(RAIZ / "src", {".py"}).values():
        usadas |= set(re.findall(r'ajustes\.valor\("([a-z0-9_.]+)"\)', texto))
    for texto in _fontes(RAIZ / "app_ui", {".js", ".html"}).values():
        usadas |= set(re.findall(r'aj\?\.\("([a-z0-9_.]+)"\)', texto))
    assert usadas - set(POR_CHAVE) == set(), "o código pede um ajuste que não está na tabela"
    assert set(POR_CHAVE) - usadas == set(), "ajuste na tabela que nenhum lugar do código usa (enganaria quem muda o valor)"


def test_o_valor_de_reserva_da_tela_e_igual_ao_de_fabrica():
    achou = 0
    for caminho, texto in _fontes(RAIZ / "app_ui", {".js"}).items():
        for chave, reserva in re.findall(r'aj\?\.\("([a-z0-9_.]+)"\) \?\? ([0-9.]+)', texto):
            achou += 1
            assert float(reserva) == float(POR_CHAVE[chave][1]), (caminho.name, chave, reserva, POR_CHAVE[chave][1])
    assert achou >= 15


def test_exemplo_acompanha_a_tabela():
    spec = importlib.util.spec_from_file_location("gerar_ajustes_exemplo", RAIZ / "Automacoes" / "gerar_ajustes_exemplo.py")
    gerador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gerador)
    atual = json.loads((RAIZ / "ajustes.exemplo.json").read_text(encoding="utf-8"))
    assert atual == gerador.montar(), "rode: .venv\\Scripts\\python.exe Automacoes\\gerar_ajustes_exemplo.py"
    valores = {f"{g}.{n}": v for g, bloco in atual.items() if isinstance(bloco, dict) for n, v in bloco.items() if not n.startswith("_")}
    assert set(valores) == set(POR_CHAVE)
    assert all(valores[c] == POR_CHAVE[c][1] for c in POR_CHAVE)                  # o exemplo é todo de fábrica


def test_meu_cria_completa_e_nao_mexe_nos_valores_do_usuario(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("gerar_ajustes_exemplo2", RAIZ / "Automacoes" / "gerar_ajustes_exemplo.py")
    gerador = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gerador)
    monkeypatch.setattr(gerador, "RAIZ", tmp_path)
    gerador.main(["--meu"])
    criado = json.loads((tmp_path / "ajustes.json").read_text(encoding="utf-8"))
    assert criado["recarregar"]["limite_segundos"] == 10
    criado["recarregar"]["limite_segundos"] = 20
    criado["tela"].pop("k_volta_segundos")                                           # como se fosse uma chave nova de uma versão futura
    criado["tela"]["chave_digitada_errado"] = 1
    (tmp_path / "ajustes.json").write_text(json.dumps(criado), encoding="utf-8")
    gerador.main(["--meu"])
    depois = json.loads((tmp_path / "ajustes.json").read_text(encoding="utf-8"))
    assert depois["recarregar"]["limite_segundos"] == 20 and depois["tela"]["k_volta_segundos"] == 5
    assert depois["tela"]["chave_digitada_errado"] == 1                              # nunca apaga o que o usuário escreveu


def test_ajustes_json_nunca_vai_ao_github():
    assert "ajustes.json" in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines() or \
        "ajustes.json" in [linha.strip() for linha in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()]


def test_a_tela_recebe_so_tempos_e_limites():
    js = ajustes.js_da_tela()
    assert js.startswith("window.AJUSTES = {") and "window.aj = " in js
    dados = json.loads(js.split("window.AJUSTES = ")[1].split(";\n")[0])
    assert set(dados) == {"tela", "filtro", "recarregar"} and dados["tela"]["k_volta_segundos"] == 5
    assert "assinaturas" not in js and "google" not in js and "mensagem" not in js


def test_aj_do_navegador_le_o_valor_e_devolve_undefined_quando_nao_ha():
    if not shutil.which("node"):
        pytest.skip("Node não instalado")
    script = ajustes.js_da_tela() + "console.log(JSON.stringify([aj('tela.k_volta_segundos'), aj('tela.nao_existe'), aj('grupo.nada'), aj('filtro.prioridade_alta_a_partir_de')]));"
    saida = subprocess.run(["node", "-e", "globalThis.window = globalThis;" + script], capture_output=True, text=True, encoding="utf-8", timeout=30)
    assert saida.returncode == 0, saida.stderr
    assert json.loads(saida.stdout) == [5, None, None, 10]
