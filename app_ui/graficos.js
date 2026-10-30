// Gráficos em SVG puro (sem biblioteca): linhas com crosshair e barras horizontais.
// Séries validadas (dataviz) contra os cartões do tema claro (#fffdf8) e do escuro (#112420).
// Texto, grade e fundo vêm dos tokens da página, lidos a cada desenho (o tema segue o Windows).
const VIZ = {
  serie: ["#3987e5", "#d95926"],
  texto: "#16261f", texto2: "#52605a", mudo: "#86918a", grade: "#e3dccb", eixo: "#cbbf9f", fundo: "#fffdf8",
};
function coresDoTema() {
  const css = getComputedStyle(document.documentElement), v = n => css.getPropertyValue(n).trim();
  Object.assign(VIZ, { texto: v("--tinta") || VIZ.texto, texto2: v("--tinta-2") || VIZ.texto2, mudo: v("--tinta-3") || VIZ.mudo,
                       grade: v("--linha") || VIZ.grade, eixo: v("--linha-forte") || VIZ.eixo, fundo: v("--folha") || VIZ.fundo });
}
const NS = "http://www.w3.org/2000/svg";

function svgEl(tag, attrs, pai) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs || {})) el.setAttribute(k, v);
  if (pai) pai.appendChild(el);
  return el;
}

function ticksLimpos(max, n = 4) {
  if (max <= 0) return [0, 1];
  const bruto = max / n, mag = 10 ** Math.floor(Math.log10(bruto));
  const passo = [1, 2, 2.5, 5, 10].map(m => m * mag).find(p => p >= bruto);
  const topo = Math.ceil(max / passo) * passo;
  const t = [];
  for (let v = 0; v <= topo + 1e-9; v += passo) t.push(Math.round(v));
  return t;
}

const fmtN = v => (v ?? 0).toLocaleString("pt-BR");
const ddmm = iso => iso.slice(8, 10) + "/" + iso.slice(5, 7);

function legenda(el, chaves) {
  el.innerHTML = chaves.map((c, ci) =>
    `<span class="viz-leg"><span class="viz-chave" style="background:${VIZ.serie[ci]}"></span>${c.nome}</span>`).join("");
}

// itens: [{rotulo, n}] — uma série só (sem legenda: o título diz o que é)
function graficoBarrasH(el, itens, { aoClicar } = {}) {
  coresDoTema();
  el.innerHTML = "";
  const ctx = document.createElement("canvas").getContext("2d");
  ctx.font = '12px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif';
  const rotuloW = Math.ceil(Math.max(40, ...itens.map(i => ctx.measureText(i.rotulo).width))) + 12;
  const largura = Math.max(280, el.clientWidth || 400), linha = 30;
  const altura = itens.length * linha + 4, w = largura - rotuloW - 48;
  const max = Math.max(1, ...itens.map(i => i.n));
  const svg = svgEl("svg", { width: largura, height: altura, role: "img" }, el);
  itens.forEach((it, k) => {
    const y0 = k * linha + 4, bw = Math.max(it.n ? 4 : 0, (it.n / max) * w), bh = 18;
    const g = svgEl("g", { style: aoClicar ? "cursor:pointer" : "" }, svg);
    svgEl("text", { x: rotuloW - 8, y: y0 + 13, "text-anchor": "end", fill: VIZ.texto2, "font-size": 12 }, g).textContent = it.rotulo;
    if (bw) {
      const r = Math.min(4, bw / 2);
      svgEl("path", { d: `M${rotuloW},${y0} h${bw - r} a${r},${r} 0 0 1 ${r},${r} v${bh - 2 * r} a${r},${r} 0 0 1 -${r},${r} h-${bw - r} z`,
                      fill: it.cor || VIZ.serie[0] }, g);
    }
    svgEl("text", { x: rotuloW + bw + 6, y: y0 + 13, fill: VIZ.texto, "font-size": 12, "font-weight": 600 }, g).textContent = fmtN(it.n);
    svgEl("rect", { x: 0, y: y0 - 4, width: largura, height: linha, fill: "transparent" }, g);
    svgEl("title", {}, g).textContent = `${it.rotulo}: ${fmtN(it.n)}`;
    if (aoClicar) g.addEventListener("click", () => aoClicar(it));
  });
}

