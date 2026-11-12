// colunas.js: recolher as colunas dos E-mails (João, 09/11/2026, desenho aprovado no Artifact "Recolher Colunas do Painel").
// A coluna das PASTAS (esquerda) e a da LISTA de e-mails têm uma setinha ‹ no canto: ela recolhe a coluna para uma tirinha fina, com a seta ›;
// clicar na tirinha traz a coluna de volta. A leitura do e-mail ganha o espaço. O Painel lembra como ficou (localStorage "painel.colunas": "p", "l" ou "pl").
// As pastas são redesenhadas a cada atualização, então garantirColunas() recoloca a seta e a tirinha depois de cada desenho (correio_lista.js).
// A lista tem os botões fixos no index.html. O CSS está em pecas/colunas.css.
const COL_ESQ = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M15 6l-6 6 6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const COL_DIR = '<svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true"><path d="M9 6l6 6-6 6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>';
const colEstado = { p: false, l: false };
try { const s = localStorage.getItem("painel.colunas") || ""; colEstado.p = s.includes("p"); colEstado.l = s.includes("l"); } catch (e) { /* sem armazenamento: começa aberta */ }

function aplicarColunas() {
  const v = $("v-correio");
  if (!v) return;
  v.classList.toggle("col-p-fechada", colEstado.p);
  v.classList.toggle("col-l-fechada", colEstado.l);
  try { localStorage.setItem("painel.colunas", (colEstado.p ? "p" : "") + (colEstado.l ? "l" : "")); } catch (e) { /* só nesta janela */ }
}
function garantirColunas() {   // as pastas são refeitas por innerHTML: a seta e a tirinha voltam junto
  const a = $("cx-pastas");
  if (!a) return;
  if (!a.querySelector(":scope > .col-barra")) {
    a.insertAdjacentHTML("afterbegin", `<div class="col-barra"><button type="button" class="col-seta" data-colapsar="p" aria-label="Recolher as pastas" title="Recolher as pastas">${COL_ESQ}</button></div>`);
  }
  if (!a.querySelector(":scope > .col-tira")) {
    a.insertAdjacentHTML("beforeend", `<button type="button" class="col-tira" data-colapsar="p" aria-label="Mostrar as pastas" title="Mostrar as pastas"><span class="col-seta-ic">${COL_DIR}</span><span class="nome">Pastas</span></button>`);
  }
}
document.addEventListener("click", e => {
  const b = e.target.closest("#v-correio [data-colapsar]");
  if (!b) return;
  const k = b.dataset.colapsar;
  colEstado[k] = !colEstado[k];
  aplicarColunas();
  // o foco acompanha: recolheu -> vai para a tirinha; voltou -> vai para a seta
  requestAnimationFrame(() => document.querySelector(`#v-correio ${colEstado[k] ? ".col-tira" : ".col-seta"}[data-colapsar="${k}"]`)?.focus());
});
aplicarColunas();
