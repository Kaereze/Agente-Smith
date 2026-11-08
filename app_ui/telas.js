// Lógica das telas do Painel (separada do index.html em 07/11/2026). TOKEN e PAGINA vêm do index.html (o servidor troca os dois).
const NOMES = {aguardando_envio:"Aguardando envio", na_fila:"Sem NF", em_tratamento:"Em tratamento",
               tratativa:"Tratativa", nf_parcial:"NF parcial", concluida:"NF emitida", sem_resposta:"Sem resposta"};
// Uma cor por situação em todo o Painel (lista, cartões e gráficos): vermelho = sem NF / atrasada, violeta = e-mail sem
// resposta, azul = em andamento, âmbar = envio pendente, verde = emitida
const COR_SIT = {na_fila:"var(--erro)", em_tratamento:"var(--info)", tratativa:"var(--info)", nf_parcial:"var(--info)",
                 aguardando_envio:"var(--tinta-3)", sem_resposta:"var(--roxo)", concluida:"var(--ok)", envio_pendente:"var(--atencao)"};
// Notas fiscais (lateral): "Em aberto" = tudo que ainda não tem NF + e-mails sem resposta
const SITUACOES = [["aberto", "Em aberto"], ["na_fila"], ["em_tratamento"], ["tratativa"], ["nf_parcial"], ["aguardando_envio"],
                   ["sem_resposta"], ["concluida"], ["envio_pendente", "Envio pendente"], ["minhas", "Minhas"], ["todas", "Todas"]];
// Pedido do usuário (08/10/2026): uma tela "Notas fiscais" com duas abas (formulários e e-mails), situações como
// cartões de filtro e os demais filtros em pílulas com menu
const ORIGENS = [["form", "Na Caixa de Entrada"]];   // espelho do Outlook (usuário, 11/10/2026); e-mails têm a seção própria
const SIT_EMAIL = [["todos", "Todos", "var(--linha-forte)"], ["sem_nf", "Sem NF", "var(--roxo)"],
                   ["com_nf", "NF pronta, falta enviar", "var(--atencao)"], ["falta_nota", "Diz que não recebeu", "var(--erro)"],
                   ["dividida", "Nota dividida", "var(--info)"]];
const ENVIO = {todos: ["Todos", () => true], sim: ["Enviado", s => s.enviado], nao: ["Não enviado", s => !s.enviado]};
const PERIODOS_NF = [["7", "Últimos 7 dias"], ["15", "Últimos 15 dias"], ["30", "Últimos 30 dias"], ["45", "Últimos 45 dias"],
                     ["0", "Todo o período"]];
const POR_PAGINA = 100;
let st = {fila:[], agente:"", status:{}, emails:[], hoteis:[], pcs:[]}, timer = null, intervalo = 15;
let filtro = "todas", filtroEmail = "todos", origem = "form", agenteF = "", envio = "todos", periodo = "45";
let pagina = 0, sel = null, emailSel = null, ordem = "";   // ordem "": automática
let AG = {}, TODOS = [];   // hotel -> agente (Cadastro_Hoteis) · formulários + e-mails num formato só
try { const p = JSON.parse(localStorage.getItem("painel.caixa2") || "{}");
      if (["todas", "urgentes", "falta_dado", "dividida", "doc_diferente", "envio_pendente", "concluida", "minhas"].includes(p.filtro)) filtro = p.filtro;   // filtros v2
      if (p.filtroEmail) filtroEmail = p.filtroEmail; if (p.agente) agenteF = p.agente; } catch (e) {}
const guardarCaixa = () => { try { localStorage.setItem("painel.caixa2", JSON.stringify({origem, filtro, filtroEmail, agente: agenteF})); } catch (e) {} };

