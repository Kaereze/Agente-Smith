/* Tamanho da tela (João, 19/11/2026): tira o zoom solto do navegador embutido e deixa o Painel do tamanho certo para a largura e a
   escala do Windows DAQUELE PC. Automático (padrão) ou manual (90 a 150%). A escolha fica gravada neste PC.
   Só existe na janela do app (pywebview): quem aplica o zoom é o Python, pelo WebView2 (ZoomFactor), então vh, vw e as posições dos
   menus continuam certos (o "zoom" do CSS embolava tudo isso). Sem a janela (navegador comum) não faz nada. */
(function () {
  const BASE = 1500, MIN = 0.85, MAX = 1.3, PASSO = 0.05;   // largura de conforto, e os limites do automático (nunca ilegível)
  const MANUAL = [0.9, 1, 1.1, 1.25, 1.5];
  const CHAVE = "painel.escala";
  let pref = "auto", atual = 1, ocupado = false, tempo = 0;
  try { pref = localStorage.getItem(CHAVE) || "auto"; } catch (e) {}
  if (pref !== "auto" && !MANUAL.includes(Number(pref))) pref = "auto";

  // largura da janela na escala 1 (já com a escala do Windows) -> o zoom que deixa o conteúdo do tamanho de conforto
  function calcular(larguraNaEscala1) {
    const bruto = Math.min(MAX, Math.max(MIN, larguraNaEscala1 / BASE));
    return Number((Math.round(bruto / PASSO) * PASSO).toFixed(2));
  }
  const api = () => window.pywebview && window.pywebview.api && window.pywebview.api.definir_escala ? window.pywebview.api : null;

  async function aplicar() {
    const a = api();
    if (!a || ocupado) return;
    ocupado = true;
    try {
      const antes = Number(await a.escala_atual()) || 1;
      const alvo = pref === "auto" ? calcular(window.innerWidth * antes) : Number(pref);
      atual = Number(await a.definir_escala(alvo)) || antes;   // sempre chama: desliga o zoom solto (Ctrl + e -) mesmo quando o valor não muda
    } catch (e) { /* sem escala: a tela fica como estava */ }
    ocupado = false;
    desenhar();
  }
  function escolher(valor) {
    pref = valor;
    try { localStorage.setItem(CHAVE, pref); } catch (e) {}
    aplicar();
  }
  function html() {
    if (!window.pywebview) return "";
    const rot = v => Math.round(v * 100) + "%";
    return `<div class="op-sep"></div><div class="op-escala" id="op-escala" role="group" aria-label="Tamanho da tela">
      <div class="op-escala-t"><b>Tamanho da tela</b><small>${pref === "auto" ? "Automático: " + rot(atual) + " neste PC" : "Fixo em " + rot(Number(pref))}</small></div>
      <div class="op-escala-b"><button type="button" data-escala="auto" aria-pressed="${pref === "auto"}">Auto</button>${
        MANUAL.map(v => `<button type="button" data-escala="${v}" aria-pressed="${pref === String(v)}">${rot(v)}</button>`).join("")}</div></div>`;
  }
  function desenhar() {
    const el = document.getElementById("op-escala");
    if (!el) return;
    const novo = document.createElement("div");
    novo.innerHTML = html();
    const dentro = novo.querySelector("#op-escala");
    if (dentro) el.innerHTML = dentro.innerHTML;
  }
  document.addEventListener("click", e => {
    const b = e.target.closest && e.target.closest("[data-escala]");
    if (!b) return;
    e.stopPropagation();
    escolher(b.dataset.escala);
  });
  window.addEventListener("resize", () => {   // janela redimensionada: no automático, reajusta quando ela para de mexer
    if (pref !== "auto") return;
    clearTimeout(tempo);
    tempo = setTimeout(aplicar, 700);
  });
  window.addEventListener("pywebviewready", aplicar);
  window.painelEscala = { calcular, html, desenhar, aplicar };
})();
