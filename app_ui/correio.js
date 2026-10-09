// E-mails: espelho do Outlook dos 4 PCs, no formato do Outlook (usuário, 08/10/2026): lista compacta, 1 linha por
// e-mail separada por Hoje / Ontem / Esta semana; ao clicar, o e-mail aberto à direita (De, Para, Data, texto) e o
// histórico do hóspede puxado ao vivo do Outlook. Tudo que se faz aqui (responder, encaminhar, excluir) roda no
// Outlook do PC dono por trás, sem abrir janela. A busca vai direto ao Outlook dos 4 PCs. Usa api/$/esc/toast/st.
let cx = { caixa: "entrada", dados: null, sel: null, hist: {}, textos: {}, hotel: "", live: null, buscando: "",
           resolvendo: {}, escondidos: {}, desfazer: null, manterNaoLido: {}, timerBusca: null, conv: {} };
const CAIXAS = { entrada: "Caixa de entrada", urgencia: "Urgência", enviados: "Itens enviados" };
const CLASSES = { corrigir: ["Corrigir / cancelar NF", "erro"], complementar: ["Nota complementar", "atencao"],
  cobranca: ["Cobrança", "atencao"], dados_tomador: ["Dados do tomador", "info"], pedido_nf: ["Pedido de NF", "ok"] };
const PASTAS = { entrada: "Recebido", enviado: "Enviado", excluido: "Excluído" };
const RESOLVENDO_MS = 4 * 60 * 1000;   // cinza até o espelho do PC dono confirmar (até ~2 min) e a linha sumir

async function carregarCorreio() {
  try {
    const j = await api("/api/correio");
    if (!j.emails) return;
    cx.dados = j;
    const agora = Date.now();
    for (const [k, t] of Object.entries(cx.resolvendo)) if (agora - t > RESOLVENDO_MS) delete cx.resolvendo[k];
    desenharLateralCorreio();
    if (pn.vista === "correio") desenharCorreio();
  } catch (e) { /* a próxima volta tenta de novo */ }
}

const emailsDa = caixa => (cx.dados?.emails || []).filter(e => !cx.escondidos[e.id] && (caixa === "urgencia" ? e.urgente : !e.urgente));
function desenharLateralCorreio() {
  const c = cx.dados?.contagem || {};
  const n = (id, v, alerta) => { const el = $(id); if (!el) return; el.textContent = v ? v.toLocaleString("pt-BR") : "";
    el.classList.toggle("alerta-n", !!(alerta && v)); };
  n("nav-entrada-n", c.entrada_nao_lidos); n("nav-urgencia-n", emailsDa("urgencia").length, true);
}

