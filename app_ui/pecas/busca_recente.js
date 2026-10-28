// Histórico da pesquisa (28/10/2026, pedido do João): as pesquisas das últimas 24 h ficam na caixa de busca de cima, para repetir
// "nome ou e-mail do hóspede" com um clique; passou de 24 h, some (reseta). Fica SÓ no navegador deste PC (localStorage): nada vai ao
// servidor, à planilha nem a outro PC. Não guarda o que parece CPF/CNPJ (LGPD). Troca a decisão de 11/10 ("nada fica guardado").
(() => {
  const entrada = document.getElementById("busca");
  if (!entrada) return;
  const CHAVE = "painel.buscas", VALIDADE_MS = 24 * 3600 * 1000, MAX = 12, OCIOSO_MS = 1200;
  const caixa = entrada.closest("label.busca") || entrada.parentElement;
  const h = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  let painel, marcado = -1, timer;

  const gravar = lista => { try { localStorage.setItem(CHAVE, JSON.stringify(lista.slice(0, MAX))); } catch (e) { /* sem armazenamento: não guarda */ } };
  function ler() {   // só o que tem menos de 24 h; o resto é apagado na hora
    try {
      const todas = JSON.parse(localStorage.getItem(CHAVE) || "[]");
      const corte = Date.now() - VALIDADE_MS;
      const vivas = Array.isArray(todas) ? todas.filter(x => x && typeof x.t === "string" && x.em > corte) : [];
      if (!Array.isArray(todas) || vivas.length !== todas.length) gravar(vivas);
      return vivas;
    } catch (e) { return []; }
  }
  // CPF/CNPJ (11 ou 14 dígitos, sem letras) não fica guardado
  const pareceDocumento = t => { const d = t.replace(/\D/g, ""); return (d.length === 11 || d.length === 14) && !/[a-zà-ú]{3,}/i.test(t); };
  function guardar(texto) {
    const t = String(texto || "").trim();
    if (t.length < 3 || pareceDocumento(t)) return;
    const baixo = t.toLowerCase();
    // quem continua digitando ("joa" -> "joao" -> "joao silva") substitui o pedaço anterior em vez de empilhar
    const lista = ler().filter(x => { const b = x.t.toLowerCase(); return b !== baixo && !baixo.startsWith(b); });
    lista.unshift({ t, em: Date.now() });
    gravar(lista);
  }
  const quando = em => {
    const min = Math.max(0, Math.round((Date.now() - em) / 60000));
    return min < 1 ? "agora" : min < 60 ? `há ${min} min` : `há ${Math.floor(min / 60)} h`;
  };

  function montar() {
    if (painel) return;
    painel = document.createElement("div");
    painel.className = "bh"; painel.hidden = true; painel.setAttribute("role", "listbox"); painel.setAttribute("aria-label", "Pesquisas das últimas 24 horas");
    painel.addEventListener("mousedown", e => e.preventDefault());   // clicar na lista não tira o foco da caixa
    painel.addEventListener("click", e => {
      const x = e.target.closest("[data-bh-x]");
      if (x) { gravar(ler().filter((_, i) => i !== +x.dataset.bhX)); return desenhar(); }
      if (e.target.closest("[data-bh-limpar]")) { gravar([]); return fechar(); }
      const it = e.target.closest("[data-bh-t]");
      if (it) usar(it.dataset.bhT);
    });
    caixa.appendChild(painel);
  }
  const visiveis = () => {
    const digitado = entrada.value.trim().toLowerCase();
    return ler().filter(x => !digitado || (x.t.toLowerCase().includes(digitado) && x.t.toLowerCase() !== digitado));
  };
  function desenhar() {
    montar();
    const itens = visiveis();
    marcado = Math.min(marcado, itens.length - 1);
    if (!itens.length) return fechar();
    painel.innerHTML = `<div class="bh-cab"><span>Pesquisas das últimas 24 h</span><button type="button" data-bh-limpar>Limpar</button></div>`
      + itens.map((x, i) => `<div class="bh-it${i === marcado ? " on" : ""}" role="option" data-bh-t="${h(x.t)}"><span class="bh-t">${h(x.t)}</span>`
        + `<small>${quando(x.em)}</small><button type="button" class="bh-x" data-bh-x="${i}" aria-label="Tirar esta pesquisa" title="Tirar">×</button></div>`).join("");
    painel.hidden = false;
  }
  function fechar() { if (painel) painel.hidden = true; marcado = -1; }
  function usar(t) {
    entrada.value = t; fechar(); guardar(t);
    entrada.dispatchEvent(new Event("input", { bubbles: true }));   // a pesquisa roda como se tivesse sido digitada
    entrada.focus();
  }

  ler();   // ao abrir o Painel já apaga o que passou de 24 h (o histórico "reseta" sozinho)
  entrada.addEventListener("focus", () => { marcado = -1; desenhar(); });
  entrada.addEventListener("click", () => { if (!painel || painel.hidden) desenhar(); });
  entrada.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(() => guardar(entrada.value), OCIOSO_MS);   // só guarda quando para de digitar
    marcado = -1; desenhar();
  });
  entrada.addEventListener("keydown", e => {
    if (e.key === "Enter") { clearTimeout(timer); guardar(entrada.value); const it = painel && !painel.hidden ? painel.querySelectorAll(".bh-it")[marcado] : null;
      if (it) { e.preventDefault(); usar(it.dataset.bhT); } else fechar(); return; }
    if (e.key === "Escape") { fechar(); return; }
    if (e.key !== "ArrowDown" && e.key !== "ArrowUp") return;
    if (!painel || painel.hidden) { desenhar(); if (painel.hidden) return; }
    const n = painel.querySelectorAll(".bh-it").length;
    e.preventDefault();
    marcado = e.key === "ArrowDown" ? (marcado + 1) % n : (marcado - 1 + n) % n;
    desenhar();
  });
  entrada.addEventListener("blur", () => { clearTimeout(timer); guardar(entrada.value); setTimeout(fechar, 120); });
  document.addEventListener("click", e => { if (painel && !painel.hidden && !caixa.contains(e.target)) fechar(); });
})();
