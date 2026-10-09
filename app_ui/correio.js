// E-mails: o espelho do Outlook dos 4 PCs (Caixa de entrada, Urgência, Itens enviados) — pedido do usuário, 08/10/2026.
// O Painel não guarda e-mail: o que está aqui é o que está no Outlook agora. Respondeu, fica cinza e some; o texto
// inteiro vem ao vivo do PC dono da caixa; a busca pergunta aos Outlooks dos 4 PCs. Usa api/$/esc/toast/st (index.html).
let cx = { caixa: "entrada", dados: null, sel: null, conv: null, textos: {}, hotel: "", live: null, buscando: "",
           resolvendo: {}, escondidos: {}, desfazer: null, abertoEm: 0, manterNaoLido: {}, enviadoSel: null };
const CAIXAS = { entrada: "Caixa de entrada", urgencia: "Urgência", enviados: "Itens enviados" };
const CLASSES = { corrigir: ["Corrigir / cancelar NF", "erro"], complementar: ["Nota complementar", "atencao"],
  cobranca: ["Cobrança", "atencao"], dados_tomador: ["Dados do tomador", "info"], pedido_nf: ["Pedido de NF", "ok"] };
const PASTAS = { entrada: "Entrada", enviado: "Enviado", excluido: "Excluído" };
const RESOLVENDO_MS = 4 * 60 * 1000;   // cinza até o espelho do PC dono confirmar (até ~2 min) e a linha sumir

async function carregarCorreio() {
  try {
    const j = await api("/api/correio");
    if (!j.conversas) return;
    cx.dados = j;
    const agora = Date.now();
    for (const [k, t] of Object.entries(cx.resolvendo)) if (agora - t > RESOLVENDO_MS) delete cx.resolvendo[k];
    desenharLateralCorreio();
    if (pn.vista === "correio") desenharCorreio();
  } catch (e) { /* a próxima volta tenta de novo */ }
}

const convsDa = caixa => (cx.dados?.conversas || []).filter(c => !cx.escondidos[c.de] && (caixa === "urgencia" ? c.urgente : !c.urgente));
function desenharLateralCorreio() {
  const c = cx.dados?.contagem || {};
  const n = (id, v, alerta) => { const el = $(id); if (!el) return; el.textContent = v ? v.toLocaleString("pt-BR") : "";
    el.classList.toggle("alerta-n", !!(alerta && v)); };
  n("nav-entrada-n", c.entrada_nao_lidos); n("nav-urgencia-n", c.urgencia, true);
  n("nav-enviados-n", (cx.dados?.enviados || []).length);
}

const nomeAgente = pc => (cx.dados?.pcs || []).find(p => p.pc === pc)?.agente || pc;
const pcOnline = pc => !!(cx.dados?.pcs || []).find(p => p.pc === pc)?.online;
const iniciais = n => (String(n || "?").trim().split(/\s+/).slice(0, 2).map(p => p[0]).join("") || "?").toUpperCase();
function horaCurta(iso) {
  if (!iso) return "";
  const d = iso.slice(0, 10);
  return d === hojeIsoF() ? iso.slice(11, 16) : d === ontemIso() ? "Ontem" : d.slice(8, 10) + "/" + d.slice(5, 7);
}
const chipClasse = c => CLASSES[c] ? `<span class="cx-chip c-${CLASSES[c][1]}">${esc(CLASSES[c][0])}</span>` : "";
function textoBusca(c) {
  const u = c.ultimo || c;
  return semAcento([c.nome, c.de, u.assunto, u.previa, (c.hoteis || [c.hotel]).join(" "), u.para,
    (c.classes || []).map(k => CLASSES[k]?.[0]).join(" "), (c.agentes || []).join(" ")].join(" \n "));
}
function passaBusca(c, busca) {
  if (!busca) return true;
  const t = textoBusca(c);
  return semAcento(busca).split(/\s+/).filter(Boolean).every(p => t.includes(p) || soDigitos(t).includes(soDigitos(p)));
}

