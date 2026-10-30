"""Aba Agentes do Smith (28/10/2026): estado ao vivo só com sinal real, rota só do administrador e mapa completo."""
import datetime
import json
import re
from pathlib import Path

import agentes_smith
import app_servidor

RAIZ = Path(__file__).resolve().parents[1]
AGORA = datetime.datetime(2026, 10, 28, 14, 0, 0)


def _pc(agente, online=True, **extra):
    base = {"pc": "PC-" + agente.upper(), "agente": agente, "online": online, "visto": "2026-10-28T13:59:30", "outlook": "aberto",
            "versao": "'2026.10.28.1", "papel": "conferente", "conferencia": "2026-10-28T13:58:00", "conferencia_resumo": "2 NF · 0 tratativa",
            "conferencia_atrasada": False, "rede": "192.168.0.10:8766", "saude": {"saida": 0}}
    base.update(extra)
    return base


def _est(res, agente_id, quem):
    return next(x for x in res["agentes"][agente_id] if x["pc"] == quem)


def test_pc_ligado_e_em_dia():
    res = agentes_smith.estado([_pc("Clara"), _pc("João", papel="principal")], AGORA)
    assert res["pcs_total"] == 2 and res["pcs_ligados"] == 2
    for id_agente in ("app_servidor", "rede_pcs", "saude", "atualizador", "outlook_vivo", "conferente", "rede_local"):
        assert _est(res, id_agente, "Clara")["est"] == "ok", id_agente


def test_pc_desligado_aparece_como_desligado_e_nao_como_defeito():
    res = agentes_smith.estado([_pc("Clara", online=False, visto="2026-10-28T12:40:00"), _pc("João")], AGORA)
    assert res["pcs_ligados"] == 1
    assert _est(res, "conferente", "Clara") == {"pc": "Clara", "est": "desligado", "texto": "PC sem sinal desde as 12:40."}
    assert _est(res, "conferente", "João")["est"] == "ok"


def test_pc_sem_horario_nao_escreve_ponto_de_interrogacao():
    texto = _est(agentes_smith.estado([_pc("Clara", online=False, visto="")], AGORA), "saude", "Clara")["texto"]
    assert texto == "PC sem sinal." and "?" not in texto


def test_versao_diferente_pede_atencao_so_de_quem_esta_atras():
    res = agentes_smith.estado([_pc("Clara", versao="'2026.10.27.15"), _pc("João"), _pc("Cristian")], AGORA)
    assert _est(res, "atualizador", "Clara")["est"] == "atencao"
    assert "2026.10.28.1" in _est(res, "atualizador", "Clara")["texto"]
    assert _est(res, "atualizador", "João")["est"] == "ok"


def test_outlook_sem_janela_e_fechado():
    res = agentes_smith.estado([_pc("Clara", outlook="sem janela"), _pc("Cristian", outlook="fechado"), _pc("João")], AGORA)
    assert _est(res, "outlook_vivo", "Clara")["est"] == "atencao"
    assert _est(res, "outlook_vivo", "Cristian")["est"] == "parado"
    assert _est(res, "outlook_vivo", "João")["est"] == "ok"


def test_conferente_atrasado_e_email_preso_na_saida():
    res = agentes_smith.estado([_pc("Clara", conferencia_atrasada=True, saude={"saida": 3}), _pc("João")], AGORA)
    assert _est(res, "conferente", "Clara")["est"] == "atencao"
    assert _est(res, "saude", "Clara")["est"] == "atencao" and "3 e-mail" in _est(res, "saude", "Clara")["texto"]


def test_rede_local_sem_endereco_pede_atencao():
    res = agentes_smith.estado([_pc("Clara", rede=""), _pc("João")], AGORA)
    assert _est(res, "rede_local", "Clara")["est"] == "atencao"


