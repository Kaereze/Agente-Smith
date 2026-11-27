// "Quem está neste PC" (clique no avatar da cápsula): quem trabalha aqui (trocar pergunta antes: a troca por um clique já zerou
// a caixa do João duas vezes), o tema (Sistema, Claro, Escuro, gravado neste PC), o tamanho da tela (só na janela do app),
// a ajuda e "Fechar o Painel" (o X da janela só esconde).
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Icone from "../componentes/Icone.jsx";
import Botao from "../componentes/Botao.jsx";
import Janela from "../componentes/Janela.jsx";
import { useAvisos } from "../componentes/Avisos.jsx";
import { api } from "../api.js";

export const TEMAS = [["", "Sistema"], ["claro", "Claro"], ["escuro", "Escuro"]];
const ESCALAS = [0.9, 1, 1.1, 1.25, 1.5];
const BASE = 1500, MIN = 0.85, MAX = 1.3, PASSO = 0.05;   // automático: largura de conforto e os limites (nunca ilegível)
const lerEscala = () => { try { return localStorage.getItem("painel.escala") || "auto"; } catch { return "auto"; } };
const pywebview = () => window.pywebview?.api || null;
// Iniciais que não se repetem: Cristian e Clara viravam os dois "C"; com outro nome de mesma letra, vão 2 letras
export const iniciais = (n, todos = []) => { const a = String(n || "?").trim(); return (todos.some((o) => o !== n && o?.[0]?.toUpperCase() === a[0]?.toUpperCase()) ? a.slice(0, 2) : a[0] || "?").toUpperCase(); };

// Tamanho da tela: quem aplica o zoom é o Python, pelo WebView2 (ZoomFactor). Sem a janela do app, não faz nada.
export async function aplicarEscala(pref = lerEscala()) {
  const a = pywebview();
  if (!a?.definir_escala) return null;
  try {
    const antes = Number(await a.escala_atual()) || 1;
    const bruto = Math.min(MAX, Math.max(MIN, (window.innerWidth * antes) / BASE));
    const alvo = pref === "auto" ? Number((Math.round(bruto / PASSO) * PASSO).toFixed(2)) : Number(pref);
    return Number(await a.definir_escala(alvo)) || antes;
  } catch { return null; }
}

export default function MenuOperador({ estado, tema, escolherTema, aoFechar, abrirAjuda, ancora, reler }) {
  const { recado } = useAvisos();
  const caixa = useRef(null);
  const [trocar, setTrocar] = useState("");
  const [escala, setEscala] = useState(lerEscala);
  const [zoom, setZoom] = useState(null);
  const atual = estado?.agente || "";
  const lista = [...new Set([atual, ...(estado?.operadores || [])].filter(Boolean))];
  const app = !!pywebview();

  useEffect(() => { if (app) pywebview().escala_atual?.().then((v) => setZoom(Number(v) || 1)).catch(() => {}); }, [app]);
  useEffect(() => {
    caixa.current?.querySelector("button")?.focus({ preventScroll: true });
    const fora = (ev) => { if (!caixa.current?.contains(ev.target) && !ev.target.closest?.(".janela-fundo") && !ev.target.closest?.(".capsula-avatar")) aoFechar(); };
    const tecla = (ev) => { if (ev.key === "Escape" && !document.querySelector(".janela-fundo")) aoFechar(); };
    document.addEventListener("mousedown", fora);
    window.addEventListener("keydown", tecla);
    return () => { document.removeEventListener("mousedown", fora); window.removeEventListener("keydown", tecla); };
  }, [aoFechar]);

  const confirmarTroca = async () => {
    const nome = trocar;
    setTrocar("");
    const r = await api("/api/agente", { nome });
    if (r.ok === false) return recado(r.motivo || r.erro || "Não deu para trocar agora", true);
    recado("Operador: " + nome);
    aoFechar();
    reler?.();
  };
  const escolherEscala = async (v) => {
    setEscala(v);
    try { localStorage.setItem("painel.escala", v); } catch { /* só nesta janela */ }
    const z = await aplicarEscala(v);
    if (z) setZoom(z);
  };
  const r = ancora?.getBoundingClientRect();
  const celular = window.innerWidth <= 760;
  const pos = !r ? {} : celular ? { right: 10, bottom: window.innerHeight - r.top + 10 } : { left: r.right + 14, bottom: Math.max(8, window.innerHeight - r.bottom) };

  return createPortal(
    <>
      <div ref={caixa} className="menu-op" role="dialog" aria-label="Quem está neste PC" style={pos}>
        <div className="op-cab"><b>Quem está neste PC</b><small>{estado?.pc || ""}</small></div>
        {lista.map((o) => (
          <button key={o} type="button" className={`op-item${o === atual ? " sel" : ""}`} aria-pressed={o === atual} onClick={() => (o === atual ? aoFechar() : setTrocar(o))}>
            <span className="capsula-avatar">{iniciais(o, lista)}</span>
            <span className="op-n">{o}<small>{o === atual ? "você, neste PC" : `trocar para ${o}`}</small></span>
            {o === atual && <Icone nome="check" tamanho={16} />}
          </button>
        ))}
        {!lista.includes("João") && <p className="op-nota">O usuário João só é usado no PC dele.</p>}
        <div className="op-sep" />
        <div className="op-grupo"><b>Tema</b>
          <div className="op-botoes" role="group" aria-label="Tema">
            {TEMAS.map(([v, t]) => <button key={t} type="button" aria-pressed={tema === v} onClick={() => escolherTema(v)}>{t}</button>)}
          </div>
        </div>
        {app && (
          <div className="op-grupo"><b>Tamanho da tela</b><small>{escala === "auto" ? `Automático${zoom ? `: ${Math.round(zoom * 100)}% neste PC` : ""}` : `Fixo em ${Math.round(Number(escala) * 100)}%`}</small>
            <div className="op-botoes" role="group" aria-label="Tamanho da tela">
              <button type="button" aria-pressed={escala === "auto"} onClick={() => escolherEscala("auto")}>Auto</button>
              {ESCALAS.map((v) => <button key={v} type="button" aria-pressed={escala === String(v)} onClick={() => escolherEscala(String(v))}>{Math.round(v * 100)}%</button>)}
            </div>
          </div>
        )}
        <div className="op-sep" />
        <button type="button" className="op-item" onClick={() => { aoFechar(); abrirAjuda(); }}>
          <span className="op-ic"><Icone nome="ajuda" tamanho={17} /></span><span className="op-n">Ajuda<small>o que cada nome significa e os atalhos (tecla ?)</small></span></button>
        {app && (
          <button type="button" className="op-item" title="O X só esconde a janela (abre na hora). Isto fecha de verdade." onClick={() => pywebview()?.sair?.()}>
            <span className="op-ic"><Icone nome="desligar" tamanho={17} /></span><span className="op-n">Fechar o Painel<small>o X da janela só esconde</small></span></button>
        )}
      </div>
      {trocar && (
        <Janela titulo={`Trocar este PC para ${trocar}?`} sub={`O Painel passa a mostrar e a contar as caixas como se fosse ${trocar}. Troque só se este PC mudou de dono.`}
          aoFechar={() => setTrocar("")} largura={460}
          rodape={<><Botao onClick={() => setTrocar("")}>Cancelar</Botao><Botao tipo="principal" onClick={confirmarTroca}>Trocar para {trocar}</Botao></>}>
          <span data-foco tabIndex={-1} />
        </Janela>
      )}
    </>,
    document.body,
  );
}
