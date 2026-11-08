// correio_ficha.js: parte de correio.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// Ficha do pedido (creme), no topo do e-mail como na prévia: tomador, documento, o que pede, nota, prazo e os 3 botões
// Resumo fixo do hóspede (usuário, 21/10/2026: desenho Pr1/Pr2 do quadro): a faixa parada no topo do e-mail com quem
// é, as etiquetas, o prazo, o que ele quer e os botões. "Ver ficha completa" abre a tabela do pedido (peça formularioHtml).
function dadosDoResumo(e) {
  const ped = pedidoDoEmail(e), d = ped || dadosDoFormulario(e);
  if (!d) return { ped: null, dados: null };
  const c = (...r) => campoDoPedido(d, ...r);
  return { ped, dados: d, tom: c(/nome.*tomador/, /razao social/, /^nome( completo)?$/),
           doc: c(/documento.*tomador/, /cpf.*cnpj|cnpj.*cpf/, /^cnpj/, /^cpf(?!.*titular)/), pede: c(/informac/, /o que.*nota/, /itens/),
           tit: c(/nome.*titular/, /nome do hospede/, /^hospede/), ci: c(/check.?in/), co: c(/check.?out/) };
}
function resumoFixoHtml(e, entra = false) {
  // Etapas do pedido (27/10/2026, opção C): ficha única no topo; as regras estão em pecas/etapas.js
  if (e.pasta === "enviado") return "";
  const r = dadosDoResumo(e), ehForm = (e.classes || []).includes("formulario"), ped = r.ped;
  const nome = r.tit || (soDigitos(r.doc || "").length === 11 ? r.tom : "") || (ehForm ? r.tom || "Hóspede do formulário" : e.nome || e.de || "");
  const c = cx.cobre?.[e.id] && !cx.cobre[e.id].carregando ? cx.cobre[e.id] : null;
  const alvoH = alvoHistorico(e), h = alvoH ? cx.hist[alvoH.de] : null;
  const enviadas = (c?.nfs || []).length ? c.nfs.map(n => ({ nf: n.nf, quando: "" })) : (h?.conv?.nfs_enviadas || []).map(v => ({ nf: (v.nfs || []).join(", "), quando: v.quando || "" }));
  const [docF, docT] = r.doc ? valorDoForm("CPF/CNPJ", r.doc) : ["", ""];
  const [datas, diarias] = r.ci && r.co ? valorDoForm("Datas", `${r.ci} → ${r.co}`) : ["", ""];
  const campo = (...t) => r.dados ? campoDoPedido(r.dados, ...t) : "";
  const partes = ped?.partes > 1 ? ped.partes : campo(/dividida em|quantas vezes/);
  const m = etapasModelo({
    hora: e.quando ? String(e.quando).slice(11, 16) : "", falta: ped && typeof faltaDados === "function" ? faltaDados(ped) : [], semFormulario: !r.dados,
    tom: r.tom, doc: docF, docRot: docT || "CPF / CNPJ", datas, diarias, valor: campo(/valor.*nota/), pede: r.pede,
    divisao: ped?.dividida || ped?.partes > 1 || (e.quartos?.[0] || e.quartos || 0) >= 2 ? `Dividir em ${partes || 2} notas` : "",
    reserva: campo(/estada|reserva/), titular: r.tit, notas: e.notas || [], nfsEnviadas: enviadas,
    situacaoPedido: ped ? situacaoDoPedido(ped) : "", cobre: c, temPedido: !!ped, reconhece: RECONHECE_NF });
  const onde = [e.hotel || ped?.hotel || "", e.pc ? "PC de " + nomeAgente(e.pc) + (pcOnline(e.pc) ? "" : " (desligado)") : ""].filter(Boolean).join(" · ");
  const podeAbrir = !!r.dados && !ehForm, aberta = podeAbrir && !!cx.fichaAberta;
  return etapasTelaHtml(m, e, { nome, prazo: prazoInfo(ped?.prazo || e.prazo), onde, chave: ped?.chave || "", entra, podeAbrir, aberta,
    fichaHtml: aberta ? formularioHtml(r.dados, e) : "" });
}
try { cx.fichaAberta = localStorage.getItem("painel.fichaAberta") === "1"; } catch (e) { cx.fichaAberta = false; }
document.addEventListener("click", ev => {
  if (!ev.target.closest?.("[data-resumo-ficha]")) return;
  cx.fichaAberta = !cx.fichaAberta;
  try { localStorage.setItem("painel.fichaAberta", cx.fichaAberta ? "1" : ""); } catch (e) { /* sem armazenamento: só nesta janela */ }
  desenharLeituraCorreio();
});
// Pedido repetido no e-mail (usuário, 21/10/2026: "1 · Mostrar no e-mail", desenho Pr3): o robô já junta os formulários
// iguais (mesmo hotel, CPF/CNPJ, datas e valor; hospedes.marcar); aqui só aparece o aviso e a comparação. Nada é gravado.
function outroDoRepetido(s) {   // o pedido "irmão": o principal (se este é o repetido) ou o 1º repetido (se este é o principal)
  if (!s) return null;
  if (s.repetido_de) return acharPedido(s.repetido_de) || null;
  return s.repetidos?.length ? (acharPedido(s.repetidos[0].chave) || s.repetidos[0]) : null;
}
function linhasComparacao(a, b) {   // [rótulo, este, o outro, diferente?]
  const c = (s, ...r) => campoDoPedido(s, ...r) || "";
  const datas = s => [c(s, /check.?in/), c(s, /check.?out/)].filter(Boolean).join(" → ");
  const situ = s => nomeSituacao(s);
  const doc = s => { const v = c(s, /documento.*tomador/, /cpf.*cnpj|cnpj.*cpf/, /^cnpj/, /^cpf(?!.*titular)/); return v ? valorDoForm("CPF/CNPJ", v)[0] : ""; };
  const linhas = [["Quem", s => c(s, /nome.*titular/, /nome do hospede/) || s.nome || ""], ["CPF/CNPJ", doc],
    ["Nota em", s => c(s, /nome.*tomador/, /razao social/)], ["Hotel", s => s.hotel || ""], ["Datas", datas], ["O que pede", s => c(s, /informac/, /o que.*nota/)],
    ["Pedido em", s => String(s.data || "").slice(0, 10).split("-").reverse().join("/")], ["Situação", situ]];
  return linhas.map(([rot, f]) => { const x = f(a), y = f(b); return [rot, x, y, !["Pedido em", "Situação"].includes(rot) && x !== y]; });
}
function avisoRepetidoHtml(e) {
  const s = pedidoDoEmail(e), outro = outroDoRepetido(s);
  if (!s || !outro) return "";
  const vezes = (s.repetido_de ? (outro.repetidos?.length || 1) : s.repetidos.length) + 1;
  const quando = String(outro.data || "").slice(0, 10).split("-").reverse().join("/");
  const comparar = cx.compararRep === e.id;
  return `<section class="ol-repetido" role="status" aria-label="Pedido repetido">
    <div class="rp1"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/></svg>
      <div><b>Este hóspede já pediu nota desta estadia · ${vezes}x</b>
        <p>Mesmo hotel, CPF/CNPJ e datas: ${s.repetido_de ? "o pedido principal" : "outro formulário"} de ${esc(quando || "outra data")} · ${esc(outro.hotel || "")} · ${esc(nomeSituacao(outro))}. O robô conta como um pedido só: trate pelo principal.</p></div></div>
    <div class="rp-bts"><button type="button" class="p" data-ver-pedido="${esc(outro.chave)}">Abrir o outro pedido</button>
      <button type="button" data-repetido-comparar="${esc(e.id)}" aria-expanded="${comparar}">${comparar ? "Fechar comparação" : "Comparar"}</button></div>
    ${comparar ? `<div class="rp-cmp" role="table"><span class="h"></span><span class="h">Este pedido</span><span class="h">O outro</span>${linhasComparacao(s, outro).map(([r, x, y, d]) =>
      `<span class="k">${esc(r)}</span><span class="${d ? "dif" : ""}">${esc(x || "—")}</span><span class="${d ? "dif" : ""}">${esc(y || "—")}</span>`).join("")}</div>
      <p class="rp-nota">O que é diferente fica em âmbar.</p>` : ""}</section>`;
}
document.addEventListener("click", ev => {
  const b = ev.target.closest?.("[data-repetido-comparar]");
  if (!b) return;
  cx.compararRep = cx.compararRep === b.dataset.repetidoComparar ? "" : b.dataset.repetidoComparar;
  desenharLeituraCorreio();
});
// Formulário aberto como o e-mail que chega no Outlook: o hotel, a solicitação e a tabela Campo / Valor, linha a linha
// Igual ao e-mail do Emissor Automático (Prévia 5, 20/10/2026): "Enviado por", "Dados para emissão de Nota Fiscal:", a
// tabela Campo / Valor numa ordem fixa (os dois formulários caem nela; campo fora da lista vai para o fim) e "Enviado em"
const OCULTOS_FORM = /^(enviado|carimbo|importante|avalia|preenchimento|ritmo|sugest|sincroniz|endereco de e-?mail|e-?mail$)/i;
const ORDEM_FORM = [/^termos/, /documento.*tomador/, /nome.*tomador/, /^cep/, /telefone/, /cpf.*titular/, /nome.*titular/,
  /check.?in/, /check.?out/, /informac/, /^nota dividida/, /dividida em|quantas vezes/, /valor.*nota/];
