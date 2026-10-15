// E-mails: espelho do Outlook dos 4 PCs, no formato do Outlook (usuário, 08/10/2026): lista compacta, 1 linha por
// e-mail separada por Hoje / Ontem / Esta semana; ao clicar, o e-mail aberto à direita (De, Para, Data, texto) e o
// histórico do hóspede puxado ao vivo do Outlook. Tudo que se faz aqui (responder, encaminhar, excluir) roda no
// Outlook do PC dono por trás, sem abrir janela. A busca vai direto ao Outlook dos 4 PCs. Usa api/$/esc/toast/st.
let cx = { caixa: "entrada", dados: null, sel: null, hist: {}, textos: {}, hotel: "", live: null, buscando: "",
           resolvendo: {}, escondidos: {}, desfazer: null, manterNaoLido: {}, timerBusca: null, conv: {},
           soNaoLidos: false, fechados: {} };   // Todas / Não lidos e os grupos de caixas recolhidos (igual ao Outlook, 15/10/2026)
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
    if (typeof desenharSeletorCaixa === "function") desenharSeletorCaixa();
    if (pn.vista === "correio") desenharCorreio();
    else if (pn.vista === "fila") desenharAbasNotas();   // e-mails chegaram: atualiza os números das abas
  } catch (e) { /* a próxima volta tenta de novo */ }
}

const doEscopo = (e, alvo) => doAgente([nomeAgente(e.pc)], alvo);   // a caixa é do PC de quem (filtro dos 4 agentes)
const emailsDa = (caixa, alvo) => (cx.dados?.emails || []).filter(e => !cx.escondidos[e.id] && doEscopo(e, alvo) && (caixa === "urgencia" ? e.urgente : true));   // Entrada = a caixa inteira, igual ao Outlook (14/10/2026)
function desenharLateralCorreio() {
  const c = cx.dados?.contagem || {};
  const n = (id, v, alerta) => { const el = $(id); if (!el) return; el.textContent = v ? v.toLocaleString("pt-BR") : "";
    el.classList.toggle("alerta-n", !!(alerta && v)); };
  n("nav-entrada-n", emailsDa("entrada").filter(e => e.lido === false).length);   // não lidos do Outlook, do agente escolhido
  n("nav-urgencia-n", emailsDa("urgencia").length, true);
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
  const base = cx.caixa === "enviados" ? (cx.dados?.enviados || []).map(e => ({ ...e, pasta: "enviado" })).filter(doEscopo) : emailsDa(cx.caixa);
  const lista = base.filter(e => (!cx.hotel || (e.hotel || "").split(" / ").includes(cx.hotel)) && (!cx.soNaoLidos || e.lido === false));
  return lista;   // o mais recente primeiro também na Urgência (usuário, 09/10/2026)
}