function desenharCorreio() {
  const v = $("v-correio");
  if (!v) return;
  const busca = $("busca").value.trim();
  const d = cx.dados;
  $("cx-titulo").textContent = busca ? `Busca: “${busca}”` : CAIXAS[cx.caixa];
  // PCs desligados: o espelho deles fica parado na última foto (e as ações esperam o PC ligar)
  const off = (d?.pcs || []).filter(p => !p.online);
  $("cx-avisos").innerHTML = off.length ? `<span class="cx-aviso" title="${esc(off.map(p => `${p.agente || p.pc}: ${p.espelho
      ? "espelho de " + quando(p.espelho) : "ainda sem espelho (Painel sem a versão nova)"}`).join("\n"))}"><span class="dot off"></span>
    Desligado agora: <b>${esc(off.map(p => p.agente || p.pc).join(", "))}</b> · os e-mails deles ficam na última foto e o que for pedido sai quando ligarem</span>` : "";
  let lista;
  if (cx.caixa === "enviados") {
    lista = (d?.enviados || []).filter(e => (!cx.hotel || e.hotel === cx.hotel) && passaBusca(e, busca));
  } else {
    lista = (busca ? (d?.conversas || []).filter(c => !cx.escondidos[c.de]) : convsDa(cx.caixa))
      .filter(c => (!cx.hotel || c.hoteis.includes(cx.hotel)) && passaBusca(c, busca));
    if (cx.caixa === "urgencia" && !busca) lista = lista.slice().sort((a, b) => a.desde.localeCompare(b.desde));   // mais velho primeiro
  }
  desenharFiltrosCorreio(lista.length, busca);
  const vazio = busca ? `Nada com “${esc(busca)}” no espelho.` : cx.caixa === "entrada" ? "Caixa de entrada em dia: nada esperando resposta. 🎉"
    : cx.caixa === "urgencia" ? "Nenhum e-mail em urgência." : "Nada enviado nas últimas 24 h.";
  // a lista é refeita a cada 15 s: quem estava com o foco numa linha continua nela
  const focada = document.activeElement?.closest?.("#cx-lista .cx-linha");
  const chaveFoco = focada && ["cx", "cxEnv", "cxLive"].map(k => focada.dataset[k] && [k, focada.dataset[k]]).find(Boolean);
  $("cx-lista").innerHTML = (lista.length ? lista.map(cx.caixa === "enviados" ? linhaEnviado : linhaConversa).join("")
    : `<div class="vazio">${vazio}</div>`) + blocoBuscaAoVivo(busca);
  if (chaveFoco) [...$("cx-lista").querySelectorAll(".cx-linha")].find(l => l.dataset[chaveFoco[0]] === chaveFoco[1])?.focus();
  desenharLeituraCorreio();
}

function desenharFiltrosCorreio(total, busca) {
  const hoteis = new Set();
  (cx.caixa === "enviados" ? cx.dados?.enviados || [] : convsDa(cx.caixa)).forEach(c => (c.hoteis || [c.hotel]).forEach(h => h && hoteis.add(h)));
  const opcoes = [...hoteis].sort((a, b) => a.localeCompare(b, "pt"));
  if (cx.hotel && !opcoes.includes(cx.hotel)) opcoes.unshift(cx.hotel);
  $("cx-filtros").innerHTML = `<label class="sel"><select id="cx-hotel" aria-label="Filtrar por hotel">
      <option value="">Todos os hotéis</option>${opcoes.map(h => `<option ${h === cx.hotel ? "selected" : ""}>${esc(h)}</option>`).join("")}</select></label>
    ${busca ? `<span class="aviso-busca">Procurando no espelho (o que está sem resposta). Para respondidos e antigos, use “Procurar no Outlook”.</span>` : ""}
    <span class="resultado">${total.toLocaleString("pt-BR")} ${cx.caixa === "enviados" ? (total === 1 ? "e-mail" : "e-mails") : (total === 1 ? "conversa" : "conversas")}</span>`;
  $("cx-hotel").onchange = e => { cx.hotel = e.target.value; desenharCorreio(); };
}

