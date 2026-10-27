// Botão de caixas com problema (27/10/2026, desenho aprovado pelo João): uma caixa de entrada com sinal de perigo, logo
// abaixo da bolha de avisos. Só existe enquanto algum PC está com o Outlook sem enviar/receber. O clique abre um quadro do
// tamanho do de avisos com o que o Painel sabe (e-mails presos por caixa, o motivo) e o botão "Reiniciar o Outlook de X"
// (fecha à força e abre de novo, o que o João fazia à mão). O X só guarda o quadro: o botão nunca some sozinho.
// Usa os globais do Painel: api(), acaoLonga(), esc().
(() => {
  const ATUALIZA_MS = 15000;
  let bt, pn, aberto = false, dados = { pcs: [] }, lista = [], st = {}, lido = 0, buscando = false;

  function montar() {
    if (bt) return;
    bt = document.createElement("button");
    bt.type = "button"; bt.className = "cp-bt pisca"; bt.hidden = true;
    bt.setAttribute("aria-label", "Caixas com problema"); bt.title = "Caixas que não enviam ou não recebem";
    bt.innerHTML = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 13h5l1 3h6l1-3h5"/><path d="M5 5h14l2 8v6H3v-6z"/></svg><span class="cp-n"></span>`;
    pn = document.createElement("aside");
    pn.className = "cp-pn"; pn.hidden = true; pn.setAttribute("role", "dialog"); pn.setAttribute("aria-label", "Caixas com problema");
    document.body.append(bt, pn);
    bt.addEventListener("click", () => { aberto = !aberto; pn.hidden = !aberto; if (aberto) { buscar(true); pintar(); } });
    pn.addEventListener("click", e => {
      const b = e.target.closest("button"); if (!b) return;
      if (b.classList.contains("cp-x")) { aberto = false; pn.hidden = true; return; }   // em espera: o botão continua avisando
      const pc = b.dataset.pc;
      if (b.dataset.q) { st[pc] = { fase: "conf" }; pintar(); }
      else if (b.dataset.nao) { delete st[pc]; pintar(); }
      else if (b.dataset.sim) reiniciar(pc);
    });
    document.addEventListener("keydown", e => { if (e.key === "Escape" && aberto) { aberto = false; pn.hidden = true; } });
  }

  async function buscar(forca) {
    if (buscando || (!forca && Date.now() - lido < ATUALIZA_MS)) return;
    buscando = true;
    try { dados = await api("/api/caixas"); lido = Date.now(); } catch (e) { /* a tela mostra o que já tinha */ }
    buscando = false;
    if (aberto) pintar();
  }

  function pintar() {
    if (!pn || !aberto) return;
    const pcs = (dados.pcs || []).filter(p => lista.some(x => x.pc === p.pc) || st[p.pc]);
    pn.innerHTML = `<div class="cp-cab"><b>Caixas com problema</b><button type="button" class="cp-x" aria-label="Deixar em espera" title="Deixar em espera (o botão continua avisando)">×</button></div>`
      + (pcs.length ? pcs.map(p => {
        const s = st[p.pc] || {}, nome = esc(p.agente);
        const linhas = (p.caixas || []).map(c => `<div class="cp-lin"><i></i><div><b>${esc(c.caixa)}</b><small>${c.presos} e-mail${c.presos > 1 ? "s" : ""} preso${c.presos > 1 ? "s" : ""} na Caixa de Saída</small></div></div>`).join("")
          + (p.textos || []).map(t => `<div class="cp-lin cp-amb"><i></i><div><small>${esc(t)}</small></div></div>`).join("")
          + (p.erro ? `<div class="cp-lin cp-amb"><i></i><div><small>Não consegui ler as caixas deste PC: ${esc(p.erro)}</small></div></div>` : "");
        const acao = s.fase === "andando" ? `<div class="cp-res cp-cinza">Reiniciando o Outlook de ${nome}…</div>`
          : s.fase === "res" ? `<div class="cp-res ${s.ok ? (s.aviso ? "cp-am" : "cp-azul") : "cp-verm"}">${esc(s.texto)}</div>`
          : s.fase === "conf" ? `<div class="cp-conf">Isso <b>fecha o Outlook de ${nome} de vez</b> e abre de novo (uns 30 s). Rascunhos abertos lá o Outlook costuma guardar sozinho. Continuar?<div class="cp-acao"><button type="button" data-sim="1" data-pc="${esc(p.pc)}">Sim, reiniciar</button><button type="button" class="s" data-nao="1" data-pc="${esc(p.pc)}">Cancelar</button></div></div>`
          : "";
        return `<section class="cp-pc"><h4>${nome}</h4>${linhas}${acao}`
          + (s.fase === "conf" || s.fase === "andando" ? "" : `<div class="cp-acao"><button type="button" data-q="1" data-pc="${esc(p.pc)}">Reiniciar o Outlook de ${nome}</button></div>`) + `</section>`;
      }).join("") : `<div class="cp-rod">Nenhuma caixa com problema agora.</div>`)
      + `<div class="cp-rod">O × só guarda este quadro: o botão fica na tela enquanto houver caixa com problema.</div>`;
  }

  async function reiniciar(pc) {
    const p = (dados.pcs || []).find(x => x.pc === pc), nome = p?.agente || pc;
    st[pc] = { fase: "andando" }; pintar();
    const longa = acaoLonga(`Reiniciando o Outlook de ${nome}`, { limiteMs: 0 });   // a tela do K abre na hora
    let r;
    try { r = await api("/api/outlook/reiniciar", { pc }); } catch (e) { r = { erro: "o Painel deste PC não respondeu" }; }
    const ok = !!r.ok && !r.erro;
    longa.fim(ok, r.erro || "");
    st[pc] = { fase: "res", ok, aviso: ok && (r.presos || r.aviso),
      texto: ok ? (r.presos ? `Abriu, mas ainda há ${r.presos} e-mail(s) preso(s) em ${nome}. Veja se alguma janela do Outlook pede senha.`
        : `Voltou: o Outlook de ${nome} abriu${r.saiu ? ` e ${r.saiu} e-mail(s) saíram` : ""}. O botão some quando o Painel confirmar.`)
        : `${r.erro || "Não deu certo"}. Pode precisar de alguém no PC de ${nome}.` };
    pintar(); buscar(true);
  }

  // chamada a cada leitura do estado, com a lista de avisos de saúde (só os de caixa interessam)
  window.caixasProblema = function (avisos) {
    montar();
    lista = (avisos || []).filter(a => a.tipo === "caixa" && a.pc);
    const pcs = new Set(lista.map(a => a.pc));
    document.body.classList.toggle("tem-caixas", pcs.size > 0);
    bt.hidden = pcs.size === 0;
    bt.querySelector(".cp-n").textContent = pcs.size || "";
    if (!pcs.size) { aberto = false; pn.hidden = true; st = {}; return; }
    if (aberto) { buscar(false); pintar(); }
  };
})();