function desenharCorreio() {
  if (!$("v-correio")) return;
  const busca = $("busca").value.trim().length >= 3 ? $("busca").value.trim() : "";
  const lista = itensDaTela(busca);
  const naoLidos = lista.filter(e => e.pasta !== "enviado" && e.lido === false).length;
  $("cx-titulo").textContent = busca ? "Resultado da pesquisa" : CAIXAS[cx.caixa];
  $("op-cartoes-emails").innerHTML = segOperadores(v => cx.caixa === "enviados"
    ? (cx.dados?.enviados || []).filter(e => doEscopo(e, v)).length : emailsDa(cx.caixa, v).length);
  $("det-op-emails").innerHTML = detalheOperador();
  $("cx-dica").textContent = busca ? "Resultado direto do Outlook dos 4 PCs: inclui respondidos, enviados e excluídos, de qualquer data. Clique pra ler."
    : { entrada: "Igual à Caixa de Entrada do Outlook dos 4 PCs: tudo o que está lá, respondido ou não. Cada linha: quem mandou e a hora; embaixo, o assunto e o hotel. Negrito = não lido · ponto vermelho = urgente · \"respondido\" = já teve resposta. Clique pra ler (as setas ↑ ↓ andam pela lista).",
        urgencia: "O que precisa de atenção agora: pedido de correção/cancelamento de NF, NF com CPF/CNPJ diferente do pedido ou mais de 7 dias sem resposta. A caixa vermelha mostra o que o robô achou na NF.",
        enviados: "O que saiu das caixas dos hotéis nas últimas 24 h (pelo Outlook ou pelo Painel)." }[cx.caixa];
  const nEm = x => `${x.toLocaleString("pt-BR")} e-mail${x === 1 ? "" : "s"}`;
  $("cx-sub").innerHTML = esc(busca ? `“${busca}” · ${nEm(lista.length)} no Outlook dos PCs` :
    cx.caixa === "enviados" ? `${lista.length} nas últimas 24 h` : `${nEm(lista.length)}${naoLidos ? ` · ${naoLidos} não lido${naoLidos === 1 ? "" : "s"}` : ""}`)
    + (cx.hotel ? ` · ${esc(cx.hotel)}` : "") + statusBusca(busca);
  desenharFiltroHotel();
  desenharPastas();
  if ($("cx-lcab")) $("cx-lcab").innerHTML = busca ? `<span class="cx-ord">Resultado da pesquisa no Outlook dos 4 PCs</span>` :
    `<button type="button" data-cx-filtro="todas" aria-pressed="${!cx.soNaoLidos}">Todas</button>` +
    (cx.caixa === "enviados" ? "" : `<button type="button" data-cx-filtro="naolidos" aria-pressed="${cx.soNaoLidos}">Não lidos</button>`) +
    `<span class="cx-ord">${esc(cx.hotel || CAIXAS[cx.caixa])} · por data ↓</span>`;
  // a lista é refeita a cada 15 s: quem estava com o foco numa linha continua nela
  const focada = document.activeElement?.closest?.("#cx-lista .cx-l");
  const idFoco = focada?.dataset.id;
  let grupo = "", html = "";
  for (const e of lista) {
    const g = cx.caixa === "urgencia" && !busca ? "" : grupoData(e.quando);
    if (g && g !== grupo) { html += `<div class="cx-grupo">${g}</div>`; grupo = g; }
    html += linhaEmail(e);
  }
  const quem = escopoAtual() === "todos" ? "" : ` de ${escopoAtual()}`;
  const vazio = cx.buscando ? "Procurando no Outlook dos PCs…" : busca ? `Nenhum e-mail com “${esc(busca)}”.`
    : cx.caixa === "enviados" ? "Nada enviado nas últimas 24 h." : cx.soNaoLidos ? "Nenhum e-mail não lido aqui." : "";
  $("cx-lista").innerHTML = html || (vazio ? `<div class="vazio">${vazio}</div>`
    : caixaEmDia(cx.caixa === "urgencia" ? `Nada urgente na caixa${quem}.` : `Caixa de Entrada vazia${quem}.`));
  if (idFoco) $("cx-lista").querySelector(`.cx-l[data-id="${CSS.escape(idFoco)}"]`)?.focus();
  desenharLeituraCorreio();
}

function statusBusca(busca) {
  if (!busca) return "";
  if (cx.buscando === busca) return " · procurando no Outlook dos PCs…";
  const r = cx.live;
  if (!r || r.termo !== busca) return "";
  const falhou = Object.entries(r.pcs || {}).filter(([pc, s]) => !s.ok && pcOnline(pc)).map(([pc]) => r.agentes?.[pc] || pc);
  return falhou.length ? ` · <span class="alerta-txt">sem resposta de ${esc(falhou.join(", "))}</span>` : "";
}

