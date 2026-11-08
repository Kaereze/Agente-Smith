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

// soSeMudou (velocidade 3): volta automática — pedidos e e-mails iguais aos que a tela já tem = não redesenha.
// Quem chama depois de uma ação (marcar, excluir...) usa carregar() e a tela redesenha sempre, como antes.
let emCarga = 0;
async function carregar(soSeMudou = false) { emCarga++; try { return await carregarJa(soSeMudou); } finally { emCarga--; } }
async function carregarJa(soSeMudou){
  try {
    // dias: o dobro da janela da Visão geral (o resumo compara com o período anterior inteiro)
    const dias = periodo === "0" ? 0 : Math.max(typeof pn !== "undefined" && pn.vista === "gerencia" ? 75 : 45, 2 * (typeof pn !== "undefined" ? pn.janela : 30));
    const j = await api("/api/estado?dias=" + dias + "&vista=" + (typeof pn !== "undefined" ? pn.vista : ""));   // período menor é filtrado aqui
    ultimoOk = Date.now();
    if (j.erro === "não autorizado") { location.reload(); return; }   // servidor reiniciado (atualização): pega a sessão nova
    // tela nova no disco (atualização sem reinício): recarrega, mas nunca com uma mensagem sendo escrita
    if (j.pagina && j.pagina !== PAGINA && !document.querySelector(".modal-fundo") && !(typeof envNF !== "undefined" && envNF)) {
      location.reload(); return;
    }
    let em = null;
    if (soSeMudou && j.__igual) {   // pedidos iguais: e os e-mails? iguais também = a tela fica como está
      try { em = await api("/api/emails"); } catch (e) { em = {}; }
      if (em.__igual) {   // só o cabeçalho muda: hora da leitura e PCs no ar
        st = {...st, atualizado_em: j.atualizado_em, pcs: j.pcs || st.pcs};
        if (!j.erro) $("sync-txt").textContent = "Central sincronizada " + quando(j.atualizado_em).slice(-5);
        desenharPcsCabecalho(st.pcs);
        carregarCorreio(true); avisoParado(); clearTimeout(timer); timer = setTimeout(() => carregar(true), intervalo * 1000); return;
      }
    }
    const roboAntes = JSON.stringify(st.status || {});
    st = {...st, ...j}; intervalo = j.atualizar_segundos || 15;
    // pedido repetido (Etapa 2): conta 1 vez só; o repetido fica ligado ao principal e abre pelo detalhe dele
    if (j.fila) { st.filaRep = j.fila.filter(s => s.repetido_de); st.fila = j.fila.filter(s => !s.repetido_de); }

    desenharOperador(j.agente, j.operadores || [], j.pc);
    $("pill-demo").classList.toggle("oculta", !j.demo);
    $("pill-casa").classList.toggle("oculta", !j.so_ver);
    document.documentElement.classList.toggle("e-admin", !!j.admin);
    if (j.tema !== undefined && j.tema !== temaServidor) { temaServidor = j.tema; if (j.tema !== (document.documentElement.dataset.theme || "")) aplicarTema(j.tema); }
    if (!j.atualizado_em && !j.erro) {   // primeira leitura da planilha ainda em andamento
      $("sync-txt").textContent = "lendo a planilha…"; $("lista").innerHTML = `<div class="vazio">Carregando solicitações…</div>`;
      clearTimeout(timer); timer = setTimeout(carregar, 2000); return;
    }
    const ok = !j.erro;
    $("sync-dot").className = "dot " + (ok ? "on" : "off");
    $("sync-txt").textContent = ok ? "Central sincronizada " + quando(j.atualizado_em).slice(-5) : "sem conexão com a planilha";
    const s = j.status || {};
    if (typeof rbChip === "function") rbChip();   // o chip do robô (robo.js) mostra o estado, o resumo e a resposta
    desenharPcsCabecalho(j.pcs || []);
    desenharSaude(j.saude || []);
    window.caixasProblema?.(j.saude || []);   // botão de caixas com problema (pecas/caixas.js)
    // pedidos aparecem já; os e-mails (outra rota) entram em seguida, sem segurar a tela
    montarTodos();
    try { if (!em) em = await api("/api/emails"); if (em.emails) { st.emails = em.emails; st.este_pc = em.este_pc; } } catch(e) {}
    montarTodos();
    carregarCorreio(soSeMudou);
    if (pn.vista === "visao") desenharVisao();
    if (pn.vista === "gerencia") desenharGerencia();
    if (typeof rbVigiar === "function") rbVigiar();   // chip do robô na barra de baixo (robo.js)
  } catch(e) {
    $("sync-dot").className = "dot off"; $("sync-txt").textContent = "app desconectado";
  }
  avisoParado();
  clearTimeout(timer); timer = setTimeout(() => carregar(true), intervalo * 1000);
}

// Tela que se atualiza sozinha (velocidade 3, 21/10/2026): a cada 3 s pergunta ao Painel deste PC se tem dado novo
// (leitura da Central, NF do Dropbox, envio que terminou). Só relê quando tem; a volta de 15 s continua de garantia.
let marcaTela = null;
setInterval(async () => {
  if (document.visibilityState !== "visible" || emCarga) return;
  try {
    const r = await fetch("/api/versao", {headers: {"X-Token": TOKEN}});
    const j = await r.json();
    if (!j.v) return;
    if (marcaTela !== null && j.v !== marcaTela) { clearTimeout(timer); carregar(true); }
    marcaTela = j.v;
  } catch (e) { /* a volta de 15 s cobre */ }
}, 3000);

// Tela que não trava (usuário, 21/10/2026, desenho Pr6): 1 min sem resposta do servidor com a tela à vista acende a faixa
// laranja; F5 recarrega (a janela do app desliga as teclas do navegador; Ctrl+R continua sendo Responder, correio.js);
// a janela (app_janela) pergunta se a tela
// está viva por window.__painelVivo.
let ultimoOk = Date.now(), f5Pedido = 0;
window.__painelVivo = () => Date.now() - ultimoOk;
function avisoParado() {
  const parado = Date.now() - ultimoOk > 60000 && document.visibilityState === "visible";
  if (parado) $("aviso-parado-txt").textContent = `há ${Math.max(1, Math.round((Date.now() - ultimoOk) / 60000))} min`;
  $("aviso-parado").classList.toggle("oculta", !parado);
}
function recarregarTela() {   // com mensagem sendo escrita, pede o 2º aperto (não perde o texto sem querer)
  const escrevendo = document.querySelector(".modal-fundo") || (typeof envNF !== "undefined" && envNF);
  if (escrevendo && Date.now() - f5Pedido > 3000) { f5Pedido = Date.now(); toast("Tem mensagem sendo escrita. Aperte F5 de novo para recarregar mesmo assim.", true); return; }
  location.reload();
}
document.addEventListener("keydown", e => {
  if (e.key === "F5" && !e.ctrlKey && !e.altKey && !e.shiftKey) { e.preventDefault(); recarregarTela(); }
});
$("aviso-parado-bt").addEventListener("click", recarregarTela);
document.addEventListener("visibilitychange", () => {   // janela mostrada de novo: dados na hora, sem esperar os 15 s
  if (document.visibilityState === "visible" && Date.now() - ultimoOk > 20000) { clearTimeout(timer); carregar(); }
});

function montarTodos() {
    AG = {}; (st.hoteis || []).forEach(h => AG[h.hotel] = h.agente);
    // Hóspede respondeu dizendo que falta nota/diária: o pedido dele não está resolvido, mesmo com NF
    const faltas = {};
    st.emails.forEach(m => { if (m.falta_nota && m.solicitacao) faltas[m.solicitacao.chave] = m.falta_nota; });
    st.fila.forEach(s => { s.falta_nota = faltas[s.chave] || ""; if (s.falta_nota && s.situacao === "concluida") s.situacao = "nf_parcial"; });
    TODOS = espelhoCaixa().map(s => ({tipo: "form", id: s.chave, s, hoteis: [s.hotel],
                                      quando: s.na_caixa?.recebido || (s.data + "T" + horaDoCarimbo(s.carimbo))}))
      .concat(st.emails.map(m => ({tipo: "email", id: m.id, m, hoteis: m.hotel.split(" / "), quando: m.recebido || ""})))
      .sort((a, b) => b.quando.localeCompare(a.quando));
    desenhar();
}

// Notas fiscais = o que está na Caixa de Entrada do Outlook dos 4 PCs (usuário, 11/10/2026): a solicitação do robô
// saiu da caixa (movida ou excluída), sai daqui. Pedido repetido: se só o repetido está na caixa, aparece ele.
function espelhoCaixa() {
  const principais = new Set(st.fila.filter(s => s.na_caixa).map(s => s.chave));
  return st.fila.filter(s => s.na_caixa).concat((st.filaRep || []).filter(s => s.na_caixa && !principais.has(s.repetido_de)));
}
const nomePc = pc => (st.pcs || []).find(p => p.pc === pc)?.agente || pc;
// bolinha com a inicial e a cor do operador dono da caixa (só no "Todos": com um operador escolhido é redundante)
const opMini = nome => nome && escopoAtual() === "todos"
  ? `<span class="op-mini" style="background:${corOp(nome)}" title="Caixa de ${esc(nome)}">${esc(inicial(nome))}</span>` : "";
