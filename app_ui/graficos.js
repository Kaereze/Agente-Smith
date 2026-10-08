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

// serie: [{data, ...}], chaves: [{k, nome}] (no máximo 2 — cada uma pega uma cor fixa pela posição)
function graficoLinhas(el, serie, chaves, { altura = 260, notaDoDia } = {}) {
  coresDoTema();
  el.innerHTML = "";
  if (!serie.length) { el.textContent = "Sem dados no período."; return; }
  const largura = Math.max(320, el.clientWidth || 600);
  const m = { t: 14, r: 64, b: 26, l: 42 };
  const w = largura - m.l - m.r, h = altura - m.t - m.b;
  const max = Math.max(1, ...serie.flatMap(p => chaves.map(c => p[c.k] || 0)));
  const ticks = ticksLimpos(max), topo = ticks[ticks.length - 1];
  const x = i => m.l + (serie.length === 1 ? w / 2 : (i * w) / (serie.length - 1));
  const y = v => m.t + h - (v / topo) * h;

  const svg = svgEl("svg", { width: largura, height: altura, role: "img",
                             "aria-label": chaves.map(c => c.nome).join(" e ") + " por dia" }, el);
  for (const t of ticks) {
    svgEl("line", { x1: m.l, x2: m.l + w, y1: y(t), y2: y(t), stroke: t === 0 ? VIZ.eixo : VIZ.grade, "stroke-width": 1 }, svg);
    svgEl("text", { x: m.l - 8, y: y(t) + 4, "text-anchor": "end", fill: VIZ.mudo, "font-size": 12 }, svg).textContent = fmtN(t);
  }
  const passoX = Math.max(1, Math.ceil(serie.length / Math.max(2, Math.floor(w / 56))));
  serie.forEach((p, i) => {
    if (i % passoX === 0 || i === serie.length - 1)
      svgEl("text", { x: x(i), y: altura - 6, "text-anchor": "middle", fill: VIZ.mudo, "font-size": 12 }, svg).textContent = ddmm(p.data);
  });
  chaves.forEach((c, ci) => {
    // null = dia ainda sem dado: a linha para no último ponto conhecido
    const idx = serie.map((p, i) => i).filter(i => serie[i][c.k] != null);
    if (!idx.length) return;
    const pts = idx.map(i => `${x(i)},${y(serie[i][c.k])}`).join(" ");
    svgEl("polyline", { points: pts, fill: "none", stroke: VIZ.serie[ci], "stroke-width": 2,
                        "stroke-linejoin": "round", "stroke-linecap": "round" }, svg);
    const iu = idx[idx.length - 1], ult = serie[iu][c.k], ux = x(iu), uy = y(ult);
    svgEl("circle", { cx: ux, cy: uy, r: 4, fill: VIZ.serie[ci], stroke: VIZ.fundo, "stroke-width": 2 }, svg);
    svgEl("text", { x: ux + 9, y: uy + 4, fill: VIZ.texto, "font-size": 12, "font-weight": 600 }, svg).textContent = fmtN(ult);
  });

  // Hover: crosshair + tooltip no dia mais próximo
  const cruz = svgEl("line", { y1: m.t, y2: m.t + h, stroke: VIZ.texto2, "stroke-width": 1, visibility: "hidden" }, svg);
  const pontos = chaves.map((c, ci) => svgEl("circle", { r: 5, fill: VIZ.serie[ci], stroke: VIZ.fundo, "stroke-width": 2, visibility: "hidden" }, svg));
  const alvo = svgEl("rect", { x: m.l, y: m.t, width: w, height: h, fill: "transparent" }, svg);
  const dica = document.createElement("div");
  dica.className = "viz-dica";
  el.style.position = "relative";
  el.appendChild(dica);
  alvo.addEventListener("mousemove", ev => {
    const r = svg.getBoundingClientRect();
    const i = Math.max(0, Math.min(serie.length - 1, Math.round(((ev.clientX - r.left - m.l) / w) * (serie.length - 1))));
    const p = serie[i];
    cruz.setAttribute("x1", x(i)); cruz.setAttribute("x2", x(i)); cruz.setAttribute("visibility", "visible");
    chaves.forEach((c, ci) => { pontos[ci].setAttribute("cx", x(i)); pontos[ci].setAttribute("cy", y(p[c.k] || 0));
                                pontos[ci].setAttribute("visibility", p[c.k] == null ? "hidden" : "visible"); });
    const dia = new Date(p.data + "T12:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" });
    const nota = notaDoDia ? notaDoDia(p) : "";
    dica.innerHTML = `<b>${dia}</b>` + chaves.map((c, ci) =>
      `<div><span class="viz-chave" style="background:${VIZ.serie[ci]}"></span>${c.nome}: <b>${p[c.k] == null ? "ainda sem dado" : fmtN(p[c.k])}</b></div>`).join("") +
      (nota ? `<div class="viz-nota">${nota}</div>` : "");
    dica.style.display = "block";
    const px = x(i) + 14, cabe = px + dica.offsetWidth < largura;
    dica.style.left = (cabe ? px : x(i) - dica.offsetWidth - 14) + "px";
    dica.style.top = m.t + "px";
  });
  alvo.addEventListener("mouseleave", () => {
    dica.style.display = "none"; cruz.setAttribute("visibility", "hidden");
    pontos.forEach(pt => pt.setAttribute("visibility", "hidden"));
  });
}

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

