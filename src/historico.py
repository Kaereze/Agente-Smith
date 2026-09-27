"""Log de Envios (aba + CSV) e lista de já enviadas (válvula de escape)."""
import csv
import datetime
import json
import os

from log_util import configurar_logging
from arquivos import salvar_json

logger = configurar_logging(__name__)

ABA_LOG = "Log de Envios"
CABECALHO_LOG = [
    "Data e hora", "Quem pediu", "Como foi pedido", "Modo", "Resultado", "O que aconteceu",
    "Enviado para", "Agente", "Hotel", "Qtd. de solicitações", "Linhas da planilha", "Hóspedes",
    "E-mails desta execução", "Código do e-mail (procure no Outlook)",
]

SUCESSO = "✔ Sucesso"
ATENCAO = "⚠ Atenção"
ERRO = "✖ Erro"
NADA = "— Nada a enviar"

MODO_TEXTO = {"PRODUCAO": "Valendo", "TESTE": "Teste (só pro e-mail de teste)", "SIMULACAO": "Simulação (nada enviado)"}

ORIGEM_AGENDADO = "Automático (Agendador do Windows)"
ORIGEM_SOLICITACAO_NOVA = "Automático (solicitação nova)"
ORIGEM_MANUAL = "Manual no computador"
ORIGEM_CLAUDIO = "Botão Ativar Claudio"
ORIGEM_SEPARADO = "Botão Envio Separado"


def texto_simples(erro):
    """Traduz um erro técnico pra uma frase que qualquer um entende."""
    t = f"{type(erro).__name__}: {erro}"
    baixo = t.lower()
    if "outlook" in baixo:
        return "O Outlook não respondeu. Confira se ele está aberto e sem nenhuma janela de aviso na frente."
    if "permission" in baixo or "403" in baixo:
        return "O robô não tem permissão nessa planilha (ela precisa estar compartilhada com a conta do robô)."
    if "429" in baixo or "quota" in baixo:
        return "O Google pediu pra esperar (muitos acessos seguidos). Tente de novo em 1 minuto."
    if "timed out" in baixo or "connection" in baixo or "network" in baixo:
        return "Sem internet ou o Google demorou demais pra responder."
    if "chave do google" in baixo or "credentials" in baixo:
        return "O arquivo de acesso ao Google não foi encontrado no computador."
    return "Erro inesperado: " + str(erro)[:180]


def explicar_aba_pulada(erro_aba):
    """'Solicitação... (VIVALDI) (respostas): sem a coluna 'Enviado'' -> frase simples."""
    aba, _, motivo = erro_aba.partition(": ")
    m = motivo.lower()
    if "sem a coluna" in m:
        frase = "A aba foi pulada porque está sem a linha de cabeçalho (não achei a coluna Enviado)."
    elif "não tem e-mail" in m:
        frase = "A aba foi pulada porque o agente desse hotel ainda não tem e-mail cadastrado no robô."
    elif "não está no" in m:
        frase = "A aba foi pulada porque o hotel não está na aba Cadastro_Hoteis."
    else:
        frase = "A aba foi pulada: " + motivo
    return aba, frase