function linhaConversa(c) {
  const u = c.ultimo, cinza = !!cx.resolvendo[c.de], sel = cx.sel === c.de;
  const off = c.pcs.filter(pc => !pcOnline(pc));
  const nf = c.notas?.length ? `<span class="cx-chip c-ok" title="${esc(c.notas.map(n => n.nome).join(" · "))}">NF ${esc(c.notas.map(n => n.nf).join(", "))} emitida</span>` : "";
  return `<div class="cx-linha ${c.nao_lidos && !cinza ? "nao-lido" : ""} ${sel ? "sel" : ""} ${cinza ? "resolvendo" : ""}" role="option"
      tabindex="0" aria-selected="${sel}" data-cx="${esc(c.de)}">
    <span class="cx-av" aria-hidden="true">${esc(iniciais(c.nome))}</span>
    <span class="cx-meio">
      <span class="cx-l1"><b>${esc(c.nome)}</b>${c.total > 1 ? `<span class="cx-qtd" title="${c.total} e-mails sem resposta">${c.total}</span>` : ""}
        ${cinza ? `<span class="cx-chip c-cinza">respondido · saindo da caixa</span>` : ""}</span>
      <span class="cx-l2">${esc(u.assunto || "(sem assunto)")}</span>
      <span class="cx-l3">${esc(u.previa || "")}</span>
      <span class="cx-chips">${c.classes.filter(k => k !== "pedido_nf").map(chipClasse).join("")}${nf}${c.quartos >= 2 ? `<span class="cx-chip c-info">dividida · ${c.quartos} quartos</span>` : ""}
        ${c.falta_nota ? `<span class="cx-chip c-erro">diz que falta nota</span>` : ""}</span>
    </span>
    <span class="cx-dir">
      <span class="cx-hora" title="${esc(quando(u.quando))}">${horaCurta(u.quando)}</span>
      <span class="cx-hotel">${esc(c.hoteis.join(" / "))}</span>
      ${c.urgente ? `<span class="cx-espera">${diasDesde(c.desde) > 7 ? diasDesde(c.desde) + " dias" : "correção"}</span>` : ""}
      ${off.length ? `<span class="cx-off" title="O PC dono desta caixa está desligado: a resposta sai quando ele ligar">PC desligado</span>` : ""}
      ${c.nao_lidos && !cinza ? `<span class="so-leitor">não lido</span>` : ""}
    </span></div>`;
}

function linhaEnviado(e) {
  const sel = cx.enviadoSel === e.id;
  return `<div class="cx-linha ${sel ? "sel" : ""}" role="option" tabindex="0" aria-selected="${sel}" data-cx-env="${esc(e.id)}">
    <span class="cx-av env" aria-hidden="true">↗</span>
    <span class="cx-meio"><span class="cx-l1"><b>Para: ${esc(e.para)}</b></span>
      <span class="cx-l2">${esc(e.assunto || "(sem assunto)")}</span><span class="cx-l3">${esc(e.previa || "")}</span>
      <span class="cx-chips">${e.anexos.length ? `<span class="cx-chip c-cinza">📎 ${esc(e.anexos.join(", "))}</span>` : ""}</span></span>
    <span class="cx-dir"><span class="cx-hora">${horaCurta(e.quando)}</span><span class="cx-hotel">${esc(e.hotel)}</span>
      <span class="cx-hotel">${esc(nomeAgente(e.pc))}</span></span></div>`;
}

