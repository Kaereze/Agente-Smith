// Tela de carregamento (27/10/2026, desenho aprovado pelo João): a logo K sendo desenhada no meio do Painel em qualquer ação
// que passe de 3 s. O cartão do canto (barra, PCs) só aparece quando a ação tem o que contar (ex.: Enviar/Receber dos 4 PCs).
// Enquanto roda, a tela TRAVA (nem clique nem tecla chegam atrás). Depois de 5 s a tela grande sai (stand-by) e o K pequeno do
// rodapé segue mostrando que algo anda. Terminou: o K fica verde (certo) ou treme vermelho (erro, com o motivo no cartão).
// Escuta "painel:acao-longa" e "painel:acao-longa-fim" (api.js). Avisa o rodapé por "painel:espera" { n }.
import { useEffect, useRef, useState } from "react";
import { K } from "./logoK.js";
import { aj } from "../ajustes.js";
import "./Carregando.css";

const VOLTA_MS = aj("tela.k_volta_segundos", 5) * 1000, STANDBY_MS = aj("tela.k_standby_segundos", 5) * 1000;
const DESTRAVA_MS = aj("tela.k_trava_maxima_segundos", 90) * 1000, MIN_VISIVEL_MS = 1200;
const CAMINHO = K.itens.map((i) => i[0]).join("");

export function LogoK({ classe = "", id = "k" }) {
  return (
    <svg className={`cg-k ${classe}`} viewBox={`-6 -6 ${K.w + 12} ${K.h + 12}`} aria-hidden="true" style={{ "--fim": K.fim + "s" }}>
      <defs>
        <mask id={`${id}-mascara`} maskUnits="userSpaceOnUse" x={-6} y={-6} width={K.w + 12} height={K.h + 12}>
          <g className="mk">{K.itens.map(([d, ini, dur], i) => <path key={i} d={d} pathLength="1" style={{ "--ini": ini + "s", "--dur": dur + "s" }} />)}</g>
          <rect className="mk-cheio" x={-6} y={-6} width={K.w + 12} height={K.h + 12} />
        </mask>
      </defs>
      <path className="pr" d={CAMINHO} fillRule="evenodd" mask={`url(#${id}-mascara)`} />
    </svg>
  );
}

// O K pequeno do rodapé (do tamanho dos ícones): contorno fraco e uma faixa de tinta que varre em repetição
export function MiniK() {
  return (
    <svg className="cg-mini" viewBox={`-6 -6 ${K.w + 12} ${K.h + 12}`} aria-hidden="true">
      <clipPath id="cg-mini-cp"><rect className="faixa" x={-6} y={-6} width={K.w + 12} height={K.h + 12} /></clipPath>
      <path className="base" d={CAMINHO} fillRule="evenodd" />
      <path className="tinta" d={CAMINHO} fillRule="evenodd" clipPath="url(#cg-mini-cp)" />
    </svg>
  );
}

