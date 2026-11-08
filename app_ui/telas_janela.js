// telas_janela.js: parte de telas.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
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