function agentesDo(it) {
  if (it.tipo === "form" && it.s.na_caixa?.pc) return [nomePc(it.s.na_caixa.pc)];   // quem tem a caixa no Outlook
  const a = it.hoteis.map(h => AG[h]).filter(Boolean);
  return a.length ? a : it.tipo === "email" ? [it.m.agente_pc] : [];
}
function passaSit(it, f) {
  if (it.tipo === "email") {
    const m = it.m;
    return f === "todos" ? true : f === "sem_nf" ? !m.notas?.length : f === "com_nf" ? !!m.notas?.length
      : f === "falta_nota" ? !!m.falta_nota : f === "dividida" ? m.quartos >= 2 : true;
  }
  const s = it.s;
  if (f === "todas") return true;
  if (f === "envio_pendente") return !!s.envio_pendente;
  if (f === "aberto") return s.situacao !== "concluida";
  if (f === "atrasadas") return s.situacao !== "concluida" && diasDesde(s.data) > PRAZO.med;
  if (f === "doc_diferente") return !!(s.alerta_doc && s.alerta_doc.length);
  if (f === "minhas") return s.dono === st.agente && s.situacao !== "concluida";
  if (f === "urgentes") return !!motivoUrgente(s);
  if (f === "falta_dado") return faltaDados(s).length > 0;
  if (f === "dividida") return !!s.dividida;
  if (f === "concluida") return s.situacao === "concluida" && !s.envio_pendente;   // "NF enviada": só a que saiu (21/10/2026)
  return s.situacao === f;
}
// O que é preciso pra emitir (campoDoPedido, faltaDados, faltaExtras): pecas/regras_nf.js
// Urgência (usuário, 14/10/2026): prazo perto de vencer (ou vencido) ou o hóspede cobrou de novo
function motivoUrgente(s) {
  if (s.situacao === "concluida") return "";
  if ((st.filaRep || []).some(r => r.repetido_de === s.chave)) return "Cobrou de novo";
  const i = prazoInfo(s.prazo);
  return !i ? "" : i.resta <= 0 ? "Prazo vencido" : i.resta <= 6 ? "Vence em " + i.tempo : "";
}
function tagsPedido(s) { return etiquetasDoPedido(s); }   // a peça única das etiquetas (pecas/etiqueta.js)
function faltaBanner(s) {
  const falta = faltaDados(s);
  if (!falta.length) return "";
  const txt = { "nome": "o nome de quem vai na nota", "CPF/CNPJ": "o CPF ou CNPJ", "o que quer na nota": "o que entra na nota (diárias, consumo ou estacionamento)" };
  return `<div class="falta-banner" role="status"><div><b>Falta ${falta.length} dado${falta.length > 1 ? "s" : ""} para emitir</b>
    <span>O hóspede não informou ${esc(falta.map(f => txt[f] || f).join(", "))}.</span></div>
    <button type="button" class="dest" data-pedir-dados="${esc(s.chave)}">Pedir o que falta</button></div>`;
}
// Prazo de atendimento: quantos dias o pedido (ou o e-mail) espera
// Pedidos dos últimos 45 dias (os contadores de sempre); st.fila pode trazer mais, pra comparar períodos
const filaBase = () => { const d = new Date(); d.setDate(d.getDate() - 45); const c = d.toLocaleDateString("sv-SE"); return st.fila.filter(s => !s.data || s.data >= c); };
const diasDesde = iso => Math.max(0, Math.round((new Date(hojeIsoF() + "T12:00") - new Date(String(iso).slice(0, 10) + "T12:00")) / 864e5));
const PRAZO = { ok: 2, med: 7 };   // até 2 dias verde, até 7 âmbar, acima vermelho
// Prazo (SLA) da Etapa 2 (usuário, 09/10/2026): correção e cobrança 24 h, pedido 48 h, dias corridos. O servidor manda
// quando vence; o que falta é contado aqui, então o selo anda sozinho entre as atualizações.
function prazoInfo(p) {
  if (!p || !p.vence) return null;
  const resta = (new Date(p.vence) - Date.now()) / 36e5, h = Math.abs(resta);
  const nivel = resta <= 0 ? "vencido" : resta <= p.horas / 2 ? "perto" : "ok";
  const tempo = h < 1 ? Math.max(1, Math.round(h * 60)) + " min" : h < 48 ? Math.round(h) + " h" : Math.round(h / 24) + " dias";
  return { nivel, resta, tempo, texto: resta <= 0 ? "venceu há " + tempo : "vence em " + tempo };
}
function prazoHtml(p, mini = false, semPrazo = "—") {
  const i = prazoInfo(p);
  if (!i) return `<span class="prazo fim">${semPrazo}</span>`;
  return `<span class="prazo ${i.nivel} ${mini ? "mini" : ""}" title="Prazo de ${esc(p.nome)}: ${p.horas} h, dias corridos (${i.texto})">${
    mini ? "⏱ " + (i.resta <= 0 ? "venceu" : i.tempo) : i.texto}</span>`;
}
function esperaHtml(it) {
  if (it.tipo === "form") return prazoHtml(it.s.prazo, false, it.s.situacao === "tratativa" ? "com o hóspede" : "—");
  const resolvido = false;
  if (resolvido) return `<span class="espera fim">—</span>`;
  const d = diasDesde(it.quando);
  const cls = d <= PRAZO.ok ? "ok" : d <= PRAZO.med ? "med" : "alto";
  return `<span class="espera ${cls}" title="Esperando desde ${dataBr(it.quando.slice(0, 10))}">${d === 0 ? "hoje" : d === 1 ? "1 dia" : d + " dias"}</span>`;
}
function corteDoPeriodo() {
  if (periodo === "0") return "";
  const d = new Date(); d.setDate(d.getDate() - Number(periodo));   // igual ao corte do servidor (dias=45)
  return d.toLocaleDateString("sv-SE");
}
// Busca do jeito do Outlook: sem acento e sem maiúscula ("Corné" acha "CORNELIO"), pedaço de palavra, cada
// palavra digitada em qualquer campo (nome, e-mail, assunto, corpo, anexos, NF, CPF/CNPJ com ou sem pontuação)
const semAcento = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const soDigitos = s => s.replace(/(\d)[.\-\/\s](?=\d)/g, "$1");
function textoDo(it) {
  if (!it._t) {
    const t = semAcento((it.tipo === "form"
      ? [it.s.nome, it.s.email, it.s.hotel, it.s.carimbo, it.s.nfs.map(n => "nf " + n).join(" "), it.s.dono,
         it.s.falta_nota, ...it.s.campos.map(c => c[0] + " " + c[1])]
      : [it.m.nome, it.m.de, it.m.assunto, it.m.hotel, it.m.caixa, it.m.agente_pc, it.m.texto, (it.m.anexos || []).join(" "),
         (it.m.hospedes_quartos || []).join(" "), it.m.falta_nota]).join(" \n "));
    it._t = t + " \n " + soDigitos(t);
  }
  return it._t;
}
// "NF 196" é o número exato da nota (não acha 1960 nem o 196 de um telefone); o resto é pedaço de palavra
let _termos = ["", []];
const escRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function termosDaBusca(busca) {
  if (_termos[0] === busca) return _termos[1];
  const termos = [];
  const resto = semAcento(busca).replace(/\bnfs?-?e?\s*(?:n[º°o]\.?\s*)?(\d+)\b/g, (_, n) => {
    termos.push(new RegExp(`nf\\S*\\s*(?:n[º°o]\\.?\\s*)?${n}(?!\\d)`)); return " ";
  });
  resto.split(/\s+/).filter(Boolean).map(soDigitos).forEach(p => termos.push(new RegExp(escRe(p))));
  _termos = [busca, termos];
  return termos;
}
function passa(it, ignorar = "", busca) {   // ignorar: "origem|sit"...
  if (!ignorar.includes("origem") && it.tipo !== origem) return false;
  // pesquisando, procura na aba inteira: situação, hotel, agente e período não escondem o que bate
  if (busca) return termosDaBusca(busca).every(re => re.test(textoDo(it)));
  if (!ignorar.includes("sit") && !passaSit(it, it.tipo === "form" ? filtro : filtroEmail)) return false;
  if (!ignorar.includes("agente") && agenteF && !agentesDo(it).includes(agenteF)) return false;
  if (!ignorar.includes("escopo") && !doAgente(agentesDo(it))) return false;
  if (!ignorar.includes("hotel") && !fhPassa(it.hoteis)) return false;
  if (it.tipo === "form") return true;   // espelho da caixa: sem período nem "e-mail ao hotel" (está tudo no Outlook)
  if (!ignorar.includes("envio") && it.tipo === "form" && !ENVIO[envio][1](it.s)) return false;
  const corte = ignorar.includes("periodo") ? "" : corteDoPeriodo();
  if (corte && it.quando.slice(0, 10) < corte) return false;
  return true;
}
const ln = (attrs, rotulo, n, atual, bola) =>
  `<button class="ln ${n === 0 ? "vazio-n" : ""}" ${attrs} aria-current="${atual}">${bola ? `<span class="bola" style="background:${bola}"></span>` : ""}${esc(rotulo)}${n !== "" ? `<span class="n">${n.toLocaleString("pt-BR")}</span>` : ""}</button>`;

// Nota dividida: quantas das partes já têm NF ("Dividida em quantas vezes"; sem número = 2)
function tagDivisao(s) {
  const partes = Math.max(s.partes || 1, 2), feitas = s.nfs.length, falta = partes - feitas;
  if (!feitas) return "";
  return feitas >= partes ? `<span class="tag nf-ok" title="NF ${esc(s.nfs.join(", "))}">NF emitida</span>`
    : `<span class="tag nf-parc" title="NF ${esc(s.nfs.join(", "))} · ${feitas} de ${partes}">falta ${falta} nota${falta > 1 ? "s" : ""}</span>`;
}
// NF emitida x e-mail com a NF enviado ao hóspede (a colega emite e esquece de mandar)
const textoEnvio = v => `NF ${v.nfs.join(", ")} enviada para ${v.para} em ${v.quando}`;
const marcaEnvio = s => s.envio_pendente ? `<span class="envio pend" title="A NF existe, mas nenhum e-mail com ela saiu para o hóspede">envio pendente</span>`
  : s.envios?.length && s.nfs.length ? `<span class="envio ok" title="${esc(s.envios.map(textoEnvio).join("\n"))}">enviada ✓</span>` : "";
// Hóspede diz que ainda falta nota/diária (frase dele na dica)
const tagFalta = frase => frase ? `<span class="tag falta" title="${esc(frase)}">falta nota</span>` : "";
const quadroFalta = frase => frase ? `<section class="ficha"><div class="ficha-tit"><span class="rot" style="color:var(--erro)">O hóspede diz que ainda falta nota</span>
  <span class="tag falta">falta nota</span></div><div class="ficha-corpo">“${esc(frase)}”</div></section>` : "";