// Barras deitadas empilhadas (uma por agente), total no fim; clique abre o filtro
function graficoBarrasEmpilhadas(el, itens, series, { aoClicar } = {}) {
  coresDoTema();
  el.innerHTML = "";
  if (!itens.length) { el.textContent = "Nada em aberto. 🎉"; return; }
  const ctx = document.createElement("canvas").getContext("2d");
  ctx.font = '13px "IBM Plex Sans", "Segoe UI", system-ui, sans-serif';
  const rotuloW = Math.ceil(Math.max(40, ...itens.map(i => ctx.measureText(i.rotulo).width))) + 14;
  const largura = Math.max(280, el.clientWidth || 400), linha = 40, bh = 22;
  const altura = itens.length * linha + 4, w = largura - rotuloW - 56;
  const totais = itens.map(it => series.reduce((a, s) => a + (it.partes[s.k] || 0), 0));
  const max = Math.max(1, ...totais);
  const svg = svgEl("svg", { width: largura, height: altura, role: "img", "aria-label": "Em aberto por agente" }, el);
  const dica = document.createElement("div");
  dica.className = "viz-dica";
  el.style.position = "relative";
  el.appendChild(dica);
  itens.forEach((it, k) => {
    const y0 = k * linha + 8;
    const g = svgEl("g", { style: aoClicar ? "cursor:pointer" : "" }, svg);
    svgEl("text", { x: rotuloW - 10, y: y0 + 16, "text-anchor": "end", fill: VIZ.texto, "font-size": 13, "font-weight": 600 }, g).textContent = it.rotulo;
    let x = rotuloW;
    series.forEach(s => {
      const v = it.partes[s.k] || 0;
      if (!v) return;
      const bw = Math.max(3, (v / max) * w);
      svgEl("rect", { x, y: y0, width: Math.max(1, bw - 2), height: bh, rx: 3, fill: s.cor }, g);
      x += bw;
    });
    svgEl("text", { x: x + 8, y: y0 + 16, fill: VIZ.texto, "font-size": 13, "font-weight": 600 }, g).textContent = fmtN(totais[k]);
    const alvo = svgEl("rect", { x: 0, y: y0 - 8, width: largura, height: linha, fill: "transparent" }, g);
    alvo.addEventListener("mouseenter", () => {
      dica.innerHTML = _dicaEmpilhada(it.rotulo, it.partes, series) + (aoClicar ? `<div class="viz-nota">Clique para ver as notas</div>` : "");
      dica.style.display = "block";
      dica.style.left = Math.min(largura - dica.offsetWidth - 4, x + 40) + "px";
      dica.style.top = Math.max(0, y0 - 10) + "px";
    });
    alvo.addEventListener("mouseleave", () => { dica.style.display = "none"; });
    if (aoClicar) g.addEventListener("click", () => aoClicar(it));
  });
}