const $ = id => document.getElementById(id);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
const dataBr = iso => iso ? iso.slice(8,10)+"/"+iso.slice(5,7)+"/"+iso.slice(0,4) : "";
const quando = iso => { if(!iso) return ""; const d = new Date(iso); return isNaN(d) ? iso : d.toLocaleString("pt-BR",{day:"2-digit",month:"2-digit",hour:"2-digit",minute:"2-digit"}); };
const hojeIsoF = () => new Date().toLocaleDateString("sv-SE");
const ontemIso = () => { const d = new Date(); d.setDate(d.getDate() - 1); return d.toLocaleDateString("sv-SE"); };
function horaDoCarimbo(c) { const m = String(c || "").match(/(\d{1,2}):(\d{2})/); return m ? m[1].padStart(2, "0") + ":" + m[2] : ""; }
// Formatos únicos (24/10/2026): data, CPF/CNPJ e CEP iguais em todas as telas. A planilha às vezes perde o zero da frente
// (CPF com 10 dígitos, CNPJ com 13): volta o zero. Qualquer outra coisa sai como veio.
const digitosDe = v => String(v ?? "").replace(/\D/g, "");
function fmtDoc(v) {
  let d = digitosDe(v);
  if (d.length === 10 || d.length === 13) d = "0" + d;
  if (d.length === 11) return d.replace(/(\d{3})(\d{3})(\d{3})(\d{2})/, "$1.$2.$3-$4");
  if (d.length === 14) return d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5");
  return String(v ?? "");
}
function fmtCep(v) { const d = digitosDe(v); return d.length === 8 ? d.slice(0, 5) + "-" + d.slice(5) : String(v ?? ""); }
function fmtCarimbo(s) {   // dd/mm/aaaa hh:mm: o dia já vem lido pelo servidor (s.data), a hora sai do carimbo da planilha
  if (!s?.data) return String(s?.carimbo || "");
  const [a, m, d] = s.data.split("-"), h = horaDoCarimbo(s.carimbo);
  return `${d}/${m}/${a}${h ? " " + h : ""}`;
}
function chegou(iso) {   // "10:31" hoje · "Ontem" · "05/10"
  if (!iso) return "";
  const d = iso.slice(0, 10);
  return d === hojeIsoF() ? (iso.slice(11, 16) || "Hoje") : d === ontemIso() ? "Ontem" : d.slice(8, 10) + "/" + d.slice(5, 7);
}

// Toda ação mostra o que está acontecendo (usuário, 08/10/2026): barra no topo com a frase da tabela abaixo
const FAZENDO = [["/api/correio/buscar", "Procurando no Outlook dos PCs…"], ["/api/correio/texto", "Abrindo o e-mail no Outlook do PC dono…"],
  ["/api/correio/conversa", "Juntando o histórico do hóspede…"], ["/api/correio/excluir", "Mandando excluir no Outlook do PC dono…"],
  ["/api/correio/encaminhar", "Mandando encaminhar pelo Outlook do PC dono…"], ["/api/email/responder", "Entregando a resposta ao Outlook do PC dono…"],
  ["/api/envio_nf/opcoes", "Preparando o e-mail da NF…"], ["/api/email/opcoes", "Preparando a resposta…"], ["/api/envio_nf", "Entregando a NF ao Outlook…"],
  ["/api/acao", "Gravando na planilha…"], ["/api/atualizar", "Relendo a planilha…"], ["/api/agente", "Trocando o operador…"],
  ["/api/enviar", "Pedindo o envio ao robô…"], ["/api/comando", "Mandando o comando ao PC…"], ["/api/outlook/reiniciar", "Reiniciando o Outlook…"]];
