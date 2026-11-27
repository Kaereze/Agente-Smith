// O menu do botão direito num e-mail (e o "⋯" da leitura): lido/não lido, urgência, tirar da caixa de entrada.
// Em Itens Enviados: marcar ou tirar a marca de ligação. Shift+F10 ou a tecla de menu também abrem.
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Icone from "../../componentes/Icone.jsx";

export default function MenuEmail({ e, x, y, enviado, cinza, extra = [], aoEscolher, aoFechar }) {
  const caixa = useRef(null);
  const [pos, setPos] = useState({ left: x, top: y });
  useLayoutEffect(() => {
    const r = caixa.current.getBoundingClientRect();
    setPos({ left: Math.max(8, Math.min(x, innerWidth - r.width - 8)), top: Math.max(8, Math.min(y, innerHeight - r.height - 8)) });
    caixa.current.querySelector("button")?.focus({ preventScroll: true });
  }, [x, y]);
  useEffect(() => {
    const fora = (ev) => { if (!caixa.current?.contains(ev.target)) aoFechar(); };
    const tecla = (ev) => {
      if (ev.key === "Escape") { ev.stopPropagation(); aoFechar(); }
      if (ev.key === "ArrowDown" || ev.key === "ArrowUp") {
        ev.preventDefault();
        const bts = [...caixa.current.querySelectorAll("button")], i = bts.indexOf(document.activeElement);
        bts[(i + (ev.key === "ArrowDown" ? 1 : -1) + bts.length) % bts.length]?.focus();
      }
    };
    document.addEventListener("mousedown", fora);
    window.addEventListener("keydown", tecla, true);
    window.addEventListener("resize", aoFechar);
    return () => { document.removeEventListener("mousedown", fora); window.removeEventListener("keydown", tecla, true); window.removeEventListener("resize", aoFechar); };
  }, [aoFechar]);

  const item = (acao, icone, texto, cls = "", titulo = "") => (
    <button key={acao} type="button" role="menuitem" className={cls} title={titulo || undefined} onClick={() => { aoFechar(); aoEscolher(acao); }}><Icone nome={icone} tamanho={16} />{texto}</button>
  );
  const tirar = item("tirar", "pasta", "Tirar da caixa de entrada", "", "Move este e-mail para a pasta NF enviada da caixa do hotel. Nada é apagado.");
  return createPortal(
    <div ref={caixa} className="menu-email vidro" role="menu" style={pos}>
      <div className="menu-t">{enviado ? `Para: ${e.para || ""}` : e.nome || e.de || ""}</div>
      {enviado ? item(e.ligacao ? "semlig" : "lig", "telefone", e.ligacao ? "Tirar marca de ligação" : "Marcar como ligação")
        : cinza ? tirar
        : <>
            {item(e.lido === false ? "lido" : "naolido", "lido", e.lido === false ? "Marcar como lido" : "Marcar como não lido")}
            {item(e.urgente ? "normal" : "urgente", "bandeira", e.urgente ? "Tirar urgência" : "Marcar como urgente", e.urgente ? "" : "urg")}
            {e.urgente && e.motivo_urgencia && <div className="menu-n">{e.motivo_urgencia}</div>}
            {extra.filter((x) => x[3] !== "perigo").map(([acao, icone, texto, cls]) => item(acao, icone, texto, cls))}
            {tirar}
            {extra.filter((x) => x[3] === "perigo").map(([acao, icone, texto, cls]) => item(acao, icone, texto, cls))}
          </>}
    </div>,
    document.body,
  );
}
