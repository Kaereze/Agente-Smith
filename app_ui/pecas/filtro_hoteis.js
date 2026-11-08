// Peça única: filtro de VÁRIOS hotéis + prioridade pela quantidade de e-mails (03/11/2026, pedido do João, prévia aprovada).
// - Marque quantos hotéis quiser. "Meus hotéis" guarda a lista da pessoa NESTE PC (localStorage; nada vai ao Google) e a tela já abre com ela.
// - A prioridade de cada hotel vem da quantidade de e-mails na Caixa de Entrada dele: Alta 10 ou mais, Média de 4 a 9, Baixa de 1 a 3, sem e-mail por último.
// - A lista fica agrupada por prioridade (alta primeiro). Um botão só alterna a data dentro de cada nível: mais antigo primeiro / mais novo primeiro.
// As regras são funções puras (testadas com Node); a tela é desenhada por fhHtml() e os cliques são tratados aqui. Cada tela registra o que
// refazer quando algo muda com fhOuvir(() => ...).
const FH_ALTA = globalThis.aj?.("filtro.prioridade_alta_a_partir_de") ?? 10, FH_MEDIA = globalThis.aj?.("filtro.prioridade_media_a_partir_de") ?? 4;   // e-mails na caixa de entrada do hotel
const FH_PESO = { alta: 0, media: 1, baixa: 2, vazia: 3 };
const FH_ROTULO = { alta: "Alta", media: "Média", baixa: "Baixa", vazia: "Sem e-mail" };
const FH = { sel: new Set(), meus: new Set(), ordem: "antigo", aberto: false, busca: "", digitando: false, contagem: {}, ouvintes: [], hoteis: () => [] };

const fhNivel = n => n >= FH_ALTA ? "alta" : n >= FH_MEDIA ? "media" : n >= 1 ? "baixa" : "vazia";
const fhNomes = h => Array.isArray(h) ? h : String(h || "").split(" / ").map(x => x.trim()).filter(Boolean);
const fhSemAcento = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const fhEsc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

// {hotel: quantos e-mails} de uma lista de e-mails (o campo hotel pode trazer "A / B")
function fhContar(emails) {
  const n = {};
  (emails || []).forEach(e => fhNomes(e.hotel).forEach(h => { n[h] = (n[h] || 0) + 1; }));
  return n;
}
// Sem hotel marcado, passa tudo; com hotéis marcados, passa quem tem algum deles
const fhPassa = hoteis => !FH.sel.size || fhNomes(hoteis).some(h => FH.sel.has(h));
// O melhor nível entre os hotéis do item
function fhNivelDe(hoteis) {
  let melhor = "vazia";
  fhNomes(hoteis).forEach(h => { const k = fhNivel(FH.contagem[h] || 0); if (FH_PESO[k] < FH_PESO[melhor]) melhor = k; });
  return melhor;
}
// Agrupa por nível (alta primeiro) mantendo a ordem em que a lista veio dentro de cada nível
function fhAgrupar(lista, hoteisDe) {
  return lista.map((x, i) => [x, i, FH_PESO[fhNivelDe(hoteisDe(x))]]).sort((a, b) => a[2] - b[2] || a[1] - b[1]).map(t => t[0]);
}
// Data dentro do nível: "antigo" = o mais antigo primeiro, "novo" = o mais novo primeiro
function fhPorData(lista, quandoDe) {
  const d = FH.ordem === "antigo" ? 1 : -1;
  return lista.slice().sort((a, b) => d * String(quandoDe(a) || "").localeCompare(String(quandoDe(b) || "")));
}
function fhContarNiveis(lista, hoteisDe) {
  const n = { alta: 0, media: 0, baixa: 0, vazia: 0 };
  lista.forEach(x => { n[fhNivelDe(hoteisDe(x))]++; });
  return n;
}
function fhHoteisDoNivel(nivel) { return FH.hoteis().filter(h => fhNivel(FH.contagem[h] || 0) === nivel); }
const fhRotuloOrdem = () => FH.ordem === "antigo" ? "mais antigo ↑" : "mais novo ↓";