// Voucher anexado ao e-mail com 2+ quartos (um hóspede por quarto) = nota dividida
const tagQuartos = m => m.quartos >= 2
  ? `<span class="tag" title="${esc((m.hospedes_quartos || []).join(" · "))}">dividida · ${m.quartos} quartos</span>` : "";
// O hóspede pediu dividida e depois aceitou uma nota só: a frase dele fica no título
const tagNotaUnica = s => s.nota_unica ? `<span class="tag nf-ok" title="${esc(s.nota_unica)}">1 nota a pedido do hóspede</span>` : "";

// "Equipe toda" (padrão) ou "Meus hotéis" — vale pra Notas, E-mails e os números da lateral; lembrado neste PC
// Filtro dos 4 agentes (usuário, 11/10/2026): Todos · João · Clara · Cristian · Bernardo. Cada um vê a própria
// Caixa de Entrada do Outlook (o agente do PC dono da caixa). Abre no agente deste PC; a escolha fica guardada.
let escopo = "";
try { escopo = localStorage.getItem("painel.agenteFiltro") || ""; } catch (e) {}
const ORDEM_AGENTES = ["João", "Clara", "Cristian", "Bernardo"];
const agentesEquipe = () => { const da = (st.pcs || []).filter(p => p.papel !== "so_painel").map(p => p.agente).filter(Boolean);   // PC só com o Painel (Ingrid) não tem caixa: fora do filtro, e ela abre em "Todos"
  return [...ORDEM_AGENTES.filter(a => da.includes(a)), ...da.filter(a => !ORDEM_AGENTES.includes(a)).sort()]; };
const escopoAtual = () => { const e = escopo || st.agente || "todos"; return e === "todos" || agentesEquipe().includes(e) ? e : "todos"; };
const doAgente = (agentes, alvo = escopoAtual()) => alvo === "todos" || agentes.includes(alvo);
const meuHotel = h => String(h || "").split(" / ").some(x => AG[x] === st.agente);
// Operador em botões compactos (organização, 11/10/2026): na Notas conta solicitações; nos E-mails, e-mails
function segOperadores(contar) {
  const atual = escopoAtual();
  return [["todos", "Todos"], ...agentesEquipe().map(a => [a, a])].map(([v, rotulo]) =>
    `<button role="tab" aria-selected="${atual === v}" data-escopo="${esc(v)}" aria-pressed="${atual === v}" title="${v === "todos" ? "As caixas dos 4 PCs" : "A Caixa de Entrada do PC de " + esc(v)}">${esc(rotulo)}${contar ? `<span class="qt">${contar(v).toLocaleString("pt-BR")}</span>` : ""}</button>`).join("");
}
// Cartões dos operadores: solicitações (Notas fiscais) e e-mails da Caixa de Entrada de cada um, nas duas telas
// abas de operador (11/10/2026): só nome + número; os detalhes do escolhido ficam numa linha embaixo
function detalheOperador() {
  const v = escopoAtual(), temCx = typeof emailsDa === "function";
  if (v === "todos") return "";   // usuário: os detalhes aparecem quando clica no agente
  const solic = TODOS.filter(it => it.tipo === "form" && doAgente(agentesDo(it), v)).length;
  const meus = temCx ? emailsDa("entrada", v) : [], urg = temCx ? emailsDa("urgencia", v).length : 0;
  const naoLidos = meus.filter(e => e.lido === false).length, fmt = x => x.toLocaleString("pt-BR");
  return `<span class="det-quem">Caixa de ${esc(v)}</span>` +
    `<span><b>${fmt(solic)}</b> ${solic === 1 ? "solicitação" : "solicitações"}</span>` +
    `<span><b>${fmt(meus.length)}</b> e-mails na caixa</span><span><b>${fmt(naoLidos)}</b> não lidos</span>` +
    `<span class="${urg ? "urg" : ""}"><b>${fmt(urg)}</b> urgente${urg === 1 ? "" : "s"}</span>`;
}
// Seletor "Caixa de" no topo (Figma aprovado em 14/10/2026): substitui as abas de agente; vale para todas as telas
function resumoCaixa(v) {
  const sol = TODOS.filter(it => it.tipo === "form" && doAgente(agentesDo(it), v));
  const semNf = sol.filter(it => ["na_fila", "aguardando_envio"].includes(it.s.situacao)).length;
  const atras = sol.filter(it => it.s.situacao !== "concluida" && diasDesde(it.s.data) > PRAZO.med).length;
  const emails = typeof emailsDa === "function" ? emailsDa("entrada", v).length : 0;
  return { n: sol.length, semNf, atras, emails };
}
function desenharSeletorCaixa() {
  if (!$("sc-botao")) return;
  const v = escopoAtual(), r = resumoCaixa(v), fmt = x => x.toLocaleString("pt-BR");
  $("sc-nome").textContent = v === "todos" ? "Todos os agentes" : v === st.agente ? `${v} (minha)` : v;
  $("sc-qt").textContent = fmt(r.n);
  const q = semAcentoSC($("sc-busca").value);
  const linha = (valor, nome, sub, n, ok) => {
    if (q && !semAcentoSC(nome + " " + sub).includes(q)) return "";
    return `<button type="button" role="option" class="sc-item ${valor === v ? "ativo" : ""}" aria-selected="${valor === v}" data-escopo="${esc(valor)}">
      <span class="sc-txt"><b>${esc(nome)}</b><small class="${ok ? "ok" : ""}">${esc(sub)}</small></span><span class="sc-n">${fmt(n)}</span></button>`;
  };
  const sub = x => x.n === 0 && x.emails === 0 ? "caixa em dia" : `${fmt(x.semNf)} sem NF · ${fmt(x.atras)} atrasada${x.atras === 1 ? "" : "s"} · ${fmt(x.emails)} e-mail${x.emails === 1 ? "" : "s"}`;
  const meu = st.agente && agentesEquipe().includes(st.agente) ? st.agente : "";
  const atalhos = (meu ? linha(meu, "Minha caixa", `${meu} · ${sub(resumoCaixa(meu))}`, resumoCaixa(meu).n) : "") +
    linha("todos", "Todos os agentes", "toda a equipe", resumoCaixa("todos").n);
  const equipe = agentesEquipe().map(a => { const x = resumoCaixa(a); return linha(a, a, sub(x), x.n, x.n === 0 && x.emails === 0); }).join("");
  $("sc-itens").innerHTML = (atalhos ? `<div class="sc-grupo">Atalhos</div>${atalhos}` : "") +
    (equipe ? `<div class="sc-grupo">Equipe Fiscal</div>${equipe}` : "") ||
    `<div class="sc-vazio">Ninguém com “${esc($("sc-busca").value)}”</div>`;
}
const semAcentoSC = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
function abrirSeletorCaixa(abrir) {
  const lista = $("sc-lista"), aberto = abrir ?? lista.classList.contains("oculta");
  lista.classList.toggle("oculta", !aberto);
  $("sc-botao").setAttribute("aria-expanded", aberto);
  if (aberto) { $("sc-busca").value = ""; desenharSeletorCaixa(); setTimeout(() => $("sc-busca").focus(), 20); }
}
document.addEventListener("click", e => {
  if (e.target.closest("#sc-botao")) { abrirSeletorCaixa(); return; }
  if (e.target.closest("#sc-lista [data-escopo]")) { abrirSeletorCaixa(false); setTimeout(desenharSeletorCaixa, 0); return; }
  if (!e.target.closest("#seletor-caixa")) abrirSeletorCaixa(false);
});
document.addEventListener("input", e => { if (e.target.id === "sc-busca") desenharSeletorCaixa(); });
document.addEventListener("keydown", e => {
  if (e.target.id !== "sc-busca") return;
  if (e.key === "Escape") { e.stopPropagation(); abrirSeletorCaixa(false); $("sc-botao").focus(); }
  if (e.key === "Enter") { e.preventDefault(); $("sc-itens").querySelector("[data-escopo]")?.click(); }
});
function desenharAbasNotas() {
  desenharSeletorCaixa();
  if (!$("op-cartoes-notas")) return;
  $("op-cartoes-notas").innerHTML = segOperadores(v => TODOS.filter(it => it.tipo === "form" && doAgente(agentesDo(it), v)).length);
  $("det-op-notas").innerHTML = detalheOperador();
}
function desenharLateral() {   // como o Outlook: o número é de solicitações não lidas na Caixa de Entrada
  const n = TODOS.filter(it => it.tipo === "form" && !it.s.na_caixa?.lido && doAgente(agentesDo(it))).length;
  $("nav-notas-n").textContent = n ? n.toLocaleString("pt-BR") : "";
  $("nav-notas-n").title = "Solicitações não lidas na Caixa de Entrada";
}

const HISTORICO = ["concluida"];   // o que já terminou fica discreto, ao lado da fila
const conta = (ign, f, busca) => TODOS.reduce((n, it) => n + (passa(it, ign, busca) && f(it) ? 1 : 0), 0);
function situacoesDaAba(busca) {
  if (origem === "email") return SIT_EMAIL.map(([f, nome, cor]) => [f, nome, cor, conta("sit", it => passaSit(it, f), busca)]);
  // repaginação v2 (usuário, 14/10/2026): todo e-mail já é pedido de NF; os filtros são só o que ajuda a agir
  const base = [["todas", "Todos", "var(--verde)"], ["urgentes", "Urgentes", "var(--erro)"], ["falta_dado", "Falta dado", "var(--atencao)"],
    ["dividida", "Nota dividida", "var(--info)"], ["doc_diferente", "CPF/CNPJ diferente", "var(--erro)"],
    ["envio_pendente", "NF pronta, falta enviar", "var(--atencao)"], ["concluida", "NF enviada", COR_SIT.concluida], ["minhas", "Minhas", "var(--roxo)"]];
  return base.map(([f, nome, cor]) => [f, nome, cor, conta("sit", it => passaSit(it, f), busca)])
    .filter(([f, , , n]) => n || f === filtro || f === "todas");   // o que é zero some (usuário, 09/10/2026)
}

