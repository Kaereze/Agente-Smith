// O topo em pílula. Na Visão geral: saudação + pesquisa + avisos. Nos e-mails: as abas do Outlook (Página Inicial ·
// Enviar/Receber · Exibir) + pesquisa + avisos.
// A pesquisa procura nos e-mails dos 4 PCs (a partir de 3 letras); digitar em outra tela leva para os e-mails. Ctrl+K ou Ctrl+E chegam nela.
// Histórico da pesquisa (28/10/2026): as pesquisas das últimas 24 h aparecem embaixo da caixa para repetir com um clique. Fica SÓ neste
// navegador (nada vai ao servidor nem a outro PC) e o que parece CPF/CNPJ não é guardado (LGPD).
import { useEffect, useRef, useState } from "react";
import Icone from "../componentes/Icone.jsx";
import { BotaoRedondo } from "../componentes/Botao.jsx";
import CaixasProblema from "./CaixasProblema.jsx";
import { aj } from "../ajustes.js";
import "./Moldura.css";

const ABAS = [["inicio", "Página Inicial"], ["enviar", "Enviar/Receber"], ["exibir", "Exibir"]];
const CHAVE = "painel.buscas", VALIDADE_MS = 24 * 3600 * 1000, MAX = 12;
const gravar = (l) => { try { localStorage.setItem(CHAVE, JSON.stringify(l.slice(0, MAX))); } catch { /* sem armazenamento: não guarda */ } };
function lerBuscas() {
  try {
    const todas = JSON.parse(localStorage.getItem(CHAVE) || "[]");
    const vivas = Array.isArray(todas) ? todas.filter((x) => x && typeof x.t === "string" && x.em > Date.now() - VALIDADE_MS) : [];
    if (!Array.isArray(todas) || vivas.length !== todas.length) gravar(vivas);
    return vivas;
  } catch { return []; }
}
const pareceDocumento = (t) => { const d = t.replace(/\D/g, ""); return (d.length === 11 || d.length === 14) && !/[a-zà-ú]{3,}/i.test(t); };
function guardarBusca(texto) {
  const t = String(texto || "").trim();
  if (t.length < 3 || pareceDocumento(t)) return;
  const baixo = t.toLowerCase();
  gravar([{ t, em: Date.now() }, ...lerBuscas().filter((x) => { const b = x.t.toLowerCase(); return b !== baixo && !baixo.startsWith(b); })]);   // "joa" -> "joao" substitui
}
const haQuanto = (em) => { const min = Math.max(0, Math.round((Date.now() - em) / 60000)); return min < 1 ? "agora" : min < 60 ? `há ${min} min` : `há ${Math.floor(min / 60)} h`; };

function Pesquisa({ busca, setBusca }) {
  const [aberto, setAberto] = useState(false);
  const [marcado, setMarcado] = useState(-1);
  const [, setN] = useState(0);
  const timer = useRef(null);
  const digitado = busca.trim().toLowerCase();
  const itens = aberto ? lerBuscas().filter((x) => !digitado || (x.t.toLowerCase().includes(digitado) && x.t.toLowerCase() !== digitado)) : [];
  const usar = (t) => { setBusca(t); guardarBusca(t); setAberto(false); };
  return (
    <label className="topo-busca">
      <span className="orbe" aria-hidden="true" />
      <input id="busca-topo" type="search" value={busca} autoComplete="off" spellCheck={false} role="combobox" aria-expanded={itens.length > 0} aria-controls="busca-recente"
        onChange={(ev) => { setBusca(ev.target.value); setAberto(true); setMarcado(-1); clearTimeout(timer.current); const v = ev.target.value; timer.current = setTimeout(() => guardarBusca(v), 1200); }}
        onFocus={() => { setAberto(true); setMarcado(-1); }} onBlur={() => { guardarBusca(busca); setTimeout(() => setAberto(false), aj("tela.menu_saida_milissegundos", 150)); }}
        onKeyDown={(ev) => {
          if (ev.key === "Escape") { if (itens.length) { ev.stopPropagation(); setAberto(false); } else if (busca) { ev.stopPropagation(); setBusca(""); } return; }
          if (ev.key === "Enter") { guardarBusca(busca); if (itens[marcado]) { ev.preventDefault(); usar(itens[marcado].t); } else setAberto(false); return; }
          if ((ev.key === "ArrowDown" || ev.key === "ArrowUp") && itens.length) { ev.preventDefault(); setMarcado((m) => (ev.key === "ArrowDown" ? (m + 1) % itens.length : (m - 1 + itens.length) % itens.length)); }
        }}
        placeholder={window.innerWidth < 760 ? "Pesquisar…" : "Pesquisar hóspede, CPF/CNPJ, nº da NF ou frase"} aria-label="Pesquisar nos e-mails dos 4 PCs" />
      {busca ? <button type="button" className="topo-limpar" onClick={() => setBusca("")} aria-label="Limpar a pesquisa"><Icone nome="fechar" tamanho={14} /></button> : <kbd>Ctrl K</kbd>}
      {itens.length > 0 && (
        <div className="busca-recente" id="busca-recente" role="listbox" aria-label="Pesquisas das últimas 24 horas" onMouseDown={(ev) => ev.preventDefault()}>
          <div className="br-cab"><span>Pesquisas das últimas 24 h</span><button type="button" onClick={() => { gravar([]); setAberto(false); }}>Limpar</button></div>
          {itens.map((x, i) => (
            <div key={x.t} role="option" aria-selected={i === marcado} className={`br-it${i === marcado ? " on" : ""}`} onClick={() => usar(x.t)}>
              <Icone nome="relogio" tamanho={14} /><span className="br-t">{x.t}</span><small>{haQuanto(x.em)}</small>
              <button type="button" aria-label="Tirar esta pesquisa" title="Tirar" onClick={(ev) => { ev.stopPropagation(); gravar(lerBuscas().filter((y) => y.t !== x.t)); setN((n) => n + 1); }}><Icone nome="fechar" tamanho={12} /></button>
            </div>
          ))}
        </div>
      )}
    </label>
  );
}