// Tabela do e-mail arrumada em grupos (usuário, 20/10/2026: escolheu a tela 1 do quadro, em verde e creme): Campo /
// Valor como chega no e-mail, separada em Tomador da nota · Estadia · Como quer a nota; CPF/CNPJ, CEP e telefone
// formatados; o botão copia o valor como o hóspede escreveu (pra colar na emissão).
const GRUPOS_FORM = [
  ["Tomador da nota", [[/nome.*tomador/, "Nome"], [/documento.*tomador/, "CPF/CNPJ"], [/^cep/, "CEP"], [/telefone/, "Telefone"]]],
  ["Estadia", [[/^hotel$/, "Hotel"], [/nome.*titular/, "Titular da reserva"], [/cpf.*titular/, "CPF do titular"], [/^datas$/, "Datas"], [/check.?in/, "Check-in"], [/check.?out/, "Check-out"]]],
  ["Como quer a nota", [[/informac/, "O que pede"], [/^nota dividida/, "Nota dividida"], [/dividida em|quantas vezes/, "Dividir em"], [/valor.*nota/, "Valor"], [/^enviar para$/, "Enviar para"]]],
];
const SEM_COPIAR_FORM = new Set(["Hotel", "Datas", "Check-in", "Check-out", "O que pede", "Nota dividida", "Dividir em"]);
function valorDoForm(rot, v) {   // -> [como mostrar, observação]
  const d = String(v || "").replace(/\D/g, "");
  if (/CPF|CNPJ/.test(rot) && d.length === 11) return [`${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`, "CPF"];
  if (/CPF|CNPJ/.test(rot) && d.length === 14) return [`${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`, "CNPJ"];
  if (rot === "CEP" && d.length === 8) return [`${d.slice(0, 5)}-${d.slice(5)}`, ""];
  if (rot === "Telefone" && (d.length === 10 || d.length === 11)) return [`(${d.slice(0, 2)}) ${d.slice(2, -4)}-${d.slice(-4)}`, ""];
  if (rot === "Datas") {
    const [a, b] = String(v).split(" → ").map(x => x.trim().split("/").map(Number));
    const n = a?.length === 3 && b?.length === 3 ? Math.round((new Date(b[2], b[1] - 1, b[0]) - new Date(a[2], a[1] - 1, a[0])) / 864e5) : 0;
    return [String(v), n > 0 ? `${n} diária${n > 1 ? "s" : ""}` : ""];
  }
  return [String(v), ""];
}
function formularioHtml(s, e = {}) {
  const semAc = x => String(x || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
  const campos = (s.campos || []).filter(([k, val]) => String(val || "").trim() && !OCULTOS_FORM.test(semAc(k)));
  const extras = [["Hotel", s.hotel || e.hotel || ""], ["Enviar para", s.email || ""]].filter(([, v]) => v);
  const usados = new Set(), termos = campos.find(([k]) => /^termos/.test(semAc(k)));
  if (termos) usados.add(termos);
  const ci = campos.find(([k]) => /check.?in/.test(semAc(k))), co = campos.find(([k]) => /check.?out/.test(semAc(k)));
  if (ci && co) { extras.push(["Datas", `${ci[1]} → ${co[1]}`]); usados.add(ci); usados.add(co); }   // como a ficha
  const copiar = '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h10"/></svg>';
  const linha = (rot, val) => {
    const [mostra, obs] = valorDoForm(rot, val);
    return `<div class="fg-l" role="row"><span class="k" role="cell">${esc(rot)}</span><span class="v" role="cell">${esc(mostra)}${obs ? `<small>${esc(obs)}</small>` : ""}</span>${SEM_COPIAR_FORM.has(rot) ? "<span></span>"
      : `<button type="button" class="fg-cp" data-copiar="${esc(val)}" aria-label="Copiar ${esc(rot)}" title="Copiar">${copiar}</button>`}</div>`;
  };
  const grupos = GRUPOS_FORM.map(([titulo, regras]) => {
    const linhas = regras.map(([re, rot]) => {
      const c = [...campos, ...extras].find(x => !usados.has(x) && re.test(semAc(x[0])));
      if (!c) return "";
      usados.add(c);
      return linha(rot, c[1]);
    }).join("");
    return linhas ? `<div class="fg-grp" role="row"><span role="rowheader">${esc(titulo)}</span></div>${linhas}` : "";
  }).join("");
  const resto = campos.filter(c => !usados.has(c));
  const aceitou = termos && /acordo|aceit/i.test(termos[1]);
  return `<div class="ol-form fg">${s.email ? `<div class="por">Enviado por: <span class="lnk">${esc(s.email)}</span></div>` : ""}
    <h3>Dados para emissão de Nota Fiscal</h3>
    <div class="fg-tab" role="table" aria-label="Dados para emissão de Nota Fiscal">
      <div class="fg-cab" role="row"><span role="columnheader">Campo</span><span role="columnheader">Valor</span><span role="columnheader" aria-label="Copiar"></span></div>
      ${grupos}${resto.length ? `<div class="fg-grp" role="row"><span role="rowheader">Outros campos</span></div>${resto.map(([k, v]) => linha(k, v)).join("")}` : ""}
    </div>
    <div class="fg-pe">${termos ? (aceitou ? `<span class="ok"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" aria-hidden="true"><path d="M5 12l5 5L20 7"/></svg>Aceitou os termos</span>`
      : `<span><b>Termos de aceite:</b> ${esc(termos[1])}</span>`) : ""}<span><b>Enviado em:</b> ${esc(s.carimbo || dataBr(s.data) || "")}</span></div></div>`;
}
// E-mail do Emissor Automático sem o pedido na lista do Painel: os campos saem do próprio texto ("Campo<tab>Valor")
const ROTULOS_FORM = ["Termos de aceite", "Documento Tomador", "Nome Tomador", "CEP", "Telefone para contato", "CPF do Titular da Reserva",
  "Nome do Titular da Reserva", "Check-in da Hospedagem", "Check-out da Hospedagem", "Informações necessárias na Nota Fiscal",
  "Nota Dividida", "Dividida em quantas vezes", "Valor da Nota"];
function formDoTexto(texto) {
  const t = String(texto || "").replace(/\r/g, "");
  if (!/dados para emiss[aã]o de nota fiscal/i.test(t) || !/^\s*campo\s+valor\s*$/im.test(t)) return null;
  const linhas = t.split("\n"), ini = linhas.findIndex(l => /^\s*campo\s+valor\s*$/i.test(l));
  const campos = [];
  for (const l of linhas.slice(ini + 1)) {
    if (/^\s*enviado em\s*:/i.test(l)) break;
    if (!l.trim()) continue;
    let partes = l.split(/\t+| {2,}/).map(x => x.trim()).filter(Boolean);
    if (partes.length < 2) {
      const r = ROTULOS_FORM.find(x => l.trim().toLowerCase().startsWith(x.toLowerCase() + " "));
      partes = r ? [r, l.trim().slice(r.length).trim()] : partes;
    }
    if (partes.length >= 2) campos.push([partes[0], partes.slice(1).join(" ")]);
  }
  if (!campos.length) return null;
  const por = t.match(/enviado por\s*:\s*([^\s<]+@[^\s<>]+)/i), em = t.match(/enviado em\s*:\s*(.+)/i);
  return { campos, email: por ? por[1] : "", carimbo: em ? em[1].replace(/\s*GMT.*$/, "").trim() : "" };
}
document.addEventListener("click", ev => {
  const b = ev.target.closest?.(".ol-form [data-copiar]");
  if (!b) return;
  const txt = b.dataset.copiar;
  (navigator.clipboard?.writeText(txt) || Promise.reject()).then(() => toast(`Copiado: ${txt.length > 40 ? txt.slice(0, 40) + "…" : txt}`),
    () => toast("Não deu pra copiar agora", true));
});
function desenharLeituraCorreio() {
  desenharAcoes();
  const el = $("cx-leitura");
  if (typeof envNF !== "undefined" && envNF && envNF.alvo === el) return;   // escrevendo uma resposta: não apaga
  const e = cx.sel && itemSelecionado();
  if (!e) {   // a leitura fica sempre à direita, como no Outlook
    el.innerHTML = `<div class="ol-vazio"><svg aria-hidden="true"><use href="#i-mail"/></svg><b>Selecione um e-mail para ler</b>
      <span>Clique numa linha da lista · as setas ↑ ↓ andam pelos e-mails</span></div>`;
    return;
  }
  if (document.activeElement && el.contains(document.activeElement) && /INPUT|TEXTAREA|SUMMARY/.test(document.activeElement.tagName)) return;
  const enviado = e.pasta === "enviado", robo = (e.classes || []).includes("formulario");
  const alvoH = alvoHistorico(e), h = alvoH ? cx.hist[alvoH.de] : null;
  if (alvoH && !cx.hist[alvoH.de]) setTimeout(() => carregarHistorico(alvoH.de), 0);   // e-mail de quem preencheu saiu do texto agora
  const noEspelho = (cx.dados?.emails || []).some(x => x.id === e.id), cinza = !!cx.resolvendo[e.id];
  const nome = enviado ? nomeDaCaixa(String(e.caixa || "").toLowerCase()) : (e.nome || e.de || "");
  const ender = enviado ? e.caixa : e.de;
  const para = enviado ? e.para : (e.caixa || e.para || "");
  const onde = [e.hotel, e.pc ? "PC de " + nomeAgente(e.pc) + (pcOnline(e.pc) ? "" : " (desligado)") : ""].filter(Boolean).join(" · ");
  const botoes = noEspelho && !cinza ? `<div class="ol-bts"><button type="button" data-cx-faixa="resp">${SVG(IC.resp)} Responder</button>
      <button type="button" data-cx-faixa="resp">${SVG(IC.todos)} Responder a todos</button><button type="button" data-cx-faixa="enc">${SVG(IC.enc)} Encaminhar</button>
      <button type="button" data-ol-menu aria-label="Mais ações" aria-expanded="${cx.menu}">⋯</button></div>
      ${cx.menu ? `<div class="ol-menu" role="menu"><button type="button" data-cx-faixa="nf">Responder com a NF</button>
        <button type="button" data-cx-faixa="lido">${e.lido === false ? "Marcar como lido" : "Marcar como não lido"}</button>
        <button type="button" class="perigo" data-cx-faixa="exc">Excluir</button></div>` : ""}`
    : `<span class="ol-sit">${cinza ? "Respondido · sai da caixa quando o Outlook do PC dono confirmar" : enviado ? "E-mail enviado · só leitura" : (PASTAS[e.pasta] || "") + " no Outlook · só leitura"}</span>`;
  // como o Outlook (Prévia 5, 20/10/2026): cabeçalho, de onde veio, anexos, a ficha e o texto alinhado com o nome
  const ped = pedidoDoEmail(e), dividida = (e.quartos?.[0] || e.quartos || 0) >= 2 || !!(ped && (ped.dividida || ped.partes > 1));
  const anexos = anexosHtml(e.anexos, { id: e.id, id_espelho: noEspelhoDoPainel(e) ? e.id : "", pc: e.pc, entry: e.entry || "" });
  if (RECONHECE_NF && !enviado && !robo && !(cx.cobre && cx.cobre[e.id])) setTimeout(() => carregarCobre(e.id), 0);   // NF enviada x o que ele pede
  const entra = cx.animou !== e.id ? " ol-entra" : "";
  cx.animou = e.id;
  const cab = enviado ? `<div class="ol-cab"><h1>${esc(e.assunto || "(sem assunto)")}</h1>
      <div class="ol-rem"><span class="ol-av robo" aria-hidden="true">↗</span>
        <div class="ol-q"><b>${esc(nome)} ${ender && ender !== nome ? `<small>&lt;${esc(ender)}&gt;</small>` : ""}</b><span><span class="rot-para">Para</span><i>${esc(para)}</i></span>
          ${(e.classes || []).filter(c => CLASSES[c]).length ? `<span>${e.classes.map(etiqueta).join(" ")}</span>` : ""}</div>
        <div class="ol-acoes">${botoes}<time>${esc(dataLonga(e.quando))}</time>
          <button type="button" class="link" id="cx-fechar" title="Fechar (Esc)" style="font-size:12px">fechar ✕</button></div></div></div>
    ${onde ? `<p class="ol-info"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8v.5"/></svg>${esc(onde)}</p>` : ""}`
    // opção C (27/10/2026): o remetente, "Pedido de NF", PC e os botões repetidos saíram; Responder fica na faixa do topo e no Outlook
    : `${resumoFixoHtml(e, !!entra)}${avisoRepetidoHtml(e)}<div class="c-msg"><h1>${esc(e.assunto || "(sem assunto)")}</h1>
      <div class="c-de"><span>${esc(nome)}${ender && ender !== nome ? ` &lt;${esc(ender)}&gt;` : ""} · para ${esc(para)} · ${esc(dataLonga(e.quando))}</span>
        ${noEspelho && !cinza ? "" : `<span class="c-sit">${cinza ? "Respondido · sai da caixa quando o Outlook do PC dono confirmar" : (PASTAS[e.pasta] || "") + " no Outlook · só leitura"}</span>`}
        <button type="button" class="c-fechar" id="cx-fechar" title="Fechar (Esc)">fechar ✕</button></div></div>`;
  el.innerHTML = `<div class="ol-leitura${entra}">${cab}
    ${anexos ? `<div class="ol-anexos">${anexos}</div>` : ""}
    ${e.alerta_doc ? `<div class="cx-verifica"><b>NF com CPF/CNPJ diferente do pedido</b><div>${esc(e.alerta_doc)}</div>
      <div class="dica">O robô abriu a nota deste hóspede e comparou com o formulário. Confira antes de responder.</div></div>` : ""}
    ${verificacaoHtml(e)}${enviado || !RECONHECE_NF ? "" : (cx.cobre?.[e.id]?.historico?.itens?.length && !cx.cobre[e.id].nfs?.length ? historicoNfHtml(cx.cobre[e.id]) : "")}
    <div class="ol-corpo">${robo && ped ? formularioHtml(ped, e) : (() => { const f = formDoTexto(cx.textos[e.id]?.texto); return f ? formularioHtml(f, e) : corpoTexto(e.id); })()}</div></div>`;
}

// NF já enviada x o que o hóspede pede agora (27/10/2026): nunca tira o e-mail da entrada sozinha; o Concluir é um clique da pessoa
async function carregarCobre(id) {
  cx.cobre = cx.cobre || {};
  if (cx.cobre[id]) return;
  cx.cobre[id] = { nfs: [], carregando: true };
  let r;
  try { r = await api("/api/nf_cobre?id=" + encodeURIComponent(id)); } catch (e) { r = null; }
  cx.cobre[id] = r && !r.erro && r.nfs ? r : { nfs: [] };
  if (cx.sel === id) desenharLeituraCorreio();
}
function nfCobreHtml(e) {
  const c = cx.cobre?.[e.id];
  if (!c || c.carregando || (!c.nfs?.length && !c.historico?.itens?.length)) return "";
  if (!c.nfs?.length) return historicoNfHtml(c);   // sem NF enviada ainda: só o histórico x notas prontas
  const nfs = c.nfs.map(n => `<span class="rf-chip">NF ${esc(n.nf)}${n.pdf ? ` · ${esc(n.pdf)}` : ""}</span>`).join(" ");
  const linhas = (c.linhas || []).map(l => `<div class="cobre-l ${l.ok === true ? "s" : l.ok === false ? "n" : ""}"><i>${l.ok === true ? "✓" : l.ok === false ? "✗" : "•"}</i><span><b>${esc(l.rotulo)}</b> ${esc(l.texto)}</span></div>`).join("");
  const aviso = (c.avisos_envio || []).length ? `<div class="cobre-f am">Marcado como enviado, mas não achei o envio da NF ${esc(c.avisos_envio.join(", "))} nos Itens Enviados. A resposta do hóspede com a nota anexada não conta como envio.</div>` : "";
  const faixa = c.pede_nova ? `<div class="cobre-f vm">Pede nova nota: ${esc((c.motivos || [])[0] || "")}. Foi para Urgência.</div>`
    : c.sugere_concluir ? `<div class="cobre-f az">Tudo bate com a NF ${esc(c.nfs.map(n => n.nf).join(", "))}. Pode concluir.</div>`
    : c.cobre === null ? `<div class="cobre-f am">Não consegui ler a nota enviada: confira antes de concluir.</div>` : "";
  return `<section class="cx-cobre ${c.pede_nova ? "cb-no" : c.sugere_concluir ? "cb-ok" : "cb-at"}" aria-label="NF já enviada"><div class="cobre-cab"><b>NF enviada</b>${nfs}</div>
    ${linhas}${aviso}${faixa}${c.historico?.itens?.length ? historicoNfHtml(c, true) : ""}<div class="cobre-bt"><button type="button" class="${c.sugere_concluir ? "p dest" : ""}" data-nf-concluir="${esc(e.id)}">Concluir</button>
    <span class="dica">Move a conversa inteira para a pasta “NF enviada”. Nada é apagado.</span></div></section>`;
}
function historicoNfHtml(c, dentro = false) {
  const h = c.historico;
  if (!h?.itens?.length) return "";
  const linhas = h.itens.map(i => `<div class="cobre-l ${i.ok ? "s" : "n"}"><i>${i.ok ? "✓" : "✗"}</i><span><b>${esc(i.nome)}</b> R$ ${esc(i.valor)}${i.datas ? ` · ${esc(i.datas)}` : ""}${
    i.nf ? ` → <b>NF ${esc(i.nf)}</b>` : ""} <span class="dica">${esc(i.detalhe)}</span></span></div>`).join("");
  const falta = h.itens.filter(i => !i.ok);
  const faixa = h.completo ? `<div class="cobre-f az">Todas as notas que o hóspede pediu (${h.itens.length}) estão prontas nas pastas e conferem com o histórico dele. Falta enviar.</div>`
    : `<div class="cobre-f am">Do histórico dele ainda falta: ${esc(falta.map(i => i.nome + (i.nf ? " (confira a NF " + i.nf + ")" : "")).join(", "))}.</div>`;
  const corpo = `<div class="cobre-cab"><b>Histórico do hóspede x notas prontas</b>${(c.prontas || []).map(n => `<span class="rf-chip">NF ${esc(n.nf)}</span>`).join(" ")}</div>${linhas}${faixa}`;
  return dentro ? `<div class="cobre-hist">${corpo}</div>` : `<section class="cx-cobre ${h.completo ? "cb-ok" : "cb-at"}" aria-label="Histórico do hóspede x notas">${corpo}
    <div class="cobre-bt"><span class="dica">Compara tudo o que ele escreveu (inclusive as mensagens anteriores) com as notas das pastas. Nada é enviado nem movido.</span></div></section>`;
}
function concluirConversa(id) {
  const e = (cx.dados?.emails || []).find(x => x.id === id);
  if (!e || document.querySelector(".modal-fundo")) return;
  const c = cx.cobre?.[id] || {};
  const conversa = (cx.dados?.emails || []).filter(x => x.de === e.de && x.pasta !== "enviado");
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `<div class="modal" style="width:min(520px,94vw)"><div class="modal-topo"><div><h3>Mover a conversa para “NF enviada”?</h3>
      <div class="sub">${esc(e.nome || e.de)} · ${conversa.length} e-mail${conversa.length === 1 ? "" : "s"}</div></div></div>
    <div class="ficha-corpo" style="padding:16px 22px">Os e-mails deste hóspede saem da Caixa de Entrada e vão para a pasta <b>“NF enviada” da caixa ${esc(e.caixa || "")}</b>,
      no Outlook de ${esc(nomeAgente(e.pc))}. Nada é apagado. Fica registrado que foi você.
      ${c.pede_nova ? `<div class="cobre-f vm" style="margin-top:10px">Atenção: o Painel acha que este hóspede pede nova nota (${esc((c.motivos || [])[0] || "")}).</div>` : ""}</div>
    <div class="modal-rodape"><button id="nfc-nao">Cancelar</button><button class="p" id="nfc-sim">Mover</button></div></div>`;
  document.body.appendChild(fundo);
  $("nfc-nao").onclick = () => fundo.remove();
  $("nfc-sim").onclick = () => {
    fundo.remove();
    conversa.forEach(x => { cx.escondidos[x.id] = true; });
    if (cx.sel === id) cx.sel = null;
    desenharCorreio();
    mostrarDesfazer("Conversa movida para “NF enviada”", () => { conversa.forEach(x => delete cx.escondidos[x.id]); desenharCorreio(); }, async () => {
      const r = await api("/api/correio/concluir", { id });
      if (!r.ok) { conversa.forEach(x => delete cx.escondidos[x.id]); toast(r.motivo || "Não deu pra mover", true); }
      carregarCorreio();
    }, "Movimento desfeito");
  };
}
document.addEventListener("click", ev => { const b = ev.target.closest?.("[data-nf-concluir]"); if (b) concluirConversa(b.dataset.nfConcluir); });

// Verificação da NF (Etapa 2): 1 motivo principal em destaque, o que a NF diz, a comparação e o resto que ele citou
function verificacaoHtml(e) {
  const a = e.analise_d;
  if (!a) return e.analise ? `<div class="cx-verifica"><b>Verificação da NF</b><div>${esc(e.analise)}</div>
    <div class="dica">O robô abriu a NF (anexada ou no Dropbox) e cruzou com o que o cliente escreveu. Confira antes de reenviar.</div></div>` : "";
  return `<div class="cx-verifica"><b>Verificação da NF</b>
    <div class="cx-motivo">Motivo: ${esc(a.m)}${a.d ? ` <small>(${esc(a.d)})</small>` : ""}</div>
    <div>${esc(a.nf || "")}</div>${(a.c || []).map(c => `<div>${c.startsWith("⚠") ? `<b style="text-transform:none;letter-spacing:0">${esc(c)}</b>` : "· " + esc(c)}</div>`).join("")}
    ${a.o?.length ? `<div class="cx-tambem">também citou: ${esc(a.o.join(", "))}</div>` : ""}
    <div class="dica">O robô abriu a NF (anexada ou no Dropbox) e cruzou com o que o cliente escreveu. Confira antes de reenviar.</div></div>`;
}

// Histórico do hóspede (usuário, 20/10/2026): no formulário o remetente é o Emissor Automático (o mesmo de todos os
// hotéis), então o histórico vai pelo e-mail de quem preencheu e, quando dá, só desta hospedagem: mesmo hotel, desde
// DIAS_ANTES_CHECKIN dias antes do check-in. Sem check-in: tudo do hóspede. Sem o e-mail de quem preencheu: sem histórico.
const DIAS_ANTES_CHECKIN = globalThis.aj?.("tela.dias_antes_checkin") ?? 30;
function alvoHistorico(e) {
  if (!e || e.pasta === "enviado") return null;
  if (!(e.classes || []).includes("formulario")) return e.de ? { de: e.de } : null;
  const ped = pedidoDoEmail(e), f = ped ? null : formDoTexto(cx.textos[e.id]?.texto);
  const de = String(ped?.email || f?.email || "").trim().toLowerCase();
  if (!de.includes("@")) return null;
  const ci = ((ped || f)?.campos || []).find(([k]) => /check.?in/i.test(String(k)))?.[1] || "";
  const m = String(ci).match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (!m) return { de };
  const d = new Date(+m[3], +m[2] - 1, +m[1] - DIAS_ANTES_CHECKIN);
  const desde = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  return { de, desde, caixa: String(e.caixa || "").toLowerCase(), hotel: e.hotel || "" };
}
document.addEventListener("click", ev => {
  const b = ev.target.closest?.("[data-hist-tudo]");
  if (!b) return;
  const id = b.dataset.histTudo;
  (cx.histTudo ||= {})[id] = !cx.histTudo[id];
  desenharLeituraCorreio();
});
