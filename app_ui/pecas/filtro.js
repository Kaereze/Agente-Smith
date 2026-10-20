// Peça única: pílula "Rótulo: valor ▾" com menu (usuário, 20/10/2026: "o mesmo botão em todas as telas; mudou uma
// vez, muda em todas"). Usada em: caixa de entrada (Filtro, Hotel), Notas fiscais (Situação, Hotel), Monitoramento (PC).
//
// Uso:
//   html = pecaFiltro({ id, rotulo, valor, padrao, nomePadrao, opcoes, busca, placeholder, alinhar })
//   registrarFiltro(id, { escolher: v => ..., redesenhar: () => ... })
//   opcoes: [{ v, nome, n, grupo, sep, classe, bolinha }]  (n: número = contagem, texto = observação;
//            grupo: título antes do 1º item do grupo; sep: linha antes do item; bolinha: "on" | "off")
// A peça guarda só qual menu está aberto e o que foi digitado na busca; o valor escolhido é da tela.
const PF = { aberto: "", busca: {}, regs: {}, digitando: "" };
const pfEsc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const pfSemAcento = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const PF_SETA = '<svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>';

function pecaFiltro({ id, rotulo, valor = "", padrao = "", nomePadrao = "Todos", opcoes = [], busca = false,
                      placeholder = "Buscar…", alinhar = "esquerda" }) {
  const ativo = valor !== padrao && valor !== undefined && valor !== null;
  const atual = opcoes.find(o => o.v === valor);
  const nome = ativo ? (atual?.nome ?? valor) : nomePadrao;
  const aberto = PF.aberto === id;
  let menu = "";
  if (aberto) {
    const termo = busca ? pfSemAcento(PF.busca[id] || "") : "";
    const vistos = termo ? opcoes.filter(o => pfSemAcento(o.nome).includes(termo)) : opcoes;
    let grupo = null;
    const itens = vistos.map((o, i) => {
      let antes = "";
      if (o.grupo !== undefined && o.grupo !== grupo) { grupo = o.grupo; antes = o.grupo ? `<div class="pf-grupo">${pfEsc(o.grupo)}</div>` : ""; }
      else if (o.sep && i > 0 && !termo) antes = "<hr>";
      const n = o.n === undefined || o.n === null ? "" : `<em>${pfEsc(typeof o.n === "number" ? o.n.toLocaleString("pt-BR") : o.n)}</em>`;
      return antes + `<button type="button" role="menuitemradio" aria-checked="${o.v === valor || (!ativo && o.v === padrao)}"
        data-pf-escolher="${pfEsc(id)}" data-v="${pfEsc(o.v)}" class="${pfEsc(o.classe || "")}">${o.bolinha ? `<i class="pc-bol ${o.bolinha === "on" ? "on" : ""}" aria-hidden="true"></i>` : ""}${pfEsc(o.nome)}${n}</button>`;
    }).join("");
    menu = `<div class="ol-filtro-menu pf-menu ${alinhar === "direita" ? "pf-dir" : "pf-esq"}" role="menu" aria-label="${pfEsc(rotulo)}">
      ${busca ? `<input type="search" class="pf-busca" data-pf-busca="${pfEsc(id)}" placeholder="${pfEsc(placeholder)}" value="${pfEsc(PF.busca[id] || "")}" autocomplete="off" aria-label="${pfEsc(placeholder)}">` : ""}
      <div class="pf-lista">${itens || `<div class="pf-vazio">Nada com esse nome</div>`}</div></div>`;
  }
  return `<span class="ol-filtro peca-filtro" data-pf="${pfEsc(id)}"><button type="button" class="ol-filtro-bt ${ativo ? "on" : ""}" data-pf-abrir="${pfEsc(id)}"
      aria-haspopup="menu" aria-expanded="${aberto}">${pfEsc(rotulo)}: <b>${pfEsc(nome)}</b>${PF_SETA}</button>${ativo
    ? `<button type="button" class="ol-filtro-x" data-pf-escolher="${pfEsc(id)}" data-v="${pfEsc(padrao)}" aria-label="Tirar o filtro ${pfEsc(rotulo)}">✕</button>` : ""}${menu}</span>`;
}

