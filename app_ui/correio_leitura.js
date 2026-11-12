// correio_leitura.js: parte de correio.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// ---------- leitura: o e-mail aberto, como no Outlook ----------
function itemSelecionado() {
  const todos = [...(cx.dados?.emails || []), ...(cx.dados?.enviados || []).map(e => ({ ...e, pasta: "enviado" })),
                 ...(cx.live?.resultados || [])];
  return todos.find(e => e.id === cx.sel);
}
// Responder / encaminhar dentro do painel de leitura, com o original citado embaixo (como o Outlook)
// Formulário do Emissor Automático (usuário, 20/10/2026): o original embaixo da resposta é a mesma tabela da leitura
// (formularioHtml, peça única) e o e-mail do hóspede é o "Enviado por" (o remetente é o Emissor, o mesmo de todos).
function dadosDoFormulario(e) {
  if (!e || !(e.classes || []).includes("formulario")) return null;
  return pedidoDoEmail(e) || formDoTexto(cx.textos[e.id]?.texto);
}
function emailDoFormulario(e) {
  const d = dadosDoFormulario(e), x = String(d?.email || "").trim().toLowerCase();
  return x.includes("@") ? x : "";
}
function citacaoHtml(id) {
  const e = itemSelecionado() || (cx.dados?.emails || []).find(x => x.id === id), t = cx.textos[id] || {};
  if (!e) return "";
  const form = dadosDoFormulario(e);
  return `<div class="cx-cit-cab"><b>De:</b> ${esc(e.nome || e.de)} &lt;${esc(e.de)}&gt;<br><b>Enviado:</b> ${esc(dataLonga(e.quando))}<br>
    <b>Para:</b> ${esc(e.caixa || e.para || "")}<br><b>Assunto:</b> ${esc(e.assunto || "")}</div>${form ? formularioHtml(form, e) : `<div class="cx-texto">${esc(t.texto || e.previa || "")}</div>`}`;
}
function escrever(id, modo) {   // modo: "resp" | "nf" | "enc"
  const alvo = $("cx-leitura");
  if (cx.sel !== id) { cx.sel = id; desenharCorreio(); }
  abrirEnvioNF(null, { id, comNF: modo === "nf", encaminhar: modo === "enc", citacao: citacaoHtml(id) }, alvo);
}
// semFicha: as setas ↑ ↓ andam pela lista mostrando a leitura de sempre (a ficha do hóspede abre no clique), e "Abrir e-mail do pedido" também.
function abrirEmail(id, semFicha = false) {
  if (typeof envNF !== "undefined" && envNF && envNF.alvo && cx.sel !== id) { toast("Envie ou descarte a mensagem que está escrevendo", true); return; }
  cx.sel = id;
  const e = itemSelecionado();
  // Chegou um formulário (João, 09/11/2026): abre a ficha do hóspede no lugar do leitor. E-mail normal segue a leitura de sempre.
  const ficha = !semFicha && !cx.semFicha && typeof emailEhFormulario === "function" && emailEhFormulario(e);
  if (ficha) abrirHospedeDoEmail(e); else desenharCorreio();
  if (!e) return;
  carregarTexto(e);
  const alvoH = alvoHistorico(e);
  if (alvoH) carregarHistorico(alvoH.de);
  preCarregarAnexos(e);
  if (e.lido === false && !cx.manterNaoLido[e.id]) {   // abriu = lido (pra equipe toda)
    api("/api/correio/evento", { ids: [e.id], acao: "LIDO" });
    e.lido = true;
    if (cx.dados?.contagem) cx.dados.contagem.entrada_nao_lidos = Math.max(0, cx.dados.contagem.entrada_nao_lidos - 1);
    desenharLateralCorreio(); if (!ficha) desenharCorreio();
  }
  delete cx.manterNaoLido[e.id];
}
async function carregarTexto(e) {
  const chave = e.id;
  if (cx.textos[chave]) return;
  cx.textos[chave] = { carregando: true };
  const espelho = (cx.dados?.emails || []).some(x => x.id === e.id) || (cx.dados?.enviados || []).some(x => x.id === e.id);
  const q = new URLSearchParams({ id: espelho ? e.id : "", pc: e.pc || "", entry: e.entry || "" });
  const r = await api("/api/correio/texto?" + q);
  cx.textos[chave] = r.erro ? { erro: r.erro } : r;
  if (cx.sel === chave || cx.hist.aberto === chave) desenharLeituraCorreio();   // pré-carregado: só guarda
  if (typeof hospedeTextoChegou === "function") hospedeTextoChegou(chave);   // a ficha do hóspede esperava o texto do formulário
}
// Abrir na hora (usuário, 15/10/2026: "quando eu clicar, abrir instantaneamente"): o texto dos primeiros e-mails da
// lista e dos vizinhos do aberto já vem antes do clique; as fotos do e-mail aberto também
let preFila = [], preAtivos = 0;
function preCarregar(lista) {
  const i = lista.findIndex(e => e.id === cx.sel);
  const alvos = [...(i >= 0 ? [lista[i + 1], lista[i - 1], lista[i + 2]] : []), ...lista.slice(0, 15)]
    .filter(e => e && !cx.textos[e.id] && e.pasta !== "excluido");
  preFila = [...new Map(alvos.map(e => [e.id, e])).values()];
  puxarFila();
}
function puxarFila() {
  while (preAtivos < 2 && preFila.length) {
    const e = preFila.shift();
    if (cx.textos[e.id]) continue;
    preAtivos++;
    carregarTexto(e).finally(() => { preAtivos--; puxarFila(); });
  }
}
async function preCarregarAnexos(e) {
  const fotos = (e.anexos || []).filter(n => /\.(png|jpe?g|gif|webp|bmp)$/i.test(n)).slice(0, 3);
  for (const nome of fotos) {
    const k = e.id + "|" + nome;
    if (visor.urls[k]) continue;
    const q = new URLSearchParams({ id: noEspelhoDoPainel(e) ? e.id : "", pc: e.pc || "", entry: e.entry || "", nome });
    const r = await api("/api/correio/anexo?" + q);
    if (r.erro || !r.b64 || visor.urls[k]) continue;
    const bin = atob(r.b64), bytes = new Uint8Array(bin.length);
    for (let j = 0; j < bin.length; j++) bytes[j] = bin.charCodeAt(j);
    visor.urls[k] = { url: URL.createObjectURL(new Blob([bytes], { type: r.tipo })), tipo: r.tipo, tamanho: r.tamanho };
  }
}
async function carregarHistorico(de) {   // tudo do hóspede no Outlook dos PCs (qualquer pasta e data) + formulários
  if (cx.hist[de]) return;
  // na hora: o que o Painel já tem deste endereço (caixa de entrada e enviados); a busca nos 4 PCs completa depois
  const doEnd = x => x.de === de || String(x.para || "").toLowerCase().includes(String(de).toLowerCase());
  const locais = [...(cx.dados?.emails || []).map(x => ({ ...x, pasta: x.pasta || "entrada" })),
                  ...(cx.dados?.enviados || []).map(x => ({ ...x, pasta: "enviado" }))].filter(doEnd);
  cx.hist[de] = { resultados: locais, pcs: {}, agentes: {}, conv: null, parcial: true };
  desenharLeituraCorreio();
  const juntar = (lista, extra) => { const vistos = new Set(lista.map(x => x.id)); extra.forEach(x => vistos.has(x.id) || (vistos.add(x.id), lista.push(x))); };
  api("/api/correio/conversa?de=" + encodeURIComponent(de)).then(conv => {
    if (!cx.hist[de] || conv.erro) return;
    cx.hist[de].conv = conv; desenharLeituraCorreio();
    const outros = (conv.enderecos || []).slice(0, 2);   // hóspede único: os outros endereços dele (mesmo CPF/CNPJ)
    outros.forEach(x => api("/api/correio/buscar?q=" + encodeURIComponent(x)).then(rx => {
      juntar(cx.hist[de].resultados, (rx.resultados || []).filter(y => y.de === x || (y.para || "").includes(x))); desenharLeituraCorreio(); }));
  });
  const r = await api("/api/correio/buscar?q=" + encodeURIComponent(de));
  if (!cx.hist[de]) return;
  juntar(cx.hist[de].resultados, (r.resultados || []).filter(x => x.de === de || (x.para || "").includes(de)));
  Object.assign(cx.hist[de], { pcs: r.pcs || {}, agentes: r.agentes || {}, parcial: false });
  desenharLeituraCorreio();
}

