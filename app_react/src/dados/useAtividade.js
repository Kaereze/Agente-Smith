// O que cada PC está fazendo (/api/atividade): PCs da equipe, registro do robô e versão. Relido a cada 20 s.
import { useEffect, useState } from "react";
import { api } from "../api.js";

export default function useAtividade() {
  const [atividade, setAtividade] = useState(null);
  useEffect(() => {
    let vivo = true;
    const ler = async () => {
      try { const j = await api("/api/atividade"); if (vivo && j.ok !== false) setAtividade(j); } catch { /* tenta de novo na próxima volta */ }
    };
    ler();
    const t = setInterval(ler, 20000);
    return () => { vivo = false; clearInterval(t); };
  }, []);
  return { atividade };
}
