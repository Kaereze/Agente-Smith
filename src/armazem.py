"""Armazém: o catálogo de TODO dado que o Painel grava neste PC (08/11/2026).

Antes, cada módulo montava o caminho do seu arquivo (`PASTA_ESTADO / "algo.json"`) e ninguém sabia dizer, de uma vez, o que o Painel
guarda, onde, por quanto tempo e se tem dado de hóspede. Agora:

- **Um lugar só diz o que existe**: `DADOS` (arquivo, formato, para que serve, se tem dado pessoal, quanto tempo fica, quem escreve).
- **Um lugar só dá o caminho**: `caminho("nf_achadas.json")`. Nome fora do catálogo é erro na hora (typo ou arquivo novo sem declarar).
- **Um lugar só sabe apagar dado pessoal**: `pessoais()` lista o que tem dado de hóspede (usado pela ferramenta do pedido do titular).
- É o ponto de troca para o banco de dados: quando o Supabase entrar, o que muda é daqui para dentro, não nos 20 módulos.

`testes/test_armazem.py` falha se um módulo voltar a montar caminho de `estado/` por conta própria ou se faltar descrição.
"""
import dataclasses

import config


@dataclasses.dataclass(frozen=True)
class Dado:
    arquivo: str
    formato: str           # json · sqlite · cache · texto · trava · pasta
    para_que: str
    pessoal: bool = False  # tem nome, CPF/CNPJ, e-mail ou texto de hóspede
    guarda: str = "enquanto o Painel precisa"
    quem: str = ""         # módulo que escreve
    refaz: bool = True     # dá para reconstruir (do Outlook, da Planilha ou do Dropbox) se o arquivo sumir


def _d(arquivo, formato, para_que, quem, pessoal=False, guarda="enquanto o Painel precisa", refaz=True):
    return Dado(arquivo, formato, para_que, pessoal, guarda, quem, refaz)