let emAndamento = 0;
function carregando(path, liga, erro) {
  const frase = (FAZENDO.find(([p]) => path.startsWith(p)) || [])[1];
  if (!frase) return;
  const b = $("carregando");
  emAndamento = Math.max(0, emAndamento + (liga ? 1 : -1));
  // a faixa não mostra mais "carregando": isso agora é a tela do K (pecas/carregando.js). Ela fica só para o erro rápido.
  if (liga) { clearTimeout(b._h); return; }
  if (erro) { b.classList.add("erro"); $("carregando-txt").textContent = "Não deu certo: " + erro; b._h = setTimeout(() => b.classList.add("oculta"), 6000); return; }
  if (!emAndamento) b._h = setTimeout(() => b.classList.add("oculta"), 250);
}
// Velocidade 3 (21/10/2026): o que esta tela já tem destas rotas. Igual = o Painel responde só {__igual} (mais a hora
// da leitura e os PCs) e aqui devolvemos a cópia guardada (lida de novo, igual a uma resposta nova) com essas partes
// novas por cima, marcada com j.__igual (não entra no {...j}).
const COMPARADAS = ["/api/estado", "/api/emails", "/api/correio"], GUARDADAS = {}, REDESENHO_MS = 60000;
const SEM_TELA_K = ["/api/correio/evento", "/api/tema", "/api/enviar_receber", "/api/outlook/reiniciar", "/api/atualizar"];   // rápidas ou com tela própria
async function api(path, corpo){
  carregando(path, true);
  const longa = corpo && !SEM_TELA_K.some(p => path.startsWith(p)) ? acaoLonga((FAZENDO.find(([p]) => path.startsWith(p)) || [])[1] || "Trabalhando…") : null;   // passou de 3 s: tela do K
  const base = path.split("?")[0], guardada = !corpo && COMPARADAS.includes(base) ? GUARDADAS[base] : null;
  const headers = {"X-Token":TOKEN,"Content-Type":"application/json"};
  if (guardada && guardada.path === path && Date.now() - guardada.em < REDESENHO_MS) headers["X-Versao"] = guardada.v;
  let r;
  try {
    r = await fetch(path, {method: corpo ? "POST" : "GET", headers, body: corpo ? JSON.stringify(corpo) : undefined});
  } catch (e) { carregando(path, false, "o Painel deste PC não respondeu"); longa?.fim(false); throw e; }
  const texto = await r.text().catch(() => "");
  let j;
  try { j = JSON.parse(texto); } catch (e) { j = {ok:false, motivo:"resposta inválida"}; }
  if (j && j.__igual === true) {
    if (!headers["X-Versao"]) { carregando(path, false); longa?.fim(true); return api(path, corpo); }   // nunca acontece; por garantia
    const junto = {...j}; delete junto.__igual;
    j = Object.assign(JSON.parse(guardada.texto), junto);
    Object.defineProperty(j, "__igual", {value: true, enumerable: false});
  } else if (r.ok && r.headers.get("X-Versao")) {
    GUARDADAS[base] = {path, v: r.headers.get("X-Versao"), texto, em: Date.now()};
  }
  if (!r.ok && j.ok === undefined) j.ok = false;
  carregando(path, false, j.ok === false ? (j.motivo || j.erro) : j.erro);
  longa?.fim(j.ok !== false && !j.erro, j.motivo || j.erro || "");
  return j;
}
function toast(msg, erro){ const t = $("toast"); t.textContent = msg; t.className = "toast" + (erro ? " erro" : ""); t.style.display = "block";
  clearTimeout(t._h); t._h = setTimeout(() => t.style.display = "none", erro ? 5000 : 2500); }

