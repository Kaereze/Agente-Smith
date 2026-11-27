// Os dados que a tela precisa, lidos do servidor do Painel e relidos de tempos em tempos.
// estado  = /api/estado  (pedidos dos formulários, PCs, robô)
// correio = /api/correio (e-mails das caixas dos 4 PCs, enviados, contagens)
import { useCallback, useEffect, useState } from "react";
import { api } from "../api.js";

export default function usePainel() {
  const [estado, setEstado] = useState(null);
  const [correio, setCorreio] = useState(null);
  const [erro, setErro] = useState("");
  const [lidoEm, setLidoEm] = useState(null);

  const ler = useCallback(async () => {
    try {
      const [e, c] = await Promise.all([api("/api/estado?dias=30"), api("/api/correio?caixa=entrada")]);
      if (e && e.ok !== false) setEstado(e);
      if (c && c.ok !== false) setCorreio(c);
      setErro(e?.erro || "");
      setLidoEm(new Date());
    } catch {
      setErro("O Painel deste PC não respondeu. Tentando de novo…");
    }
  }, []);

  useEffect(() => {
    ler();
    const segundos = Math.max(10, estado?.atualizar_segundos || 15);
    const t = setInterval(ler, segundos * 1000);
    return () => clearInterval(t);
  }, [ler, estado?.atualizar_segundos]);

  return { estado, correio, erro, lidoEm, reler: ler };
}