// ---------- busca ao vivo nos Outlooks dos 4 PCs ----------
function blocoBuscaAoVivo(busca) {
  if (busca.length < 3) return "";
  if (cx.buscando === busca) return `<div class="cx-live"><div class="anel" style="width:20px;height:20px;border-width:2px"></div>
    Procurando “${esc(busca)}” no Outlook dos PCs ligados (Entrada, Enviados e Excluídos)…</div>`;
  const r = cx.live;
  if (!r || r.termo !== busca) return `<div class="cx-live"><button class="prim" id="cx-buscar-outlook">
    <svg class="ic"><use href="#i-busca"/></svg>Procurar “${esc(busca)}” no Outlook dos 4 PCs</button>
    <span class="dica">Inclui e-mails já respondidos, enviados e excluídos, de qualquer data. Atalho: Enter.</span></div>`;
  const pcs = Object.entries(r.pcs || {}).map(([pc, s]) => `<span class="cx-pc ${s.ok ? "" : "ruim"}">${esc(r.agentes?.[pc] || pc)}:
    ${s.ok ? `${s.achados}${s.completo ? "" : "+"}` : esc(s.erro)}</span>`).join("");
  return `<div class="cx-live-cab"><span class="rot">No Outlook dos PCs · ${r.resultados.length} achados</span>${pcs}</div>` +
    (r.resultados.length ? r.resultados.map(x => `<div class="cx-linha cx-achado ${cx.sel === "live:" + x.id ? "sel" : ""}" role="option" tabindex="0"
        data-cx-live="${esc(x.id)}">
      <span class="cx-av ${x.pasta === "enviado" ? "env" : ""}" aria-hidden="true">${x.pasta === "enviado" ? "↗" : esc(iniciais(x.nome || x.de))}</span>
      <span class="cx-meio"><span class="cx-l1"><b>${esc(x.pasta === "enviado" ? "Para: " + x.para : (x.nome || x.de))}</b>
          <span class="cx-chip c-cinza">${PASTAS[x.pasta] || x.pasta}</span></span>
        <span class="cx-l2">${esc(x.assunto || "(sem assunto)")}</span><span class="cx-l3">${esc(x.previa || "")}</span></span>
      <span class="cx-dir"><span class="cx-hora">${dataBr(x.quando.slice(0, 10))}</span><span class="cx-hotel">${esc(x.hotel)}</span>
        <span class="cx-hotel">${esc(r.agentes?.[x.pc] || x.pc)}</span></span></div>`).join("")
      : `<div class="vazio">Nenhum e-mail com “${esc(busca)}” no Outlook dos PCs que responderam.</div>`);
}
async function buscarNoOutlook() {
  const busca = $("busca").value.trim();
  if (busca.length < 3) return toast("Digite pelo menos 3 letras", true);
  cx.buscando = busca; desenharCorreio();
  const r = await api("/api/correio/buscar?q=" + encodeURIComponent(busca));
  cx.buscando = "";
  if (r.erro) { toast(r.erro, true); cx.live = null; } else cx.live = r;
  if ($("busca").value.trim() === busca) desenharCorreio();
  $("anuncio").textContent = r.resultados ? `${r.resultados.length} e-mails achados no Outlook` : "";
}

// ---------- leitura (conversa do hóspede) ----------
async function abrirConversa(de) {
  cx.sel = de; cx.enviadoSel = null; cx.conv = null; cx.abertoEm = Date.now();
  desenharCorreio();
  const r = await api("/api/correio/conversa?de=" + encodeURIComponent(de));
  if (cx.sel !== de) return;
  cx.conv = r.erro ? { erro: r.erro } : r;
  desenharLeituraCorreio();
  const c = (cx.dados?.conversas || []).find(x => x.de === de);
  if (c && c.nao_lidos && !cx.manterNaoLido[de]) {   // abriu = lido (pra equipe toda)
    const ids = (cx.conv.linha_do_tempo || []).filter(x => x.tipo === "recebido" && !x.lido).map(x => x.id);
    if (ids.length) {
      api("/api/correio/evento", { ids, acao: "LIDO" });
      c.nao_lidos = 0; cx.dados.contagem.entrada_nao_lidos = Math.max(0, (cx.dados.contagem.entrada_nao_lidos || 0) - (c.urgente ? 0 : ids.length));
      desenharLateralCorreio(); desenharCorreio();
    }
  }
  delete cx.manterNaoLido[de];
  (cx.conv.linha_do_tempo || []).filter(x => x.tipo !== "formulario").forEach(x => carregarTexto(x.id, x.pc));
}
async function carregarTexto(id, pc, entry) {
  const chave = id || entry;
  if (cx.textos[chave]) return;
  cx.textos[chave] = { carregando: true };
  const q = new URLSearchParams({ id: id || "", pc: pc || "", entry: entry || "" });
  const r = await api("/api/correio/texto?" + q);
  cx.textos[chave] = r.erro ? { erro: r.erro } : r;
  desenharLeituraCorreio();
}

