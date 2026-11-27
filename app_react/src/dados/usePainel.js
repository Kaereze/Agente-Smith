// Os dados que a tela precisa, lidos do servidor do Painel e relidos de tempos em tempos.
// estado  = /api/estado  (pedidos dos formulários, PCs, robô, saúde)
// correio = /api/correio (e-mails das caixas dos 4 PCs, enviados, contagens)
// Tela que não trava (21/10/2026, desenho Pr6), igual à tela de antes:
//   - a cada 3 s pergunta /api/versao; se tem dado novo, relê na hora (a volta de 15 s continua de garantia);
//   - janela mostrada de novo depois de 20 s: relê já;
//   - o servidor reiniciou ("não autorizado") ou a tela nova chegou no disco (estado.pagina mudou): recarrega,
//     mas nunca com uma mensagem sendo escrita;
//   - 1 min sem resposta do servidor com a tela à vista: `parado` (a faixa "Sem dados há N min" aparece);
//   - a janela do app (app_janela.py) pergunta se a tela está viva por window.__telaInteira e window.__painelVivo.
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "../api.js";

export const escrevendo = () => !!document.querySelector(".escrever, .janela-fundo textarea");

export default function usePainel() {
  const [estado, setEstado] = useState(null);
  const [correio, setCorreio] = useState(null);
  const [erro, setErro] = useState("");
  const [lidoEm, setLidoEm] = useState(null);
  const [parado, setParado] = useState(0);   // minutos sem dados (0 = tudo certo)
  const ultimoOk = useRef(Date.now()), pagina = useRef(null), marca = useRef(null), lendo = useRef(false);

  const ler = useCallback(async () => {
    lendo.current = true;
    try {
      const [e, c] = await Promise.all([api("/api/estado?dias=30"), api("/api/correio?caixa=entrada")]);
      if (e?.erro === "não autorizado") { window.location.reload(); return; }   // servidor reiniciado: pega a sessão nova
      if (e?.pagina) {
        if (pagina.current && e.pagina !== pagina.current && !escrevendo()) { window.location.reload(); return; }   // tela nova no disco
        pagina.current = pagina.current || e.pagina;
      }
      if (e && e.ok !== false) setEstado(e);
      if (c && c.ok !== false) setCorreio(c);
      setErro(e?.erro || "");
      ultimoOk.current = Date.now();
      setLidoEm(new Date());
      setParado(0);
    } catch {
      setErro("O Painel deste PC não respondeu. Tentando de novo…");
    } finally {
      lendo.current = false;
    }
  }, []);

  useEffect(() => {
    ler();
    const segundos = Math.max(10, estado?.atualizar_segundos || 15);
    const t = setInterval(ler, segundos * 1000);
    return () => clearInterval(t);
  }, [ler, estado?.atualizar_segundos]);

  useEffect(() => {
    window.__painelVivo = () => Date.now() - ultimoOk.current;
    window.__telaInteira = true;
    const versao = setInterval(async () => {
      if (document.visibilityState !== "visible" || lendo.current) return;
      try {
        const j = await api("/api/versao");
        if (!j.v) return;
        if (marca.current !== null && j.v !== marca.current) ler();
        marca.current = j.v;
      } catch { /* a volta de 15 s cobre */ }
    }, 3000);
    const vigia = setInterval(() => {
      const ms = Date.now() - ultimoOk.current;
      setParado(ms > 60000 && document.visibilityState === "visible" ? Math.max(1, Math.round(ms / 60000)) : 0);
    }, 5000);
    const visivel = () => { if (document.visibilityState === "visible" && Date.now() - ultimoOk.current > 20000) ler(); };
    document.addEventListener("visibilitychange", visivel);
    return () => { clearInterval(versao); clearInterval(vigia); document.removeEventListener("visibilitychange", visivel); };
  }, [ler]);

  return { estado, correio, erro, lidoEm, parado, reler: ler };
}