def test_copia_e_robo_so_do_pc_principal_e_pela_idade():
    principal = _pc("João", papel="principal", saude={"saida": 0, "copia": "2026-10-28T13:55:00", "robo": "2026-10-28T13:20:00"})
    res = agentes_smith.estado([principal, _pc("Clara", saude={"saida": 0, "copia": "2026-10-28T08:00:00"})], AGORA)
    assert _est(res, "sincronizar", "João")["est"] == "ok"
    assert _est(res, "main", "João")["est"] == "atencao"      # 40 min: era esperado a cada 10
    assert len(res["agentes"]["sincronizar"]) == 1            # a Clara não é o principal: o dado dela não conta
    antigo = _pc("João", papel="principal", saude={"saida": 0, "copia": "2026-10-28T10:30:00"})
    assert _est(agentes_smith.estado([antigo], AGORA), "sincronizar", "João")["est"] == "parado"


def test_agente_sem_sinal_real_nao_aparece_na_resposta():
    res = agentes_smith.estado([_pc("João", papel="principal")], AGORA)
    for sem_sinal in ("faxina", "espelho_emails", "indice_emails", "nf_achadas", "painel_metricas", "vigia_formularios", "envio_pc_dono"):
        assert sem_sinal not in res["agentes"], sem_sinal


def test_rota_so_do_administrador_e_arquivo_fora_da_lista_publica():
    fonte = "".join(p.read_text(encoding="utf-8") for p in [RAIZ / "src" / "app_servidor.py", *sorted((RAIZ / "src").glob("estado_*.py"))])
    trecho = fonte[fonte.index('if url.path in ("/agentes/mapa", "/api/agentes", "/api/desempenho")'):]
    trecho = trecho[:trecho.index("estatico = ESTATICOS.get(url.path)")]
    assert "e_admin_aqui(estado.cfg, nome_do_agente(), liberado())" in trecho and "403" in trecho
    assert trecho.index("e_admin_aqui") < trecho.index("agentes_smith.estado") < trecho.index("mapa.html")   # nada é lido antes de checar
    assert not [c for c in app_servidor.ESTATICOS if c.startswith("/agentes")]                                # o mapa não sai pela lista pública


def test_botao_so_no_grupo_admin_e_quadro_carrega_so_ao_abrir():
    html = (RAIZ / "app_ui" / "index.html").read_text(encoding="utf-8")
    grupo = html[html.index('id="rot-admin"'):]
    grupo = grupo[:grupo.index("</nav>")]
    assert 'data-vista="agentes"' in grupo and "Agentes do Smith" in grupo
    assert html.count('data-vista="agentes"') == 1                      # só existe esse botão, dentro do grupo admin
    assert 'id="agentes-quadro"' in html and 'id="agentes-quadro" ' in html and "src=" not in html[html.index('id="agentes-quadro"'):html.index("</iframe>")]
    js = (RAIZ / "app_ui" / "painel.js").read_text(encoding="utf-8")
    assert 'agentes: "Agentes do Smith"' in js and 'agentesQuadro(v === "agentes")' in js


def _blocos_do_mapa():
    html = (RAIZ / "app_ui" / "agentes" / "mapa.html").read_text(encoding="utf-8")
    return html, {n["id"] for n in json.loads(re.search(r"var N = (\[.*\]);", html).group(1))}


def test_mapa_tem_todos_os_modulos_de_src():
    """O mapa precisa conter tudo (pedido do João, 28/10/2026). Módulo novo em src/? Acrescente o bloco em `var N` e as ligações
    em `var E` de app_ui/agentes/mapa.html (e no Mapa do sistema.drawio): Segundo Cérebro/3 Mapa do projeto/Mapa visual do sistema.md."""
    _, blocos = _blocos_do_mapa()
    faltando = sorted(p.stem for p in (RAIZ / "src").glob("*.py") if p.stem not in blocos)
    assert not faltando, f"módulo(s) de src/ fora do mapa de Agentes do Smith: {faltando}"


def test_mapa_lista_so_agentes_que_existem_e_nao_chama_a_internet():
    html, blocos = _blocos_do_mapa()
    ids = re.findall(r'\["([a-z_]+)", "[^"]+", "[^"]+", "(?:João|4 PCs)"\]', html)
    assert len(ids) >= 19 and not [i for i in ids if i not in blocos]
    assert "/api/agentes" in html
    assert not re.search(r"""(?:src|href)=["']https?://|fetch\(["']https?://|@import""", html)     # sem fonte nem script de fora