const MAIS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>';
const ICONE_FILTRO = { hotel: "i-hotel", agente: "i-gente", periodo: "i-cal", envio: "i-mail" };
const icF = campo => `<svg class="ic"><use href="#${ICONE_FILTRO[campo] || "i-busca"}"/></svg>`;
const SETA_F = '<svg class="seta-f"><use href="#i-seta"/></svg>';

function desenharFiltros(busca, total) {
  desenharAbasNotas();
  $("mesa").classList.toggle("um-op", escopoAtual() !== "todos");   // um agente escolhido: a coluna Operador só repetiria o nome
  // resumo de 1 linha (do operador escolhido)
  const minhas = TODOS.filter(it => it.tipo === "form" && doAgente(agentesDo(it)));
  const semNf = minhas.filter(it => ["na_fila", "aguardando_envio"].includes(it.s.situacao)).length;
  const atrasadas = minhas.filter(it => it.s.situacao !== "concluida" && diasDesde(it.s.data) > PRAZO.med).length;
  const quem = escopoAtual() === "todos" ? "nas caixas dos 4 PCs" : "na caixa de " + escopoAtual();
  $("notas-resumo").innerHTML = `<b>${minhas.length}</b> ${minhas.length === 1 ? "solicitação" : "solicitações"} ${esc(quem)} · <b>${semNf}</b> sem NF` +
    (atrasadas ? ` · <span class="ruim">${atrasadas} atrasada${atrasadas > 1 ? "s" : ""} (+7 dias)</span>` : "");
  $("abas-origem").innerHTML = ORIGENS.map(([o, nome]) =>
    `<button class="aba-o" role="tab" data-aba-o="${o}" aria-selected="${origem === o}">${nome}<span class="cnt">${
      conta("origem|sit", it => it.tipo === o, busca).toLocaleString("pt-BR")}</span></button>`).join("");
  const atual = origem === "form" ? filtro : filtroEmail;
  const todas = situacoesDaAba(busca);
  const semEspelho = Object.entries(st.caixa_pcs || {}).filter(([, p]) => !p.espelho).map(([pc, p]) => p.agente || pc);
  const desligados = Object.entries(st.caixa_pcs || {}).filter(([, p]) => p.espelho && !p.online).map(([pc, p]) => `${p.agente || pc} (de ${quando(p.atualizado).slice(-11)})`);
  $("notas-avisos").innerHTML = (semEspelho.length ? `<div class="aviso-linha">${esc(semEspelho.join(", "))} ainda sem a versão nova: as solicitações ${semEspelho.length > 1 ? "deles" : "dele"} aparecem quando o PC atualizar.</div>` : "") +
    (desligados.length ? `<div class="aviso-linha">PC desligado: ${esc(desligados.join(", "))} — mostrando a caixa como estava.</div>` : "");
  // Situação e Hotel: a peça única do Filtro (pecas/filtro.js), igual à caixa de entrada (usuário, 20/10/2026)
  const porF = Object.fromEntries(todas.map(x => [x[0], x]));
  const TOPO = ["todas", "todos", "minhas"], AGIR = ["urgentes", "atrasadas", "falta_dado", "doc_diferente", "dividida", "envio_pendente"];
  const grupos = [TOPO.filter(f => porF[f]),
    [...AGIR.filter(f => porF[f]), ...todas.map(x => x[0]).filter(f => !TOPO.includes(f) && !AGIR.includes(f) && !HISTORICO.includes(f))],
    HISTORICO.filter(f => porF[f])].filter(g => g.length);
  const padraoSit = origem === "form" ? "todas" : "todos";
  $("status-cards").innerHTML = pecaFiltro({ id: "nf-situacao", rotulo: "Situação", valor: atual === "aberto" ? padraoSit : atual, padrao: padraoSit,
    nomePadrao: "Todas", opcoes: grupos.flatMap((g, gi) => g.map((f, i) => ({ v: f, nome: ["todas", "todos"].includes(f) ? "Todas as solicitações" : porF[f][1],
      n: porF[f][3], sep: gi > 0 && i === 0, classe: ["atrasadas", "doc_diferente"].includes(f) && porF[f][3] ? "r" : "" }))) });
  const algum = FH.sel.size || agenteF;
  fhAtualizarContagem();
  $("filtros-linha").innerHTML = fhHtml() +
    (algum ? `<button class="fp-limpar" data-limpa="tudo">Limpar filtros</button>` : "") +
    (busca ? `<span class="aviso-busca">Buscando em toda a aba: situação e filtros não valem enquanto pesquisa</span>` : "") +
    `<span class="resultado">${total.toLocaleString("pt-BR")} ${total === 1 ? "resultado" : "resultados"}</span>`;
  $("notas-cab").classList.toggle("buscando", !!busca);
}

registrarFiltro("nf-situacao", { escolher: v => { if (origem === "form") filtro = v; else filtroEmail = v; ordem = ""; pagina = 0; guardarCaixa(); desenhar(); },
                                 redesenhar: () => desenhar() });
fhOuvir(() => { pagina = 0; if (typeof pn !== "undefined" && pn.vista === "fila") desenhar(); });   // Notas fiscais: vários hotéis (pecas/filtro_hoteis.js)

// Visão geral e outros atalhos abrem a tela de notas já filtrada
function abrirNotas({ filtro: f = "aberto", agente = "", origem: o = "form" } = {}) {
  origem = o; if (o === "form") filtro = f; else filtroEmail = f;
  agenteF = ""; if (agente) escopo = agente; FH.sel = new Set(); envio = "todos"; pagina = 0; sel = null; emailSel = null;
  $("busca").value = ""; guardarCaixa(); trocarVista("fila");
}

// Filtro de uma situação só: a coluna não repete a etiqueta, mostra quem está cuidando
const visaoMista = () => origem === "email" ? filtroEmail === "todos"
  : ["aberto", "todas", "minhas", "envio_pendente", "atrasadas", "doc_diferente"].includes(filtro);
function linhaHtml(it) {
  if (it.tipo === "form") {
    const s = it.s;
    // colunas alinhadas (design fiscal, 11/10/2026): hóspede · hotel · operador · situação · prazo · chegou
    const alerta = s.alerta_doc?.length || s.falta_nota || s.sem_formulario;
    const naoLido = s.na_caixa && !s.na_caixa.lido;
    return `<div class="linha nf-l col ${sel === s.chave ? "sel" : ""} ${naoLido ? "nao-lido" : ""}" role="option" tabindex="0" data-k="${esc(s.chave)}"
        title="${alerta ? "Tem um aviso: abra pra ver" : ""}">
      <span class="c-nome">${esc(s.nome)}${alerta ? `<span class="c-aviso" aria-label="tem aviso">●</span>` : ""}</span>
      <span class="c-hotel">${esc(s.hotel)}</span>
      <span class="c-op">${esc(agentesDo(it)[0] || "")}</span>
      <span class="c-sit tags-nf">${tagsPedido(s)}</span>
      <span class="c-prazo">${s.prazo ? prazoHtml(s.prazo) : `<span class="prazo fim">—</span>`}</span>
      <span class="c-hora">${chegou(it.quando)}</span>${naoLido ? `<span class="so-leitor">não lido</span>` : ""}</div>`;
  }
  const m = it.m;
  return `<div class="linha ${emailSel === m.id ? "sel" : ""}" role="option" tabindex="0" data-em="${esc(m.id)}">
    <span class="quem-linha"><b>${esc(m.nome || m.de)}${m.falta_nota ? pecaAlerta("nao_recebeu", { titulo: m.falta_nota }) : ""}${tagQuartos(m)}${m.anexos.length ? `<span class="tag">${m.anexos.length} anexo${m.anexos.length > 1 ? "s" : ""}</span>` : ""}${m.solicitacao ? '<span class="tag nf-ok">tem pedido</span>' : ""}</b>
      <small>${esc(m.assunto || "(sem assunto)")}</small></span>
    ${esperaHtml(it)}<span class="col-hotel">${esc(m.hotel)}<small>${m.pc_online ? "PC de " + esc(m.agente_pc || m.pc) : '<span class="erro-txt">PC desligado</span>'}</small></span>
    <span class="hora col-chegou">${chegou(it.quando)}</span>
    <span>${m.notas?.length ? pecaSituacao("pronta", { texto: "NF pronta, falta enviar · " + m.notas.map(n => n.nf).join(", "), titulo: m.notas.map(n => n.nome).join(" · ") })
      : pecaSituacao("sem_nf")}</span></div>`;
}

