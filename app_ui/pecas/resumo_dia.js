// Peça única do Resumo do dia (João, 07/11/2026): números que sobem, gráfico de linha por hora com dica, barras que crescem,
// barra de prazo e de situação, lista de atenção e a opção "Ver como tabela". Desenho aprovado em
// "Segundo Cérebro/6 Documentos/Designs/2026-11-07 Resumo de ontem (dashboard).html". SVG e CSS puros, sem biblioteca.
//
//   resumoDiaPeca(d)       -> HTML do miolo (KPIs, gráficos, listas); quem monta o cabeçalho e os dados é o painel.js
//   resumoDiaAnimar(raiz)  -> liga a animação de entrada (só quando os números mudaram ou ao abrir a tela)
// A dica (tooltip) e o teclado usam delegação de eventos no document: a tela pode ser redesenhada a cada 15 s sem perder nada.
// d: { kpis:[{r, v, fmt:"n"|"p"|"h", delta:"<html>", spark:[n]|null, nota}], horas:[{h, ped, nfs}], prazo:{pct, ok, total},
//      abertos:[{nome, n, k:"a"|"c"|"b"}], vencidos, equipe:[{nome, rec, nfs}], hoteis:[{nome, n}], atencao:"<html>", tabela:bool, titulos:{...} }

const RS_COR = { a: "var(--rs-a)", b: "var(--rs-b)", c: "var(--rs-c)" };
const rsEsc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const rsNum = (v, fmt) => fmt === "p" ? Math.round(v) + "%" : fmt === "h" ? Math.round(v) + " h" : Math.round(v).toLocaleString("pt-BR");
const rsDados = obj => rsEsc(JSON.stringify(obj));

function rsSpark(vals) {
  if (!vals || vals.length < 2) return "";
  const max = Math.max(...vals), min = Math.min(...vals), n = vals.length;
  const pts = vals.map((v, i) => [i * 200 / (n - 1), 30 - (max === min ? 15 : (v - min) / (max - min) * 26)]);
  const ult = pts[n - 1];
  return `<svg class="rs-spark" viewBox="0 0 200 34" preserveAspectRatio="none" aria-hidden="true">
    <path class="rs-tr" pathLength="1" d="M${pts.map(p => p[0].toFixed(1) + "," + p[1].toFixed(1)).join("L")}" stroke="var(--rs-a)" vector-effect="non-scaling-stroke"/>
    <circle cx="${ult[0]}" cy="${ult[1].toFixed(1)}" r="3" fill="var(--rs-a)"/></svg>`;
}

function rsKpis(d) {
  return `<div class="rs-kpis">${d.kpis.map((k, i) => `<div class="rs-cartao rs-kpi" style="--i:${i}">
    <small>${rsEsc(k.r)}</small><b data-cnt="${k.v == null ? "" : k.v}" data-fmt="${k.fmt}">${k.v == null ? "—" : rsNum(k.v, k.fmt)}</b>
    <span class="rs-delta">${k.delta || ""}</span>${rsSpark(k.spark)}${k.nota ? `<span class="rs-nota">${rsEsc(k.nota)}</span>` : ""}</div>`).join("")}</div>`;
}