function blocoTexto(chave) {
  const t = cx.textos[chave];
  if (!t || t.carregando) return `<div class="dica">Buscando o texto no Outlook do PC dono…</div>`;
  if (t.erro) return `<div class="dica erro-txt">${esc(t.erro)}</div>`;
  return `<div class="texto-email">${esc(t.texto || "(sem texto)")}</div>` + (t.citado ? `<details class="cx-citado"><summary>Mensagens anteriores coladas embaixo</summary>
    <div class="texto-email">${esc(t.citado)}</div></details>` : "") + (t.origem && t.origem !== "ao vivo" && t.origem !== "este PC"
    ? `<div class="dica">${esc(t.origem)}</div>` : "");
}
const anexosHtml = an => an?.length ? `<div class="anexos">${an.map(a => `<div class="anexo"><span class="ext">${esc(String(a).split(".").pop().toUpperCase().slice(0, 4))}</span><span>${esc(a)}</span></div>`).join("")}</div>` : "";

function desenharLeituraCorreio() {
  const el = $("cx-leitura");
  const aberto = !!(cx.sel || cx.enviadoSel);
  $("cx-mesa").classList.toggle("com-leitura", aberto);
  el.classList.toggle("oculta", !aberto);
  if (!aberto) { el.innerHTML = ""; return; }
  if (document.activeElement && el.contains(document.activeElement) && /INPUT|TEXTAREA/.test(document.activeElement.tagName)) return;
  if (cx.enviadoSel) return leituraEnviado(el);
  if (String(cx.sel).startsWith("live:")) return leituraAchado(el);
  const c = (cx.dados?.conversas || []).find(x => x.de === cx.sel);
  const conv = cx.conv;
  if (!conv) { el.innerHTML = `<div class="vazio">Abrindo a conversa…</div>`; return; }
  if (conv.erro) { el.innerHTML = `<div class="vazio">${esc(conv.erro)}</div>`; return; }
  const recebidos = conv.linha_do_tempo.filter(x => x.tipo === "recebido");
  const ultimo = recebidos[0];
  const lido = recebidos.find(x => x.lido_por);
  const cinza = !!cx.resolvendo[cx.sel];
  el.innerHTML = `
    <div class="acoes">
      ${ultimo && !cinza ? `<button class="prim" data-cx-resp-nf="${esc(ultimo.id)}"><svg class="ic"><use href="#i-enviar"/></svg>Responder com a NF</button>
      <button data-cx-resp="${esc(ultimo.id)}"><svg class="ic"><use href="#i-resp"/></svg>Responder</button>
      <button data-cx-enc="${esc(ultimo.id)}">Encaminhar</button>
      <button data-cx-naolido="${esc(ultimo.id)}">Marcar como não lido</button>` : cinza ? `<span class="dica">Respondido: o e-mail sai da caixa quando o Outlook do PC dono confirmar.</span>` : ""}
      <button class="fechar" id="cx-fechar" aria-label="Fechar leitura">×</button></div>
    <header class="cab-msg"><h2>${esc(conv.nome)}</h2>
      <div class="remet"><div class="avatar">${esc(iniciais(conv.nome))}</div><b>${esc(conv.de)}</b>
        <span class="quando">${c ? c.total + (c.total === 1 ? " e-mail sem resposta" : " e-mails sem resposta") : ""}</span>
        <span class="de">${esc((c?.hoteis || []).join(" / "))}${c ? " · caixa no PC de " + esc(c.agentes.join(", ")) : ""}</span></div>
      <div class="etiquetas">${(c?.classes || []).map(chipClasse).join("")}
        ${lido ? `<span class="etq">lido por ${esc(lido.lido_por)} às ${esc(String(lido.lido_em).slice(11, 16))}</span>` : ""}
        ${c && c.pcs.some(pc => !pcOnline(pc)) ? `<span class="etq ruim">PC dono desligado: o que for pedido sai quando ele ligar</span>` : ""}</div></header>
    <div class="corpo-msg">
      ${conv.nfs_enviadas.length ? `<section class="ficha cx-ja"><div class="ficha-tit"><span class="rot" style="color:var(--ok)">NF já enviada para este e-mail</span></div>
        <div class="ficha-corpo">${conv.nfs_enviadas.map(v => `<div>✓ NF ${esc(v.nfs.join(", "))} enviada para ${esc(v.para)} em ${esc(v.quando)} · ${esc(v.hotel)}</div>`).join("")}
        <div class="dica">Conferido pelo robô no Outlook (e no PDF da nota). Confira se o hóspede está pedindo outra nota antes de reenviar.</div></div></section>` : ""}
      <div class="cx-tempo">${conv.linha_do_tempo.map(cartaoTempo).join("")}</div>
    </div>`;
}