function desenhar(){
  const busca = $("busca").value.trim();
  desenharLateral();
  let lista = TODOS.filter(it => passa(it, "", busca));
  // o mais recente primeiro (usuário, 09/10/2026); "Prazo" vira pro mais atrasado primeiro
  const ord = ordem || "recente";
  if (ord === "antigo") lista = lista.slice().reverse();
  lista = fhAgrupar(lista, it => it.hoteis);   // prioridade do hotel primeiro (alta antes de baixa); a data segue a ordem escolhida acima
  const seta = o => ord === o ? (o === "antigo" ? " ↓" : " ↓") : "";
  $("linhas-cab").className = "nf-cab";
  $("linhas-cab").innerHTML = `<span class="c-nome">Hóspede</span><span class="c-hotel">Hotel</span><span class="c-op">Operador</span>
    <span class="c-sit">Avisos</span><span class="c-prazo">Prazo</span>
    <button class="ord c-hora" data-ordem="${ord === "recente" ? "antigo" : "recente"}" title="Inverter a ordem" style="justify-self:end;border:0;background:none;padding:0">Chegou ${ord === "recente" ? "↓" : "↑"}</button>`;
  desenharFiltros(busca, lista.length);
  const aviso = `${lista.length.toLocaleString("pt-BR")} ${lista.length === 1 ? "resultado" : "resultados"}`;
  if ($("anuncio").textContent !== aviso) $("anuncio").textContent = aviso;
  const paginas = Math.max(1, Math.ceil(lista.length / POR_PAGINA));
  pagina = Math.min(pagina, paginas - 1);
  $("titulo-caixa").textContent = busca ? `Busca: “${busca}”` : "Notas fiscais";
  $("titulo-n").textContent = "";
  const p = periodo === "0" ? "" : ` dos últimos ${periodo} dias`;
  $("lista").innerHTML = lista.length ? lista.slice(pagina * POR_PAGINA, (pagina + 1) * POR_PAGINA).map(linhaHtml).join("")
    : busca ? `<div class="vazio">Nada com “${esc(busca)}” ${origem === "form" ? "nos formulários" + (periodo === "0" ? "" : " carregados") : "nos e-mails sem resposta"}.<br>
        Veja a outra aba${origem === "email" ? "; e-mail já respondido só aparece no Outlook" : ""}.</div>`
    : filtro === "todas" && !FH.sel.size ? caixaEmDia(escopoAtual() === "todos"
      ? "Nenhuma solicitação na Caixa de Entrada dos 4 PCs." : `Nenhuma solicitação na Caixa de Entrada de ${escopoAtual()}.`)
    : `<div class="vazio">Nada com esses filtros.<br>Escolha outra situação ou tire um filtro.</div>`;
  const de = lista.length ? pagina * POR_PAGINA + 1 : 0, ate = Math.min(lista.length, (pagina + 1) * POR_PAGINA);
  $("pag-txt").textContent = `Mostrando ${de.toLocaleString("pt-BR")}–${ate.toLocaleString("pt-BR")} de ${lista.length.toLocaleString("pt-BR")}` +
    (busca ? " · busca na aba inteira" : FH.sel.size ? " · " + (FH.sel.size === 1 ? [...FH.sel][0] : FH.sel.size + " hotéis") : agenteF ? " · hotéis de " + agenteF : "");
  // páginas: primeira, vizinhas da atual e última
  const nums = [...new Set([0, pagina - 1, pagina, pagina + 1, paginas - 1])].filter(p => p >= 0 && p < paginas).sort((a, b) => a - b);
  $("pags").innerHTML = paginas < 2 ? "" : nums.map((p, i) => (i && p - nums[i - 1] > 1 ? `<span style="align-self:center">…</span>` : "") +
    `<button data-pag="${p}" aria-current="${p === pagina}">${p + 1}</button>`).join("");
  desenharDetalhe();
}

function desenharDetalhe() {
  const s = sel && acharPedido(sel), e = emailSel && st.emails.find(x => x.id === emailSel);
  const ol = !!document.querySelector(".app.modo-ol");   // igual à caixa de entrada: a ficha fica sempre à direita (17/10/2026)
  $("mesa").classList.toggle("com-leitura", !!(s || e) || ol);
  $("detalhe").classList.toggle("oculta", !(s || e) && !ol);
  if (e) return desenharDetalheEmail(e);
  if (!s) { $("detalhe").dataset.k = ""; $("detalhe").innerHTML = ol ? `<div class="ol-vazio"><svg aria-hidden="true"><use href="#i-nf"/></svg>
    <b>Selecione uma solicitação para abrir a ficha</b><span>Clique numa linha da lista · as setas ↑ ↓ andam pelas solicitações</span></div>` : ""; return; }
  if (typeof envNF !== "undefined" && envNF && envNF.alvo === $("detalhe")) return;   // escrevendo o e-mail da NF: não apaga
  // não redesenha enquanto alguém digita no painel de leitura (a lista atualiza sozinha a cada 15 s)
  const foco = document.activeElement;
  if (foco && $("detalhe").contains(foco) && /INPUT|TEXTAREA/.test(foco.tagName) && $("detalhe").dataset.k === s.chave) return;
  $("detalhe").dataset.k = s.chave;
  const meu = s.dono === st.agente, livre = !s.dono;
  const hist = s.historico.slice().reverse();
  $("detalhe").innerHTML = `
    <div class="acoes">
      <button class="prim" data-envnf="${esc(s.chave)}"><svg class="ic"><use href="#i-enviar"/></svg>Enviar NF</button>
      ${livre ? `<button data-a="ASSUMIR"><svg class="ic"><use href="#i-mao"/></svg>Assumir</button>` : ""}
      ${meu ? `<button data-a="LIBERAR">Liberar</button>` : ""}
      ${!livre && !meu ? `<button class="perigo" data-a="LIBERAR" data-v="forcar" title="Tira de ${esc(s.dono)}">Liberar à força</button>` : ""}
      <button data-pedir-dados="${esc(s.chave)}" class="${faltaDados(s).length ? "dest" : ""}" title="Novo e-mail ao hóspede, da caixa do hotel, pedindo só o que falta">Pedir o que falta</button>
      <button data-copiar="1"><svg class="ic"><use href="#i-copiar"/></svg>Copiar dados</button>
      <button data-a="DIVIDIDA" data-v="${s.dividida ? "nao" : "sim"}">${s.dividida ? "Não é dividida" : "Nota dividida"}</button>
      <button class="fechar" id="d-fechar" aria-label="Fechar leitura">×</button></div>
    <header class="cab-msg"><h2>${esc(s.nome)}</h2>
      <div class="remet"><div class="avatar">${esc((s.nome || "?").trim().charAt(0).toUpperCase())}</div><b>Solicitação pelo formulário · ${esc(s.hotel)}</b>
        <span class="quando">${esc(fmtCarimbo(s))}<br><span class="dado">linha ${s.linha}</span></span>
        <span class="de">&lt;${esc(s.email)}&gt;</span></div>
      <div class="etiquetas">${etiquetasDoPedido(s)}
        ${s.prazo ? prazoHtml(s.prazo) : ""}
        ${s.dono ? `<span class="etq">Com ${esc(s.dono)} desde ${quando(s.dono_desde)}</span>` : ""}
        ${s.dividida ? tagDivisao(s) : tagNotaUnica(s)}
        ${s.enviado ? "" : `<span class="etq ruim">E-mail ao hotel não enviado</span>`}</div></header>
    <div class="corpo-msg">${faltaBanner(s)}${fichaResumoHtml(s)}${quadrosEtapa2(s)}${quadroFalta(s.falta_nota)}
      <details class="ficha-form orig" data-dobra="form" ${DOBRA.form ? "open" : ""}><summary>Dúvida no que o hóspede digitou? <u>Ver respostas originais do formulário</u> <span class="dica">${dataBr(s.data)}</span></summary>
        <dl><dt>E-mail do hóspede</dt><dd>${esc(s.email)}</dd>${s.campos.map(c =>
          `<dt>${esc(c[0])}</dt><dd class="${/\d{3}[.\/-]\d/.test(c[1]) ? "dado" : ""}">${esc(c[1])}</dd>`).join("")}</dl></details>
      <section class="ficha ficha-nf"><div class="ficha-tit"><span class="rot">Nota fiscal ${s.partes > 1 || s.dividida ? `· dividida em ${Math.max(s.partes, 2)}` : ""}</span></div>
        <div class="ficha-corpo">
          ${s.nfs.length ? `<div class="etiquetas">${s.nfs.map(n => `<span class="nf-num">NF ${esc(n)}${s.nfs_conferente.includes(n) ? " · conferente"
            : ` <a href="#" data-desfaz="${esc(n)}" title="Desfazer">×</a>`}</span>`).join("")}</div>` : `<span class="dica">Nenhuma NF ainda.</span>`}
          ${s.nfs.length ? (s.envio_pendente
            ? `<div class="envio pend" style="font-size:11.5px">Envio pendente: a nota existe, mas nenhum e-mail com o PDF saiu para ${esc(s.email)}</div>`
            : s.envios?.length ? s.envios.map(v => `<div class="envio ok" style="font-size:11.5px">✓ ${esc(textoEnvio(v))}</div>`).join("")
            : `<span class="dica">Envio por e-mail não registrado (pedido de mais de 14 dias)</span>`) : ""}
          <div class="linha-form"><input id="d-nf" placeholder="Número da NF emitida" inputmode="numeric"><button class="prim" id="d-nf-ok">Marcar NF</button></div>
        </div></section>
      ${noOutlookHtml(s)}
      <details class="ficha ficha-trat dobra" data-dobra="trat" ${DOBRA.trat ? "open" : ""}><summary class="ficha-tit"><span class="rot">Anotar / registrar tratativa</span><span class="dica">clique pra abrir</span></summary>
        <div class="ficha-corpo"><textarea id="d-txt" placeholder="Ex.: pedi o CNPJ correto por e-mail"></textarea>
          <div class="linha-form" style="justify-content:flex-end"><button data-txt="OBS">Anotar</button><button class="creme" data-txt="TRATATIVA">Registrar tratativa</button></div></div></details>
      <details class="ficha dobra" data-dobra="hist" ${DOBRA.hist ? "open" : ""}><summary class="ficha-tit"><span class="rot">Histórico · ${hist.length}</span><span class="dica">quem fez o quê</span></summary>
        <div class="ficha-corpo">${hist.length ? `<div class="historico">${hist.map(h => `<div class="passo-h"><span class="dado">${quando(h.quando)}</span><b>${esc(h.agente)}</b> ${esc(rotulo(h))}</div>`).join("")}</div>`
          : `<span class="dica">Sem ações ainda.</span>`}</div></details>
    </div>`;
}