function corpoTexto(chave) {
  const t = cx.textos[chave];
  if (!t || t.carregando) return `<p class="dica">Abrindo o e-mail no Outlook do PC dono…</p>`;
  if (t.erro) return `<p class="dica erro-txt">${esc(t.erro)}</p>`;
  return `<div class="cx-texto">${esc(t.texto || "(sem texto)")}</div>` + (t.citado ? `<details class="cx-citado"><summary>Mostrar mensagens anteriores</summary>
    <div class="cx-texto">${esc(t.citado)}</div></details>` : "") +
    (t.origem && !["ao vivo", "este PC"].includes(t.origem) ? `<p class="dica">${esc(t.origem)}</p>` : "");
}
// Anexos clicáveis (usuário, 14/10/2026): a foto ou o PDF do hóspede abre aqui mesmo, pedido ao vivo pro PC dono
const anexosHtml = (an, alvo) => {
  if (!an?.length) return "";
  const chave = alvo ? (alvo.id || alvo.entry || "") : "";
  if (chave) (cx.anexoAlvos ||= {})[chave] = { id: alvo.id_espelho ?? alvo.id ?? "", pc: alvo.pc || "", entry: alvo.entry || "", nomes: an };
  return `<div class="cx-anexos">${an.map((a, i) => `<button type="button" class="cx-anexo" ${chave ? `data-anexo="${esc(chave)}" data-i="${i}"` : "disabled"}
    title="Ver aqui no Painel"><b>${esc(String(a).split(".").pop().toUpperCase().slice(0, 4))}</b>${esc(a)}</button>`).join("")}</div>`;
};
const noEspelhoDoPainel = e => (cx.dados?.emails || []).some(x => x.id === e.id) || (cx.dados?.enviados || []).some(x => x.id === e.id);
const visor = { chave: "", i: 0, urls: {} };
function abrirVisor(chave, i) {
  const alvo = cx.anexoAlvos?.[chave];
  if (!alvo) return;
  visor.chave = chave; visor.i = Math.max(0, Math.min(i, alvo.nomes.length - 1));
  let el = $("visor");
  if (!el) { el = document.createElement("div"); el.id = "visor"; el.className = "visor-fundo"; document.body.appendChild(el); }
  el.classList.remove("oculta");
  desenharVisor();
}
async function desenharVisor() {
  const el = $("visor"), alvo = cx.anexoAlvos?.[visor.chave];
  if (!el || !alvo) return;
  const nome = alvo.nomes[visor.i], k = visor.chave + "|" + nome, n = alvo.nomes.length;
  const cab = (extra = "") => `<div class="visor" role="dialog" aria-label="Anexo ${esc(nome)}"><div class="visor-cab">
      <b title="${esc(nome)}">${esc(nome)}</b>${n > 1 ? `<span class="visor-n">${visor.i + 1} de ${n}</span>
      <button type="button" data-visor="-1" aria-label="Anexo anterior">‹</button><button type="button" data-visor="1" aria-label="Próximo anexo">›</button>` : ""}
      ${extra}<button type="button" class="visor-x" data-visor-fechar aria-label="Fechar">×</button></div>`;
  const u = visor.urls[k];
  if (!u) {
    el.innerHTML = cab() + `<div class="visor-corpo"><div class="vazio">Pedindo o anexo ao Outlook do PC dono…</div></div></div>`;
    const q = new URLSearchParams({ id: alvo.id || "", pc: alvo.pc || "", entry: alvo.entry || "", nome });
    const r = await api("/api/correio/anexo?" + q);
    if (r.erro || !r.b64) { visor.urls[k] = { erro: r.erro || "não veio o arquivo" }; }
    else {
      const bin = atob(r.b64), bytes = new Uint8Array(bin.length);
      for (let j = 0; j < bin.length; j++) bytes[j] = bin.charCodeAt(j);
      visor.urls[k] = { url: URL.createObjectURL(new Blob([bytes], { type: r.tipo })), tipo: r.tipo, tamanho: r.tamanho };
    }
    if (visor.chave + "|" + alvo.nomes[visor.i] !== k) return;   // trocou de anexo enquanto carregava
    return desenharVisor();
  }
  if (u.erro) { el.innerHTML = cab() + `<div class="visor-corpo"><div class="vazio">Não deu para abrir: ${esc(u.erro)}</div></div></div>`; return; }
  const baixar = `<a class="visor-baixar" href="${u.url}" download="${esc(nome)}">Baixar</a>`;
  const corpo = u.tipo.startsWith("image/") ? `<img src="${u.url}" alt="${esc(nome)}" class="visor-img" data-visor-zoom>`
    : u.tipo === "application/pdf" || u.tipo.startsWith("text/") ? `<iframe src="${u.url}" title="${esc(nome)}" class="visor-pdf"></iframe>`
    : `<div class="vazio">Esse tipo de arquivo não dá para mostrar aqui.<br>Use "Baixar" para abrir no programa do PC.</div>`;
  el.innerHTML = cab(baixar) + `<div class="visor-corpo">${corpo}</div></div>`;
}
function fecharVisor() { $("visor")?.classList.add("oculta"); }
document.addEventListener("click", ev => {
  const a = ev.target.closest("[data-anexo]");
  if (a) { ev.stopPropagation(); return abrirVisor(a.dataset.anexo, Number(a.dataset.i)); }
  if (ev.target.closest("[data-visor-fechar]") || ev.target.id === "visor") return fecharVisor();
  const m = ev.target.closest("[data-visor]");
  if (m) { visor.i = (visor.i + Number(m.dataset.visor) + cx.anexoAlvos[visor.chave].nomes.length) % cx.anexoAlvos[visor.chave].nomes.length; return desenharVisor(); }
  const z = ev.target.closest("[data-visor-zoom]");
  if (z) z.classList.toggle("grande");
});
window.addEventListener("keydown", ev => {   // com o visor aberto, as teclas são dele (Delete não exclui o e-mail de trás)
  if (!$("visor") || $("visor").classList.contains("oculta")) return;
  ev.stopPropagation();
  if (ev.key === "Escape") { ev.preventDefault(); fecharVisor(); }
  if (ev.key === "ArrowRight" || ev.key === "ArrowLeft") { ev.preventDefault(); const n = cx.anexoAlvos[visor.chave].nomes.length;
    visor.i = (visor.i + (ev.key === "ArrowRight" ? 1 : -1) + n) % n; desenharVisor(); }
}, true);