// ---------- guardado neste PC ----------
function fhGuardar() { try { localStorage.setItem("painel.meusHoteis", JSON.stringify([...FH.meus])); } catch (e) { /* só nesta janela */ } }
function fhGuardarOrdem() { try { localStorage.setItem("painel.ordemData", FH.ordem); } catch (e) { /* só nesta janela */ } }
function fhIniciar() {
  try {
    const m = JSON.parse(localStorage.getItem("painel.meusHoteis") || "null");
    if (Array.isArray(m)) { FH.meus = new Set(m); FH.sel = new Set(m); }   // a tela abre com "Meus hotéis" marcados
    const o = localStorage.getItem("painel.ordemData");
    if (o === "novo" || o === "antigo") FH.ordem = o;
  } catch (e) { /* sem armazenamento: começa sem filtro */ }
}
function fhOuvir(fn) { FH.ouvintes.push(fn); }
function fhMudou() {
  FH.ouvintes.forEach(fn => { try { fn(); } catch (e) { /* a outra tela pode nem estar aberta */ } });
  requestAnimationFrame(fhPosRender);
}

// ---------- tela ----------
const FH_SETA = '<svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';
function fhCorpoHtml() {
  const termo = fhSemAcento(FH.busca.trim());
  let grupo = "";
  const hs = FH.hoteis().slice().sort((a, b) => FH_PESO[fhNivel(FH.contagem[a] || 0)] - FH_PESO[fhNivel(FH.contagem[b] || 0)]
    || (FH.contagem[b] || 0) - (FH.contagem[a] || 0) || a.localeCompare(b, "pt")).filter(h => !termo || fhSemAcento(h).includes(termo));
  return hs.map(h => {
    const n = FH.contagem[h] || 0, k = fhNivel(n);
    const cab = k !== grupo ? (grupo = k, `<div class="fh-grupo">${k === "vazia" ? "Sem e-mail" : "Prioridade " + FH_ROTULO[k].toLowerCase()}</div>`) : "";
    return cab + `<label class="fh-op"><input type="checkbox" data-fh-h="${fhEsc(h)}" ${FH.sel.has(h) ? "checked" : ""}><span class="fh-nome">${fhEsc(h)}</span>`
      + `<span class="fh-pri ${k}">${FH_ROTULO[k]}</span><em>${n.toLocaleString("pt-BR")}</em></label>`;
  }).join("") || `<div class="pf-vazio">Nada com esse nome</div>`;
}
function fhHtml() {
  const n = FH.sel.size, nomes = [...FH.sel];
  const bt = n ? `<b>${fhEsc(nomes[0])}</b>${n > 1 ? ` <span class="fh-mais">+${n - 1}</span>` : ""}` : "<b>Todos</b>";
  const menu = !FH.aberto ? "" : `<div class="ol-filtro-menu pf-menu pf-esq fh-menu" role="menu" aria-label="Hotel">
    <input type="search" class="pf-busca" id="fh-busca" placeholder="Buscar hotel…" value="${fhEsc(FH.busca)}" autocomplete="off" aria-label="Buscar hotel">
    <div class="fh-acoes"><button type="button" data-fh-acao="meus" class="fh-bt-on">Meus hotéis</button><button type="button" data-fh-acao="altas">Só prioridade alta</button>
      <button type="button" data-fh-acao="todos">Todos</button><button type="button" data-fh-acao="limpar">Limpar</button></div>
    <div class="fh-lista" id="fh-lista">${fhCorpoHtml()}</div>
    <div class="fh-rodape"><span>${n ? `${n} selecionado${n > 1 ? "s" : ""}` : "Nenhum selecionado"}</span><button type="button" data-fh-acao="salvar">Salvar como meus hotéis</button></div></div>`;
  return `<span class="ol-filtro peca-filtro fh-wrap" data-fh><button type="button" class="ol-filtro-bt ${n ? "on" : ""}" data-fh-abrir aria-haspopup="menu" aria-expanded="${FH.aberto}">`
    + `Hotel: ${bt}${FH_SETA}</button>${n ? `<button type="button" class="ol-filtro-x" data-fh-acao="limpar" aria-label="Tirar o filtro Hotel">✕</button>` : ""}${menu}</span>`;
}
// Depois de redesenhar a tela com o menu aberto e a pessoa digitando: devolve o foco à busca
function fhPosRender() {
  if (!FH.aberto) return;
  // o menu fica solto na tela (position: fixed), logo abaixo do botão: a coluna estreita da lista não corta mais
  const menu = document.querySelector(".fh-menu"), bt = document.querySelector("[data-fh-abrir]");
  if (menu && bt) {
    const r = bt.getBoundingClientRect();
    menu.style.top = Math.round(r.bottom + 6) + "px";
    menu.style.left = Math.round(Math.max(8, Math.min(r.left, window.innerWidth - 410))) + "px";
  }
  if (!FH.digitando) return;
  const i = document.getElementById("fh-busca");
  if (i) { i.focus(); i.setSelectionRange(i.value.length, i.value.length); }
}
// O botão de ordem (um só): alterna a data entre mais antigo e mais novo
const fhBotaoOrdem = () => `<button type="button" class="ol-ord fh-ordem" data-fh-ordem title="Ordem por data: clique para alternar entre mais antigo e mais novo">Data: ${fhRotuloOrdem()}</button>`;