// Filtro de hotel no topo, ao lado da pesquisa (botão com ícone + menu com busca, agrupado por agente)
function desenharFiltroHotel() {
  if (pn.vista !== "correio") return;
  ($("cx-filtro-hotel") || $("topo-filtro")).innerHTML = pilula("cx-hotel", "Hotel", cx.hotel).replace(/#i-busca/, "#i-hotel");
}
function contarHoteisCorreio() {   // quantos e-mails cada hotel tem na caixa aberta (sem o filtro de hotel)
  const hotel = cx.hotel; cx.hotel = "";
  const busca = $("busca").value.trim().length >= 3 ? $("busca").value.trim() : "";
  const lista = itensDaTela(busca);
  cx.hotel = hotel;
  const n = {};
  lista.forEach(e => (e.hotel || "").split(" / ").forEach(h => h && (n[h] = (n[h] || 0) + 1)));
  return n;
}
function opcoesHotelCorreio(op, buscaPop) {
  const n = contarHoteisCorreio(), busca = semAcento(buscaPop), grupos = {};
  (st.hoteis || []).forEach(h => { if (!busca || semAcento(h.hotel).includes(busca)) (grupos[h.agente || "Sem agente"] ||= []).push(h.hotel); });
  return (busca ? "" : op("cx-hotel", "", "Todos os hotéis", !cx.hotel)) + Object.entries(grupos).map(([a, hs]) =>
    `<div class="pop-grupo">${esc(a)}</div>` + hs.sort((x, y) => (n[y] || 0) - (n[x] || 0) || x.localeCompare(y, "pt"))
      .map(h => op("cx-hotel", h, h, h === cx.hotel, n[h] || 0)).join("")).join("") || `<div class="pop-grupo">Nenhum hotel com esse nome</div>`;
}

// Faixa de ações (no lugar dos avisos): quem mandou + etiquetas + os botões grandes; sem e-mail aberto, o resumo da caixa
const iniciais = n => (String(n || "?").trim().split(/\s+/).slice(0, 2).map(p => p[0]).join("") || "?").toUpperCase();
function desenharAcoes() {
  const el = $("cx-acoes");
  const e = cx.sel && itemSelecionado();
  const pode = !!(e && (cx.dados?.emails || []).some(x => x.id === e.id) && !cx.resolvendo[e.id]);
  document.querySelectorAll("[data-cx-faixa]").forEach(b => { b.disabled = !pode; });
  if (!e) {
    el.classList.add("vazio-acoes");
    const c = cx.dados?.contagem || {};
    const quem = escopoAtual() === "todos" ? "nas 4 caixas" : "de " + escopoAtual();
    el.innerHTML = `<div class="ind"><b>${emailsDa("entrada").filter(e => e.lido === false).length.toLocaleString("pt-BR")}</b><small>não lidos na entrada ${esc(quem)}</small></div>
      <div class="ind urg"><b>${emailsDa("urgencia").length.toLocaleString("pt-BR")}</b><small>em urgência</small></div>
      <div class="ind"><b>${(cx.dados?.enviados || []).filter(e => doEscopo(e)).length.toLocaleString("pt-BR")}</b><small>enviados nas últimas 24 h</small></div>
      <span class="dica-prof so-texto" style="margin-left:auto">Clique num e-mail pra ler e responder · ↑ ↓ andam pela lista · tecla ? = ajuda</span>`;
    return;
  }
  el.classList.remove("vazio-acoes");
  const noEspelho = (cx.dados?.emails || []).some(x => x.id === e.id);
  const cinza = !!cx.resolvendo[e.id], enviado = e.pasta === "enviado";
  const ic = id => `<svg class="ic"><use href="#${id}"/></svg>`;
  const botoes = noEspelho && !cinza ? `
      <button class="prim" data-cx-resp-nf="${esc(e.id)}" title="Ctrl+Shift+R">${ic("i-enviar")}Responder com NF</button>
      <button data-cx-resp="${esc(e.id)}" title="Ctrl+R">${ic("i-resp")}Responder</button>
      <button data-cx-enc="${esc(e.id)}" title="Ctrl+F">${ic("i-enc")}Encaminhar</button>
      <button class="perigo" data-cx-excluir="${esc(e.id)}" title="Delete">${ic("i-lixo")}Excluir</button>
      <button data-cx-naolido="${esc(e.id)}" title="Volta a ficar como não lido pra equipe">${ic("i-olho")}Não lido</button>`
    : cinza ? `<span class="dica">Respondido · sai da caixa quando o Outlook do PC dono confirmar</span>`
    : `<span class="dica">${enviado ? "E-mail enviado" : (PASTAS[e.pasta] || "") + " no Outlook"} · só leitura</span>`;
  el.innerHTML = `<div class="av" aria-hidden="true">${enviado ? "↗" : esc(iniciais(e.nome || e.de))}</div>
    <div class="quem"><b>${esc(enviado ? "Para: " + e.para : e.nome || e.de)}</b>
      <small>${esc(e.hotel || "")}${e.pc ? " · caixa no PC de " + esc(nomeAgente(e.pc)) : ""} · ${esc(quando(e.quando))}</small>
      ${(e.classes || []).length ? `<div class="linha-et">${e.classes.map(etiqueta).join("")}</div>` : ""}</div>
    <div class="botoes">${noEspelho && !cinza ? "" : botoes}<button class="fechar" id="cx-fechar" aria-label="Fechar o e-mail" title="Fechar (Esc)">×</button></div>
    ${noEspelho && !cinza ? `<span class="dica-prof so-texto" style="flex-basis:100%">Atalhos: Ctrl+R responder · Ctrl+Shift+R com NF · Ctrl+F encaminhar · Delete excluir · Ctrl+U não lido</span>` : ""}`;
}

// Lista limpa (usuário, 11/10/2026: "muita informação dentro de uma só"): 2 linhas como o Outlook — quem mandou e a
// hora; o assunto e o hotel pequeno. Prazo, etiquetas, análise da NF e prévia ficam no e-mail aberto.
function linhaEmail(e) {
  const enviado = e.pasta === "enviado", excluido = e.pasta === "excluido";
  const cinza = !!cx.resolvendo[e.id], sel = cx.sel === e.id, naoLido = !enviado && e.lido === false && !cinza;
  const quem = enviado ? "Para: " + (e.para || "") : (e.nome || e.de || (e.classes?.includes("aviso") ? "Aviso do Outlook" : "(sem remetente)"));
  const situacao = cinza || e.respondido ? " · respondido" : excluido ? " · excluído" :
    e.classes?.includes("formulario") ? " · solicitação do formulário" : e.classes?.includes("aviso") ? " · aviso do Outlook" : enviado && e.via ? (e.via === "painel" ? " · pelo Painel" : " · pelo Outlook") : "";
  return `<div class="cx-l ${naoLido ? "nao-lido" : ""} ${sel ? "sel" : ""} ${cinza ? "cinza" : ""}" role="option" tabindex="0"
      aria-selected="${sel}" data-id="${esc(e.id)}" title="${e.urgente ? esc(e.motivo_urgencia || "Urgente") : ""}">
    <div class="cx-l1">${e.urgente && !cinza ? `<span class="cx-ponto" aria-label="urgente"></span>` : ""}<span class="cx-quem">${esc(quem)}</span>
      <span class="cx-hora">${horaCurta(e.quando)}</span></div>
    <div class="cx-l2">${esc(e.assunto || "(sem assunto)")}<span class="cx-onde"> · ${esc(e.hotel || "")}${situacao}</span>${e.pc ? opMini(nomeAgente(e.pc)) : ""}</div>
    ${tagsEmail(e, cinza)}${naoLido ? `<span class="so-leitor">não lido</span>` : ""}</div>`;
}
// Tags da repaginação v2 (usuário, 14/10/2026): só urgência, nota dividida e falta de dados
function pedidoDoEmail(e) {
  return e.solicitacao && typeof acharPedido === "function" ? acharPedido(e.solicitacao.chave) : null;
}
function tagsEmail(e, cinza) {
  if (e.pasta !== "entrada" || cinza || e.respondido) return "";
  const s = pedidoDoEmail(e), falta = s && typeof faltaDados === "function" ? faltaDados(s) : [];
  const urg = e.urgente ? (/dias sem resposta/.test(e.motivo_urgencia || "") ? e.motivo_urgencia.replace(/^(\d+) dias sem resposta$/, "Sem resposta há $1 dias")
    : /corre/i.test(e.motivo_urgencia || "") ? "Pedido de correção" : "Urgente") : "";
  const tags = (urg ? `<span class="tg t-urg">${esc(urg)}</span>` : "") +
    (falta.length ? `<span class="tg t-falta">Falta: ${esc(falta[0])}${falta.length > 1 ? ` +${falta.length - 1}` : ""}</span>` : "") +
    ((e.quartos?.[0] || e.quartos || 0) >= 2 ? `<span class="tg t-div">Nota dividida</span>` : "");
  return tags ? `<div class="cx-l3">${tags}</div>` : "";
}
// Faixa do pedido ligado ao e-mail, acima dele (prévia v2): prazo, o que falta, quem cuida, abrir a ficha
function faixaPedido(e) {
  const s = pedidoDoEmail(e);
  if (!s) return e.solicitacao ? `<div class="cx-pedido"><div><small>Pedido</small><b>do formulário de ${esc(String(e.solicitacao.data || "").split("-").reverse().join("/"))}</b></div>
    <div><small>Hotel</small><b>${esc(e.solicitacao.hotel || "")}</b></div><div><small>Situação</small><b>pedido antigo, fora da lista de Notas fiscais</b></div></div>` : "";
  const falta = typeof faltaDados === "function" ? faltaDados(s) : [];
  return `<div class="cx-pedido" aria-label="Pedido ligado a este e-mail">
    <div><small>Pedido</small><b>${esc(s.nome)}</b></div>
    <div><small>Prazo</small>${s.prazo ? prazoHtml(s.prazo) : "<b>—</b>"}</div>
    <div><small>Dados para emitir</small>${falta.length ? `<b class="atn">falta ${esc(falta.join(", "))}</b>` : `<b class="ok">completos</b>`}</div>
    <div><small>Com</small><b>${esc(s.dono || "ninguém")}</b></div>
    ${s.nfs?.length ? `<div><small>NF</small><b class="ok">${esc(s.nfs.join(", "))}</b></div>` : ""}
    <button type="button" class="cx-abrir-ficha" data-abrir-ficha="${esc(s.chave)}">Abrir ficha</button></div>`;
}
document.addEventListener("click", ev => {
  const b = ev.target.closest("[data-abrir-ficha]");
  if (!b || typeof abrirNotas !== "function") return;
  const chave = b.dataset.abrirFicha;
  abrirNotas({ filtro: "todas" });
  sel = chave; desenhar();
});

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
// Responder / encaminhar dentro do painel de leitura, com o original citado embaixo (como o Outlook)
function citacaoHtml(id) {
  const e = itemSelecionado() || (cx.dados?.emails || []).find(x => x.id === id), t = cx.textos[id] || {};
  if (!e) return "";
  return `<div class="cx-cit-cab"><b>De:</b> ${esc(e.nome || e.de)} &lt;${esc(e.de)}&gt;<br><b>Enviado:</b> ${esc(dataLonga(e.quando))}<br>
    <b>Para:</b> ${esc(e.caixa || e.para || "")}<br><b>Assunto:</b> ${esc(e.assunto || "")}</div><div class="cx-texto">${esc(t.texto || e.previa || "")}</div>`;
}
function escrever(id, modo) {   // modo: "resp" | "nf" | "enc"
  const alvo = $("cx-leitura");
  if (cx.sel !== id) { cx.sel = id; desenharCorreio(); }
  abrirEnvioNF(null, { id, comNF: modo === "nf", encaminhar: modo === "enc", citacao: citacaoHtml(id) }, alvo);
}
function abrirEmail(id) {
  if (typeof envNF !== "undefined" && envNF && envNF.alvo && cx.sel !== id) { toast("Envie ou descarte a mensagem que está escrevendo", true); return; }
  cx.sel = id;
  const e = itemSelecionado();
  desenharCorreio();
  if (!e) return;
  carregarTexto(e);
  if (e.pasta !== "enviado" && e.de) carregarHistorico(e.de);
  if (e.lido === false && !cx.manterNaoLido[e.id]) {   // abriu = lido (pra equipe toda)
    api("/api/correio/evento", { ids: [e.id], acao: "LIDO" });
    e.lido = true;
    if (cx.dados?.contagem) cx.dados.contagem.entrada_nao_lidos = Math.max(0, cx.dados.contagem.entrada_nao_lidos - 1);
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
  // hóspede único: os e-mails dos outros endereços dele (mesmo CPF/CNPJ) entram no histórico também
  const outros = (conv.enderecos || []).slice(0, 2);
  if (!outros.length) return;
  const extras = await Promise.all(outros.map(x => api("/api/correio/buscar?q=" + encodeURIComponent(x))));
  const vistos = new Set(cx.hist[de].resultados.map(x => x.id));
  extras.forEach((rx, k) => (rx.resultados || []).filter(x => (x.de === outros[k] || (x.para || "").includes(outros[k])) && !vistos.has(x.id) && vistos.add(x.id))
    .forEach(x => cx.hist[de].resultados.push(x)));
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

function desenharLeituraCorreio() {
  desenharAcoes();
  const el = $("cx-leitura");
  if (typeof envNF !== "undefined" && envNF && envNF.alvo === el) return;   // escrevendo uma resposta: não apaga
  const e = cx.sel && itemSelecionado();
  if (!e) {   // a leitura fica sempre à direita, como no Outlook (o topo da página não some: é onde está a pesquisa)
    el.innerHTML = `<div class="cx-ler-vazio"><svg aria-hidden="true"><use href="#i-mail"/></svg><b>Selecione um e-mail para ler</b>
      <span>Clique numa linha da lista · as setas ↑ ↓ andam pelos e-mails</span></div>`;
    return;
  }
  if (document.activeElement && el.contains(document.activeElement) && /INPUT|TEXTAREA|SUMMARY/.test(document.activeElement.tagName)) return;
  const enviado = e.pasta === "enviado";
  const h = !enviado && e.de ? cx.hist[e.de] : null;
  el.innerHTML = `${enviado ? "" : faixaPedido(e)}
    <div class="cx-msg">
      <h2>${esc(e.assunto || "(sem assunto)")}</h2>
      ${e.alerta_doc ? `<div class="cx-verifica"><b>NF com CPF/CNPJ diferente do pedido</b><div>${esc(e.alerta_doc)}</div>
        <div class="dica">O robô abriu a nota deste hóspede e comparou com o formulário. Confira antes de responder.</div></div>` : ""}
      ${verificacaoHtml(e)}
      <div class="cx-ficha">
        <div class="cx-fl"><span>De</span><span>${enviado ? esc(e.caixa) : `<b>${esc(e.nome || e.de)}</b> &lt;${esc(e.de)}&gt;`}</span></div>
        <div class="cx-fl"><span>Para</span><span>${esc(enviado ? e.para : e.caixa || e.para)}</span></div>
        <div class="cx-fl"><span>Data</span><span>${esc(dataLonga(e.quando))}</span></div>
        <div class="cx-fl"><span>Hotel</span><span>${esc(e.hotel || "")}${e.pc ? ` · caixa no PC de ${esc(nomeAgente(e.pc))}${e.pc && !pcOnline(e.pc) ? " (desligado: o que for pedido sai quando ele ligar)" : ""}` : ""}</span></div>
        ${(e.classes || []).length ? `<div class="cx-fl"><span>Assunto</span><span>${e.classes.map(etiqueta).join("")}</span></div>` : ""}
        ${e.pasta === "entrada" && e.prazo ? `<div class="cx-fl"><span>Prazo</span><span>${prazoHtml(e.prazo)} · ${esc(e.prazo.nome)} (${e.prazo.horas} h, contado do 1º e-mail sem resposta)</span></div>` : ""}
        ${e.lido_por ? `<div class="cx-fl"><span>Lido</span><span>por ${esc(e.lido_por)} às ${esc(String(e.lido_em).slice(11, 16))}</span></div>` : ""}
      </div>
      ${avisoNfJaEnviada(h)}
      ${corpoTexto(e.id)}${anexosHtml(e.anexos, { id: e.id, id_espelho: noEspelhoDoPainel(e) ? e.id : "", pc: e.pc, entry: e.entry || "" })}
      ${h ? historicoHtml(h, e) : ""}
    </div>`;
}

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
  const outros = h.conv?.enderecos || [];
  return `<section class="cx-hist"><div class="cx-hist-t">Histórico deste hóspede no Outlook <span>${linhas.length}</span></div>
    ${outros.length ? `<p class="dica">Mesmo hóspede (mesmo CPF/CNPJ) também usa: ${esc(outros.join(", "))}</p>` : ""}
    ${linhas.map(l => l.html).join("") || `<p class="dica">Nenhum outro e-mail deste endereço no Outlook dos PCs ligados.</p>`}
    ${sem.length ? `<p class="dica">Sem resposta de: ${esc(sem.join(", "))} (desligado).</p>` : ""}</section>`;
}
function linhaHist(x) {
  const aberto = cx.hist.aberto === x.id;
  return `<div class="cx-h ${aberto ? "aberto" : ""}" data-cx-hist="${esc(x.id)}" tabindex="0" role="button" aria-expanded="${aberto}">
      <span class="cx-h-tipo t-${x.pasta}">${x.pasta === "enviado" ? "↗ Enviado" : x.pasta === "excluido" ? "✕ Excluído" : "↙ Recebido"}</span>
      <span class="cx-h-data">${esc(quando(x.quando))}</span><span class="cx-h-ass">${esc(x.assunto || "(sem assunto)")}</span>
      <span class="cx-h-pc">${esc(nomeAgente(x.pc))}</span></div>
    ${aberto ? `<div class="cx-h-corpo">${corpoTexto(x.id)}${anexosHtml(x.anexos, { id: x.id, id_espelho: "", pc: x.pc, entry: x.entry || "" })}</div>` : ""}`;
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

// Caixas de entrada à esquerda, como as pastas do Outlook (usuário, 15/10/2026: "só as caixas de entrada"):
// todas as caixas no alto e, por agente, a caixa de cada hotel com os não lidos. Clicar filtra a lista.
function desenharPastas() {
  const el = $("cx-pastas");
  if (!el) return;
  const naoLidos = {}, entrada = emailsDa("entrada");
  entrada.forEach(e => { if (e.lido === false) (e.hotel || "").split(" / ").forEach(h => h && (naoLidos[h] = (naoLidos[h] || 0) + 1)); });
  const total = entrada.filter(e => e.lido === false).length;
  const grupos = {};
  (st.hoteis || []).forEach(h => { if (doAgente([h.agente])) (grupos[h.agente || "Sem agente"] ||= []).push(h.hotel); });
  const n = v => v ? `<em>${v.toLocaleString("pt-BR")}</em>` : "";
  el.innerHTML = `<button type="button" class="cx-pa todas ${cx.hotel ? "" : "on"}" data-cx-pasta="">
      <svg class="ic" aria-hidden="true"><use href="#i-caixa"/></svg><span class="nm">Todas as caixas</span>${n(total)}</button>` +
    Object.entries(grupos).sort(([a], [b]) => a.localeCompare(b, "pt")).map(([ag, hs]) => {
      const aberto = !cx.fechados[ag], soma = hs.reduce((s, h) => s + (naoLidos[h] || 0), 0);
      return `<button type="button" class="cx-pg" data-cx-grupo="${esc(ag)}" aria-expanded="${aberto}"><span class="seta">▼</span>${esc(ag)}${soma ? `<small>${soma}</small>` : ""}</button>` +
        (aberto ? hs.sort((x, y) => x.localeCompare(y, "pt")).map(h => `<button type="button" class="cx-pa ${naoLidos[h] ? "tem" : ""} ${cx.hotel === h ? "on" : ""}"
          data-cx-pasta="${esc(h)}" title="Caixa de entrada · ${esc(h)}"><span class="nm">${esc(h)}</span>${n(naoLidos[h])}</button>`).join("") : "");
    }).join("");
}
try { cx.fechados = JSON.parse(localStorage.getItem("painel.caixasFechadas") || "{}") || {}; } catch (e) {}
document.addEventListener("click", ev => {
  const t = ev.target.closest("[data-cx-pasta],[data-cx-grupo],[data-cx-filtro],[data-cx-faixa]");
  if (!t) return;
  const d = t.dataset;
  if (d.cxPasta !== undefined) { cx.hotel = d.cxPasta; cx.sel = null; return desenharCorreio(); }
  if (d.cxGrupo !== undefined) {
    cx.fechados[d.cxGrupo] = !cx.fechados[d.cxGrupo];
    try { localStorage.setItem("painel.caixasFechadas", JSON.stringify(cx.fechados)); } catch (e) {}
    return desenharPastas();
  }
  if (d.cxFiltro) { cx.soNaoLidos = d.cxFiltro === "naolidos"; cx.sel = null; return desenharCorreio(); }
  const id = cx.sel;
  if (!id || t.disabled) return;
  if (d.cxFaixa === "resp") return escrever(id, "resp");
  if (d.cxFaixa === "nf") return escrever(id, "nf");
  if (d.cxFaixa === "enc") return escrever(id, "enc");
  if (d.cxFaixa === "exc") return excluir(id);
  if (d.cxFaixa === "naolido") return marcarNaoLido(id);
});

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
  if (d.cxResp) return escrever(d.cxResp, "resp");
  if (d.cxRespNf) return escrever(d.cxRespNf, "nf");
  if (d.cxEnc) return escrever(d.cxEnc, "enc");
  if (d.cxExcluir) return excluir(d.cxExcluir);
  if (d.cxNaolido) marcarNaoLido(d.cxNaolido);
});
function marcarNaoLido(id) {
  const x = (cx.dados?.emails || []).find(m => m.id === id);
  api("/api/correio/evento", { ids: [id], acao: "NAO_LIDO" });
  if (x && x.lido !== false) { x.lido = false; cx.dados.contagem.entrada_nao_lidos++; }
  cx.manterNaoLido[id] = true; cx.sel = null; desenharLateralCorreio(); desenharCorreio();
  toast("Marcado como não lido para a equipe");
}
// Atalhos iguais aos do Outlook (usuário, 09/10/2026). Não valem enquanto se digita num campo ou com janela aberta.
document.addEventListener("keydown", e => {
  const digitando = /INPUT|TEXTAREA|SELECT/.test(e.target.tagName) || e.target.isContentEditable;
  const janela = !!document.querySelector(".modal-fundo");
  const k = (e.key || "").toLowerCase();
  if (e.key === "?" && !digitando && !janela) { e.preventDefault(); return abrirAjuda(); }
  if (e.ctrlKey && k === "e" && !janela) { e.preventDefault(); $("busca").focus(); $("busca").select(); return; }
  if (pn.vista !== "correio" || digitando || janela) return;
  const aberto = cx.sel && (cx.dados?.emails || []).some(x => x.id === cx.sel) && !cx.resolvendo[cx.sel] ? cx.sel : "";
  const precisa = () => { toast("Abra um e-mail da caixa primeiro (clique ou use as setas)", true); };
  if (e.ctrlKey && k === "r") { e.preventDefault(); return aberto ? escrever(aberto, e.shiftKey ? "nf" : "resp") : precisa(); }
  if (e.ctrlKey && k === "f") { e.preventDefault(); return aberto ? escrever(aberto, "enc") : precisa(); }
  if (e.key === "Delete") { e.preventDefault(); return aberto ? excluir(aberto) : precisa(); }
  if (e.ctrlKey && k === "u") { e.preventDefault(); return aberto ? marcarNaoLido(aberto) : precisa(); }
  if (e.ctrlKey && k === "q") {
    e.preventDefault();
    if (!aberto) return precisa();
    const x = (cx.dados?.emails || []).find(m => m.id === aberto);
    if (x && x.lido === false) { api("/api/correio/evento", { ids: [aberto], acao: "LIDO" }); x.lido = true; desenharLateralCorreio(); desenharCorreio(); }
    return toast("Marcado como lido para a equipe");
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
  if (e.key === "Escape" && !document.querySelector(".modal-fundo") && cx.sel && !(typeof envNF !== "undefined" && envNF && envNF.alvo)) { cx.sel = null; desenharCorreio(); }
});

// Novo e-mail ao hóspede (usuário, 13/10/2026): como no Outlook, com a solicitação de dados já pronta
document.addEventListener("click", e => {
  if (e.target.closest("#cx-novo")) abrirEnvioNF(null, { novo: true });
});