function rsLinha(d) {
  const W = 720, H = 250, m = { e: 34, d: 14, t: 12, b: 26 }, hs = d.horas, n = hs.length;
  const max = Math.max(4, ...hs.map(x => x.ped), ...hs.map(x => x.nfs)), topo = Math.ceil(max / 4) * 4;
  const X = i => m.e + i * (W - m.e - m.d) / Math.max(1, n - 1), Y = v => H - m.b - v / topo * (H - m.b - m.t);
  let eixo = "";
  for (let v = 0; v <= topo; v += topo / 4) eixo += `<line x1="${m.e}" x2="${W - m.d}" y1="${Y(v)}" y2="${Y(v)}" class="${v === 0 ? "rs-base" : ""}"/><text x="${m.e - 8}" y="${Y(v) + 4}" text-anchor="end">${v}</text>`;
  hs.forEach((x, i) => { if (i % 2 === 0) eixo += `<text x="${X(i)}" y="${H - 6}" text-anchor="middle">${x.h}h</text>`; });
  const trilha = vals => "M" + vals.map((v, i) => X(i).toFixed(1) + "," + Y(v).toFixed(1)).join("L");
  const area = `${trilha(hs.map(x => x.ped))}L${X(n - 1)},${Y(0)}L${X(0)},${Y(0)}Z`;
  const colunas = hs.map((x, i) => {
    const larg = (W - m.e - m.d) / Math.max(1, n - 1);
    return `<rect class="rs-hit" x="${(X(i) - larg / 2).toFixed(1)}" y="${m.t}" width="${larg.toFixed(1)}" height="${H - m.t - m.b}" data-i="${i}" data-x="${X(i).toFixed(1)}" data-ya="${Y(x.ped).toFixed(1)}" data-yb="${Y(x.nfs).toFixed(1)}"
      data-d="${rsDados({ t: x.h + "h", l: [["a", "Pedidos", x.ped], ["b", "NFs enviadas", x.nfs]] })}"/>`;
  }).join("");
  return `<svg class="rs-linha-svg" viewBox="0 0 ${W} ${H}" role="img" tabindex="0" aria-label="Pedidos recebidos e NFs enviadas por hora. Use as setas para percorrer as horas."
      data-n="${n}"><g class="rs-eixo">${eixo}</g>
    <path d="${area}" fill="var(--rs-a)" class="rs-area"/>
    <path class="rs-tr rs-fio" pathLength="1" d="${trilha(hs.map(x => x.ped))}" stroke="var(--rs-a)"/>
    <path class="rs-tr rs-fio" pathLength="1" d="${trilha(hs.map(x => x.nfs))}" stroke="var(--rs-b)"/>
    <line class="rs-cruz" y1="${m.t}" y2="${H - m.b}" opacity="0"/><circle class="rs-pa" r="4" fill="var(--rs-a)" opacity="0"/><circle class="rs-pb" r="4" fill="var(--rs-b)" opacity="0"/>${colunas}</svg>`;
}

function rsBarras(linhas, duas) {
  if (!linhas.length) return `<div class="rs-vazio">Sem movimento.</div>`;
  const max = Math.max(1, ...linhas.map(l => Math.max(l.rec ?? l.n ?? 0, l.nfs || 0)));
  return `<div class="rs-barras">${linhas.map(l => {
    const a = l.rec ?? l.n ?? 0, b = l.nfs || 0;
    const dados = rsDados({ t: l.nome, l: duas ? [["a", "Recebidos", a], ["b", "NFs enviadas", b]] : [["a", "Pedidos", a]] });
    return `<div class="rs-br" tabindex="0" data-d="${dados}"><span class="rs-nome" title="${rsEsc(l.nome)}">${rsEsc(l.nome)}</span>
      <div class="rs-trilho"><div class="rs-barra" style="width:${a / max * 100}%"></div>${duas ? `<div class="rs-barra rs-o" style="width:${b / max * 100}%"></div>` : ""}</div>
      <span class="rs-val">${duas ? `${a} · ${b}` : a}</span></div>`;
  }).join("")}</div>`;
}

function rsTabelas(d) {
  const t = (cab, linhas) => `<table class="rs-tab"><thead><tr>${cab.map((c, i) => `<th${i ? ' class="n"' : ""}>${rsEsc(c)}</th>`).join("")}</tr></thead><tbody>${linhas.map(l => `<tr>${l.map((c, i) => `<td${i ? ' class="n"' : ""}>${rsEsc(c)}</td>`).join("")}</tr>`).join("")}</tbody></table>`;
  return `<div class="rs-cartao"><h2>Os mesmos números, em tabela</h2><p class="rs-dica">para ler sem gráfico, copiar ou imprimir</p>
    ${t(["Hora", "Pedidos recebidos", "NFs enviadas"], d.horas.map(x => [x.h + "h", x.ped, x.nfs]))}<br>
    ${t(["Agente", "Recebidos", "NFs enviadas"], d.equipe.map(x => [x.nome, x.rec, x.nfs]))}<br>
    ${t(["Hotel", "Pedidos"], d.hoteis.map(x => [x.nome, x.n]))}</div>`;
}