// ---------- cliques ----------
function fhAcao(a) {
  const conhecidos = new Set(FH.hoteis());
  if (a === "limpar") FH.sel = new Set();
  else if (a === "todos") FH.sel = new Set(conhecidos);
  else if (a === "altas") FH.sel = new Set(fhHoteisDoNivel("alta"));
  else if (a === "meus") FH.sel = new Set([...FH.meus].filter(h => conhecidos.has(h)));
  else if (a === "salvar") { FH.meus = new Set(FH.sel); fhGuardar(); if (typeof toast === "function") toast(FH.meus.size ? `Meus hotéis salvos (${FH.meus.size}) neste PC` : "Lista Meus hotéis esvaziada"); }
  fhMudou();
}
function fhAlternarNivel(nivel) {
  const hs = fhHoteisDoNivel(nivel);
  const igual = hs.length > 0 && FH.sel.size === hs.length && hs.every(h => FH.sel.has(h));
  FH.sel = igual ? new Set() : new Set(hs);
  fhMudou();
}
document.addEventListener("click", e => {
  const abrir = e.target.closest("[data-fh-abrir]"), acao = e.target.closest("[data-fh-acao]"), ordem = e.target.closest("[data-fh-ordem]"), nivel = e.target.closest("[data-fh-nivel]");
  if (abrir) { FH.aberto = !FH.aberto; FH.busca = ""; FH.digitando = false; return fhMudou(); }
  if (acao) return fhAcao(acao.dataset.fhAcao);
  if (ordem) { FH.ordem = FH.ordem === "antigo" ? "novo" : "antigo"; fhGuardarOrdem(); return fhMudou(); }
  if (nivel) return fhAlternarNivel(nivel.dataset.fhNivel);
  if (FH.aberto && !e.target.closest("[data-fh]")) { FH.aberto = false; FH.digitando = false; fhMudou(); }
});
document.addEventListener("change", e => {
  const h = e.target.closest?.("[data-fh-h]");
  if (!h) return;
  if (h.checked) FH.sel.add(h.dataset.fhH); else FH.sel.delete(h.dataset.fhH);
  fhMudou();
});
document.addEventListener("input", e => {
  if (e.target.id !== "fh-busca") return;
  FH.busca = e.target.value; FH.digitando = true;
  const l = document.getElementById("fh-lista");
  if (l) l.innerHTML = fhCorpoHtml();   // só a lista do menu: a tela atrás não precisa refazer a cada letra
});
document.addEventListener("keydown", e => { if (e.key === "Escape" && FH.aberto) { FH.aberto = false; FH.digitando = false; fhMudou(); } });
fhIniciar();
