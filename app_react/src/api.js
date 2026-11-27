// Conversa com o servidor do Painel. A senha da sessão vem no <meta name="painel-token">.
// Toda ação (POST) que passa de 3 s abre a tela de carregamento (o K sendo desenhado, componentes/Carregando.jsx):
// a ação avisa por "painel:acao-longa" e, ao terminar, por "painel:acao-longa-fim". As rápidas ou com tela própria ficam de fora.
import { aj } from "./ajustes.js";

const TOKEN = document.querySelector('meta[name="painel-token"]')?.content || "";
const LIMITE_MS = aj("tela.acao_longa_segundos", 3) * 1000;
const SEM_TELA_K = ["/api/correio/evento", "/api/tema", "/api/enviar_receber", "/api/outlook/reiniciar", "/api/atualizar", "/api/acesso", "/api/correio/urgencia", "/api/ligacao"];
const TITULOS = [["/api/correio/excluir", "Mandando excluir no Outlook do PC dono…"], ["/api/correio/encaminhar", "Mandando encaminhar pelo Outlook do PC dono…"],
  ["/api/email/responder", "Entregando a resposta ao Outlook do PC dono…"], ["/api/email/novo", "Entregando o e-mail ao Outlook do PC dono…"],
  ["/api/envio_nf/conferir", "Conferindo a NF com o pedido…"], ["/api/envio_nf", "Entregando a NF ao Outlook…"], ["/api/agente", "Trocando o operador…"],
  ["/api/enviar", "Pedindo o envio ao robô…"], ["/api/comando", "Mandando o comando ao PC…"], ["/api/cadastro/adicionar", "Gravando o cadastro…"],
  ["/api/robo/ligado", "Avisando o robô…"], ["/api/correio/mover_nf", "Movendo no Outlook do PC dono…"]];

let seq = 0;
// Ação longa: avisa a tela se passar do limite (ou na hora, com limiteMs: 0). detalhe: { titulo, itens(), progresso(), standbyMs }
export function acaoLonga(titulo, detalhe = {}) {
  const acao = { id: "acao-" + (++seq), titulo, inicio: Date.now(), itens: () => [], progresso: () => null, ...detalhe };
  let avisou = false;
  const timer = setTimeout(() => { avisou = true; window.dispatchEvent(new CustomEvent("painel:acao-longa", { detail: acao })); }, detalhe.limiteMs ?? LIMITE_MS);
  return {
    acao,
    fim(ok = true, texto = "") {
      clearTimeout(timer);
      if (avisou) window.dispatchEvent(new CustomEvent("painel:acao-longa-fim", { detail: { id: acao.id, ok, texto } }));
    },
  };
}

export async function api(caminho, corpo) {
  const base = caminho.split("?")[0];
  const longa = corpo && !SEM_TELA_K.some((p) => base.startsWith(p))
    ? acaoLonga((TITULOS.find(([p]) => base.startsWith(p)) || [])[1] || "Trabalhando…") : null;
  let j;
  try {
    const r = await fetch(caminho, {
      method: corpo ? "POST" : "GET",
      headers: { "X-Token": TOKEN, "Content-Type": "application/json" },
      body: corpo ? JSON.stringify(corpo) : undefined,
    });
    const texto = await r.text();
    try { j = JSON.parse(texto); } catch { j = { ok: false, motivo: "resposta inválida" }; }
    if (!r.ok && j.ok !== false) j = { ...j, ok: false };
  } catch (e) {
    longa?.fim(false, "o Painel deste PC não respondeu");
    throw e;
  }
  longa?.fim(j.ok !== false && !j.erro, j.motivo || j.erro || "");
  return j;
}