export default function Topo({ modo, agente, avisos, busca, setBusca, aba, setAba, estado, irPara, admin }) {
  const [abertos, setAbertos] = useState(false);
  const sino = useRef(null);
  useEffect(() => {
    if (!abertos) return undefined;
    const fora = (ev) => { if (!sino.current?.contains(ev.target)) setAbertos(false); };
    const tecla = (ev) => { if (ev.key === "Escape") setAbertos(false); };
    document.addEventListener("mousedown", fora); window.addEventListener("keydown", tecla);
    return () => { document.removeEventListener("mousedown", fora); window.removeEventListener("keydown", tecla); };
  }, [abertos]);
  const graves = avisos.filter((a) => a.grave).length;
  return (
    <header className="topo vidro">
      {modo === "emails" ? (
        <div className="topo-abas" role="tablist" aria-label="Faixa de comandos">
          {ABAS.map(([k, t]) => <button key={k} type="button" role="tab" aria-selected={aba === k} aria-pressed={aba === k} onClick={() => setAba(k)}>{t}</button>)}
        </div>
      ) : (
        <div className="topo-quem">
          <span className="capsula-avatar grande" aria-hidden="true">{(agente || "?").slice(0, 1)}</span>
          <b>Bem-vindo, {agente || "…"}</b>
        </div>
      )}
      <Pesquisa busca={busca} setBusca={setBusca} />
      <CaixasProblema saude={estado?.saude} soVer={!!estado?.so_ver} />
      <div className="sino" ref={sino}>
        <BotaoRedondo icone="sino" titulo={`Avisos: ${avisos.length}`} branco ponto={avisos.length > 0} onClick={() => setAbertos(!abertos)} />
        {abertos && (
          <div className="avisos" role="dialog" aria-label="Avisos">
            <div className="avisos-cab"><b>Avisos</b>{graves > 0 && <span className="avisos-graves">{graves} importante{graves > 1 ? "s" : ""}</span>}</div>
            {avisos.length === 0 && <p>Nenhum aviso agora. Tudo funcionando.</p>}
            {avisos.map((a, i) => <AvisoLinha key={a.texto + i} a={a} admin={admin} ir={(t) => { setAbertos(false); irPara(t); }} />)}
          </div>
        )}
      </div>
    </header>
  );
}

function AvisoLinha({ a, admin, ir }) {
  const [passos, setPassos] = useState(false);
  return (
    <div className={`aviso${a.grave ? " grave" : ""}`}>
      <Icone nome={a.icone} />
      <div>{a.texto}<small>{a.detalhe}</small>
        <span className="aviso-bts">
          {a.ajuda?.passos && <button type="button" aria-expanded={passos} onClick={() => setPassos(!passos)}>Como resolver</button>}
          {a.ajuda?.ver === "robo" && <button type="button" onClick={() => ir("robo")}>Ver os pedidos</button>}
          {a.ir && <button type="button" onClick={() => ir(a.ir)}>Abrir</button>}
          {a.monitor && admin && <button type="button" onClick={() => ir("maquinas")}>Ver no Monitoramento</button>}
        </span>
        {passos && <ol className="aviso-passos">{a.ajuda.passos.map((p) => <li key={p}>{p}</li>)}</ol>}
      </div>
    </div>
  );
}