DADOS = {d.arquivo: d for d in [
    _d("app.json", "json", "Preferências deste PC: tema e operador escolhido", "app_servidor", refaz=False),
    _d("maquina.json", "json", "Identidade deste PC (nome e papel: principal ou comum)", "config", refaz=False),
    _d("versao_rodando.txt", "texto", "Versão do Painel que está rodando (para pedir reinício quando chega código novo)", "estado_sistema"),
    _d("painel_cache.pkl", "cache", "Último estado do Painel, para abrir já carregado depois de reiniciar", "app_servidor", True, "só o último"),
    _d("painel_cache_casa.pkl", "cache", "O mesmo, do modo casa", "app_servidor", True, "só o último"),
    _d("painel_cache_demo.pkl", "cache", "O mesmo, da demonstração (dados fictícios)", "app_servidor", False, "só o último"),
    _d("canceladas.json", "json", "NFs canceladas ou substituídas achadas nas pastas do Dropbox", "canceladas", True, "recalculado a cada leitura"),
    _d("nf_achadas.json", "json", "NFs achadas nas pastas (documento, valores, datas), ligadas aos pedidos e e-mails", "nf_achadas", True, "últimos 30 dias de pasta"),
    _d("cache_textos_nf.json", "json", "Texto lido de PDFs de NF, para não ler duas vezes", "confirmar_nfs", True, "enquanto o PDF existe"),
    _d("confirmar_nfs.json", "json", "Quais e-mails e notas o conferente já viu", "confirmar_nfs", True, "enquanto o conferente precisa"),
    _d("confirmar_status.json", "json", "Resultado da última volta do conferente (o Painel publica para os outros PCs)", "confirmar_nfs"),
    _d("controle_nf.json", "json", "Registro do que o conferente achou em cada NF", "conferente", True, "enquanto o conferente precisa"),
    _d("espelho_emails.json", "json", "Espelho da Caixa de Entrada deste PC (remetente, assunto, prévia)", "espelho_emails", True, "janela de 14 dias"),
    _d("indice_emails.sqlite", "sqlite", "Índice de pesquisa dos e-mails das caixas deste PC (inclui texto do hóspede)", "indice_emails", True,
       "12 meses (ajustes.json: email.indice_dias)"),
    _d("lido_aplicado.json", "json", "Marcas de lido/não lido que o Painel já aplicou no Outlook", "app_servidor"),
    _d("envios_pendentes.json", "json", "Diário de envios do robô que ainda esperam confirmação", "diario_envios", True, "3 dias"),
    _d("ja_enviadas.json", "json", "Solicitações que o robô já atendeu (para não repetir envio)", "main", True, "150 dias (faxina)"),
    _d("robo_antigo.json", "json", "Hotéis ativos no robô antigo", "robo_antigo"),
    _d("planilhas_sem_cadastro.json", "json", "Planilhas de hotel que ainda não estão no Cadastro_Hoteis", "sincronizar"),
    _d("sincronizacao.json", "json", "Estado da cópia das planilhas dos hotéis para a Central", "sincronizar", True),
    _d("sincronizacao_versoes.json", "json", "Versão de cada planilha de hotel na última cópia (para copiar só o que mudou)", "sincronizar", True),
    _d("ultima_copia.txt", "texto", "Hora da última cópia concluída", "sincronizar"),
    _d("_ciclo_copia.txt", "trava", "Marca de que a rodada da cópia está rodando", "sincronizar"),
    _d("faxina.json", "json", "Quando foi a última faxina das abas da Central", "faxina"),
    _d("contagem_painel.json", "json", "Contagem dos e-mails do fim de semana por operador", "contagem_painel", False, "enquanto o relatório precisa"),
    _d("enviar_receber_tempos.json", "json", "Quanto tempo cada PC levou no Enviar/Receber (para estimar o próximo)", "enviar_receber"),
    _d("cota_google", "pasta", "Consumo da cota do Google deste PC, por programa", "cota_google"),
    _d("acessos", "pasta", "Registro de quem abriu e-mail, anexo ou ficha (sem nome nem CPF do hóspede)", "acessos", False, "12 meses", False),
    _d("app_webview", "pasta", "Cache do navegador da janela do Painel (limpo ao abrir)", "limpeza"),
    _d("app_edge", "pasta", "Cache do navegador da janela, quando abre pelo Edge (limpo ao abrir)", "limpeza"),
    _d("_painel.lock", "trava", "Trava: um servidor do Painel por PC", "app_servidor"),
    _d("_janela.lock", "trava", "Trava: uma janela do Painel por PC", "app_janela"),
    _d("_execucao.lock", "trava", "Trava: uma execução do robô por PC", "lock_execucao"),
    _d("_conferente.lock", "trava", "Trava: um conferente por PC", "conferente"),
]}
# arquivos com data no nome (o nome tem AAAAMMDD): o modelo, e a descrição para o catálogo
BACKUPS = (
    _d("backup_tratamento_AAAAMMDD.json", "json", "Cópia do Tratamento antes da faxina", "faxina", True, "poucos dias"),
    _d("backup_central_AAAAMMDD_HHMMSS.json", "json", "Cópia da Central para recuperar erro", "sincronizar", True, "24 h (144 cópias)"),
)


def raiz():
    """Pasta `estado/` (lida na hora, para os testes poderem trocar em `config.PASTA_ESTADO`)."""
    return config.PASTA_ESTADO


def caminho(arquivo):
    """Caminho de um dado do catálogo. Nome que não está em DADOS é erro: declare o arquivo aqui antes de usar."""
    if arquivo not in DADOS:
        raise KeyError(f"'{arquivo}' não está no catálogo de dados (src/armazem.py): declare o arquivo lá")
    return raiz() / arquivo


def backup_tratamento(dia):
    return raiz() / f"backup_tratamento_{dia:%Y%m%d}.json"


def backup_central(momento):
    return raiz() / f"backup_central_{momento:%Y%m%d_%H%M%S}.json"


def pessoais():
    """O que guarda dado de hóspede neste PC (para o pedido do titular e para a revisão de LGPD)."""
    return [d for d in [*DADOS.values(), *BACKUPS] if d.pessoal]


def tamanho(arquivo):
    """Bytes que o dado ocupa agora (pasta: soma dos arquivos). 0 se ainda não existe."""
    p = caminho(arquivo)
    try:
        if p.is_dir():
            return sum(f.stat().st_size for f in p.rglob("*") if f.is_file())
        return p.stat().st_size
    except OSError:
        return 0


def resumo():
    """Linhas para o Monitoramento e para o mapa dos dados: o que existe, quanto pesa, se tem dado pessoal."""
    return [{"arquivo": d.arquivo, "formato": d.formato, "para_que": d.para_que, "pessoal": d.pessoal, "guarda": d.guarda,
             "quem": d.quem, "bytes": tamanho(d.arquivo)} for d in DADOS.values()]

