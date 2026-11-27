// Pastas à esquerda: "Todas as caixas" e, por PC, a caixa de cada hotel (nome, e-mail e não lidos). Escolher uma caixa filtra a
// lista; o classificador em cima da lista (Todas, Não lidos, Urgência, Formulários, Enviados) vale também dentro dela.
// PC sem caixa de hotel (o de casa) não entra.
import { useState } from "react";
import Icone from "../../componentes/Icone.jsx";

export const nomeDaCaixa = (c, hoteis) => (hoteis || []).filter((h) => h.email === c).map((h) => h.hotel).join(" / ")
  || String(c).split("@")[1]?.replace(/^(redeandrade|hotel)/, "").replace(/(hotel)?\.com(\.br)?$/, "").toUpperCase() || c;

export default function Pastas({ caixa, escolher, entrada, total, pcs, hoteis, estePc }) {
  const [abertos, setAbertos] = useState({});
  const [todas, setTodas] = useState({});
  const naoLidos = {};
  entrada.forEach((e) => { if (e.lido === false) { const c = String(e.caixa || "").toLowerCase(); naoLidos[c] = (naoLidos[c] || 0) + 1; } });
  const n = (v) => (v ? <span className="qt">{v.toLocaleString("pt-BR")}</span> : null);
  const lista = [...(pcs || [])].filter((p) => (p.contas_lista || []).length)
    .sort((a, b) => (a.pc === estePc ? -1 : b.pc === estePc ? 1 : String(a.agente).localeCompare(String(b.agente), "pt")));
  return (
    <aside className="pn vidro pastas entra" aria-label="Caixas dos hotéis">
      <button type="button" className={`pasta${caixa === "" ? " sel" : ""}`} onClick={() => escolher("")}>
        <Icone nome="caixa" tamanho={17} /><span>Todas as caixas</span>{n(total)}</button>
      <div className="pn-cab">Caixas dos hotéis</div>
      {lista.map((p) => {
        const contas = [...new Set(p.contas_lista.map((c) => String(c).toLowerCase()))]
          .map((c) => ({ c, hotel: nomeDaCaixa(c, hoteis), n: naoLidos[c] || 0 })).sort((a, b) => a.hotel.localeCompare(b.hotel, "pt"));
        const aberto = abertos[p.pc] ?? (p.pc === estePc || contas.some((x) => x.c === caixa) || lista.length === 1);
        const soma = contas.reduce((s, x) => s + x.n, 0);
        const mostrar = todas[p.pc] || contas.length <= 6 ? contas : contas.filter((x, i) => i < 4 || x.c === caixa);
        return (
          <div key={p.pc} className="pc-grupo">
            <button type="button" className={`pasta agente${aberto ? "" : " fechado"}`} aria-expanded={aberto} onClick={() => setAbertos({ ...abertos, [p.pc]: !aberto })}
              title={p.online ? "PC ligado" : "PC desligado"}>
              <span className="capsula-avatar" style={{ width: 30, height: 30, fontSize: 12 }}>{(p.agente || "?").slice(0, 1)}</span>
              <span className="agente-texto"><b>{p.agente || p.pc}</b><small className={p.online ? "pc-ok" : "pc-fora"}>{p.online ? "PC ligado" : "PC desligado"} · {contas.length} caixas</small></span>
              {n(soma)}
            </button>
            {aberto && mostrar.map((x) => (
              <button key={x.c} type="button" className={`pasta caixa-hotel${x.c === caixa ? " sel" : ""}${x.n ? " tem" : ""}`} aria-pressed={x.c === caixa} title={x.c}
                onClick={() => escolher(x.c === caixa ? "" : x.c)}>
                <span className="nm"><b>{x.hotel}</b><small>{x.c}</small></span>{n(x.n)}</button>
            ))}
            {aberto && mostrar.length < contas.length && <button type="button" className="mais-caixas" onClick={() => setTodas({ ...todas, [p.pc]: true })}>Mostrar mais {contas.length - mostrar.length} caixas</button>}
          </div>
        );
      })}
    </aside>
  );
}