export default function Carregando() {
  const [vista, setVista] = useState({ on: false, trava: false, fase: "desenha", volta: 0, cartao: null });
  const ativos = useRef(new Map()), espera = useRef(new Set()), timers = useRef({}), abriuEm = useRef(0), fim = useRef(false);

  useEffect(() => {
    const t = timers.current;
    const limpar = () => { ["ciclo", "tick", "fechar", "destrava", "standby"].forEach((k) => { clearInterval(t[k]); clearTimeout(t[k]); }); };
    const avisarEspera = () => window.dispatchEvent(new CustomEvent("painel:espera", { detail: { n: espera.current.size } }));
    const cartaoDe = (a) => {
      let itens = [], prog = null;
      try { itens = a.itens() || []; prog = a.progresso(); } catch { /* a ação pode ter sumido */ }
      return itens.length ? { titulo: a.titulo, itens, prog } : null;
    };
    const esconder = () => {
      limpar(); fim.current = false;
      setVista((v) => ({ ...v, on: false, trava: false, cartao: null }));
      if (espera.current.size) { espera.current.clear(); avisarEspera(); }
    };
    const abrir = (ev) => {
      const a = ev.detail;
      ativos.current.set(a.id, a);
      if (t.tick && !fim.current) return;   // já aberta: só soma a ação
      limpar(); fim.current = false; abriuEm.current = Date.now();
      setVista({ on: true, trava: true, fase: "desenha", volta: 0, cartao: cartaoDe(a) });
      t.ciclo = setInterval(() => setVista((v) => ({ ...v, volta: v.volta + 1 })), VOLTA_MS);   // desenha, segura e apaga em loop
      t.tick = setInterval(() => { const ult = [...ativos.current.values()].pop(); if (ult) setVista((v) => ({ ...v, cartao: cartaoDe(ult) })); }, 400);
      t.destrava = setTimeout(() => setVista((v) => ({ ...v, trava: false })), DESTRAVA_MS);   // nunca prende ninguém para sempre
      t.standby = setTimeout(() => {
        if (!ativos.current.has(a.id) || fim.current) return;
        clearInterval(t.ciclo); clearInterval(t.tick); t.tick = null;
        setVista((v) => ({ ...v, on: false, trava: false, cartao: null }));
        espera.current.add(a.id); avisarEspera();
      }, a.standbyMs ?? STANDBY_MS);
    };
    const terminar = (ev) => {
      const { id, ok, texto } = ev.detail, a = ativos.current.get(id);
      ativos.current.delete(id);
      if (espera.current.delete(id)) avisarEspera();
      if (ativos.current.size) return;
      const emStandby = !t.tick;
      setTimeout(() => {
        fim.current = true; clearTimeout(t.standby); clearInterval(t.ciclo); clearInterval(t.tick); t.tick = null; clearTimeout(t.destrava);
        const c = a ? cartaoDe(a) : null;
        if (emStandby && ok) return esconder();
        setVista((v) => ({ ...v, on: !emStandby, trava: false, fase: ok ? "ok" : "erro",
          cartao: !ok ? { titulo: c ? "Terminou com aviso" : "Não deu certo", detalhe: c ? "" : texto || "", itens: c?.itens || [], prog: 1, erro: true } : c && { ...c, prog: 1, pronto: true } }));
        t.fechar = setTimeout(esconder, ok ? 1500 : 6000);
      }, Math.max(0, MIN_VISIVEL_MS - (Date.now() - abriuEm.current)));
    };
    // tela travada: nenhuma tecla chega atrás (só o cartão do canto continua usável)
    const tecla = (e) => {
      const veu = document.querySelector(".cg-veu.trava");
      if (veu && !e.target.closest?.(".cg-info")) { e.stopImmediatePropagation(); e.preventDefault(); }
    };
    window.addEventListener("painel:acao-longa", abrir);
    window.addEventListener("painel:acao-longa-fim", terminar);
    document.addEventListener("keydown", tecla, true);
    return () => { limpar(); window.removeEventListener("painel:acao-longa", abrir); window.removeEventListener("painel:acao-longa-fim", terminar); document.removeEventListener("keydown", tecla, true); };
  }, []);

  const c = vista.cartao;
  const fechar = () => setVista((v) => ({ ...v, on: false, trava: false, cartao: null }));
  return (
    <>
      <div className={`cg-veu${vista.on ? " on" : ""}${vista.trava ? " trava" : ""}`} role="status" aria-label="Carregando" aria-hidden={!vista.on}>
        <LogoK key={vista.fase + vista.volta} classe={vista.fase} />
      </div>
      <aside className={`cg-info vidro${c ? " on" : ""}${c?.erro ? " erro" : ""}`} aria-live="polite">
        {c && <>
          <div className="cg-tit">{c.titulo}</div>
          {c.detalhe && <div className="cg-det">{c.detalhe}</div>}
          {c.itens.length > 0 && <>
            <div className={`cg-bar${c.erro ? " erro" : ""}`}><i style={{ width: `${Math.round((c.prog ?? 0) * 100)}%` }} /></div>
            <div className="cg-meta"><span>{c.prog != null ? `${Math.round(c.prog * 100)}%` : ""}</span><span>{c.pronto ? "pronto" : c.erro ? "atenção" : ""}</span></div>
            <ul className="cg-pcs">{c.itens.map((p) => (
              <li key={p.pc} className={`${p.estado}${p.aviso ? " aviso" : ""}`}><span className="pt" /><span className="nm">{p.agente || p.pc}</span>
                <span className="rs">{p.estado === "andando" ? "trabalhando…" : p.res}</span></li>
            ))}</ul>
          </>}
          <div className="cg-rod"><button type="button" onClick={fechar}>Fechar</button></div>
        </>}
      </aside>
    </>
  );
}