function registrarFiltro(id, { escolher, redesenhar }) { PF.regs[id] = { escolher, redesenhar }; }

function pfFechar(voltarFoco = false) {
  const id = PF.aberto;
  if (!id) return;
  PF.aberto = ""; PF.busca[id] = ""; PF.digitando = "";
  PF.regs[id]?.redesenhar?.();
  if (voltarFoco) setTimeout(() => document.querySelector(`[data-pf-abrir="${CSS.escape(id)}"]`)?.focus(), 0);
}
function pfFocarMenu(id) {   // ao abrir: a busca (se tiver) ou o item escolhido, pra dar pra usar só o teclado
  setTimeout(() => {
    const m = document.querySelector(`[data-pf="${CSS.escape(id)}"] .pf-menu`);
    if (!m) return;
    const alvo = m.querySelector(".pf-busca") || m.querySelector('[aria-checked="true"]') || m.querySelector("button");
    alvo?.focus();
  }, 0);
}
function pfFocarBusca(id) {
  const i = document.querySelector(`[data-pf-busca="${CSS.escape(id)}"]`);
  if (i && document.activeElement !== i) { i.focus(); const n = i.value.length; i.setSelectionRange(n, n); }
}

document.addEventListener("click", ev => {
  const abrir = ev.target.closest?.("[data-pf-abrir]"), escolher = ev.target.closest?.("[data-pf-escolher]");
  if (abrir) {
    const id = abrir.dataset.pfAbrir, antes = PF.aberto;
    PF.aberto = antes === id ? "" : id; PF.busca[id] = "";
    if (antes && antes !== id) PF.regs[antes]?.redesenhar?.();
    PF.regs[id]?.redesenhar?.();
    if (PF.aberto) pfFocarMenu(id);
    return;
  }
  if (escolher) {
    const id = escolher.dataset.pfEscolher;
    PF.aberto = ""; PF.busca[id] = ""; PF.digitando = "";
    PF.regs[id]?.escolher?.(escolher.dataset.v);
    return;
  }
  if (PF.aberto && !ev.target.closest?.(".peca-filtro")) pfFechar();   // clicou fora: fecha
});
document.addEventListener("input", ev => {
  const i = ev.target.closest?.("[data-pf-busca]");
  if (!i) return;
  const id = i.dataset.pfBusca;
  PF.busca[id] = i.value; PF.digitando = id;
  PF.regs[id]?.redesenhar?.();
  pfFocarBusca(id);
});
document.addEventListener("keydown", ev => {
  if (!PF.aberto) return;
  const menu = document.querySelector(`[data-pf="${CSS.escape(PF.aberto)}"] .pf-menu`);
  if (ev.key === "Escape") { ev.stopPropagation(); return pfFechar(true); }
  if (!menu || !["ArrowDown", "ArrowUp", "Home", "End"].includes(ev.key)) return;
  const ops = [...menu.querySelectorAll("button")];
  if (!ops.length) return;
  ev.preventDefault();
  const i = ops.indexOf(document.activeElement);
  const prox = ev.key === "Home" ? 0 : ev.key === "End" ? ops.length - 1 : ev.key === "ArrowDown" ? Math.min(ops.length - 1, i + 1) : i - 1;
  if (prox < 0 && menu.querySelector(".pf-busca")) menu.querySelector(".pf-busca").focus(); else ops[Math.max(0, prox)].focus();
}, true);
// A tela se redesenha sozinha (dados novos a cada 15 s): se alguém está digitando na busca, o foco volta pra ela
new MutationObserver(() => { if (PF.digitando && PF.aberto === PF.digitando) pfFocarBusca(PF.digitando); })
  .observe(document.documentElement, { childList: true, subtree: true });
