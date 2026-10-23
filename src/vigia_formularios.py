"""Cópia rápida dos formulários (23/10/2026, OK do João): pedido do hóspede no Painel em ~10-20 s, e não 6-12 min.

Só no PC principal, numa linha própria dentro do conferente. A cada VIGIA_SEGUNDOS pergunta ao Drive quais planilhas da
pasta dos hotéis mudaram (a listagem não gasta a cota das planilhas; medido em 22/10: o Drive mostra o pedido novo em
1-2 s). Mudou? Copia só aqueles hotéis para a Central (sincronizar.sincronizar com so_hoteis) e avisa os Painéis pela
rede, que releem as abas dos hotéis na hora.

O e-mail para o hotel continua na rodada das 10 em 10 (opção A do João). Enquanto essa rodada roda (sincronizar.CICLO),
a vigia espera; e ela segura a trava só pelos segundos da cópia (a rodada espera até 45 s por ela, não pula).
Leituras na fatia própria "vigia_formularios" (cota_google), não na do conferente.
"""
import threading
import time

from log_util import configurar_logging

logger = configurar_logging("vigia_formularios")

VIGIA_SEGUNDOS = 10
MAPA_SEGUNDOS = 600   # cadastro e abas da Central: relidos a cada 10 min (a listagem do Drive é a de cada volta)


class VigiaFormularios:
    """listar() -> [{"id", "name", "version", ...}] · copiar(arquivos, ids) -> lista de hotéis que mudaram na Central,
    ou None quando não pôde agora (trava ocupada: tenta na próxima volta) · avisar() · ciclo_rodando() -> bool."""

    def __init__(self, listar, copiar, avisar, ciclo_rodando):
        self.listar, self.copiar, self.avisar, self.ciclo_rodando = listar, copiar, avisar, ciclo_rodando
        self.vistas = None        # {id: version} da última listagem
        self.pendentes = set()    # ids que mudaram e ainda não foram copiados

    def volta(self):
        """Uma olhada. -> hotéis que entraram na Central agora (lista, talvez vazia)."""
        arquivos = self.listar()
        versoes = {a["id"]: str(a.get("version", "")) for a in arquivos}
        if self.vistas is None:   # primeira volta: só guarda (o que já existia a rodada das 10 em 10 copia)
            self.vistas = versoes
            return []
        self.pendentes |= {i for i, v in versoes.items() if self.vistas.get(i) != v}
        self.vistas = versoes
        self.pendentes &= set(versoes)   # planilha que saiu da pasta não fica pendente
        if not self.pendentes or self.ciclo_rodando():
            return []
        ids = set(self.pendentes)
        try:
            mudaram = self.copiar(arquivos, ids)
        except Exception as e:
            logger.warning(f"⚠️ Cópia rápida falhou ({str(e)[:120]}) — tento de novo em {VIGIA_SEGUNDOS} s")
            return []
        if mudaram is None:
            return []
        self.pendentes -= ids
        if mudaram:
            self.avisar()
        return mudaram


def _copiador(cfg):
    """copiar(arquivos, ids) de verdade: trava do robô (sem esperar), mapa guardado 10 min, só os hotéis das planilhas."""
    import sincronizar
    from config import caminho_chave_google
    from lock_execucao import adquirir_lock, liberar_lock
    from sheets import BackendGoogle
    guardado = {"mapa": None, "em": -1e9}

    def copiar(arquivos, ids):
        if not adquirir_lock():
            return None
        try:
            inicio = time.monotonic()
            if guardado["mapa"] is None or inicio - guardado["em"] > MAPA_SEGUNDOS:
                chave = caminho_chave_google(cfg)
                guardado["mapa"] = sincronizar.mapear_fontes(BackendGoogle(chave), cfg, chave, arquivos=arquivos)
                guardado["em"] = inicio
            mapa = dict(guardado["mapa"])
            mapa["por_hotel"], mapa["sem_hotel"] = sincronizar.agrupar_por_hotel(arquivos, cfg, mapa["cadastro"])
            hoteis = {h for h, lista in mapa["por_hotel"].items() if any(a["id"] in ids for a in lista)}
            if not hoteis:
                return []
            relatorio, _, _ = sincronizar.sincronizar(gravar=True, so_hoteis=hoteis, mapa=mapa)
            mudaram = [r["hotel"] for r in relatorio if r.get("mudou")]
            if mudaram:
                logger.info(f"⚡ Formulário novo na Central em {time.monotonic() - inicio:.1f} s: {', '.join(sorted(mudaram))}")
            return mudaram
        finally:
            liberar_lock()
    return copiar


def iniciar(cfg, avisar):
    """Liga a vigia numa linha própria. -> a linha, ou None se estiver desligada no config ("vigia_formularios")."""
    opcoes = cfg.get("vigia_formularios", {})
    if not opcoes.get("ligada", True):
        logger.info("ℹ️ Vigia dos formulários desligada no config — a cópia fica de 10 em 10 min.")
        return None
    segundos = max(5, int(opcoes.get("segundos", VIGIA_SEGUNDOS)))

    def rodar():
        import cota_google
        import sincronizar
        from config import caminho_chave_google, carregar_config, e_principal
        cota_google.usar_nesta_linha("vigia_formularios")
        chave = caminho_chave_google(cfg)
        vigia = VigiaFormularios(lambda: sincronizar.listar_pasta(chave, cfg["fontes_hoteis"]["pasta_drive_id"]),
                                 _copiador(cfg), avisar, sincronizar.ciclo_rodando)
        logger.info(f"⚡ Vigia dos formulários ligada: olha o Drive a cada {segundos} s")
        while True:
            try:
                if e_principal(carregar_config()):
                    vigia.volta()
            except Exception as e:
                logger.warning(f"⚠️ Vigia dos formulários: {str(e)[:150]} — tento de novo em {segundos} s")
            time.sleep(segundos)

    linha = threading.Thread(target=rodar, name="vigia_formularios", daemon=True)
    linha.start()
    return linha