function resumoDiaPeca(d) {
  const tot = d.abertos.reduce((s, a) => s + a.n, 0);
  const seg = d.abertos.filter(a => a.n > 0).map(a => `<div class="rs-seg" tabindex="0" style="--cor:${RS_COR[a.k]};flex-basis:${a.n / Math.max(1, tot) * 100}%"
      data-d="${rsDados({ t: a.nome, l: [[a.k, "Pedidos", a.n + " (" + Math.round(100 * a.n / Math.max(1, tot)) + "%)"]] })}">${a.n}</div>`).join("");
  const lista = d.abertos.map(a => `<div><span><i style="background:${RS_COR[a.k]}"></i>${rsEsc(a.nome)}</span><b>${a.n}</b></div>`).join("");
  const painel = `${rsKpis(d)}
    <div class="rs-grade">
      <div class="rs-cartao rs-g8"><h2>Pedidos e NFs ao longo do dia</h2><p class="rs-dica">por hora · passe o mouse, ou use as setas, para ver cada hora</p>
        <div class="rs-leg"><span><i style="background:var(--rs-a)"></i>Pedidos recebidos</span><span><i style="background:var(--rs-b)"></i>NFs enviadas</span></div>
        <div class="rs-graf">${rsLinha(d)}</div></div>
      <div class="rs-cartao rs-g4"><h2>Prazo das NFs</h2><p class="rs-dica">enviadas em até 48 h</p>
        ${d.prazo.pct == null ? `<div class="rs-vazio">Nenhuma NF enviada neste dia.</div>` : `<div class="rs-rot">${d.prazo.pct}% no prazo</div>
        <div class="rs-meter" role="img" aria-label="${d.prazo.pct}% enviadas no prazo"><div style="--p:${d.prazo.pct}%"></div></div>
        <p class="rs-dica" style="margin:0 0 6px">${d.prazo.ok} de ${d.prazo.total} saíram em até 48 h</p>`}
        <h2 class="rs-h2b">${rsEsc(d.titulos.abertos)}</h2><p class="rs-dica">${tot.toLocaleString("pt-BR")} em aberto · ${d.vencidos.toLocaleString("pt-BR")} já vencidos</p>
        <div class="rs-segbar" role="img" aria-label="Pedidos em aberto por situação">${seg}</div><div class="rs-lista-seg">${lista}</div></div>
    </div>
    <div class="rs-grade">
      <div class="rs-cartao rs-g6"><h2>${rsEsc(d.titulos.equipe)}</h2><p class="rs-dica">pedidos recebidos e NFs enviadas por agente</p>
        <div class="rs-leg"><span><i class="rs-q" style="background:var(--rs-a)"></i>Recebidos</span><span><i class="rs-q" style="background:var(--rs-b)"></i>NFs enviadas</span></div>${rsBarras(d.equipe, true)}</div>
      <div class="rs-cartao rs-g6"><h2>Hotéis com mais pedidos</h2><p class="rs-dica">os 6 maiores do dia</p>${rsBarras(d.hoteis, false)}</div>
    </div>
    <div class="rs-cartao"><h2>${rsEsc(d.titulos.atencao)}</h2><p class="rs-dica">urgentes e com dado faltando · clique para abrir a ficha</p><div class="rs-atencao">${d.atencao}</div></div>`;
  return `<div class="rs-corpo${d.tabela ? " rs-tabela-on" : ""}"><div class="rs-so-graficos">${painel}</div><div class="rs-so-tabela">${rsTabelas(d)}</div></div>`;
}