function cartaoTempo(x) {
  if (x.tipo === "formulario") return `<article class="cx-cartao form"><div class="cx-cartao-cab"><span class="cx-tipo">Formulário</span>
      <b>${esc(x.hotel)}</b><span class="dica">${dataBr(x.quando)}</span>
      <span class="pilula p-${x.situacao}">${NOMES[x.situacao] || x.situacao}${x.nfs.length ? " · NF " + esc(x.nfs.join(", ")) : ""}</span>
      <button class="link" data-ver-pedido="${esc(x.chave)}">ver o pedido</button></div></article>`;
  const env = x.tipo === "enviado";
  return `<article class="cx-cartao ${env ? "env" : ""}"><div class="cx-cartao-cab"><span class="cx-tipo">${env ? "Enviado" : "Recebido"}</span>
      <b>${esc(x.assunto || "(sem assunto)")}</b><span class="dica" title="${esc(quando(x.quando))}">${esc(quando(x.quando))}</span>
      ${env ? `<span class="dica">para ${esc(x.para)} · pela caixa ${esc(x.caixa)}</span>` : `<span class="dica">para ${esc(x.caixa)}</span>`}
      ${!env ? `<span class="cx-mini"><button data-cx-resp="${esc(x.id)}">Responder</button><button data-cx-enc="${esc(x.id)}">Encaminhar</button>
        <button class="perigo" data-cx-excluir="${esc(x.id)}">Excluir</button></span>` : ""}</div>
    ${blocoTexto(x.id)}${anexosHtml(x.anexos)}</article>`;
}

function leituraEnviado(el) {
  const e = (cx.dados?.enviados || []).find(x => x.id === cx.enviadoSel);
  if (!e) { cx.enviadoSel = null; el.innerHTML = ""; return; }
  el.innerHTML = `<div class="acoes"><span class="dica">Enviado pela caixa ${esc(e.caixa)} (PC de ${esc(nomeAgente(e.pc))})</span>
      <button class="fechar" id="cx-fechar" aria-label="Fechar leitura">×</button></div>
    <header class="cab-msg"><h2>${esc(e.assunto || "(sem assunto)")}</h2>
      <div class="remet"><div class="avatar">↗</div><b>Para: ${esc(e.para)}</b><span class="quando">${esc(quando(e.quando))}</span>
        <span class="de">${esc(e.hotel)}</span></div></header>
    <div class="corpo-msg">${blocoTexto(e.id)}${anexosHtml(e.anexos)}</div>`;
  carregarTexto(e.id, e.pc);
}
function leituraAchado(el) {
  const id = String(cx.sel).slice(5), x = (cx.live?.resultados || []).find(r => r.id === id);
  if (!x) { el.innerHTML = ""; return; }
  el.innerHTML = `<div class="acoes"><span class="dica">${PASTAS[x.pasta] || x.pasta} · Outlook do PC de ${esc(cx.live.agentes?.[x.pc] || x.pc)} · só leitura</span>
      <button class="fechar" id="cx-fechar" aria-label="Fechar leitura">×</button></div>
    <header class="cab-msg"><h2>${esc(x.assunto || "(sem assunto)")}</h2>
      <div class="remet"><div class="avatar">${esc(iniciais(x.nome || x.de))}</div><b>${esc(x.nome || x.de)}</b>
        <span class="quando">${esc(quando(x.quando))}</span><span class="de">${esc(x.de)} → ${esc(x.para)} · ${esc(x.hotel)}</span></div></header>
    <div class="corpo-msg">${blocoTexto(x.entry)}${anexosHtml(x.anexos)}</div>`;
  carregarTexto("", x.pc, x.entry);
}

