// Número que sobe do 0 até o valor quando a tela abre (e desliga com "reduzir movimento" do Windows).
import { useEffect, useState } from "react";

export const semMovimento = () => {
  try { return window.matchMedia("(prefers-reduced-motion: reduce)").matches; } catch { return false; }
};

export default function Conta({ valor, sufixo = "" }) {
  const [x, setX] = useState(semMovimento() ? valor : 0);
  useEffect(() => {
    if (semMovimento()) { setX(valor); return; }
    let quadro, inicio;
    const passo = (t) => {
      inicio ??= t;
      const p = Math.min(1, (t - inicio) / 950);
      setX(valor * (1 - Math.pow(1 - p, 3)));
      if (p < 1) quadro = requestAnimationFrame(passo);
    };
    quadro = requestAnimationFrame(passo);
    return () => cancelAnimationFrame(quadro);
  }, [valor]);
  return <span aria-label={`${valor}${sufixo}`}>{Math.round(x).toLocaleString("pt-BR")}{sufixo}</span>;
}

// Liga as barras e os anéis logo depois de abrir, para eles crescerem.
export function useLigado() {
  const [ligado, setLigado] = useState(semMovimento());
  useEffect(() => { const t = setTimeout(() => setLigado(true), 90); return () => clearTimeout(t); }, []);
  return ligado;
}
