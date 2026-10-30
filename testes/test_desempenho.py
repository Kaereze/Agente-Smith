"""Medidor de desempenho (28/10/2026): só mede, não muda comportamento, não guarda dado de hóspede."""
import logging
from pathlib import Path

import pytest

import desempenho

RAIZ = Path(__file__).resolve().parents[1]


class Relogio:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


class LogFalso:
    def __init__(self):
        self.avisos = []

    def warning(self, texto):
        self.avisos.append(texto)

    def info(self, texto):
        self.avisos.append(texto)


def _medidor():
    perf, agora = Relogio(), Relogio()
    return desempenho.Medidor(relogio=perf, agora=agora), perf, agora


def test_mede_o_tempo_de_cada_etapa():
    m, perf, _ = _medidor()
    with m.medir("painel.atualizar"):
        perf.t += 0.25
    with m.medir("painel.atualizar"):
        perf.t += 0.75
    r = m.resumo()["painel.atualizar"]
    assert (r["n"], r["ultimo_ms"], r["medio_ms"], r["max_ms"], r["lentas"]) == (2, 750, 500, 750, 0)


def test_erro_dentro_da_etapa_continua_subindo_e_o_tempo_fica_registrado():
    m, perf, _ = _medidor()
    with pytest.raises(ValueError):
        with m.medir("x"):
            perf.t += 2
            raise ValueError("falhou")
    assert m.resumo()["x"]["n"] == 1 and m.resumo()["x"]["ultimo_ms"] == 2000


def test_p95_ignora_o_pico_raro_mas_o_maximo_mostra():
    m, _, _ = _medidor()
    for i in range(100):
        m.registrar("rota", 0.1 if i < 99 else 5.0)
    r = m.resumo()["rota"]
    assert r["p95_ms"] == 100 and r["max_ms"] == 5000


def test_aviso_so_acima_do_limite_e_no_maximo_um_por_minuto():
    m, _, agora = _medidor()
    log = LogFalso()
    m.registrar("laco", 5, limite=30, logger=log)              # dentro do limite: nada
    assert log.avisos == []
    m.registrar("laco", 40, limite=30, logger=log)
    m.registrar("laco", 41, limite=30, logger=log)             # no mesmo minuto: não repete o aviso
    assert len(log.avisos) == 1 and "laco" in log.avisos[0] and "40" in log.avisos[0]
    agora.t += 61
    m.registrar("laco", 42, limite=30, logger=log)
    assert len(log.avisos) == 2 and m.resumo()["laco"]["lentas"] == 3   # as 3 lentas contam, o log é que não se repete


def test_nomes_de_etapa_tem_teto():
    m, _, _ = _medidor()
    for i in range(desempenho.MAX_ETAPAS + 30):
        m.registrar(f"etapa{i}", 0.01)
    assert len(m.resumo()) == desempenho.MAX_ETAPAS + 1 and "outras" in m.resumo()


def test_rota_curta_corta_o_que_vem_depois_do_ponto_de_interrogacao():
    assert desempenho.rota_curta("/api/correio/texto?id=ABC123&x=1") == "GET /api/correio/texto"
    assert desempenho.rota_curta("/", "POST") == "POST página"
    assert desempenho.rota_curta("/assinaturas/joao.png") == "GET /assinaturas/*"
    assert "?" not in desempenho.rota_curta("/api/email/opcoes?de=fulano@exemplo.com.br")


def test_resumo_periodico_vai_ao_log_so_de_tempos_em_tempos():
    m, perf, agora = _medidor()
    log = LogFalso()
    m.registrar("conferente.uma_volta", 12.0)
    assert m.talvez_resumir(log, cada_s=600) is False          # ainda não deu 10 min
    agora.t += 601
    assert m.talvez_resumir(log, cada_s=600) is True and "conferente.uma_volta" in log.avisos[0]
    assert m.talvez_resumir(log, cada_s=600) is False


def test_medidor_do_programa_existe_e_nao_derruba_sem_logger():
    desempenho.MEDIDOR.registrar("teste.sem_logger", desempenho.LIMITE_LACO_S + 1, desempenho.LIMITE_LACO_S)   # usa o log padrão
    assert desempenho.MEDIDOR.resumo()["teste.sem_logger"]["lentas"] >= 1
    assert logging.getLogger("desempenho") is not None


def test_laços_e_respostas_do_servidor_e_do_conferente_estao_cronometrados():
    servidor = "".join(p.read_text(encoding="utf-8") for p in [RAIZ / "src" / "app_servidor.py", *sorted((RAIZ / "src").glob("estado_*.py"))])
    for etapa in ("painel.volta_completa", "painel.atualizar", "painel.notas_emails", "painel.fiscal_intelligence", "painel.canceladas", "painel.salvar_cache"):
        assert f'"{etapa}"' in servidor, etapa
    assert 'setattr(Handler, verbo, _cronometrado(' in servidor
    conferente = (RAIZ / "src" / "conferente.py").read_text(encoding="utf-8")
    for etapa in ("conferente.uma_volta", "conferente.confirmar_nfs", "conferente.espelho_emails", "conferente.vigia_outlook", "conferente.publicar_cota"):
        assert f'"{etapa}"' in conferente, etapa
    assert "talvez_resumir(logger)" in conferente


def test_resumo_so_para_o_administrador():
    servidor = "".join(p.read_text(encoding="utf-8") for p in [RAIZ / "src" / "app_servidor.py", *sorted((RAIZ / "src").glob("estado_*.py"))])
    trecho = servidor[servidor.index('if url.path in ("/agentes/mapa", "/api/agentes", "/api/desempenho")'):]
    trecho = trecho[:trecho.index("estatico = ESTATICOS.get(url.path)")]
    assert trecho.index("e_admin_aqui") < trecho.index("desempenho.MEDIDOR.resumo()")
