// A janela por cima da tela (confirmar, encaminhar, ver anexo, dados da emissão). Uma peça para todas:
//   <Janela titulo="Excluir este e-mail?" sub="..." aoFechar={...} rodape={<botões>}>texto</Janela>
// Esc e o × fecham; clicar fora fecha só quando `fecharFora` (não perde o que se digitou por engano). O foco entra na janela.
import { useEffect, useRef } from "react";
import { createPortal } from "react-dom";
import Icone from "./Icone.jsx";
import "./Janela.css";

export default function Janela({ titulo, sub, children, rodape, aoFechar, largura = 540, fecharFora = true, classe = "" }) {
  const caixa = useRef(null);
  const fechar = useRef(aoFechar), fora = useRef(fecharFora);
  fechar.current = aoFechar; fora.current = fecharFora;
  useEffect(() => {
    const antes = document.activeElement;
    const alvo = caixa.current?.querySelector("[data-foco], input, textarea, button.botao-principal, button.botao-verde, button.botao-perigo") || caixa.current;
    alvo?.focus({ preventScroll: true });
    // Esc fecha; com algo digitado (fecharFora = false), só o × e os botões fecham (não perde o que se escreveu)
    const tecla = (ev) => { if (ev.key === "Escape") { ev.stopPropagation(); if (fora.current) fechar.current?.(); } };
    window.addEventListener("keydown", tecla, true);
    return () => { window.removeEventListener("keydown", tecla, true); antes?.focus?.({ preventScroll: true }); };
  }, []);
  return createPortal(
    <div className="janela-fundo" onMouseDown={(ev) => { if (fecharFora && ev.target === ev.currentTarget) aoFechar?.(); }}>
      <div ref={caixa} className={`janela ${classe}`} role="dialog" aria-modal="true" aria-label={titulo} tabIndex={-1} style={{ width: `min(${largura}px, calc(100vw - 24px))` }}>
        <div className="janela-cab">
          <div><h3>{titulo}</h3>{sub && <p>{sub}</p>}</div>
          {aoFechar && <button type="button" className="janela-x" onClick={aoFechar} aria-label="Fechar" title="Fechar (Esc)"><Icone nome="fechar" tamanho={16} /></button>}
        </div>
        <div className="janela-corpo">{children}</div>
        {rodape && <div className="janela-rodape">{rodape}</div>}
      </div>
    </div>,
    document.body,
  );
}