// Ficha-resumo (desenho aprovado no Figma, 14/10/2026): tudo que precisa pra emitir, sem rolar. O que falta fica em âmbar.
function fichaResumoHtml(s) {
  const semAc = x => String(x || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const campo = (...testes) => { const c = (s.campos || []).find(([k]) => testes.some(r => r.test(semAc(k)))); return c ? String(c[1]).trim() : ""; };
  const nomeTom = campo(/nome.*tomador/, /razao social/, /^nome( completo)?$/);
  const docTom = campo(/documento.*tomador/, /cpf.*cnpj|cnpj.*cpf/, /^cnpj/, /^cpf(?!.*titular)/);
  const cep = campo(/\bcep\b/), endereco = campo(/endereco/), fone = campo(/telefone|celular|whats/);
  const titular = campo(/nome.*titular/), cpfTit = campo(/cpf.*titular/);
  const entrada = campo(/check.?in|data de entrada|entrada/), saida = campo(/check.?out|data de saida|saida/);
  const info = campo(/informac/, /observac/), dividida = campo(/dividid/);
  const val = (v, dado) => v ? `<dd class="${dado ? "dado" : ""}">${esc(v)}</dd>` : `<dd class="falta">falta pedir</dd>`;
  const opc = (v, dado) => v ? `<dd class="${dado ? "dado" : ""}">${esc(v)}</dd>` : `<dd class="vazio-fr">—</dd>`;
  const hist = (s.historico || []).slice(-3).reverse();
  const sit = nomeSituacao(s);
  return `<section class="ficha-resumo" aria-label="Resumo do pedido">
    <div class="fr-grade">
      <div class="fr-bloco"><h4>Tomador da nota</h4><dl>
        <dt>Nome</dt>${val(nomeTom)}<dt>CPF/CNPJ</dt>${val(docTom && fmtDoc(docTom), true)}<dt>CEP</dt>${val(cep && fmtCep(cep), true)}
        ${endereco ? `<dt>Endereço</dt><dd>${esc(endereco)}</dd>` : ""}<dt>Telefone</dt>${opc(fone, true)}</dl></div>
      <div class="fr-bloco"><h4>Estadia</h4><dl>
        <dt>Hotel</dt><dd>${esc(s.hotel)}</dd><dt>Titular</dt>${opc(titular)}${cpfTit ? `<dt>CPF titular</dt><dd class="dado">${esc(fmtDoc(cpfTit))}</dd>` : ""}
        <dt>Datas</dt>${entrada || saida ? `<dd class="dado">${esc(entrada || "?")} → ${esc(saida || "?")}</dd>` : `<dd class="falta">falta pedir</dd>`}</dl></div>
      <div class="fr-bloco"><h4>Como quer a nota</h4><dl>
        <dt>Pedido</dt>${opc(info)}<dt>Dividida</dt><dd>${s.dividida ? `sim${s.partes > 1 ? ` · ${s.partes} notas` : ""}` : esc(dividida || "não")}</dd>
        <dt>Enviar para</dt><dd>${esc(s.email || "")}</dd></dl></div>
      <div class="fr-bloco"><h4>Situação e histórico</h4><dl>
        <dt>Situação</dt><dd>${esc(sit)}</dd><dt>Prazo</dt><dd>${s.prazo ? prazoHtml(s.prazo) : "—"}</dd>
        ${hist.length ? hist.map(h => `<dt class="dado">${esc(quando(h.quando))}</dt><dd>${esc(h.agente)} · ${esc(rotulo(h))}</dd>`).join("") : `<dt>Ações</dt><dd class="vazio-fr">nenhuma ainda</dd>`}</dl></div>
    </div></section>`;
}
// "Pedir dados": Novo e-mail ao hóspede, da caixa do hotel, com a solicitação de dados (assunto combina)
document.addEventListener("click", e => {
  const b = e.target.closest("[data-pedir-dados]");
  if (!b) return;
  const s = acharPedido(b.dataset.pedirDados);
  if (s) abrirEnvioNF(null, { novo: true, para: s.email, conta: s.na_caixa?.caixa || "", solicitar: true, faltas: [...faltaDados(s), ...faltaExtras(s)] });
});

// Etapa 2: CPF/CNPJ da NF diferente do pedido, pedido repetido e os outros pedidos do mesmo hóspede (e-mail ou CPF/CNPJ)
const linhaPedido = o => `<div class="outro-ped" data-k="${esc(o.chave)}" role="button" tabindex="0"><span class="dado">${dataBr(o.data)} ${esc(horaDoCarimbo(o.carimbo))}</span>
  <span>${esc(o.hotel)} · ${esc(o.nome)}${o.email ? ` <span class="dado">&lt;${esc(o.email)}&gt;</span>` : ""}</span>
  <span>${pecaSituacao(situacaoDoPedido(o), { texto: nomeSituacao(o) })}</span></div>`;
function caixaEmDia(texto) {
  return `<div class="vazio feliz"><b>Nada pendente</b><span>${esc(texto)}</span></div>`;
}
// seções que abrem e fecham (Anotar, Histórico): ficam como você deixou, mesmo com a lista atualizando a cada 15 s
const DOBRA = { trat: false, hist: false, form: false };
document.addEventListener("toggle", e => { const d = e.target; if (d.dataset?.dobra) DOBRA[d.dataset.dobra] = d.open; }, true);
function noOutlookHtml(s) {
  const c = s.na_caixa;
  if (!c) return `<div class="no-outlook"><span>Esta solicitação <b>não está</b> na Caixa de Entrada de nenhum PC (já foi tratada no Outlook).</span></div>`;
  return (s.sem_formulario ? `<div class="quadro-e2 atencao"><b>Formulário não achado na planilha</b><div>A solicitação está no Outlook, mas não achei a linha do formulário dela. Abra o e-mail no Outlook pra ver os dados.</div></div>` : "") +
    `<div class="no-outlook"><span>No Outlook: <b>Caixa de Entrada</b> de ${esc(c.caixa)}</span><span>PC de <b>${esc(nomePc(c.pc))}</b></span>
      <span>chegou ${esc(quando(c.recebido))}</span><span>${c.lido ? "lida" : "<b>não lida</b>"}</span>${c.emails > 1 ? `<span>${c.emails} e-mails do robô com este pedido</span>` : ""}</div>`;
}
function quadrosEtapa2(s) {
  let h = "";
  for (const a of s.alerta_doc || []) h += `<div class="quadro-e2 erro" role="alert"><b>⚠ NF ${esc(a.nf)}: CPF/CNPJ diferente do pedido</b>
    <div>${esc(a.texto)}</div><div class="dica">O robô abriu a nota e comparou com o formulário. Confira antes de enviar ao hóspede (ou refaça a NF).</div>
    <div class="acoes-q"><button data-doc-ok="${esc(a.nf)}">Está certo (o hóspede pediu assim)</button></div></div>`;
  for (const a of s.aviso_doc || []) h += `<div class="quadro-e2"><b>CPF/CNPJ do formulário digitado errado</b><div>NF ${esc(a.nf)}: ${esc(a.texto)}</div>
    <div class="dica">O documento do formulário não passa no dígito verificador; o da nota passa. A NF provavelmente saiu certa.</div></div>`;
  if (s.repetido_de) {
    const p = acharPedido(s.repetido_de);
    h += `<div class="quadro-e2 atencao"><b>Pedido repetido</b><div>O hóspede mandou este mesmo formulário de novo (mesmo CPF/CNPJ, estadia e valor). Ele conta como 1, junto com o principal:</div>
      ${p ? linhaPedido(p) : ""}</div>`;
  }
  if (s.repetidos?.length) h += `<div class="quadro-e2 atencao"><b>Pedido repetido · ${s.repetidos.length + 1}x</b>
    <div>O hóspede mandou o formulário ${s.repetidos.length + 1} vezes (mesmo CPF/CNPJ, estadia e valor). Conta como 1 pedido: trate só este.</div>
    ${s.repetidos.map(linhaPedido).join("")}</div>`;
  if (s.outros_pedidos?.length) h += `<section class="ficha"><div class="ficha-tit"><span class="rot">Outros pedidos deste hóspede · ${s.outros_total}</span>
    <span class="dica">mesmo e-mail ou mesmo CPF/CNPJ</span></div><div class="ficha-corpo" style="display:grid;gap:6px">${s.outros_pedidos.map(linhaPedido).join("")}
    ${s.outros_total > s.outros_pedidos.length ? `<span class="dica">e mais ${s.outros_total - s.outros_pedidos.length}</span>` : ""}</div></section>`;
  return h;
}

function desenharDetalheEmail(e) {
  $("detalhe").dataset.k = "";
  $("detalhe").innerHTML = `
    <div class="acoes">
      <button class="prim" data-resp-nf="${esc(e.id)}"><svg class="ic"><use href="#i-enviar"/></svg>Responder com a NF</button>
      <button data-resp="${esc(e.id)}"><svg class="ic"><use href="#i-resp"/></svg>Responder</button>
      ${e.solicitacao ? `<button data-ver-pedido="${esc(e.solicitacao.chave)}">Ver pedido do formulário (${dataBr(e.solicitacao.data)})</button>` : ""}
      <button class="fechar" id="d-fechar" aria-label="Fechar leitura">×</button></div>
    <header class="cab-msg"><h2>${esc(e.assunto || "(sem assunto)")}</h2>
      <div class="remet"><div class="avatar">${esc((e.nome || e.de || "?").trim().charAt(0).toUpperCase())}</div><b>${esc(e.nome || e.de)}</b>
        <span class="quando">${chegou(e.recebido) === "Ontem" ? "Ontem" : dataBr(e.recebido.slice(0, 10))}<br><span class="dado">${esc(e.recebido.slice(11, 16))}</span></span>
        <span class="de">&lt;${esc(e.de)}&gt; para ${esc(e.caixa)}</span></div>
      <div class="etiquetas">${e.notas?.length ? `<span class="pilula p-concluida">NF ${esc(e.notas.map(n => n.nf).join(", "))} emitida</span><span class="etq ruim">envio pendente</span>`
        : `<span class="pilula p-sem_resposta">Sem resposta</span>`}<span class="etq">E-mail direto</span>
        <span class="etq">${esc(e.hotel)}</span><span class="etq ${e.pc_online ? "" : "ruim"}">Caixa no PC de ${esc(e.agente_pc || e.pc)}${e.pc_online ? "" : " · desligado: a resposta sai quando ele ligar"}</span></div></header>
    <div class="corpo-msg">${quadroFalta(e.falta_nota)}
      ${e.notas?.length ? `<section class="ficha"><div class="ficha-tit"><span class="rot" style="color:var(--atencao)">NF já emitida · envio pendente</span>
        <span class="pilula p-concluida">NF ${esc(e.notas.map(n => n.nf).join(", "))}</span></div><dl>${e.notas.map(n =>
          `<dt>NF ${esc(n.nf)}</dt><dd>${esc(n.nome)}<div class="dica">salva no Dropbox em ${esc(n.modificado)} · ${esc(n.prova)}</div></dd>`).join("")}</dl></section>` : ""}
      ${e.quartos >= 2 ? `<section class="ficha"><div class="ficha-tit"><span class="rot">Nota dividida · voucher com ${e.quartos} quartos</span>
        <span class="tag">dividida</span></div><dl>${(e.hospedes_quartos.length ? e.hospedes_quartos : Array(e.quartos).fill("(nome não lido)"))
          .map((n, k) => `<dt>Quarto ${k + 1}</dt><dd>${esc(n)}</dd>`).join("")}</dl></section>` : ""}
      <div class="texto-email">${esc(e.texto || "(sem texto)")}</div>
      ${e.anexos.length ? `<div><div class="rot" style="margin-bottom:8px">Anexos</div><div class="anexos">${e.anexos.map(a =>
        `<div class="anexo"><span class="ext">${esc(String(a).split(".").pop().toUpperCase().slice(0, 4))}</span><span>${esc(a)}</span></div>`).join("")}</div></div>` : ""}
    </div>`;
}

function rotulo(h){
  const m = {ASSUMIR:"assumiu", LIBERAR: h.valor === "forcar" ? "liberou à força" : "liberou", NF:"marcou NF " + h.valor,
             DESFAZER_NF:"desfez NF " + h.valor, TRATATIVA:"tratativa: " + h.valor, OBS:"anotou: " + h.valor,
             DIVIDIDA: h.valor === "sim" ? "marcou nota dividida" : "tirou nota dividida"};
  return m[h.acao] || h.acao;
}

const acharPedido = k => st.fila.find(x => x.chave === k) || (st.filaRep || []).find(x => x.chave === k);
async function acao(a, valor){
  const s = acharPedido(sel); if (!s) return;
  document.querySelectorAll("#detalhe button").forEach(b => b.disabled = true);
  const r = await api("/api/acao", {chave: s.chave, acao: a, valor: valor || ""});
  if (r.ok) toast("Feito ✔"); else toast(r.motivo || "Não deu certo", true);
  $("detalhe").dataset.k = "";
  await carregar();
}

const irPraCaixa = () => { if (pn.vista !== "fila") trocarVista("fila"); };
document.addEventListener("click", async e => {
  const t = e.target.closest("[data-ordem],[data-aba-o],[data-st],[data-limpa],[data-pag],[data-k],[data-em],[data-a],[data-txt],[data-desfaz],[data-copiar],[data-resp],[data-resp-nf],[data-ver-pedido],[data-doc-ok],#d-fechar,#d-nf-ok");
  if (!t) return;
  const d = t.dataset;
  if (d.ordem) { ordem = d.ordem; pagina = 0; return desenhar(); }
  if (d.abaO) { origem = d.abaO; pagina = 0; sel = null; emailSel = null; guardarCaixa(); return desenhar(); }
  if (d.st) { if (origem === "form") filtro = d.st; else filtroEmail = d.st; ordem = ""; pagina = 0; guardarCaixa(); return desenhar(); }
  if (d.limpa) {
    if (d.limpa === "hotel" || d.limpa === "tudo") FH.sel = new Set();
    if (d.limpa === "agente" || d.limpa === "tudo") agenteF = "";
    if (d.limpa === "envio" || d.limpa === "tudo") envio = "todos";
    if ((d.limpa === "tudo" || d.limpa === "periodo") && periodo !== "45") { const antes = periodo; periodo = "45"; if (antes === "0") carregar(); }
    pagina = 0; guardarCaixa(); return desenhar();
  }
  if (d.pag) { pagina = Number(d.pag); desenhar(); $("lista").scrollTop = 0; return; }
  if (d.k) { sel = d.k; emailSel = null; return desenhar(); }
  if (d.em) { emailSel = d.em; sel = null; return desenhar(); }
  if (t.id === "d-fechar") { sel = null; emailSel = null; return desenhar(); }
  if (d.resp) return abrirEnvioNF(null, { id: d.resp, comNF: false });
  if (d.respNf) return abrirEnvioNF(null, { id: d.respNf, comNF: true });
  if (d.verPedido) { filtro = "todas"; origem = "form"; FH.sel = new Set(); agenteF = ""; sel = d.verPedido; emailSel = null; irPraCaixa(); return desenhar(); }
  if (d.a) {
    if (d.v === "forcar" && !confirm("Tirar esta solicitação de quem está tratando?")) return;
    return acao(d.a, d.v);
  }
  if (t.id === "d-nf-ok") { const n = $("d-nf").value.trim().replace(/\D/g, ""); if (!n) return toast("Digite o número da NF", true); return acao("NF", n); }
  if (d.docOk) { if (confirm("O CPF/CNPJ da NF " + d.docOk + " está certo? O alerta some pra equipe toda.")) return acao("OBS", `Conferido: CPF/CNPJ da NF ${d.docOk} está certo`); return; }
  if (d.desfaz) { e.preventDefault(); if (confirm("Desfazer a NF " + d.desfaz + "?")) return acao("DESFAZER_NF", d.desfaz); return; }
  if (d.txt) { const v = $("d-txt").value.trim(); if (!v) return toast("Escreva o texto primeiro", true); return acao(d.txt, v); }
  if (d.copiar) {
    const s = acharPedido(sel);
    try { await navigator.clipboard.writeText([`Hotel: ${s.hotel}`, `E-mail: ${s.email}`, ...s.campos.map(c => `${c[0]}: ${c[1]}`)].join("\n")); toast("Dados copiados"); }
    catch (err) { toast("Não consegui copiar", true); }
  }
});
document.addEventListener("keydown", e => {
  const l = e.target.closest?.(".linha");
  if (l && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); l.click(); }
});
$("busca").addEventListener("input", () => {
  // a busca de cima vai sempre direto ao Outlook dos 4 PCs (usuário, 11/10/2026). Só o histórico das últimas 24 h da caixa fica no
  // navegador deste PC (pecas/busca_recente.js, 28/10/2026); nada disso vai ao servidor
  if (pn.vista !== "correio" && $("busca").value.trim().length >= 3) trocarVista("correio");
  if (pn.vista === "correio") return agendarBusca();
  pagina = 0; desenhar();
});
// Tema: segue o Windows (padrão), claro ou escuro — fica guardado neste PC
const TEMAS = [["", "Sistema"], ["light", "Claro"], ["dark", "Escuro"]];
let temaServidor = null;   // o tema guardado neste PC (estado/app.json) vale mais que o do navegador
function aplicarTema(t, guardarNoPc = false) {
  if (guardarNoPc) { temaServidor = t; api("/api/tema", { tema: t }); }
  if (t) document.documentElement.dataset.theme = t; else delete document.documentElement.dataset.theme;
  const nome = (TEMAS.find(x => x[0] === t) || TEMAS[0])[1];
  $("tema-nome").textContent = nome;
  $("btn-tema").setAttribute("aria-label", `Tema: ${nome}. Clique para trocar`);
  try { localStorage.setItem("painel.tema", t); } catch (e) {}
  if (typeof pn !== "undefined" && pn.vista === "visao") desenharVisao();
}
$("btn-tema").addEventListener("click", () => {
  const i = TEMAS.findIndex(x => x[0] === (document.documentElement.dataset.theme || ""));
  aplicarTema(TEMAS[(i + 1) % TEMAS.length][0], true);
  toast("Tema: " + $("tema-nome").textContent);
});
try { aplicarTema(localStorage.getItem("painel.tema") || ""); } catch (e) { aplicarTema(""); }
// Ajuda: o que cada nome significa + atalhos do teclado (botão "?" ou tecla ?)
const GLOSSARIO = [["Sem NF", "var(--erro)", "Pedido que ainda não tem nota fiscal emitida."],
  ["Tratativa", "var(--info)", "Mandamos uma pergunta ao hóspede (ex.: CNPJ certo) e esperamos a resposta."],
  ["NF parcial", "var(--info)", "Nota dividida: parte das notas já saiu, falta o resto."],
  ["Envio pendente", "var(--atencao)", "A nota existe, mas o e-mail com ela ainda não saiu pro hóspede."],
  ["Aguardando envio", "var(--tinta-3)", "O pedido ainda não foi mandado pro hotel pelo robô."],
  ["NF emitida", "var(--ok)", "Nota pronta e enviada. Fica 24 h na lista e some."],
  ["Atrasadas", "var(--erro)", "Pedidos esperando há mais de 7 dias sem nota."],
  ["Urgência", "var(--erro)", "E-mail com pedido de correção/cancelamento de NF ou mais de 7 dias sem resposta."],
  ["Cobrança", "var(--atencao)", "O hóspede diz que ainda não recebeu a nota."],
  ["Nota complementar", "var(--atencao)", "Faltou diária ou consumo na nota: emitir a complementar."],
  ["Dados do tomador", "var(--info)", "O e-mail traz CPF/CNPJ, razão social: dados pra emitir."],
  ["🧾 NF emitida (Outlook)", "var(--ok)", "Etiqueta que o robô põe no e-mail do hóspede quando a nota aparece no Dropbox."]];