const nomeAgente = pc => (cx.dados?.pcs || []).find(p => p.pc === pc)?.agente || cx.live?.agentes?.[pc] || pc;
const pcOnline = pc => !!(cx.dados?.pcs || []).find(p => p.pc === pc)?.online;
function horaCurta(iso) {
  if (!iso) return "";
  const d = iso.slice(0, 10);
  return d === hojeIsoF() ? iso.slice(11, 16) : d === ontemIso() ? "Ontem " + iso.slice(11, 16) : d.slice(8, 10) + "/" + d.slice(5, 7);
}
const dataLonga = iso => { const d = new Date(iso); return isNaN(d) ? iso : d.toLocaleString("pt-BR", { weekday: "short", day: "2-digit",
  month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); };
function grupoData(iso) {   // Hoje / Ontem / Esta semana / Mais antigos (como o Outlook)
  const dias = diasDesde(iso);
  return dias === 0 ? "Hoje" : dias === 1 ? "Ontem" : dias < 7 ? "Esta semana" : dias < 14 ? "Semana passada" : "Mais antigos";
}
const etiqueta = c => CLASSES[c] ? `<span class="et et-${CLASSES[c][1]}">${esc(CLASSES[c][0])}</span>` : "";
function textoBusca(e) {
  return semAcento([e.nome, e.de, e.assunto, e.previa, e.hotel, e.para, e.caixa,
    (e.classes || []).map(k => CLASSES[k]?.[0]).join(" "), e.agente].join(" \n "));
}
function passaBusca(e, busca) {
  if (!busca) return true;
  const t = textoBusca(e);
  return semAcento(busca).split(/\s+/).filter(Boolean).every(p => t.includes(p) || soDigitos(t).includes(soDigitos(p)));
}

// ---------- lista ----------
function itensDaTela(busca) {
  if (busca) {   // busca: o que o Outlook dos PCs devolveu + o espelho dos PCs que não responderam (desligados)
    const r = cx.live && cx.live.termo === busca ? cx.live : null;
    const deles = new Set(Object.entries(r?.pcs || {}).filter(([, s]) => s.ok).map(([pc]) => pc));
    const espelho = (cx.dados?.emails || []).filter(e => !deles.has(e.pc) && passaBusca(e, busca)).map(e => ({ ...e, pasta: "entrada" }));
    const vistos = new Set();
    return [...(r?.resultados || []), ...espelho].filter(e => !vistos.has(e.id) && vistos.add(e.id))
      .filter(e => !cx.hotel || e.hotel === cx.hotel).sort((a, b) => b.quando.localeCompare(a.quando));
  }
  const base = cx.caixa === "enviados" ? (cx.dados?.enviados || []).map(e => ({ ...e, pasta: "enviado" })) : emailsDa(cx.caixa);
  const lista = base.filter(e => !cx.hotel || e.hotel === cx.hotel);
  return cx.caixa === "urgencia" ? lista.sort((a, b) => a.quando.localeCompare(b.quando)) : lista;
}

function desenharCorreio() {
  if (!$("v-correio")) return;
  const busca = $("busca").value.trim().length >= 3 ? $("busca").value.trim() : "";
  const lista = itensDaTela(busca);
  const naoLidos = lista.filter(e => e.pasta !== "enviado" && e.lido === false).length;
  $("cx-titulo").textContent = busca ? "Resultado da pesquisa" : CAIXAS[cx.caixa];
  $("cx-sub").textContent = busca ? `“${busca}” · ${lista.length} e-mail(s)` :
    cx.caixa === "enviados" ? `${lista.length} nas últimas 24 h` : `${lista.length} e-mail(s)${naoLidos ? ` · ${naoLidos} não lido(s)` : ""}`;
  const off = (cx.dados?.pcs || []).filter(p => !p.online);
  $("cx-avisos").innerHTML = (off.length ? `<span class="cx-aviso" title="Os e-mails deles aparecem como estavam na última leitura; o que for pedido sai quando ligarem.">
      Desligado: ${esc(off.map(p => p.agente || p.pc).join(", "))}</span>` : "") + statusBusca(busca);
  desenharFiltroHotel(lista);
  // a lista é refeita a cada 15 s: quem estava com o foco numa linha continua nela
  const focada = document.activeElement?.closest?.("#cx-lista .cx-l");
  const idFoco = focada?.dataset.id;
  let grupo = "", html = "";
  for (const e of lista) {
    const g = cx.caixa === "urgencia" && !busca ? "" : grupoData(e.quando);
    if (g && g !== grupo) { html += `<div class="cx-grupo">${g}</div>`; grupo = g; }
    html += linhaEmail(e);
  }
  const vazio = cx.buscando ? "Procurando no Outlook dos PCs…" : busca ? `Nenhum e-mail com “${esc(busca)}”.`
    : cx.caixa === "entrada" ? "Nenhum e-mail esperando resposta." : cx.caixa === "urgencia" ? "Nenhum e-mail em urgência." : "Nada enviado nas últimas 24 h.";
  $("cx-lista").innerHTML = html || `<div class="vazio">${vazio}</div>`;
  if (idFoco) $("cx-lista").querySelector(`.cx-l[data-id="${CSS.escape(idFoco)}"]`)?.focus();
  desenharLeituraCorreio();
}

function statusBusca(busca) {
  if (!busca) return "";
  if (cx.buscando === busca) return `<span class="cx-aviso neutro">Procurando no Outlook dos PCs…</span>`;
  const r = cx.live;
  if (!r || r.termo !== busca) return "";
  return Object.entries(r.pcs || {}).filter(([pc, s]) => s.ok || pcOnline(pc)).map(([pc, s]) => `<span class="cx-aviso ${s.ok ? "neutro" : ""}">${esc(r.agentes?.[pc] || pc)}:
    ${s.ok ? `${s.achados}${s.completo ? "" : "+"} achado(s)` : esc(s.erro)}</span>`).join("");
}

function desenharFiltroHotel(lista) {
  const hoteis = [...new Set(lista.map(e => e.hotel).filter(Boolean).concat(cx.hotel ? [cx.hotel] : []))].sort((a, b) => a.localeCompare(b, "pt"));
  $("cx-filtros").innerHTML = `<label class="cx-campo">Hotel <select id="cx-hotel"><option value="">Todos</option>${hoteis.map(h =>
    `<option ${h === cx.hotel ? "selected" : ""}>${esc(h)}</option>`).join("")}</select></label>`;
  $("cx-hotel").onchange = e => { cx.hotel = e.target.value; desenharCorreio(); };
}

function linhaEmail(e) {
  const enviado = e.pasta === "enviado", excluido = e.pasta === "excluido";
  const cinza = !!cx.resolvendo[e.id], sel = cx.sel === e.id, naoLido = !enviado && e.lido === false && !cinza;
  const quem = enviado ? "Para: " + (e.para || "") : (e.nome || e.de);
  const marcas = (e.classes || []).filter(k => k !== "pedido_nf").map(etiqueta).join("") +
    (e.notas?.length ? `<span class="et et-ok">NF ${esc(e.notas.map(n => n.nf).join(", "))} emitida</span>` : "") +
    (e.quartos >= 2 ? `<span class="et et-info">${e.quartos} quartos</span>` : "") +
    (excluido ? `<span class="et">Excluído</span>` : "") + (cinza ? `<span class="et">Respondido</span>` : "") +
    (e.pasta === "entrada" && e.pc && !pcOnline(e.pc) ? `<span class="et et-atencao" title="PC dono desligado: o que for pedido sai quando ele ligar">PC desligado</span>` : "");
  return `<div class="cx-l ${naoLido ? "nao-lido" : ""} ${sel ? "sel" : ""} ${cinza ? "cinza" : ""}" role="option" tabindex="0"
      aria-selected="${sel}" data-id="${esc(e.id)}">
    <div class="cx-l1"><span class="cx-quem">${esc(quem)}</span>${e.total_conversa > 1 && !enviado ? `<span class="cx-n" title="e-mails sem resposta deste hóspede">${e.total_conversa}</span>` : ""}
      <span class="cx-hora">${horaCurta(e.quando)}</span></div>
    <div class="cx-l2">${esc(e.assunto || "(sem assunto)")}</div>
    <div class="cx-l3"><span class="cx-hotel">${esc(e.hotel || "")}</span>${esc(e.previa || "")}</div>
    ${marcas ? `<div class="cx-l4">${marcas}</div>` : ""}${naoLido ? `<span class="so-leitor">não lido</span>` : ""}</div>`;
}

// ---------- busca: direto no Outlook dos 4 PCs ----------
function agendarBusca() {
  clearTimeout(cx.timerBusca);
  const busca = $("busca").value.trim();
  cx.sel = null;   // pesquisa nova: fecha o e-mail que estava aberto
  if (busca.length < 3) { cx.live = null; cx.buscando = ""; return desenharCorreio(); }
  cx.timerBusca = setTimeout(() => buscarNoOutlook(busca), 650);
  desenharCorreio();
}
async function buscarNoOutlook(busca) {
  cx.buscando = busca; desenharCorreio();
  const r = await api("/api/correio/buscar?q=" + encodeURIComponent(busca));
  if ($("busca").value.trim() !== busca) return;   // já digitaram outra coisa
  cx.buscando = "";
  if (r.erro) { toast(r.erro, true); cx.live = null; } else cx.live = r;
  desenharCorreio();
  $("anuncio").textContent = r.resultados ? `${r.resultados.length} e-mails achados no Outlook` : "";
}

// ---------- leitura: o e-mail aberto, como no Outlook ----------
function itemSelecionado() {
  const todos = [...(cx.dados?.emails || []), ...(cx.dados?.enviados || []).map(e => ({ ...e, pasta: "enviado" })),
                 ...(cx.live?.resultados || [])];
  return todos.find(e => e.id === cx.sel);
}
function abrirEmail(id) {
  cx.sel = id;
  const e = itemSelecionado();
  desenharCorreio();
  if (!e) return;
  carregarTexto(e);
  if (e.pasta !== "enviado" && e.de) carregarHistorico(e.de);
  if (e.lido === false && !cx.manterNaoLido[e.id]) {   // abriu = lido (pra equipe toda)
    api("/api/correio/evento", { ids: [e.id], acao: "LIDO" });
    e.lido = true;
    if (!e.urgente && cx.dados?.contagem) cx.dados.contagem.entrada_nao_lidos = Math.max(0, cx.dados.contagem.entrada_nao_lidos - 1);
    desenharLateralCorreio(); desenharCorreio();
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
  desenharLeituraCorreio();
}
async function carregarHistorico(de) {   // tudo do hóspede no Outlook dos PCs (qualquer pasta e data) + formulários
  if (cx.hist[de]) return;
  cx.hist[de] = { carregando: true };
  const [r, conv] = await Promise.all([api("/api/correio/buscar?q=" + encodeURIComponent(de)),
                                       api("/api/correio/conversa?de=" + encodeURIComponent(de))]);
  cx.hist[de] = { resultados: (r.resultados || []).filter(x => x.de === de || (x.para || "").includes(de)), pcs: r.pcs || {},
                  agentes: r.agentes || {}, conv: conv.erro ? null : conv };
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
const anexosHtml = an => an?.length ? `<div class="cx-anexos">${an.map(a => `<span class="cx-anexo"><b>${esc(String(a).split(".").pop().toUpperCase().slice(0, 4))}</b>${esc(a)}</span>`).join("")}</div>` : "";

function desenharLeituraCorreio() {
  const el = $("cx-leitura");
  const e = cx.sel && itemSelecionado();
  $("cx-mesa").classList.toggle("com-leitura", !!e);
  el.classList.toggle("oculta", !e);
  if (!e) { el.innerHTML = ""; return; }
  if (document.activeElement && el.contains(document.activeElement) && /INPUT|TEXTAREA|SUMMARY/.test(document.activeElement.tagName)) return;
  const noEspelho = (cx.dados?.emails || []).some(x => x.id === e.id);
  const cinza = !!cx.resolvendo[e.id];
  const enviado = e.pasta === "enviado";
  const acoes = noEspelho && !cinza ? `
      <button class="prim" data-cx-resp-nf="${esc(e.id)}">Responder com NF</button>
      <button data-cx-resp="${esc(e.id)}">Responder</button>
      <button data-cx-enc="${esc(e.id)}">Encaminhar</button>
      <button data-cx-excluir="${esc(e.id)}">Excluir</button>
      <button data-cx-naolido="${esc(e.id)}">Marcar como não lido</button>`
    : cinza ? `<span class="dica">Respondido. Sai da caixa quando o Outlook do PC dono confirmar.</span>`
    : `<span class="dica">${enviado ? "E-mail enviado" : PASTAS[e.pasta] || ""} · somente leitura</span>`;
  const h = !enviado && e.de ? cx.hist[e.de] : null;
  el.innerHTML = `
    <div class="cx-barra">${acoes}<button class="cx-x" id="cx-fechar" aria-label="Fechar e-mail" title="Fechar (Esc)">✕</button></div>
    <div class="cx-msg">
      <h2>${esc(e.assunto || "(sem assunto)")}</h2>
      <table class="cx-cab"><tbody>
        <tr><th>De</th><td>${enviado ? esc(e.caixa) : `<b>${esc(e.nome || e.de)}</b> &lt;${esc(e.de)}&gt;`}</td></tr>
        <tr><th>Para</th><td>${esc(enviado ? e.para : e.caixa || e.para)}</td></tr>
        <tr><th>Data</th><td>${esc(dataLonga(e.quando))}</td></tr>
        <tr><th>Hotel</th><td>${esc(e.hotel || "")}${e.pc ? ` · caixa no PC de ${esc(nomeAgente(e.pc))}${e.pc && !pcOnline(e.pc) ? " (desligado: o que for pedido sai quando ele ligar)" : ""}` : ""}</td></tr>
        ${(e.classes || []).length ? `<tr><th>Assunto</th><td>${e.classes.map(etiqueta).join("")}</td></tr>` : ""}
        ${e.lido_por ? `<tr><th>Lido</th><td>por ${esc(e.lido_por)} às ${esc(String(e.lido_em).slice(11, 16))}</td></tr>` : ""}
      </tbody></table>
      ${avisoNfJaEnviada(h)}
      ${corpoTexto(e.id)}${anexosHtml(e.anexos)}
      ${h ? historicoHtml(h, e) : ""}
    </div>`;
}

function avisoNfJaEnviada(h) {
  const nfs = h?.conv?.nfs_enviadas || [];
  if (!nfs.length) return "";
  return `<div class="cx-aviso-nf"><b>NF já enviada para este e-mail</b>${nfs.map(v => `<div>NF ${esc(v.nfs.join(", "))} · enviada para ${esc(v.para)} em ${esc(v.quando)} · ${esc(v.hotel)}</div>`).join("")}
    <div class="dica">Conferido pelo robô no Outlook e no PDF da nota. Veja se o hóspede pede outra nota antes de reenviar.</div></div>`;
}

function historicoHtml(h, atual) {
  if (h.carregando) return `<section class="cx-hist"><div class="cx-hist-t">Histórico deste hóspede no Outlook</div><p class="dica">Procurando no Outlook dos PCs…</p></section>`;
  const forms = (h.conv?.linha_do_tempo || []).filter(x => x.tipo === "formulario");
  const itens = h.resultados.filter(x => x.id !== atual.id);
  const sem = Object.entries(h.pcs).filter(([, s]) => !s.ok).map(([pc]) => h.agentes[pc] || pc);
  const linhas = [...itens.map(x => ({ q: x.quando, html: linhaHist(x) })),
    ...forms.map(f => ({ q: f.quando, html: `<div class="cx-h form"><span class="cx-h-tipo">Formulário</span><span class="cx-h-data">${dataBr(f.quando)}</span>
      <span class="cx-h-ass">${esc(f.hotel)} · ${NOMES[f.situacao] || f.situacao}${f.nfs.length ? " · NF " + esc(f.nfs.join(", ")) : ""}</span>
      <button class="link" data-ver-pedido="${esc(f.chave)}">abrir pedido</button></div>` }))]
    .sort((a, b) => String(b.q).localeCompare(String(a.q)));
  return `<section class="cx-hist"><div class="cx-hist-t">Histórico deste hóspede no Outlook <span>${linhas.length}</span></div>
    ${linhas.map(l => l.html).join("") || `<p class="dica">Nenhum outro e-mail deste endereço no Outlook dos PCs ligados.</p>`}
    ${sem.length ? `<p class="dica">Sem resposta de: ${esc(sem.join(", "))} (desligado).</p>` : ""}</section>`;
}
function linhaHist(x) {
  const aberto = cx.hist.aberto === x.id;
  return `<div class="cx-h ${aberto ? "aberto" : ""}" data-cx-hist="${esc(x.id)}" tabindex="0" role="button" aria-expanded="${aberto}">
      <span class="cx-h-tipo t-${x.pasta}">${x.pasta === "enviado" ? "↗ Enviado" : x.pasta === "excluido" ? "✕ Excluído" : "↙ Recebido"}</span>
      <span class="cx-h-data">${esc(quando(x.quando))}</span><span class="cx-h-ass">${esc(x.assunto || "(sem assunto)")}</span>
      <span class="cx-h-pc">${esc(nomeAgente(x.pc))}</span></div>
    ${aberto ? `<div class="cx-h-corpo">${corpoTexto(x.id)}${anexosHtml(x.anexos)}</div>` : ""}`;
}

// ---------- ações (rodam no Outlook do PC dono, sem abrir janela) ----------
function encaminhar(id) {
  if (document.querySelector(".modal-fundo")) return;
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `<div class="modal" style="width:min(560px,94vw)"><div class="modal-topo"><div><h3>Encaminhar e-mail</h3>
      <div class="sub">Sai pela caixa do hotel, pelo Outlook do PC dono, com o e-mail original anexado embaixo.</div></div>
      <button class="fechar" id="enc-fechar" aria-label="Fechar" style="margin-left:auto">✕</button></div>
    <div class="ficha-corpo" style="padding:16px 22px">
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
    toast(r.aviso ? "Na fila: " + r.aviso : `Encaminhado pelo Outlook do PC ${r.destino}`);
  };
}

function excluir(id) {
  const e = (cx.dados?.emails || []).find(x => x.id === id);
  if (!e || document.querySelector(".modal-fundo")) return;
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `<div class="modal" style="width:min(520px,94vw)"><div class="modal-topo"><div><h3>Excluir este e-mail?</h3>
      <div class="sub">“${esc(e.assunto || "(sem assunto)")}” · ${esc(e.nome || e.de)}</div></div></div>
    <div class="ficha-corpo" style="padding:16px 22px">Vai para os <b>Itens Excluídos do Outlook de ${esc(nomeAgente(e.pc))}</b> (dá pra
      recuperar de lá) e sai do Painel de toda a equipe. Fica registrado que foi você.</div>
    <div class="modal-rodape"><button id="exc-nao">Cancelar</button><button class="perigo" id="exc-sim">Excluir</button></div></div>`;
  document.body.appendChild(fundo);
  $("exc-nao").onclick = () => fundo.remove();
  $("exc-sim").onclick = () => {
    fundo.remove();
    cx.escondidos[id] = true; if (cx.sel === id) cx.sel = null;
    desenharCorreio();
    mostrarDesfazer("E-mail excluído", () => { delete cx.escondidos[id]; desenharCorreio(); }, async () => {
      const r = await api("/api/correio/excluir", { id });
      if (!r.ok) { delete cx.escondidos[id]; toast(r.motivo || "Não deu pra excluir", true); }
      else if (r.aviso) toast(r.aviso);
      carregarCorreio();
    });
  };
}

function mostrarDesfazer(msg, desfazer, confirmar) {   // 10 s pra desfazer: só depois disso o pedido sai daqui
  if (cx.desfazer) { clearTimeout(cx.desfazer.timer); clearInterval(cx.desfazer.tique); cx.desfazer.confirmar(); }
  const bar = $("cx-desfazer");
  let s = 10;
  const pintar = () => { bar.innerHTML = `<span>${esc(msg)} · ${s}s</span><button id="cx-desfazer-btn">Desfazer</button>`;
    $("cx-desfazer-btn").onclick = () => { clearInterval(cx.desfazer.tique); clearTimeout(cx.desfazer.timer); cx.desfazer = null;
      bar.classList.add("oculta"); desfazer(); toast("Exclusão desfeita"); }; };
  bar.classList.remove("oculta"); pintar();
  const tique = setInterval(() => { s--; if (s > 0) pintar(); }, 1000);
  const timer = setTimeout(() => { clearInterval(tique); bar.classList.add("oculta"); cx.desfazer = null; confirmar(); }, 10000);
  cx.desfazer = { timer, tique, confirmar };
}

// a resposta saiu (envio pelo Painel): a linha fica cinza até o espelho do PC dono confirmar e ela sumir
function correioRespondido(idEmail) {
  const e = (cx.dados?.emails || []).find(x => x.id === idEmail);
  (cx.dados?.emails || []).filter(x => e && x.de === e.de).forEach(x => cx.resolvendo[x.id] = Date.now());
  if (pn.vista === "correio") desenharCorreio();
}

function abrirCaixa(caixa) {
  cx.caixa = caixa; cx.sel = null; cx.hotel = "";
  try { localStorage.setItem("painel.caixaEmail", caixa); } catch (e) {}
}
try { const c = localStorage.getItem("painel.caixaEmail"); if (CAIXAS[c]) cx.caixa = c; } catch (e) {}

document.addEventListener("click", e => {
  const t = e.target.closest(".cx-l,[data-cx-hist],[data-cx-resp],[data-cx-resp-nf],[data-cx-enc],[data-cx-excluir],[data-cx-naolido],#cx-fechar,[data-caixa]");
  if (!t) return;
  const d = t.dataset;
  if (d.caixa) { abrirCaixa(d.caixa); return; }   // o trocarVista do data-vista desenha
  if (t.classList.contains("cx-l")) return abrirEmail(d.id);
  if (d.cxHist) {
    cx.hist.aberto = cx.hist.aberto === d.cxHist ? null : d.cxHist;
    const x = Object.values(cx.hist).flatMap(h => h?.resultados || []).find(r => r.id === d.cxHist);
    if (x && cx.hist.aberto) carregarTexto(x);
    return desenharLeituraCorreio();
  }
  if (t.id === "cx-fechar") { cx.sel = null; return desenharCorreio(); }
  if (d.cxResp) return abrirEnvioNF(null, { id: d.cxResp, comNF: false });
  if (d.cxRespNf) return abrirEnvioNF(null, { id: d.cxRespNf, comNF: true });
  if (d.cxEnc) return encaminhar(d.cxEnc);
  if (d.cxExcluir) return excluir(d.cxExcluir);
  if (d.cxNaolido) {
    const x = (cx.dados?.emails || []).find(m => m.id === d.cxNaolido);
    api("/api/correio/evento", { ids: [d.cxNaolido], acao: "NAO_LIDO" });
    if (x && x.lido !== false) { x.lido = false; if (!x.urgente) cx.dados.contagem.entrada_nao_lidos++; }
    cx.manterNaoLido[d.cxNaolido] = true; cx.sel = null; desenharLateralCorreio(); desenharCorreio();
    toast("Marcado como não lido para a equipe");
  }
});
document.addEventListener("keydown", e => {
  if (pn.vista !== "correio") return;
  const l = e.target.closest?.(".cx-l,[data-cx-hist]");
  if (l && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); l.click(); }
  if (l?.classList.contains("cx-l") && (e.key === "ArrowDown" || e.key === "ArrowUp")) {
    e.preventDefault();
    const todas = [...document.querySelectorAll("#cx-lista .cx-l")], i = todas.indexOf(l);
    const prox = todas[Math.max(0, Math.min(todas.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)))];
    prox?.focus(); if (prox) abrirEmail(prox.dataset.id);   // como no Outlook: a seta já abre o e-mail
  }
  if (e.key === "Escape" && !document.querySelector(".modal-fundo") && cx.sel) { cx.sel = null; desenharCorreio(); }
});