// ---------- Empilhados (cores por categoria, validadas no dataviz nos dois temas) ----------
// series: [{k, nome, cor}] em ordem fixa; itens: [{rotulo, partes: {k: n}}]
function legendaCores(el, series) {
  el.innerHTML = series.map(s =>
    `<span class="viz-leg"><span class="viz-quad" style="background:${s.cor}"></span>${s.nome}</span>`).join("");
}

function _dicaEmpilhada(titulo, partes, series) {
  const total = series.reduce((a, s) => a + (partes[s.k] || 0), 0);
  return `<b>${titulo}</b>` + series.filter(s => partes[s.k]).map(s =>
    `<div><span class="viz-quad" style="background:${s.cor}"></span>${s.nome}: <b>${fmtN(partes[s.k])}</b></div>`).join("") +
    `<div class="viz-total">Total: <b>${fmtN(total)}</b></div>`;
}

// Colunas por dia (base no zero; 2px de folga entre as partes)
function graficoColunas(el, itens, series, { altura = 280 } = {}) {
  coresDoTema();
  el.innerHTML = "";
  if (!itens.length) { el.textContent = "Sem pedidos no período."; return; }
  const largura = Math.max(320, el.clientWidth || 600);
  const m = { t: 14, r: 8, b: 28, l: 40 };
  const w = largura - m.l - m.r, h = altura - m.t - m.b;
  const totais = itens.map(it => series.reduce((a, s) => a + (it.partes[s.k] || 0), 0));
  const ticks = ticksLimpos(Math.max(1, ...totais)), topo = ticks[ticks.length - 1];
  const y = v => m.t + h - (v / topo) * h;
  const svg = svgEl("svg", { width: largura, height: altura, role: "img", "aria-label": "Pedidos por dia, por situação" }, el);
  for (const t of ticks) {
    svgEl("line", { x1: m.l, x2: m.l + w, y1: y(t), y2: y(t), stroke: t === 0 ? VIZ.eixo : VIZ.grade, "stroke-width": 1 }, svg);
    svgEl("text", { x: m.l - 8, y: y(t) + 4, "text-anchor": "end", fill: VIZ.mudo, "font-size": 12 }, svg).textContent = fmtN(t);
  }
  const passo = w / itens.length, bw = Math.max(3, Math.min(34, passo * 0.7));
  const cada = Math.max(1, Math.ceil(itens.length / Math.max(2, Math.floor(w / 52))));
  const dica = document.createElement("div");
  dica.className = "viz-dica";
  el.style.position = "relative";
  el.appendChild(dica);
  itens.forEach((it, i) => {
    const x = m.l + i * passo + (passo - bw) / 2;
    const g = svgEl("g", {}, svg);
    let base = 0;
    series.forEach(s => {
      const v = it.partes[s.k] || 0;
      if (!v) return;
      const y1 = y(base + v), alto = y(base) - y1;
      svgEl("rect", { x, y: y1 + (base ? 0 : 0), width: bw, height: Math.max(1, alto - (base + v < totais[i] ? 2 : 0)),
                      rx: 2, fill: s.cor }, g);
      base += v;
    });
    if (i % cada === 0 || i === itens.length - 1)
      svgEl("text", { x: x + bw / 2, y: altura - 8, "text-anchor": "middle", fill: VIZ.mudo, "font-size": 12 }, svg).textContent = it.rotulo;
    const alvo = svgEl("rect", { x: m.l + i * passo, y: m.t, width: passo, height: h, fill: "transparent" }, svg);
    alvo.addEventListener("mouseenter", () => {
      dica.innerHTML = _dicaEmpilhada(it.titulo || it.rotulo, it.partes, series);
      dica.style.display = "block";
      const px = x + bw + 10, cabe = px + dica.offsetWidth < largura;
      dica.style.left = (cabe ? px : x - dica.offsetWidth - 10) + "px";
      dica.style.top = m.t + "px";
      g.setAttribute("opacity", "0.85");
    });
    alvo.addEventListener("mouseleave", () => { dica.style.display = "none"; g.removeAttribute("opacity"); });
  });
}

