// correio_faixa.js: parte de correio.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// Enviar/Receber todas (27/10/2026, opção C: anel no botão): pede aos 4 PCs que rodem o Enviar/Receber do Outlook
const esperar = ms => new Promise(r => setTimeout(r, ms));
function pintarSync() {
  const er = cx.er;
  document.querySelectorAll('[data-ol-acao="sync"]').forEach(b => {
    if (!er) {
      if (b.dataset.erOrig) { b.innerHTML = b.dataset.erOrig; delete b.dataset.erOrig; b.disabled = false; b.removeAttribute("title"); b.classList.remove("er-ativo", "er-ok", "er-aviso"); }
      return;
    }
    if (!b.dataset.erOrig) b.dataset.erOrig = b.innerHTML;
    const aviso = er.fim && (er.falhas?.length || er.avisos?.length);
    const anel = `<svg class="er-anel" viewBox="0 0 36 36" aria-hidden="true"><circle class="fd" cx="18" cy="18" r="15.5"/><circle class="pr" cx="18" cy="18" r="15.5" pathLength="100" style="--p:${er.fim ? 1 : er.progresso}"/></svg>`;
    b.classList.add("er-ativo"); b.classList.toggle("er-ok", !!er.fim && !aviso); b.classList.toggle("er-aviso", !!aviso);
    b.disabled = true;
    b.innerHTML = `${anel} ${er.fim ? (aviso ? "Atualizado, com aviso" : "✓ Atualizado") : "Enviando/recebendo…"}`;
    b.title = er.fim ? [...(er.falhas || []), ...(er.avisos || [])].join(" · ") || `${er.total} PCs atualizados`
      : `${er.feitos} de ${er.total} PCs · uns ${er.eta} s`;
  });
}
// Ícone ⟳ da barra (29/10/2026): "rodando" = a tela grande está aberta; "em-espera" = passou de 5 s, o K pequeno segue carregando;
// "fim-ok" / "fim-aviso" = resultado por uns 2,6 s. Travado só enquanto roda; erro ou fim libera na hora.
const LIMITE_PEDIDO_MS = ((globalThis.aj?.("recarregar.limite_segundos") ?? 10) + 0.5) * 1000;   // o Painel corta o pedido em 10 s (enviar_receber.LIMITE_TOTAL)
let recEmCurso = false;
function pintarTopo(estado) {
  const b = $("btn-atualizar");
  if (!b) return;
  b.classList.remove("rodando", "em-espera", "fim-ok", "fim-aviso");
  if (estado) b.classList.add(estado);
  b.disabled = estado === "rodando" || estado === "em-espera";
  b.setAttribute("aria-busy", String(b.disabled));
}
// Um clique só: relê a planilha E pede o Enviar/Receber (F9) aos PCs com Outlook. Enquanto roda, outro clique não pede nada de novo;
// se der erro, libera na hora. O botão do topo e os da tela de E-mails usam esta mesma função.
async function enviarReceberTodas() {
  if (recEmCurso || (cx.er && !cx.er.fim)) return;
  recEmCurso = true; pintarTopo("rodando");
  // a tela do K abre na hora (limiteMs: 0); depois de 5 s ela sai de cena e o ícone segue (standbyMs)
  const longa = acaoLonga("Enviar/Receber todas", { limiteMs: 0, standbyMs: (globalThis.aj?.("tela.k_standby_segundos") ?? 5) * 1000, progresso: () => cx.er?.progresso ?? 0, eta: () => cx.er?.eta ?? 0, itens: () => cx.er?.pcs ?? [] });
  const aoStandby = e => { if (e.detail.id === longa.acao.id) pintarTopo("em-espera"); };
  window.addEventListener("painel:acao-standby", aoStandby);
  try { api("/api/atualizar", {}).then(() => (typeof carregar === "function" ? carregar() : null)).catch(() => {}); } catch (e) { /* relê a planilha em paralelo */ }
  try {
    const r = await api("/api/enviar_receber", {});
    if (r.erro || r.ok === false) {
      const motivo = r.erro || r.motivo || "Não deu pra pedir agora";
      longa.fim(false, motivo); pintarTopo(""); return toast(motivo, true);
    }
    cx.er = r;
    pintarSync();
    const ate = Date.now() + LIMITE_PEDIDO_MS;
    while (!cx.er.fim && Date.now() < ate) {   // no máximo 10 s; quem não respondeu vira aviso e o que deu certo ficou feito
      await esperar(500);
      const s = await api("/api/enviar_receber/status?id=" + encodeURIComponent(cx.er.id));
      if (s.erro) break;
      cx.er = s; pintarSync();
    }
    cx.er = { ...cx.er, fim: true };
    pintarSync();
    const falhas = cx.er.falhas || [], avisos = cx.er.avisos || [];
    longa.fim(!falhas.length, falhas.join("; "));
    pintarTopo(falhas.length || avisos.length ? "fim-aviso" : "fim-ok");
    setTimeout(() => pintarTopo(""), 2600);
    toast(falhas.length ? "Terminou com aviso: " + falhas.join("; ") : avisos.length ? "Atualizado. " + avisos.join("; ") : `${cx.er.total} PCs atualizados`, !!falhas.length);
    carregarCorreio();
    setTimeout(() => { cx.er = null; pintarSync(); }, 2500);
  } catch (e) {
    longa.fim(false, "Não deu pra pedir agora"); pintarTopo(""); toast("Não deu pra pedir agora", true);
  } finally {
    window.removeEventListener("painel:acao-standby", aoStandby);
    recEmCurso = false;
  }
}
const SVG = d => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const IC = { resp: '<path d="M9 14L4 9l5-5"/><path d="M4 9h11a5 5 0 015 5v5"/>', todos: '<path d="M7 14L2 9l5-5"/><path d="M12 14L7 9l5-5"/><path d="M7 9h9a5 5 0 015 5v5"/>',
  enc: '<path d="M15 14l5-5-5-5"/><path d="M20 9H9a5 5 0 00-5 5v5"/>', lixo: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  arq: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v11h14V9M10 13h4"/>', mover: '<path d="M3 7h7l2 2h9v10H3z"/>',
  lido: '<path d="M3 9l9-6 9 6v10H3z"/><path d="M3 9l9 6 9-6"/>', band: '<path d="M5 21V4h11l-2 4 2 4H5"/>', nf: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
  sync: '<path d="M20 11a8 8 0 00-14-5L4 8M4 4v4h4M4 13a8 8 0 0014 5l2-2M20 20v-4h-4"/>', novo: '<path d="M12 5v14M5 12h14"/>', novoemail: '<path d="M3 6h13v12H3z"/><path d="M3 7l6.5 5L16 7"/><path d="M19 4v6M16 7h6"/>',
  env: '<path d="M22 2L11 13M22 2l-7 20-4-9-9-4z"/>', pastas: '<path d="M3 6h7l2 2h9v11H3z"/>', tema: '<circle cx="12" cy="12" r="8"/><path d="M12 4a8 8 0 000 16z"/>',
  chapeu: '<path d="M2 9l10-5 10 5-10 5z"/><path d="M6 11v5c3 2 9 2 12 0v-5"/>', caixa: '<path d="M3 13h5l1 3h6l1-3h5"/><path d="M5 5h14l2 8v6H3v-6z"/>',
  alerta: '<path d="M12 3l9 16H3z"/><path d="M12 10v4M12 17v.5"/>', form: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/><path d="M9.5 15h5M9.5 12h5"/>' };
// Faixa de comandos do Outlook, com as 3 abas do topo (Página Inicial · Enviar/Receber · Exibir)
function desenharFaixa() {
  const el = $("cx-faixa");
  if (!el) return;
  document.querySelectorAll("[data-ol-aba]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.olAba === cx.aba)));
  const bt = (attr, ic, txt, extra = "") => `<button type="button" ${attr} ${extra}>${SVG(IC[ic])} ${txt}</button>`;
  const nao = "disabled title=\"Ainda não dá pelo Painel: faça no Outlook\"";
  el.innerHTML = cx.aba === "enviar" ? bt('data-ol-acao="sync"', "sync", "Enviar/Receber todas as pastas") + bt('data-ol-acao="pendentes"', "env", "Enviar solicitações pendentes")
    : cx.aba === "exibir" ? bt('data-ol-acao="pastas"', "pastas", cx.semPastas ? "Mostrar as pastas" : "Esconder as pastas") +
      bt('data-ol-acao="tema"', "tema", "Tema do Painel") + bt('data-ol-acao="prof"', "chapeu", "Modo professor")
    : bt('data-cx-faixa="resp"', "resp", "Responder", 'title="Ctrl+R"') + bt('data-cx-faixa="resp"', "todos", "Responder a todos") + bt('data-cx-faixa="enc"', "enc", "Encaminhar", 'title="Ctrl+F"') +
      `<span class="sep"></span>` + bt('data-cx-faixa="lido"', "lido", "Não lido/Lido", 'title="Ctrl+U / Ctrl+Q"') + bt("", "band", "Sinalizar", nao) +
      `<div class="dir">${bt("data-cx-novo", "novoemail", "Novo e-mail", 'class="faixa-novo" title="Escrever um e-mail novo: você escolhe a caixa do hotel que envia"')}${bt('data-cx-faixa="nf"', "nf", "Enviar NF", 'title="Responder com a NF · Ctrl+Shift+R"')}${bt('data-ol-acao="sync"', "sync", "Enviar/Receber todas")}</div>`;
  pintarSync();
}
function desenharFaixaGlobal() {
  const el = $("ol-faixa-g");
  if (!el) return;
  document.querySelectorAll("[data-ol-aba]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.olAba === cx.aba)));
  const bt = (attr, ic, txt, cls = "") => `<button type="button" class="${cls}" ${attr}>${SVG(IC[ic])} ${txt}</button>`;
  // as abas Página Inicial/Enviar/Receber/Exibir só aparecem nos e-mails (usuário, 20/10/2026): aqui, sempre os comandos principais
  el.innerHTML = bt('data-vista="correio" data-caixa="entrada"', "caixa", "Caixa de Entrada") +
      `<span class="sep"></span>` +
      bt('data-ol-acao="pendentes"', "env", "Enviar pendentes") + bt('data-ol-acao="sync"', "sync", "Enviar/Receber todas");
  pintarSync();
}
const hotelDaCaixa = c => (st.hoteis || []).filter(h => h.email === c).map(h => h.hotel).join(" / ");
const nomeDaCaixa = c => hotelDaCaixa(c) || String(c).split("@")[1]?.replace(/^(redeandrade|hotel)/, "").replace(/(hotel)?\.com(\.br)?$/, "").toUpperCase() || c;