const ATALHOS = [["Ctrl+R", "Responder o e-mail aberto"], ["Ctrl+Shift+R", "Responder com a NF"], ["Ctrl+F", "Encaminhar"],
  ["Delete", "Excluir (com confirmação e Desfazer)"], ["Ctrl+Q", "Marcar como lido"], ["Ctrl+U", "Marcar como não lido"],
  ["Ctrl+E", "Ir pra pesquisa"], ["↑ ↓", "E-mail anterior / próximo (já abre)"], ["Esc", "Fechar o e-mail ou a janela"], ["?", "Abrir esta ajuda"]];
function abrirAjuda() {
  if (document.querySelector(".modal-fundo")) return;
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `<div class="modal ajuda"><div class="modal-topo"><div><h3>Ajuda do Painel</h3><div class="sub">O que cada nome significa e os atalhos do teclado (iguais aos do Outlook)</div></div>
      <button class="fechar" id="ajuda-fechar" aria-label="Fechar" style="margin-left:auto">×</button></div>
    <div class="ajuda-corpo"><section><h4>O que significa</h4><dl>${GLOSSARIO.map(([t, c, d]) => `<dt><i style="--cor:${c}"></i>${esc(t)}</dt><dd>${esc(d)}</dd>`).join("")}</dl></section>
      <section><h4>Atalhos do teclado</h4><dl>${ATALHOS.map(([k, d]) => `<dt>${k.split(" ").map(x => `<kbd>${esc(x)}</kbd>`).join(" ")}</dt><dd>${esc(d)}</dd>`).join("")}</dl>
        <p class="dica" style="margin-top:14px">Os atalhos de e-mail valem na tela E-mails, com um e-mail aberto.</p></section></div></div>`;
  document.body.appendChild(fundo);
  $("ajuda-fechar").onclick = () => fundo.remove();
  fundo.addEventListener("click", ev => { if (ev.target === fundo) fundo.remove(); });
}
$("btn-ajuda").addEventListener("click", abrirAjuda);
document.addEventListener("click", e => {
  const b = e.target.closest("[data-escopo]");
  if (!b) return;
  escopo = b.dataset.escopo;
  try { localStorage.setItem("painel.agenteFiltro", escopo); } catch (er) {}
  pagina = 0; desenharLateral(); desenhar(); desenharSeletorCaixa();
  if (typeof desenharCorreio === "function") { desenharLateralCorreio(); desenharCorreio(); }
  if (pn.vista === "visao") desenharVisao();
});