// ---------- ações ----------
function encaminhar(id) {
  if (document.querySelector(".modal-fundo")) return;
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `<div class="modal"><div class="modal-topo"><div><h3>Encaminhar e-mail</h3>
      <div class="sub">Sai pela caixa do hotel, no Outlook do PC dono, com o e-mail original embaixo.</div></div>
      <button class="fechar" id="enc-fechar" aria-label="Fechar" style="margin-left:auto">×</button></div>
    <div class="ficha-corpo" style="padding:18px 22px">
      <label class="rot" for="enc-para">Para</label><input id="enc-para" placeholder="recepcao@hotel.com.br; outro@..." autocomplete="off">
      <label class="rot" for="enc-msg" style="margin-top:8px">Mensagem (opcional)</label><textarea id="enc-msg" rows="4"></textarea></div>
    <div class="modal-rodape"><span class="res" id="enc-res"></span><button class="prim" id="enc-ir">Encaminhar</button></div></div>`;
  document.body.appendChild(fundo);
  $("enc-fechar").onclick = () => fundo.remove();
  $("enc-ir").onclick = async () => {
    const para = $("enc-para").value.trim();
    if (!para.includes("@")) return toast("Preencha pra quem encaminhar", true);
    $("enc-ir").disabled = true;
    const r = await api("/api/correio/encaminhar", { id, para, corpo: $("enc-msg").value });
    if (!r.ok) { $("enc-ir").disabled = false; $("enc-res").textContent = r.motivo || "Não deu certo"; return; }
    fundo.remove();
    toast(r.aviso ? "Encaminhamento na fila: " + r.aviso : `Encaminhamento entregue ao PC ${r.destino}`);
  };
}

function excluir(id) {
  const conv = cx.conv, item = conv?.linha_do_tempo.find(x => x.id === id);
  if (!item || document.querySelector(".modal-fundo")) return;
  const c = (cx.dados?.conversas || []).find(x => x.de === conv.de);
  const dono = nomeAgente(item.pc);
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `<div class="modal" style="width:min(520px,94vw)"><div class="modal-topo"><div><h3>Excluir este e-mail?</h3>
      <div class="sub">“${esc(item.assunto || "(sem assunto)")}” de ${esc(conv.nome)}</div></div></div>
    <div class="ficha-corpo" style="padding:16px 22px">Ele vai para os <b>Itens Excluídos do Outlook de ${esc(dono)}</b> (dá pra recuperar de lá)
      e some do Painel para toda a equipe. Fica registrado que foi você.</div>
    <div class="modal-rodape"><button id="exc-nao" class="fechar-txt">Cancelar</button><button class="perigo" id="exc-sim">Excluir</button></div></div>`;
  document.body.appendChild(fundo);
  $("exc-nao").onclick = () => fundo.remove();
  $("exc-sim").onclick = () => {
    fundo.remove();
    // 10 s pra desfazer: só depois disso o pedido sai daqui
    const ultimoDaConversa = c && c.total === 1;
    if (ultimoDaConversa) { cx.escondidos[conv.de] = true; cx.sel = null; }
    else if (cx.conv) cx.conv.linha_do_tempo = cx.conv.linha_do_tempo.filter(x => x.id !== id);
    desenharCorreio();
    mostrarDesfazer(`E-mail excluído`, () => {
      delete cx.escondidos[conv.de];
      if (!ultimoDaConversa && cx.sel === conv.de) abrirConversa(conv.de); else desenharCorreio();
    }, async () => {
      const r = await api("/api/correio/excluir", { id });
      if (!r.ok) { delete cx.escondidos[conv.de]; toast(r.motivo || "Não deu pra excluir", true); }
      else if (r.aviso) toast(r.aviso);
      carregarCorreio();
    });
  };
}

