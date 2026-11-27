// Filtro de VÁRIOS hotéis (03/11/2026, prévia aprovada pelo João): marque quantos quiser. "Meus hotéis" guarda a lista da pessoa
// NESTE PC (nada vai ao Google) e a caixa já abre com ela. A prioridade de cada hotel vem da quantidade de e-mails na caixa dele:
// Alta 10 ou mais, Média de 4 a 9, Baixa de 1 a 3.
import { useEffect, useRef, useState } from "react";
import Icone from "../../componentes/Icone.jsx";
import { semAcento } from "../../dados/formulario.js";
import { aj } from "../../ajustes.js";

const ALTA = aj("filtro.prioridade_alta_a_partir_de", 10), MEDIA = aj("filtro.prioridade_media_a_partir_de", 4);
export const nivelDoHotel = (n) => (n >= ALTA ? "alta" : n >= MEDIA ? "media" : n >= 1 ? "baixa" : "vazia");
export const NIVEIS = { alta: "Alta", media: "Média", baixa: "Baixa", vazia: "Sem e-mail" };
export const hoteisDe = (e) => String(e.hotel || "").split(" / ").map((x) => x.trim()).filter(Boolean);
export function contarPorHotel(emails) {
  const c = {};
  emails.forEach((e) => hoteisDe(e).forEach((h) => { c[h] = (c[h] || 0) + 1; }));
  return c;
}
export function lerMeus() { try { return new Set(JSON.parse(localStorage.getItem("painel.meusHoteis") || "[]")); } catch { return new Set(); } }
const guardarMeus = (s) => { try { localStorage.setItem("painel.meusHoteis", JSON.stringify([...s])); } catch { /* só nesta janela */ } };

export default function FiltroHoteis({ hoteis, contagem, sel, setSel }) {
  const [aberto, setAberto] = useState(false);
  const [busca, setBusca] = useState("");
  const [meus, setMeus] = useState(lerMeus);
  const caixa = useRef(null);
  useEffect(() => {
    if (!aberto) return undefined;
    const fora = (ev) => { if (!caixa.current?.contains(ev.target)) setAberto(false); };
    const tecla = (ev) => { if (ev.key === "Escape") { ev.stopPropagation(); setAberto(false); } };
    document.addEventListener("mousedown", fora); window.addEventListener("keydown", tecla, true);
    return () => { document.removeEventListener("mousedown", fora); window.removeEventListener("keydown", tecla, true); };
  }, [aberto]);
  const termos = semAcento(busca).split(/\s+/).filter(Boolean);
  const lista = [...hoteis].filter((h) => termos.every((q) => semAcento(h).includes(q)))
    .sort((a, b) => (contagem[b] || 0) - (contagem[a] || 0) || a.localeCompare(b, "pt"));
  const alternar = (h) => { const s = new Set(sel); s.has(h) ? s.delete(h) : s.add(h); setSel(s); };
  const rotulo = !sel.size ? "Todos os hotéis" : sel.size === 1 ? [...sel][0] : `${sel.size} hotéis`;
  const ehMeus = sel.size > 0 && sel.size === meus.size && [...sel].every((h) => meus.has(h));
  return (
    <div className="fh" ref={caixa}>
      <button type="button" className={`fh-bt${sel.size ? " on" : ""}`} aria-expanded={aberto} aria-haspopup="dialog" onClick={() => setAberto(!aberto)}
        title="Escolher os hotéis que aparecem na lista">
        <Icone nome="hotel" tamanho={15} /><span>{ehMeus ? `Meus hotéis (${sel.size})` : rotulo}</span><Icone nome="seta" tamanho={13} /></button>
      {aberto && (
        <div className="fh-menu" role="dialog" aria-label="Hotéis">
          <input type="search" className="campo" placeholder="Procurar hotel…" value={busca} onChange={(ev) => setBusca(ev.target.value)} autoFocus aria-label="Procurar hotel" />
          <div className="fh-bts">
            <button type="button" onClick={() => setSel(new Set(meus))} disabled={!meus.size} title={meus.size ? [...meus].join(", ") : "Ainda não guardou os seus hotéis"}>Meus hotéis{meus.size ? ` (${meus.size})` : ""}</button>
            <button type="button" onClick={() => { const s = new Set(sel); setMeus(s); guardarMeus(s); }} disabled={!sel.size}>Guardar como meus</button>
            <button type="button" onClick={() => setSel(new Set())} disabled={!sel.size}>Todos</button>
          </div>
          <div className="fh-lista" role="group" aria-label="Hotéis">
            {lista.map((h) => {
              const n = contagem[h] || 0, nv = nivelDoHotel(n);
              return (
                <label key={h} className="fh-it">
                  <input type="checkbox" checked={sel.has(h)} onChange={() => alternar(h)} />
                  <span className="fh-nome">{h}{meus.has(h) && <small> · meu</small>}</span>
                  <span className={`fh-nv ${nv}`} title={`Prioridade ${NIVEIS[nv].toLowerCase()}: ${n} e-mail${n === 1 ? "" : "s"} na caixa`}>{n ? `${n} · ${NIVEIS[nv]}` : NIVEIS[nv]}</span>
                </label>
              );
            })}
            {!lista.length && <p className="dica">Nenhum hotel com “{busca}”.</p>}
          </div>
          <p className="dica">Prioridade pela quantidade de e-mails na caixa: Alta {ALTA} ou mais · Média {MEDIA} a {ALTA - 1} · Baixa 1 a {MEDIA - 1}. “Meus hotéis” fica só neste PC.</p>
        </div>
      )}
    </div>
  );
}