class Execucao:
    """Junta tudo o que aconteceu numa execução e grava no log no final."""

    def __init__(self, origem, quem, modo, agora=None):
        self.origem, self.quem, self.modo = origem, quem or "?", modo
        self.agora = agora or datetime.datetime.now()
        self.linhas = []   # dicts; "codigo" e "ok" servem pra contar os e-mails

    def _base(self):
        return {"data": self.agora.strftime("%d/%m/%Y %H:%M:%S"), "quem": self.quem, "origem": self.origem,
                "modo": MODO_TEXTO.get(self.modo, self.modo)}

    def geral(self, resultado, explicacao, hotel=""):
        self.linhas.append({**self._base(), "resultado": resultado, "explicacao": explicacao, "hotel": hotel})

    def email(self, email, resultado, explicacao, ok):
        """Uma linha por hotel dentro do e-mail."""
        por_hotel = {}
        for s in email.solicitacoes:
            por_hotel.setdefault(s.hotel.nome, []).append(s)
        for hotel, lista in por_hotel.items():
            self.linhas.append({
                **self._base(), "resultado": resultado, "explicacao": explicacao,
                "para": email.destinatario, "agente": lista[0].hotel.agente, "hotel": hotel,
                "qtd": len(lista), "linhas": _faixas([s.linha for s in lista]),
                "hospedes": ", ".join(s.nome_titulo for s in lista), "codigo": email.codigo, "ok": ok,
            })

    def reparo(self, solicitacoes, registros):
        """Válvula: já estavam enviadas (sem TRUE) — só marcou TRUE."""
        por_hotel = {}
        for s in solicitacoes:
            por_hotel.setdefault(s.hotel.nome, []).append(s)
        for hotel, lista in por_hotel.items():
            quando = sorted({registros[_chave_txt(s)]["quando"] for s in lista})
            self.linhas.append({
                **self._base(), "resultado": ATENCAO, "hotel": hotel, "agente": lista[0].hotel.agente,
                "explicacao": ("Estas solicitações estavam sem TRUE, mas o robô já tinha enviado "
                               f"(em {', '.join(quando)}). Não enviei de novo: só marquei TRUE."),
                "para": registros[_chave_txt(lista[0])].get("para", ""), "qtd": len(lista),
                "linhas": _faixas([s.linha for s in lista]), "hospedes": ", ".join(s.nome_titulo for s in lista),
                "codigo": ", ".join(sorted({registros[_chave_txt(s)]["codigo"] for s in lista})),
            })

    def como_tabela(self):
        codigos = {l["codigo"] for l in self.linhas if l.get("codigo") and "ok" in l}
        ok = {l["codigo"] for l in self.linhas if l.get("ok")}
        contagem = f"{len(ok)} enviado(s) de {len(codigos)}" if codigos else ""
        return [[l.get("data", ""), l.get("quem", ""), l.get("origem", ""), l.get("modo", ""), l.get("resultado", ""),
                 l.get("explicacao", ""), l.get("para", ""), l.get("agente", ""), l.get("hotel", ""),
                 l.get("qtd", ""), l.get("linhas", ""), l.get("hospedes", ""),
                 contagem if "ok" in l else "", l.get("codigo", "")] for l in self.linhas]

    def gravar(self, backend, cfg, pasta_logs):
        """Planilha (mais recente no topo) + CSV no computador. Nunca derruba o robô."""
        if not self.linhas:
            return
        tabela = self.como_tabela()
        try:
            caminho = os.path.join(str(pasta_logs), "Historico_de_Envios.csv")
            novo = not os.path.exists(caminho)
            os.makedirs(os.path.dirname(caminho), exist_ok=True)
            with open(caminho, "a", encoding="utf-8-sig", newline="") as f:
                escritor = csv.writer(f, delimiter=";")
                if novo:
                    escritor.writerow(CABECALHO_LOG)
                escritor.writerows(tabela)
        except Exception as e:
            logger.warning(f"⚠️ Não consegui gravar o histórico no computador ({e}).")
        if backend is None:
            return
        try:
            central = cfg["planilha_central_id"]
            if ABA_LOG not in backend.listar_abas(central):
                backend.criar_aba_log(central, ABA_LOG, CABECALHO_LOG)
            backend.inserir_no_topo(central, ABA_LOG, tabela)
        except Exception as e:
            logger.warning(f"⚠️ Não consegui gravar na aba '{ABA_LOG}' ({e}) — ficou só a cópia no computador "
                           f"(logs\\Historico_de_Envios.csv).")


def _faixas(numeros):
    """[131, 132, 133, 140] -> '131 a 133, 140'."""
    numeros = sorted(set(numeros))
    partes, i = [], 0
    while i < len(numeros):
        j = i
        while j + 1 < len(numeros) and numeros[j + 1] == numeros[j] + 1:
            j += 1
        partes.append(str(numeros[i]) if i == j else f"{numeros[i]} a {numeros[j]}")
        i = j + 1
    return ", ".join(partes)


# --- Válvula de escape ---
def _chave_txt(s):
    return " | ".join(str(p) for p in s.chave)


class JaEnviadas:
    """estado\\ja_enviadas.json — o que o robô CONFIRMOU que enviou (em Itens Enviados)."""

    def __init__(self, caminho):
        self.caminho = str(caminho)
        try:
            with open(self.caminho, "r", encoding="utf-8") as f:
                self.registros = json.load(f)
        except FileNotFoundError:
            self.registros = {}

    def contem(self, s):
        return _chave_txt(s) in self.registros

    def anotar(self, solicitacoes, codigo, para, quando):
        for s in solicitacoes:
            self.registros[_chave_txt(s)] = {"quando": quando.strftime("%d/%m/%Y %H:%M"), "codigo": codigo,
                                             "para": para, "hotel": s.hotel.nome, "linha": s.linha}
        self._salvar()

    def _salvar(self):
        salvar_json(self.caminho, self.registros)
