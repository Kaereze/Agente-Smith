// Pastas à esquerda, como a prévia aprovada (15/10/2026): Favoritos e, por PC, a caixa de cada hotel (nome, e-mail e não lidos).
// A caixa escolhida abre a Caixa de Entrada e os Itens Enviados dela. PC sem caixa de hotel (o de casa) não entra.
import { useState } from "react";
import Icone from "../../componentes/Icone.jsx";

export const nomeDaCaixa = (c, hoteis) => (hoteis || []).filter((h) => h.email === c).map((h) => h.hotel).join(" / ")
  || String(c).split("@")[1]?.replace(/^(redeandrade|hotel)/, "").replace(/(hotel)?\.com(\.br)?$/, "").toUpperCase() || c;
const lerFechados = () => { try { return JSON.parse(localStorage.getItem("painel.caixasFechadas") || "{}") || {}; } catch { return {}; } };

export default function Pastas({ vista, escolher, entrada, contagem, enviados, pcs, hoteis, estePc }) {
  const [fechados, setFechados] = useState(lerFechados);
  const [abertos, setAbertos] = useState({});
  const [todas, setTodas] = useState({});
  const naoLidos = {};
  entrada.forEach((e) => { if (e.lido === false) { const c = String(e.caixa || "").toLowerCase(); naoLidos[c] = (naoLidos[c] || 0) + 1; } });
  const n = (v, cls = "") => (v ? <span className={`qt ${cls}`}>{v.toLocaleString("pt-BR")}</span> : null);
  const alternarFav = () => { const f = { ...fechados, __fav: !fechados.__fav }; setFechados(f); try { localStorage.setItem("painel.caixasFechadas", JSON.stringify(f)); } catch { /* só nesta janela */ } };
  const fav = (k, icone, texto, qt, cls) => (
    <button type="button" className={`pasta${!vista.caixa && vista.pasta === k ? " sel" : ""}`} onClick={() => escolher({ pasta: k, caixa: "" })}>
      <Icone nome={icone} tamanho={17} /><span>{texto}</span>{n(qt, cls)}</button>
  );
  const lista = [...(pcs || [])].filter((p) => (p.contas_lista || []).length)
    .sort((a, b) => (a.pc === estePc ? -1 : b.pc === estePc ? 1 : String(a.agente).localeCompare(String(b.agente), "pt")));
  return (
    <aside className="pn vidro pastas entra" aria-label="Pastas">
      <button type="button" className="pn-cab grupo" aria-expanded={!fechados.__fav} onClick={alternarFav}><Icone nome="seta" tamanho={13} />Favoritos</button>
      {!fechados.__fav && <>
        {fav("entrada", "caixa", "Caixa de Entrada (todas)", contagem.entrada_nao_lidos)}
        {fav("urgencia", "alerta", "Urgência", contagem.urgencia, "urg")}
        {fav("form", "formulario", "Formulários do robô", entrada.filter((e) => (e.classes || []).includes("formulario") && e.lido === false).length)}
        {fav("enviados", "enviar", "Itens Enviados (72 h)", enviados)}
      </>}
      <div className="pn-cab">Caixas dos hotéis</div>
      {lista.map((p) => {
        const contas = [...new Set(p.contas_lista.map((c) => String(c).toLowerCase()))]
          .map((c) => ({ c, hotel: nomeDaCaixa(c, hoteis), n: naoLidos[c] || 0 })).sort((a, b) => a.hotel.localeCompare(b.hotel, "pt"));
        const aberto = abertos[p.pc] ?? (p.pc === estePc || contas.some((x) => x.c === vista.caixa) || lista.length === 1);
        const soma = contas.reduce((s, x) => s + x.n, 0);
        const mostrar = todas[p.pc] || contas.length <= 6 ? contas : contas.filter((x, i) => i < 4 || x.c === vista.caixa);
        return (
          <div key={p.pc} className="pc-grupo">
            <button type="button" className={`pasta agente${aberto ? "" : " fechado"}`} aria-expanded={aberto} onClick={() => setAbertos({ ...abertos, [p.pc]: !aberto })}
              title={p.online ? "PC ligado" : "PC desligado"}>
              <span className="capsula-avatar" style={{ width: 30, height: 30, fontSize: 12 }}>{(p.agente || "?").slice(0, 1)}</span>
              <span className="agente-texto"><b>{p.agente || p.pc}</b><small className={p.online ? "pc-ok" : "pc-fora"}>{p.online ? "PC ligado" : "PC desligado"} · {contas.length} caixas</small></span>
              {n(soma)}
            </button>
            {aberto && mostrar.map((x) => {
              const sel = x.c === vista.caixa;
              return (
                <div key={x.c}>
                  <button type="button" className={`pasta caixa-hotel${sel ? " sel" : ""}${x.n ? " tem" : ""}`} aria-expanded={sel} title={x.c}
                    onClick={() => escolher(sel && vista.pasta === "entrada" ? { pasta: "entrada", caixa: "" } : { pasta: "entrada", caixa: x.c })}>
                    <span className="nm"><b>{x.hotel}</b><small>{x.c}</small></span>{n(x.n)}</button>
                  {sel && <div className="sub-pastas">
                    <button type="button" className={vista.pasta !== "enviados" ? "on" : ""} onClick={() => escolher({ pasta: "entrada", caixa: x.c })}>Caixa de Entrada{n(x.n)}</button>
                    <button type="button" className={vista.pasta === "enviados" ? "on" : ""} onClick={() => escolher({ pasta: "enviados", caixa: x.c })}>Itens Enviados</button>
                  </div>}
                </div>
              );
            })}
            {aberto && mostrar.length < contas.length && <button type="button" className="mais-caixas" onClick={() => setTodas({ ...todas, [p.pc]: true })}>Mostrar mais {contas.length - mostrar.length} caixas</button>}
          </div>
        );
      })}
    </aside>
  );
}