function mostrarDesfazer(msg, desfazer, confirmar) {
  if (cx.desfazer) { clearTimeout(cx.desfazer.timer); cx.desfazer.confirmar(); }
  const bar = $("cx-desfazer");
  let s = 10;
  const pintar = () => { bar.innerHTML = `<span>${esc(msg)} · ${s}s</span><button id="cx-desfazer-btn">Desfazer</button>`;
    $("cx-desfazer-btn").onclick = () => { clearInterval(cx.desfazer.tique); clearTimeout(cx.desfazer.timer); cx.desfazer = null; bar.classList.add("oculta"); desfazer(); toast("Exclusão desfeita"); }; };
  bar.classList.remove("oculta"); pintar();
  const tique = setInterval(() => { s--; if (s > 0) pintar(); }, 1000);
  const timer = setTimeout(() => { clearInterval(tique); bar.classList.add("oculta"); cx.desfazer = null; confirmar(); }, 10000);
  cx.desfazer = { timer, tique, confirmar };
}

// a resposta saiu (envio pelo Painel): a linha fica cinza até o espelho do PC dono confirmar e ela sumir
function correioRespondido(idEmail) {
  const c = (cx.dados?.conversas || []).find(x => x.ids.includes(idEmail));
  if (c) { cx.resolvendo[c.de] = Date.now(); if (pn.vista === "correio") desenharCorreio(); }
}

function abrirCaixa(caixa) {
  cx.caixa = caixa; cx.sel = null; cx.enviadoSel = null; cx.hotel = "";
  try { localStorage.setItem("painel.caixaEmail", caixa); } catch (e) {}
}
try { const c = localStorage.getItem("painel.caixaEmail"); if (CAIXAS[c]) cx.caixa = c; } catch (e) {}

document.addEventListener("click", e => {
  const t = e.target.closest("[data-cx],[data-cx-env],[data-cx-live],[data-cx-resp],[data-cx-resp-nf],[data-cx-enc],[data-cx-excluir],[data-cx-naolido],#cx-fechar,#cx-buscar-outlook,[data-caixa]");
  if (!t) return;
  const d = t.dataset;
  if (d.caixa) { abrirCaixa(d.caixa); return; }   // o trocarVista do data-vista desenha
  if (d.cx) return abrirConversa(d.cx);
  if (d.cxEnv) { cx.enviadoSel = d.cxEnv; cx.sel = null; return desenharCorreio(); }
  if (d.cxLive) { cx.sel = "live:" + d.cxLive; cx.enviadoSel = null; return desenharCorreio(); }
  if (t.id === "cx-fechar") { cx.sel = null; cx.enviadoSel = null; return desenharCorreio(); }
  if (t.id === "cx-buscar-outlook") return buscarNoOutlook();
  if (d.cxResp) return abrirEnvioNF(null, { id: d.cxResp, comNF: false });
  if (d.cxRespNf) return abrirEnvioNF(null, { id: d.cxRespNf, comNF: true });
  if (d.cxEnc) return encaminhar(d.cxEnc);
  if (d.cxExcluir) return excluir(d.cxExcluir);
  if (d.cxNaolido) {
    const de = cx.sel;
    api("/api/correio/evento", { ids: [d.cxNaolido], acao: "NAO_LIDO" });
    const c = (cx.dados?.conversas || []).find(x => x.de === de);
    if (c) { c.nao_lidos = Math.max(1, c.nao_lidos); if (!c.urgente) cx.dados.contagem.entrada_nao_lidos++; }
    cx.manterNaoLido[de] = true; cx.sel = null; desenharLateralCorreio(); desenharCorreio();
    toast("Marcado como não lido pra equipe");
  }
});
document.addEventListener("keydown", e => {
  if (pn.vista !== "correio") return;
  if (e.target.id === "busca" && e.key === "Enter") { e.preventDefault(); buscarNoOutlook(); }
  const l = e.target.closest?.(".cx-linha");
  if (l && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); l.click(); }
  if (l && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
    e.preventDefault();
    const todas = [...document.querySelectorAll("#cx-lista .cx-linha")], i = todas.indexOf(l);
    todas[Math.max(0, Math.min(todas.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))]?.focus();
  }
  if (e.key === "Escape" && !document.querySelector(".modal-fundo") && (cx.sel || cx.enviadoSel)) { cx.sel = null; cx.enviadoSel = null; desenharCorreio(); }
});
