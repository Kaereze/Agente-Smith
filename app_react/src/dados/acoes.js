// Ações do Painel que mais de uma tela usa (uma regra só):
//   enviarPendentes()  → pede ao robô para mandar já os pedidos que ainda não foram ao hotel
//   useEnviarReceber() → relê a planilha e pede o Enviar/Receber (F9) aos PCs com Outlook; no máximo uns 10 s
import { useCallback, useRef, useState } from "react";
import { api } from "../api.js";
import { aj } from "../ajustes.js";

export async function enviarPendentes() {
  const j = await api("/api/enviar", {});
  return j.ok === false ? { erro: true, texto: j.motivo || j.erro || "Não deu para pedir agora." } : { texto: "Pedido entregue ao robô. Ele envia na próxima rodada." };
}

const LIMITE_MS = (aj("recarregar.limite_segundos", 10) + 0.5) * 1000;   // o servidor corta o pedido nesse tempo (+ folga da rede)
const esperar = (ms) => new Promise((r) => setTimeout(r, ms));

export function useEnviarReceber(recado, reler) {
  const [andamento, setAndamento] = useState(null);   // { feitos, total, fim, aviso }
  const rodando = useRef(false);
  const rodar = useCallback(async () => {
    if (rodando.current) return;
    rodando.current = true;
    setAndamento({ feitos: 0, total: 0 });
    api("/api/atualizar", {}).then(() => reler?.()).catch(() => {});   // relê a planilha em paralelo
    try {
      let r = await api("/api/enviar_receber", {});
      if (r.erro || r.ok === false) { recado(r.erro || r.motivo || "Não deu para pedir agora", true); setAndamento(null); return; }
      setAndamento(r);
      const ate = Date.now() + LIMITE_MS;
      while (!r.fim && Date.now() < ate) {
        await esperar(500);
        const s = await api("/api/enviar_receber/status?id=" + encodeURIComponent(r.id));
        if (s.erro) break;
        r = s; setAndamento(s);
      }
      const falhas = r.falhas || [], avisos = r.avisos || [];
      setAndamento({ ...r, fim: true, aviso: !!(falhas.length || avisos.length) });
      recado(falhas.length ? "Terminou com aviso: " + falhas.join("; ") : avisos.length ? "Atualizado. " + avisos.join("; ") : `${r.total || 0} PCs atualizados`, !!falhas.length);
      reler?.();
      setTimeout(() => setAndamento(null), 2600);
    } catch {
      recado("Não deu para pedir agora", true); setAndamento(null);
    } finally {
      rodando.current = false;
    }
  }, [recado, reler]);
  return { andamento, rodar };
}