// Cabeçalho: PCs da equipe — Outlook fechado ou conferente parado em algum PC acende o aviso
// Avisos do sistema (usuário, 14/10/2026): em vez da faixa no topo, uma caixinha no canto direito de baixo; clique abre
function desenharSaude(lista) {
  const el = $("saude");
  el.classList.toggle("oculta", !lista.length);
  if (!lista.length) { el.classList.remove("aberta"); el.innerHTML = ""; return; }
  const aberta = el.classList.contains("aberta"), grave = lista.some(p => p.nivel !== "warn");
  el.classList.toggle("grave", grave);
  el.removeAttribute("title");
  el.innerHTML = `<div class="s-painel" ${aberta ? "" : "hidden"}><div class="s-cab"><b>Avisos do sistema</b>
      <button type="button" class="s-fechar" aria-label="Fechar avisos">×</button></div>
      ${lista.map(p => `<div class="s-linha ${p.nivel}"><svg class="ic" aria-hidden="true"><use href="#i-alerta"/></svg><span>${esc(p.texto)}</span></div>`).join("")}
      <button type="button" class="s-ver so-admin">Ver no Monitoramento</button></div>
    <button type="button" class="s-bolha" aria-expanded="${aberta}" aria-label="${lista.length} aviso${lista.length > 1 ? "s" : ""} do sistema">
      <svg class="ic" aria-hidden="true"><use href="#i-alerta"/></svg><b>${lista.length}</b><span>aviso${lista.length > 1 ? "s" : ""}</span></button>`;
}
document.addEventListener("click", e => {
  const el = $("saude");
  if (e.target.closest("#saude .s-bolha")) { el.classList.toggle("aberta"); el.querySelector(".s-painel").hidden = !el.classList.contains("aberta");
    e.target.closest(".s-bolha").setAttribute("aria-expanded", el.classList.contains("aberta")); return; }
  if (e.target.closest("#saude .s-fechar")) { el.classList.remove("aberta"); el.querySelector(".s-painel").hidden = true; return; }
  if (e.target.closest("#saude .s-ver")) { el.classList.remove("aberta"); trocarVista("maquinas"); }
});
// Menu recolhível (usuário, 14/10/2026): fechado fica só com os ícones; lembra a escolha neste PC
// Menu da lateral v2 (22/10/2026): só ícones (padrão) ou com os nomes das abas, empurrando a tela; lembra neste PC
function aplicarMenu(fechado) {
  document.querySelector(".app").classList.toggle("menu-fechado", fechado);
  const b = $("btn-recolher"); b.setAttribute("aria-expanded", String(!fechado));
  b.title = fechado ? "Mostrar os nomes das abas" : "Só ícones";
  b.querySelector("span").textContent = fechado ? "Mostrar os nomes" : "Só ícones";
  if (typeof menuOperador === "function") menuOperador(false);
  try { localStorage.setItem("painel.menuNomes", fechado ? "" : "1"); } catch (e) {}
}
document.addEventListener("click", e => { if (e.target.closest("#btn-recolher")) aplicarMenu(!document.querySelector(".app").classList.contains("menu-fechado")); });
try { if (localStorage.getItem("painel.menuNomes") === "1") setTimeout(() => aplicarMenu(false), 0); } catch (e) {}
function desenharPcsCabecalho(pcs) {
  const on = pcs.filter(p => p.online);
  const fechados = on.filter(p => p.outlook === "fechado"), parados = on.filter(p => p.conferencia_atrasada);
  const nome = p => p.agente || p.pc;
  let txt = `${on.length} de ${pcs.length} PCs no ar`, cls = "on";
  if (fechados.length) { txt = "Outlook fechado: " + fechados.map(nome).join(", "); cls = "off"; }
  else if (parados.length) { txt = "conferência parada: " + parados.map(nome).join(", "); cls = "warn"; }
  else if (on.length < pcs.length) cls = "warn";
  $("pcs-dot").className = "dot " + cls; $("pcs-txt").textContent = txt;
  $("pcs").title = pcs.map(p => `${nome(p)} (${p.pc}): ${p.online ? "online" : "desligado"} · Outlook ${p.outlook || "?"} · versão ${p.versao || "?"}`).join("\n");
  const alertas = on.filter(p => p.outlook === "fechado" || p.conferencia_atrasada).length + pcs.filter(p => !p.online).length;
  $("nav-maquinas").innerHTML = `<svg class="ic"><use href="#i-log"/></svg>Monitoramento` +
    `<span class="n ${alertas ? "al" : ""}">${alertas ? alertas + (alertas === 1 ? " alerta" : " alertas") : on.length + " no ar"}</span>`;
}