// Seções da lateral abrem/fecham; o estado fica guardado neste PC
const GRUPOS_KEY = "painel.secoesFechadas";
let gruposFechados = [];
try { gruposFechados = JSON.parse(localStorage.getItem(GRUPOS_KEY) || "[]"); } catch (e) {}
document.querySelectorAll(".secao").forEach(g => {
  if (gruposFechados.includes(g.dataset.g)) g.open = false;
  else if (gruposFechados.includes("+" + g.dataset.g)) g.open = true;
  g.addEventListener("toggle", () => {
    gruposFechados = [...document.querySelectorAll(".secao")].map(x => x.open ? "+" + x.dataset.g : x.dataset.g);
    try { localStorage.setItem(GRUPOS_KEY, JSON.stringify(gruposFechados)); } catch (e) {}
  });
});
// Barra de baixo em ícones: o texto da Central vira dica ao passar o mouse (27/10/2026)
new MutationObserver(() => { const s = $("sync-txt").textContent; $("sync").title = s; $("sync").setAttribute("aria-label", s); }).observe($("sync-txt"), { childList: true, characterData: true, subtree: true });
$("btn-atualizar").addEventListener("click", async () => {
  if (typeof enviarReceberTodas === "function") return enviarReceberTodas();   // relê a planilha e pede o Enviar/Receber aos PCs (correio.js)
  $("sync-txt").textContent = "atualizando…"; await api("/api/atualizar", {}); carregar();
});
if (window.cgMiniK) $("btn-mini").appendChild(window.cgMiniK());
// Qualquer ação que passou de 5 s saiu da tela grande: o ⟳ do rodapé mostra o K pequeno enquanto ela segue (carregando.js)
window.addEventListener("painel:espera", e => {
  const b = $("btn-atualizar");
  if (!b || b.classList.contains("rodando") || b.classList.contains("fim-ok") || b.classList.contains("fim-aviso")) return;
  b.classList.toggle("em-espera", e.detail.n > 0);
});
$("btn-enviar").addEventListener("click", () => rbAbrir());   // a janela do robô substitui a de confirmação (22/10/2026)
let focoAntesDaJanela = null;
const focaveis = el => [...el.querySelectorAll('button:not([disabled]),input:not([type="hidden"]):not([hidden]),select,textarea,[contenteditable="true"],a[href],[tabindex="0"]')]
  .filter(x => x.offsetParent !== null);
new MutationObserver(mudancas => mudancas.forEach(m => {
  m.addedNodes.forEach(n => {
    if (!n.classList?.contains("modal-fundo")) return;
    focoAntesDaJanela = document.activeElement;
    const janela = n.querySelector(".modal");
    janela.setAttribute("role", "dialog"); janela.setAttribute("aria-modal", "true"); janela.tabIndex = -1;
    const titulo = janela.querySelector("h3, .compor-topo span");
    if (titulo) { titulo.id ||= "titulo-janela"; janela.setAttribute("aria-labelledby", titulo.id); }
    setTimeout(() => (focaveis(janela).find(x => !x.classList.contains("fechar")) || janela).focus(), 60);
  });
  m.removedNodes.forEach(n => {
    if ((n.classList?.contains("modal-fundo") || n.classList?.contains("janela-saindo")) && focoAntesDaJanela) { try { focoAntesDaJanela.focus(); } catch (e) {} focoAntesDaJanela = null; }
  });
})).observe(document.body, { childList: true });
document.addEventListener("keydown", e => {
  const fundo = document.querySelector(".modal-fundo");
  if (!fundo) return;
  if (e.key === "Escape") { e.preventDefault(); (fundo.querySelector("#env-fechar, #nf-fechar, .fechar"))?.click(); return; }
  if (e.key !== "Tab") return;
  const lista = focaveis(fundo);
  if (!lista.length) return;
  const i = lista.indexOf(document.activeElement);
  if (e.shiftKey && i <= 0) { e.preventDefault(); lista[lista.length - 1].focus(); }
  else if (!e.shiftKey && i === lista.length - 1) { e.preventDefault(); lista[0].focus(); }
});
// Seletor de operador: avatar com cor fixa por pessoa
const COR_OP = {};   // design fiscal (11/10/2026): sem cor por operador — a identificação é pelo nome
const corOp = n => COR_OP[n] || "#5a5a5a";
const inicial = n => (n || "?").trim().charAt(0).toUpperCase();
// Iniciais que não se repetem (22/10/2026): Cristian e Clara viravam os dois "C"; com outro nome de mesma letra, vão 2 letras
const iniciaisOp = (n, todos) => { const a = (n || "?").trim(); return (todos.some(o => o !== n && inicial(o) === inicial(a)) ? a.slice(0, 2) : a.charAt(0)).toUpperCase(); };
const SVG_OK = '<svg class="ok" width="18" height="18" viewBox="0 0 20 20" aria-hidden="true"><path d="M5 10.5l3.2 3L15 6.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const SVG_DESLIGAR = '<svg width="16" height="16" viewBox="0 0 20 20" aria-hidden="true"><path d="M10 3v6.5M5.8 5.8a6 6 0 1 0 8.4 0" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/></svg>';
let opAtual = "", opLista = [];
function desenharOperador(atual, lista, pc) {
  $("op-pc").textContent = pc || "";
  if (atual === opAtual && lista.join() === opLista.join()) return;
  opAtual = atual; opLista = lista.includes(atual) ? lista : [atual, ...lista];
  $("op-nome").textContent = atual;
  $("op-av").textContent = iniciaisOp(atual, opLista);
  $("op-av").style.background = corOp(atual);
  // "Quem está neste PC" (Opção A, 22/10/2026): nome inteiro, quem é você agora e o Fechar separado embaixo
  $("op-menu").innerHTML = `<div class="op-cab"><b>Quem está neste PC</b><small>${esc(pc || "")}</small></div>` + opLista.map(o =>
    `<button class="op-item ${o === atual ? "sel" : ""}" role="option" aria-selected="${o === atual}" data-op="${esc(o)}">
      <span class="av" style="background:${corOp(o)}">${esc(iniciaisOp(o, opLista))}</span>
      <span class="n">${esc(o)}<span class="s">${o === atual ? "você, neste PC" : "trocar para " + esc(o)}</span></span>${o === atual ? SVG_OK : ""}</button>`).join("") +
    (!opLista.includes("João") ? `<div class="op-nota">O usuário João só é usado no PC dele.</div>` : "") +
    (window.pywebview ? `<div class="op-sep"></div><button class="op-item sair" id="op-sair" title="O X só esconde a janela (abre na hora). Isto fecha de verdade.">
      <span class="av">${SVG_DESLIGAR}</span><span class="n">Fechar o Painel<span class="s">o X da janela só esconde</span></span></button>` : "");
}
document.addEventListener("click", e => { if (e.target.closest("#op-sair")) window.pywebview?.api?.sair(); });
window.addEventListener("pywebviewready", () => { opAtual = null; carregar(); });   // o botão "Fechar o Painel" só existe na janela do app
function menuOperador(abrir) {
  const op = $("op"), aberto = abrir ?? !op.classList.contains("aberto");
  op.classList.toggle("aberto", aberto);
  $("op-btn").setAttribute("aria-expanded", aberto);
  if (aberto) {   // ao lado da barra, alinhada pelo pé do avatar (a barra corta o que passa dela: posição fixa)
    const barra = document.querySelector(".lateral").getBoundingClientRect(), b = $("op-btn").getBoundingClientRect(), m = $("op-menu");
    m.style.left = Math.round(barra.right + 10) + "px";
    m.style.bottom = Math.max(8, Math.round(innerHeight - b.bottom)) + "px";
  }
}
$("op-btn").addEventListener("click", e => { e.stopPropagation(); menuOperador(); });
$("op-menu").addEventListener("click", async e => {
  const item = e.target.closest("[data-op]");
  if (!item) return;
  e.stopPropagation();
  const nome = item.dataset.op;
  menuOperador(false);
  if (nome === opAtual) return;
  const r = await api("/api/agente", {nome});
  if (r.ok) { desenharOperador(nome, opLista); toast("Operador: " + nome); carregar(); } else toast(r.motivo, true);
});
document.addEventListener("click", e => { if (!e.target.closest("#op")) menuOperador(false); });
document.addEventListener("keydown", e => {
  if (e.key !== "Escape") return;
  menuOperador(false);
  if (!document.querySelector(".modal-fundo") && (sel || emailSel) && !(typeof envNF !== "undefined" && envNF && envNF.alvo)) { sel = null; emailSel = null; desenhar(); }
});
window.__painelOk = true;