// ---------- animação de entrada ----------
function resumoDiaAnimar(raiz) {
  const corpo = raiz.querySelector(".rs-corpo");
  if (!corpo || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  corpo.classList.add("rs-pre");
  corpo.querySelectorAll("[data-cnt]").forEach(el => {
    const alvo = Number(el.dataset.cnt); if (el.dataset.cnt === "" || isNaN(alvo)) return;
    el.textContent = rsNum(0, el.dataset.fmt);
    const t0 = performance.now();
    const passo = t => { const k = Math.min(1, (t - t0) / 800); el.textContent = rsNum(alvo * (1 - Math.pow(1 - k, 3)), el.dataset.fmt); if (k < 1 && el.isConnected) requestAnimationFrame(passo); };
    requestAnimationFrame(passo);
  });
  requestAnimationFrame(() => requestAnimationFrame(() => corpo.classList.remove("rs-pre")));
}

// ---------- dica e teclado (uma vez só, no document) ----------
const RS_DICA = (() => { let el = null; return () => el || (el = Object.assign(document.body.appendChild(document.createElement("div")), { id: "rs-dica", role: "tooltip" })); })();
function rsMostrar(x, y, info) {
  const dica = RS_DICA(); dica.textContent = "";
  const t = document.createElement("div"); t.className = "rs-dt"; t.textContent = info.t; dica.appendChild(t);
  for (const [k, nome, valor] of info.l) {   // textContent sempre: nomes vêm de planilha
    const l = document.createElement("div"); l.className = "rs-dl";
    const s = document.createElement("span"), i = document.createElement("i"); i.style.background = RS_COR[k] || "var(--rs-a)"; s.append(i, nome);
    const b = document.createElement("b"); b.textContent = valor; l.append(s, b); dica.appendChild(l);
  }
  dica.classList.add("on");
  const w = dica.offsetWidth, h = dica.offsetHeight;
  dica.style.left = Math.max(8, Math.min(innerWidth - w - 8, x + 14)) + "px";
  dica.style.top = Math.max(8, Math.min(innerHeight - h - 8, y - h - 10)) + "px";
}
const rsEsconder = () => { document.getElementById("rs-dica")?.classList.remove("on"); document.querySelectorAll(".rs-cruz,.rs-pa,.rs-pb").forEach(e => e.setAttribute("opacity", 0)); };
function rsColuna(svg, i, ev) {
  const col = svg.querySelector(`.rs-hit[data-i="${i}"]`); if (!col) return;
  svg.dataset.atual = i;
  const c = svg.querySelector(".rs-cruz"), pa = svg.querySelector(".rs-pa"), pb = svg.querySelector(".rs-pb");
  c.setAttribute("x1", col.dataset.x); c.setAttribute("x2", col.dataset.x); c.setAttribute("opacity", 1);
  pa.setAttribute("cx", col.dataset.x); pa.setAttribute("cy", col.dataset.ya); pa.setAttribute("opacity", 1);
  pb.setAttribute("cx", col.dataset.x); pb.setAttribute("cy", col.dataset.yb); pb.setAttribute("opacity", 1);
  const r = svg.getBoundingClientRect(), vb = svg.viewBox.baseVal;
  rsMostrar(ev ? ev.clientX : r.left + col.dataset.x / vb.width * r.width, ev ? ev.clientY : r.top + 40, JSON.parse(col.dataset.d));
}
document.addEventListener("pointermove", ev => {
  const alvo = ev.target.closest?.(".rs-hit, .rs-br, .rs-seg");
  if (!alvo) { if (document.getElementById("rs-dica")?.classList.contains("on")) rsEsconder(); return; }
  if (alvo.classList.contains("rs-hit")) return rsColuna(alvo.closest("svg"), alvo.dataset.i, ev);
  rsMostrar(ev.clientX, ev.clientY, JSON.parse(alvo.dataset.d));
});
document.addEventListener("focusin", ev => {
  const alvo = ev.target.closest?.(".rs-br, .rs-seg, .rs-linha-svg"); if (!alvo) return;
  if (alvo.classList.contains("rs-linha-svg")) return rsColuna(alvo, alvo.dataset.atual || 0);
  const q = alvo.getBoundingClientRect(); rsMostrar(q.left + 120, q.top, JSON.parse(alvo.dataset.d));
});
document.addEventListener("focusout", ev => { if (ev.target.closest?.(".rs-br, .rs-seg, .rs-linha-svg")) rsEsconder(); });
document.addEventListener("keydown", ev => {
  const svg = ev.target.closest?.(".rs-linha-svg"); if (!svg || !["ArrowLeft", "ArrowRight"].includes(ev.key)) return;
  ev.preventDefault();
  const n = Number(svg.dataset.n), i = Number(svg.dataset.atual || 0) + (ev.key === "ArrowRight" ? 1 : -1);
  rsColuna(svg, Math.max(0, Math.min(n - 1, i)));
});
document.documentElement.addEventListener("pointerleave", rsEsconder);   // o mouse saiu da janela
