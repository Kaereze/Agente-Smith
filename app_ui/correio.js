// E-mails: espelho do Outlook dos 4 PCs, no formato do Outlook (usuário, 08/10/2026): lista compacta, 1 linha por
// e-mail separada por Hoje / Ontem / Esta semana; ao clicar, o e-mail aberto à direita (De, Para, Data, texto) e o
// histórico do hóspede puxado ao vivo do Outlook. Tudo que se faz aqui (responder, encaminhar, excluir) roda no
// Outlook do PC dono por trás, sem abrir janela. A busca vai direto ao Outlook dos 4 PCs. Usa api/$/esc/toast/st.
let cx = { caixa: "entrada", dados: null, sel: null, hist: {}, textos: {}, hotel: "", live: null, buscando: "",
           resolvendo: {}, escondidos: {}, desfazer: null, manterNaoLido: {}, timerBusca: null, conv: {},
           soNaoLidos: false, fechados: {}, caixaSel: "", soForm: false, pcsAbertos: {}, pcsTodas: {}, aba: "inicio",
           semPastas: false, menu: false };   // igual ao Outlook (15/10/2026): pasta escolhida, faixa e menus
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
  const lista = base.filter(e => (!cx.hotel || (e.hotel || "").split(" / ").includes(cx.hotel)) && (!cx.soNaoLidos || e.lido === false)
    && (!cx.caixaSel || String(e.caixa || "").toLowerCase() === cx.caixaSel) && (!cx.soForm || (e.classes || []).includes("formulario")));
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
  desenharFaixa();
  const nomePasta = cx.caixaSel ? nomeDaCaixa(cx.caixaSel) : "";
  const titulo = busca ? "Resultado da pesquisa" : cx.soForm ? "Formulários do robô" :
    (cx.caixa === "enviados" ? "Itens Enviados" : cx.caixa === "urgencia" ? "Urgência" : "Caixa de Entrada") + (nomePasta ? " · " + nomePasta : "");
  if ($("cx-lcab")) $("cx-lcab").innerHTML = `<div class="ol-lcab">` + (busca ? `<span class="ol-ord">no Outlook dos 4 PCs</span>` :
    `<button type="button" data-cx-filtro="todas" aria-pressed="${!cx.soNaoLidos}">Todas</button>` +
    (cx.caixa === "enviados" ? "" : `<button type="button" data-cx-filtro="naolidos" aria-pressed="${cx.soNaoLidos}">Não lidos</button>`) +
    `<span class="ol-ord">Por Data ↓</span>`) + `</div><div class="ol-ltit"><b>${esc(titulo)}</b> · ${lista.length.toLocaleString("pt-BR")} itens` +
    (naoLidos ? ` · ${naoLidos.toLocaleString("pt-BR")} não lidos` : "") + `</div>`;
  if ($("ol-contagem")) $("ol-contagem").innerHTML = `<span>Itens: ${lista.length.toLocaleString("pt-BR")}</span><span>Não lidos: ${naoLidos.toLocaleString("pt-BR")}</span>`;
  $("v-correio").classList.toggle("sem-pastas", !!cx.semPastas);
  // a lista é refeita a cada 15 s: quem estava com o foco numa linha continua nela
  const focada = document.activeElement?.closest?.("#cx-lista .cx-l");
  const idFoco = focada?.dataset.id;
  let grupo = "", html = "";
  for (const e of lista) {
    const g = cx.caixa === "urgencia" && !busca ? "" : grupoData(e.quando);
    if (g && g !== grupo) { html += `<div class="cx-grupo">▾ ${g}</div>`; grupo = g; }
    html += linhaEmail(e);
  }
  const quem = escopoAtual() === "todos" ? "" : ` de ${escopoAtual()}`;
  const vazio = cx.buscando ? "Procurando no Outlook dos PCs…" : busca ? `Nenhum e-mail com “${esc(busca)}”.`
    : cx.caixa === "enviados" ? "Nada enviado nas últimas 24 h." : cx.soNaoLidos ? "Nenhum e-mail não lido aqui." : "";
  $("cx-lista").innerHTML = html || (vazio ? `<div class="vazio">${vazio}</div>`
    : caixaEmDia(cx.caixa === "urgencia" ? `Nada urgente na caixa${quem}.` : `Caixa de Entrada vazia${quem}.`));
  if (idFoco) $("cx-lista").querySelector(`.cx-l[data-id="${CSS.escape(idFoco)}"]`)?.focus();
  desenharLeituraCorreio();
  if (!busca) preCarregar(lista);
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
function linhaEmail(e) {   // igual à prévia aprovada (15/10/2026): quem, assunto, hora, prévia e etiquetas
  const enviado = e.pasta === "enviado";
  const cinza = !!cx.resolvendo[e.id], sel = cx.sel === e.id, naoLido = !enviado && e.lido === false && !cinza;
  const quem = enviado ? "Para: " + (e.para || "") : (e.classes?.includes("formulario") ? "Formulário · robô" :
    e.nome || e.de || (e.classes?.includes("aviso") ? "Aviso do Outlook" : "(sem remetente)"));
  const situacao = cinza || e.respondido ? "respondido · " : e.pasta === "excluido" ? "excluído · " : "";
  const previa = situacao + (e.hotel ? e.hotel + " · " : "") + (e.previa || "");
  const clip = (e.anexos || []).length ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-label="tem anexo"><path d="M21 11l-9 9a6 6 0 01-8-8l9-9a4 4 0 016 6l-9 9a2 2 0 01-3-3l8-8"/></svg>` : "";
  return `<div class="cx-l ${naoLido ? "nao-lido" : ""} ${sel ? "sel" : ""} ${cinza ? "cinza" : ""}" role="option" tabindex="0"
      aria-selected="${sel}" data-id="${esc(e.id)}" title="${e.urgente ? esc(e.motivo_urgencia || "Urgente") : ""}">
    <span class="it-de">${esc(quem)}</span><span class="it-ic">${e.urgente && !cinza ? `<span class="urg" aria-label="urgente"></span>` : ""}${clip}</span>
    <span class="it-as">${esc(e.assunto || "(sem assunto)")}</span><time>${horaCurta(e.quando)}</time>
    <span class="it-pv">${esc(previa)}</span>${tagsEmail(e, cinza)}${naoLido ? `<span class="so-leitor">não lido</span>` : ""}</div>`;
}
// Tags da repaginação v2 (usuário, 14/10/2026): só urgência, nota dividida e falta de dados
function pedidoDoEmail(e) {
  return e.solicitacao && typeof acharPedido === "function" ? acharPedido(e.solicitacao.chave) : null;
}
function tagsEmail(e, cinza) {
  if ((e.pasta && e.pasta !== "entrada") || cinza || e.respondido) return "";
  const s = pedidoDoEmail(e), falta = s && typeof faltaDados === "function" ? faltaDados(s) : [];
  const urg = e.urgente ? (/dias sem resposta/.test(e.motivo_urgencia || "") ? e.motivo_urgencia.replace(/^(\d+) dias sem resposta$/, "Sem resposta há $1 dias")
    : /corre/i.test(e.motivo_urgencia || "") ? "Pedido de correção" : "Urgente") : "";
  const tags = (urg ? `<span class="tg t-urg">${esc(urg)}</span>` : "") +
    (falta.length ? `<span class="tg t-falta">Falta: ${esc(falta[0])}${falta.length > 1 ? ` +${falta.length - 1}` : ""}</span>` : "") +
    ((e.quartos?.[0] || e.quartos || 0) >= 2 ? `<span class="tg t-div">Nota dividida</span>` : "");
  const form = (e.classes || []).includes("formulario") ? `<span class="tg t-form">Formulário</span>` : "";
  return tags || form ? `<div class="it-tg">${tags}${form}</div>` : "";
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
  preCarregarAnexos(e);
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
  if (cx.sel === chave || cx.hist.aberto === chave) desenharLeituraCorreio();   // pré-carregado: só guarda
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

const SVG = d => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
const IC = { resp: '<path d="M9 14L4 9l5-5"/><path d="M4 9h11a5 5 0 015 5v5"/>', todos: '<path d="M7 14L2 9l5-5"/><path d="M12 14L7 9l5-5"/><path d="M7 9h9a5 5 0 015 5v5"/>',
  enc: '<path d="M15 14l5-5-5-5"/><path d="M20 9H9a5 5 0 00-5 5v5"/>', lixo: '<path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13"/>',
  arq: '<rect x="3" y="4" width="18" height="5" rx="1"/><path d="M5 9v11h14V9M10 13h4"/>', mover: '<path d="M3 7h7l2 2h9v10H3z"/>',
  lido: '<path d="M3 9l9-6 9 6v10H3z"/><path d="M3 9l9 6 9-6"/>', band: '<path d="M5 21V4h11l-2 4 2 4H5"/>', nf: '<path d="M7 3h7l5 5v13H7z"/><path d="M14 3v5h5"/>',
  sync: '<path d="M20 11a8 8 0 00-14-5L4 8M4 4v4h4M4 13a8 8 0 0014 5l2-2M20 20v-4h-4"/>', novo: '<path d="M12 5v14M5 12h14"/>',
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
    : `<button type="button" class="p" id="cx-novo" title="Escrever um e-mail novo ao hóspede, saindo da caixa do hotel">${SVG(IC.novo)} Novo e-mail</button><span class="sep"></span>` +
      bt('data-cx-faixa="exc"', "lixo", "Excluir", 'title="Delete"') + bt("", "arq", "Arquivar", nao) + bt("", "mover", "Mover ▾", nao) + `<span class="sep"></span>` +
      bt('data-cx-faixa="resp"', "resp", "Responder", 'title="Ctrl+R"') + bt('data-cx-faixa="resp"', "todos", "Responder a todos") + bt('data-cx-faixa="enc"', "enc", "Encaminhar", 'title="Ctrl+F"') +
      `<span class="sep"></span>` + bt('data-cx-faixa="lido"', "lido", "Não lido/Lido", 'title="Ctrl+U / Ctrl+Q"') + bt("", "band", "Sinalizar", nao) +
      `<div class="dir">${bt('data-cx-faixa="nf"', "nf", "Enviar NF", 'title="Responder com a NF · Ctrl+Shift+R"')}${bt('data-ol-acao="sync"', "sync", "Enviar/Receber todas")}</div>`;
}
function desenharFaixaGlobal() {
  const el = $("ol-faixa-g");
  if (!el) return;
  document.querySelectorAll("[data-ol-aba]").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.olAba === cx.aba)));
  const bt = (attr, ic, txt, cls = "") => `<button type="button" class="${cls}" ${attr}>${SVG(IC[ic])} ${txt}</button>`;
  el.innerHTML = cx.aba === "enviar" ? bt('data-ol-acao="sync"', "sync", "Enviar/Receber todas as pastas") + bt('data-ol-acao="pendentes"', "env", "Enviar solicitações pendentes")
    : cx.aba === "exibir" ? bt('data-ol-acao="tema"', "tema", "Tema do Painel") + bt('data-ol-acao="prof"', "chapeu", "Modo professor")
    : bt('data-ol-acao="novo"', "novo", "Novo e-mail", "p") + `<span class="sep"></span>` + bt('data-vista="correio" data-caixa="entrada"', "caixa", "Caixa de Entrada") +
      bt('data-vista="correio" data-caixa="urgencia"', "alerta", "Urgência") + bt('data-vista="fila"', "form", "Notas fiscais") + `<span class="sep"></span>` +
      bt('data-ol-acao="pendentes"', "env", "Enviar pendentes") + bt('data-ol-acao="sync"', "sync", "Enviar/Receber todas");
}
const hotelDaCaixa = c => (st.hoteis || []).filter(h => h.email === c).map(h => h.hotel).join(" / ");
const nomeDaCaixa = c => hotelDaCaixa(c) || String(c).split("@")[1]?.replace(/^(redeandrade|hotel)/, "").replace(/(hotel)?\.com(\.br)?$/, "").toUpperCase() || c;
// Ficha do pedido (creme), no topo do e-mail como na prévia: tomador, documento, o que pede, nota, prazo e os 3 botões
function fichaPedidoOl(e) {
  const s = pedidoDoEmail(e);
  if (!s) return e.solicitacao ? `<section class="ol-ficha"><div class="ft"><b>Ficha do pedido</b> · ${esc(e.solicitacao.hotel || "")} · formulário de
    ${esc(String(e.solicitacao.data || "").split("-").reverse().join("/"))} · pedido antigo, fora da lista de Notas fiscais</div></section>` : "";
  const tom = campoDoPedido(s, /nome.*tomador/, /razao social/, /^nome( completo)?$/);
  const doc = campoDoPedido(s, /documento.*tomador/, /cpf.*cnpj|cnpj.*cpf/, /^cnpj/, /^cpf(?!.*titular)/);
  const pede = campoDoPedido(s, /informac/, /o que.*nota/, /itens/);
  // hóspede e o CPF dele SEMPRE, mesmo com a nota no CNPJ (usuário, 15/10/2026: "nunca esquece isso")
  const hosp = campoDoPedido(s, /nome.*titular/, /nome do hospede/, /^hospede/) || (soDigitos(doc).length === 11 ? tom : "");
  const cpfH = campoDoPedido(s, /cpf.*titular/, /documento do hospede/, /cpf.*hospede/) || (soDigitos(doc).length === 11 ? doc : "");
  const v = x => x ? `<span>${esc(x)}</span>` : `<span class="falta">falta pedir</span>`;
  const i = prazoInfo(s.prazo);
  const barra = i ? Math.max(4, Math.min(100, Math.round(100 * i.resta / (s.prazo.horas || 48)))) : 0;
  const div = s.dividida || s.partes > 1 ? `<span class="div">nota dividida em ${Math.max(s.partes || 2, 2)}</span>` : "";
  return `<section class="ol-ficha" aria-label="Ficha do pedido"><div class="ft"><b>Ficha do pedido</b> · ${esc(s.hotel)}${s.dono ? " · com " + esc(s.dono) : ""} ${div}
      ${s.nfs?.length ? `<span class="div">NF ${esc(s.nfs.join(", "))}</span>` : ""}
      ${i ? `<span class="prz ${i.nivel}">prazo: ${esc(i.texto)} <i><b style="width:${barra}%"></b></i></span>` : ""}</div>
    <div class="fg"><div><small>Tomador</small>${v(tom)}</div><div><small>CNPJ / CPF</small>${v(doc)}</div>
      <div><small>O que pede</small>${v(pede)}</div><div><small>Hóspede</small>${v(hosp)}</div><div><small>CPF do hóspede</small>${v(cpfH)}</div></div>
    <div class="fb"><button type="button" class="p" data-cx-faixa="nf">Enviar NF</button>
      ${faltaDados(s).length ? `<button type="button" data-pedir-dados="${esc(s.chave)}">Pedir o que falta</button>` : ""}
      <button type="button" data-abrir-ficha="${esc(s.chave)}">Marcar tratativa</button></div></section>`;
}
// Formulário aberto como o e-mail que chega no Outlook: o hotel, a solicitação e a tabela Campo / Valor, linha a linha
const OCULTOS_FORM = /^(enviado|carimbo|termos|importante|avalia|preenchimento|ritmo|sugest|sincroniz)/i;
function formularioHtml(s) {
  const semAc = x => String(x || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  const linhas = (s.campos || []).filter(([k, val]) => String(val || "").trim() && !OCULTOS_FORM.test(semAc(k)));
  const nome = campoDoPedido(s, /nome.*tomador/, /razao social/, /^nome( completo)?$/) || s.nome || "";
  return `<div class="ol-form"><div class="ol-hot">${esc(s.hotel)} <span style="font-weight:400;opacity:.85">(formulário de ${esc(dataBr(s.data))})</span></div>
    <div class="ol-sol">Solicitação — ${esc(nome)}</div>
    <table><tr><th>Campo</th><th>Valor</th></tr>${[["E-mail do hóspede", s.email], ...linhas].map(([k, val]) =>
      `<tr><td>${esc(k)}</td><td>${esc(val)}</td></tr>`).join("")}</table></div>`;
}
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
  const h = !enviado && e.de ? cx.hist[e.de] : null;
  const noEspelho = (cx.dados?.emails || []).some(x => x.id === e.id), cinza = !!cx.resolvendo[e.id];
  const nome = enviado ? nomeDaCaixa(String(e.caixa || "").toLowerCase()) : robo ? "Robô do formulário" : (e.nome || e.de || "");
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
  el.innerHTML = `<div class="ol-cab"><h1>${esc(e.assunto || "(sem assunto)")}</h1>
      <div class="ol-rem"><span class="ol-av ${robo || enviado ? "robo" : ""}" aria-hidden="true">${esc(enviado ? "↗" : iniciais(nome).slice(0, 1))}</span>
        <div class="ol-q"><b>${esc(nome)} ${ender ? `<small>&lt;${esc(ender)}&gt;</small>` : ""}</b><span>Para <i>${esc(para)}</i>${onde ? " · " + esc(onde) : ""}</span>
          ${(e.classes || []).filter(c => CLASSES[c]).length ? `<span>${e.classes.map(etiqueta).join(" ")}</span>` : ""}</div>
        <div class="ol-acoes">${botoes}<time>${esc(dataLonga(e.quando))}</time>
          <button type="button" class="link" id="cx-fechar" title="Fechar (Esc)" style="font-size:12px">fechar ✕</button></div></div></div>
    ${enviado ? "" : fichaPedidoOl(e)}
    ${e.alerta_doc ? `<div class="cx-verifica"><b>NF com CPF/CNPJ diferente do pedido</b><div>${esc(e.alerta_doc)}</div>
      <div class="dica">O robô abriu a nota deste hóspede e comparou com o formulário. Confira antes de responder.</div></div>` : ""}
    ${verificacaoHtml(e)}${avisoNfJaEnviada(h)}
    ${!pedidoDoEmail(e) && e.pasta === "entrada" && e.prazo ? `<div class="ol-corpo" style="padding-bottom:0"><span class="dica">Prazo de resposta: ${prazoHtml(e.prazo)}</span></div>` : ""}
    <div class="ol-corpo">${robo && pedidoDoEmail(e) ? formularioHtml(pedidoDoEmail(e)) : corpoTexto(e.id)}${anexosHtml(e.anexos, { id: e.id, id_espelho: noEspelhoDoPainel(e) ? e.id : "", pc: e.pc, entry: e.entry || "" })}</div>
    ${h ? historicoHtml(h, e) : ""}`;
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
  if (h.carregando) return "";
  const forms = (h.conv?.linha_do_tempo || []).filter(x => x.tipo === "formulario");
  const itens = h.resultados.filter(x => x.id !== atual.id);
  const sem = Object.entries(h.pcs).filter(([, s]) => !s.ok && s.erro !== "sem rede agora (usa a cópia)").map(([pc]) => h.agentes[pc] || pc);
  const linhas = [...itens.map(x => ({ q: x.quando, html: linhaHist(x) })),
    ...forms.map(f => ({ q: f.quando, html: `<div class="cx-h form"><span class="cx-h-tipo">Formulário</span><span class="cx-h-data">${dataBr(f.quando)}</span>
      <span class="cx-h-ass">${esc(f.hotel)} · ${NOMES[f.situacao] || f.situacao}${f.nfs.length ? " · NF " + esc(f.nfs.join(", ")) : ""}</span>
      <button class="link" data-ver-pedido="${esc(f.chave)}">abrir pedido</button></div>` }))]
    .sort((a, b) => String(b.q).localeCompare(String(a.q)));
  const outros = h.conv?.enderecos || [];
  return `<section class="cx-hist"><div class="cx-hist-t">Histórico deste hóspede no Outlook <span>${linhas.length}</span></div>
    ${outros.length ? `<p class="dica">Mesmo hóspede (mesmo CPF/CNPJ) também usa: ${esc(outros.join(", "))}</p>` : ""}
    ${linhas.map(l => l.html).join("") || (h.parcial ? "" : `<p class="dica">Nenhum outro e-mail deste endereço no Outlook dos PCs ligados.</p>`)}
    ${h.parcial ? `<div class="cx-h-nota">Completando com o Outlook dos 4 PCs (e-mails antigos, outras pastas)…</div>` : ""}
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

// Pastas à esquerda, como a prévia aprovada (15/10/2026): Favoritos e, por PC, a caixa de cada hotel (nome + e-mail +
// não lidos); a caixa escolhida abre a Caixa de Entrada e os Itens Enviados dela.
function desenharPastas() {
  const el = $("cx-pastas");
  if (!el) return;
  const entrada = emailsDa("entrada"), nl = {};
  entrada.forEach(e => { if (e.lido === false) { const c = String(e.caixa || "").toLowerCase(); nl[c] = (nl[c] || 0) + 1; } });
  const n = (v, cls = "") => v ? `<em class="${cls}">${v.toLocaleString("pt-BR")}</em>` : "";
  const favAberto = !cx.fechados.__fav;
  const fav = (k, ic, txt, v, on, cls) => `<button type="button" class="ol-fav ${on ? "on" : ""}" data-ol-fav="${k}">${SVG(IC[ic])}${txt}${n(v, cls)}</button>`;
  const semPasta = !cx.caixaSel;
  let h = `<button type="button" class="ol-gr" data-cx-grupo="__fav" aria-expanded="${favAberto}"><span class="chev">▼</span>Favoritos</button>` +
    (favAberto ? fav("entrada", "caixa", "Caixa de Entrada (todas)", entrada.filter(e => e.lido === false).length, semPasta && cx.caixa === "entrada" && !cx.soForm) +
      fav("urgencia", "alerta", "Urgência", emailsDa("urgencia").length, semPasta && cx.caixa === "urgencia", "r") +
      fav("form", "form", "Formulários do robô", entrada.filter(e => (e.classes || []).includes("formulario") && e.lido === false).length, semPasta && cx.soForm) +
      fav("enviados", "env", "Itens Enviados", 0, semPasta && cx.caixa === "enviados") : "") + `<hr class="ol-hr">`;
  const pcs = (st.pcs || []).filter(p => doAgente([p.agente]));
  const meu = cx.dados?.este_pc || "";
  for (const p of pcs.sort((a, b) => (a.pc === meu ? -1 : b.pc === meu ? 1 : String(a.agente).localeCompare(String(b.agente), "pt")))) {
    const contas = [...new Set((p.contas_lista || []).map(c => String(c).toLowerCase()))]
      .map(c => ({ c, hotel: nomeDaCaixa(c), n: nl[c] || 0 })).sort((a, b) => a.hotel.localeCompare(b.hotel, "pt"));
    const aberto = cx.pcsAbertos[p.pc] ?? (p.pc === meu || contas.some(x => x.c === cx.caixaSel) || pcs.length === 1);
    const soma = contas.reduce((s, x) => s + x.n, 0);
    h += `<div class="ol-pc" data-ol-pc="${esc(p.pc)}" title="${p.online ? "PC ligado" : "PC desligado"}">${esc(p.agente || p.pc)}<span>${esc(p.pc)}</span></div>`;
    if (!aberto) { h += `<button type="button" class="ol-mais-cx fechado" data-ol-pc="${esc(p.pc)}"><span class="chev" style="transform:rotate(-90deg)">▼</span> ${contas.length} caixas${n(soma)}</button>`; continue; }
    const todas = cx.pcsTodas[p.pc] || contas.length <= 6;
    const mostrar = todas ? contas : contas.filter((x, i) => i < 4 || x.c === cx.caixaSel);   // como a prévia: 4 e "+ N caixas"
    for (const x of mostrar) {
      const on = x.c === cx.caixaSel;
      h += `<button type="button" class="ol-cx ${x.n ? "tem" : ""}" data-ol-caixa="${esc(x.c)}" aria-expanded="${on}" title="${esc(x.c)}"><span class="chev">▼</span>
        <span class="nm"><b>${esc(x.hotel)}</b><small>${esc(x.c.split(".com")[0])}</small></span>${n(x.n)}</button>`;
      if (on) h += `<button type="button" class="ol-sub ${cx.caixa !== "enviados" ? "on" : ""}" data-ol-sub="entrada">Caixa de Entrada${n(x.n)}</button>
        <button type="button" class="ol-sub ${cx.caixa === "enviados" ? "on" : ""}" data-ol-sub="enviados">Itens Enviados</button>`;
    }
    if (mostrar.length < contas.length) h += `<button type="button" class="ol-mais-cx" data-ol-todas="${esc(p.pc)}"><span class="chev" style="transform:rotate(-90deg)">▼</span> + ${contas.length - mostrar.length} caixas</button>`;
  }
  el.innerHTML = h;
}
try { cx.fechados = JSON.parse(localStorage.getItem("painel.caixasFechadas") || "{}") || {}; } catch (e) {}
document.addEventListener("click", ev => {
  const t = ev.target.closest("[data-ol-fav],[data-ol-caixa],[data-ol-sub],[data-ol-pc],[data-ol-todas],[data-cx-grupo],[data-cx-filtro],[data-cx-faixa],[data-ol-aba],[data-ol-acao],[data-ol-menu]");
  if (!t) { if (cx.menu && !ev.target.closest(".ol-menu")) { cx.menu = false; desenharLeituraCorreio(); } return; }
  const d = t.dataset;
  if (d.olAba) { cx.aba = d.olAba; desenharFaixaGlobal(); return desenharFaixa(); }
  if (d.olAcao) {
    if (d.olAcao === "sync") { toast("Relendo as caixas dos 4 PCs…"); $("btn-atualizar")?.click(); carregarCorreio(); }
    if (d.olAcao === "pendentes") $("btn-enviar")?.click();
    if (d.olAcao === "pastas") { cx.semPastas = !cx.semPastas; desenharCorreio(); }
    if (d.olAcao === "tema") $("btn-tema")?.click();
    if (d.olAcao === "prof") $("btn-prof")?.click();
    if (d.olAcao === "novo") abrirEnvioNF(null, { novo: true });
    return;
  }
  if (d.olMenu !== undefined) { cx.menu = !cx.menu; return desenharLeituraCorreio(); }
  if (d.olFav) {
    cx.caixaSel = ""; cx.soForm = d.olFav === "form"; cx.caixa = d.olFav === "form" ? "entrada" : d.olFav; cx.sel = null; cx.hotel = "";
    return trocarVista("correio");
  }
  if (d.olCaixa) { cx.caixaSel = cx.caixaSel === d.olCaixa && cx.caixa === "entrada" ? "" : d.olCaixa; cx.caixa = "entrada"; cx.soForm = false; cx.sel = null; cx.hotel = ""; return trocarVista("correio"); }
  if (d.olSub) { cx.caixa = d.olSub; cx.sel = null; return trocarVista("correio"); }
  if (d.olTodas) { cx.pcsTodas[d.olTodas] = true; return desenharPastas(); }
  if (d.olPc) { const atual = $("cx-pastas").querySelector(`.ol-mais-cx.fechado[data-ol-pc="${CSS.escape(d.olPc)}"]`) ? false : true;
    cx.pcsAbertos[d.olPc] = !atual; return desenharPastas(); }
  if (d.cxGrupo !== undefined) {
    cx.fechados[d.cxGrupo] = !cx.fechados[d.cxGrupo];
    try { localStorage.setItem("painel.caixasFechadas", JSON.stringify(cx.fechados)); } catch (e) {}
    return desenharPastas();
  }
  if (d.cxFiltro) { cx.soNaoLidos = d.cxFiltro === "naolidos"; cx.sel = null; return desenharCorreio(); }
  const id = cx.sel;
  cx.menu = false;
  if (!id || t.disabled) return;
  if (d.cxFaixa === "resp") return escrever(id, "resp");
  if (d.cxFaixa === "nf") return escrever(id, "nf");
  if (d.cxFaixa === "enc") return escrever(id, "enc");
  if (d.cxFaixa === "exc") return excluir(id);
  if (d.cxFaixa === "naolido") return marcarNaoLido(id);
  if (d.cxFaixa === "lido") {
    const x = (cx.dados?.emails || []).find(m => m.id === id);
    if (x && x.lido === false) { api("/api/correio/evento", { ids: [id], acao: "LIDO" }); x.lido = true; desenharLateralCorreio(); desenharCorreio(); return toast("Marcado como lido para a equipe"); }
    return marcarNaoLido(id);
  }
});

function abrirCaixa(caixa) {
  cx.caixa = caixa; cx.sel = null; cx.hotel = ""; cx.caixaSel = ""; cx.soForm = false;
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
