// correio_lista.js: parte de correio.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// ---------- lista ----------
// Filtros rápidos (João, 07/11/2026): dois botões na lista, no lugar do menu "Filtro: Todos". Um por vez; clicar de novo tira.
const FILTROS_RAPIDOS = {
  semresp: ["Sem resposta", e => e.pasta !== "enviado" && !e.respondido && !cx.resolvendo[e.id]],
  correcao: ["Correção", e => (e.classes || []).includes("corrigir") || /corre/i.test(e.motivo_urgencia || "")],
};
function rapidosHtml() {
  if (cx.caixa === "enviados") return "";
  const atual = cx.rapido; cx.rapido = "";
  const base = itensDaTela(""); cx.rapido = atual;   // quantos cada botão acharia nesta caixa, hotel e pasta
  return `<span class="ol-quebra"></span>` + Object.entries(FILTROS_RAPIDOS).map(([k, [nome, f]]) =>
    `<button type="button" class="ol-rapido" data-cx-rapido="${k}" aria-pressed="${atual === k}">${esc(nome)} <em>${base.filter(f).length.toLocaleString("pt-BR")}</em></button>`).join("");
}
function itensDaTela(busca) {
  if (busca) {   // busca: o que o Outlook dos PCs devolveu + o espelho dos PCs que não responderam (desligados)
    const r = cx.live && cx.live.termo === busca ? cx.live : null;
    const deles = new Set(Object.entries(r?.pcs || {}).filter(([, s]) => s.ok).map(([pc]) => pc));
    const espelho = (cx.dados?.emails || []).filter(e => !deles.has(e.pc) && passaBusca(e, busca)).map(e => ({ ...e, pasta: "entrada" }));
    const vistos = new Set();
    return [...(r?.resultados || []), ...espelho].filter(e => !vistos.has(e.id) && vistos.add(e.id) && !cx.escondidos[e.id])
      .filter(e => fhPassa(e.hotel)).sort((a, b) => b.quando.localeCompare(a.quando));
  }
  fhAtualizarContagem();
  const base = cx.caixa === "enviados" ? (cx.dados?.enviados || []).map(e => ({ ...e, pasta: "enviado" })).filter(e => !cx.escondidos[e.id] && doEscopo(e)) : emailsDa(cx.caixa);
  const lista = base.filter(e => fhPassa(e.hotel) && (!cx.soNaoLidos || e.lido === false) && (!cx.rapido || FILTROS_RAPIDOS[cx.rapido]?.[1](e))
    && (!cx.caixaSel || String(e.caixa || "").toLowerCase() === cx.caixaSel) && (!cx.soForm || (e.classes || []).includes("formulario")));
  // Caixa de Entrada: uma lista só, na ordem do botão Data (João, 07/11/2026: sem blocos de prioridade)
  if (cx.caixa === "entrada") return fhPorData(lista, e => e.quando);
  return lista;   // o mais recente primeiro também na Urgência (usuário, 09/10/2026)
}
// Quantos e-mails cada hotel tem na Caixa de Entrada (decide a prioridade); os hotéis vêm do Cadastro
FH.hoteis = () => [...new Set((st.hoteis || []).map(h => h.hotel).filter(Boolean))];
function fhAtualizarContagem() { FH.contagem = fhContar((cx.dados?.emails || []).filter(e => !cx.escondidos[e.id])); }
fhOuvir(() => { if (typeof pn !== "undefined" && pn.vista === "correio") desenharCorreio(); });

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
        enviados: "O que saiu das caixas dos hotéis nas últimas 72 h (pelo Outlook ou pelo Painel). Mais antigo: pesquise o e-mail do hóspede." }[cx.caixa];
  const nEm = x => `${x.toLocaleString("pt-BR")} e-mail${x === 1 ? "" : "s"}`;
  $("cx-sub").innerHTML = esc(busca ? `“${busca}” · ${nEm(lista.length)} no Outlook dos PCs` :
    cx.caixa === "enviados" ? `${lista.length} nas últimas 72 h` : `${nEm(lista.length)}${naoLidos ? ` · ${naoLidos} não lido${naoLidos === 1 ? "" : "s"}` : ""}`)
    + (FH.sel.size ? ` · ${FH.sel.size === 1 ? esc([...FH.sel][0]) : FH.sel.size + " hotéis"}` : "") + statusBusca(busca);
  desenharPastas();
  desenharFaixa();
  const nomePasta = cx.caixaSel ? nomeDaCaixa(cx.caixaSel) : "";
  const titulo = busca ? "Resultado da pesquisa" : cx.soForm ? "Formulários do robô" :
    (cx.caixa === "enviados" ? "Itens Enviados" : cx.caixa === "urgencia" ? "Urgência" : "Caixa de Entrada") + (nomePasta ? " · " + nomePasta : "");
  if ($("cx-lcab")) $("cx-lcab").innerHTML = `<div class="ol-lcab">` + (busca ? `<span class="ol-ord">no Outlook dos 4 PCs</span>` :
    `<button type="button" data-cx-filtro="todas" aria-pressed="${!cx.soNaoLidos && !cx.rapido}">Todas</button>` +
    (cx.caixa === "enviados" ? "" : `<button type="button" data-cx-filtro="naolidos" aria-pressed="${cx.soNaoLidos}">Não lidos</button>`) +
    `<span class="ol-quebra"></span>` + fhHtml() + (cx.caixa === "entrada" ? fhBotaoOrdem() : `<span class="ol-ord">Por Data ↓</span>`) + rapidosHtml()) + `</div><div class="ol-ltit"><b>${esc(titulo)}</b>${FH.sel.size ? " · " + FH.sel.size + (FH.sel.size === 1 ? " hotel" : " hotéis") : ""} · ${lista.length.toLocaleString("pt-BR")} itens` +
    (naoLidos ? ` · ${naoLidos.toLocaleString("pt-BR")} não lidos` : "") + `</div>`;
  if ($("ol-contagem")) $("ol-contagem").innerHTML = `<span title="Itens na caixa"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 13l2-7h14l2 7v5H3z"/><path d="M3 13h5l1 2h6l1-2h5"/></svg>${lista.length.toLocaleString("pt-BR")}<i class="so-leitor"> itens</i></span><span title="Não lidos"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/></svg>${naoLidos.toLocaleString("pt-BR")}<i class="so-leitor"> não lidos</i></span>`;
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
    : cx.caixa === "enviados" ? "Nada enviado nas últimas 72 h." : cx.soNaoLidos ? "Nenhum e-mail não lido aqui." : cx.rapido ? "Nenhum e-mail com este filtro." : "";
  const corpo = html || (vazio ? `<div class="vazio">${vazio}</div>`
    : caixaEmDia(cx.caixa === "urgencia" ? `Nada urgente na caixa${quem}.` : `Caixa de Entrada vazia${quem}.`));
  $("cx-lista").innerHTML = busca ? secoesDaBusca(busca) + corpo : corpo;
  if (idFoco) $("cx-lista").querySelector(`.cx-l[data-id="${CSS.escape(idFoco)}"]`)?.focus();
  desenharLeituraCorreio();
  if (!busca) preCarregar(lista);
}

// Pesquisa instantânea (Prévia 5, 20/10/2026: "estamos em ligação com o hóspede"): os pedidos do formulário (já no
// Painel) e os e-mails do espelho aparecem na hora; o Outlook dos 4 PCs completa depois (antigos, enviados, excluídos)
function pedidosDaBusca(busca) {
  const termos = semAcento(busca).split(/\s+/).filter(Boolean);
  return (st.fila || []).filter(s => {
    const t = semAcento([s.nome, s.email, s.hotel, s.dono, (s.nfs || []).join(" "), ...(s.campos || []).map(c => c[1])].join(" \n "));
    return termos.every(p => t.includes(p) || (soDigitos(p).length >= 3 && soDigitos(t).includes(soDigitos(p))));
  }).sort((a, b) => String(b.data).localeCompare(String(a.data))).slice(0, 12);
}
const marcarBusca = (texto, busca) => {
  const t = String(texto || ""), alvo = semAcento(String(busca).split(/\s+/)[0] || ""), i = alvo ? semAcento(t).indexOf(alvo) : -1;
  return i < 0 ? esc(t) : esc(t.slice(0, i)) + "<mark>" + esc(t.slice(i, i + alvo.length)) + "</mark>" + esc(t.slice(i + alvo.length));
};
function linhaPedidoBusca(s, busca) {
  const doc = campoDoPedido(s, /documento.*tomador/, /cpf.*cnpj|cnpj.*cpf/, /^cnpj/, /^cpf(?!.*titular)/);
  return `<div class="cx-l ped" role="option" tabindex="0" data-abrir-ficha="${esc(s.chave)}" title="Abrir a ficha do pedido">
    <span class="it-de">${marcarBusca(s.nome, busca)}</span><span class="it-ic"><i class="pin" aria-label="pedido do formulário"></i></span>
    <span class="it-as">${esc(s.hotel)} · ${esc(nomeSituacao(s))}</span><time>${esc(dataBr(s.data))}</time>
    <span class="it-pv">${esc([doc && "CPF/CNPJ " + doc, s.email, s.nfs?.length ? "NF " + s.nfs.join(", ") : ""].filter(Boolean).join(" · "))}</span></div>`;
}
function secoesDaBusca(busca) {
  const t0 = performance.now(), peds = pedidosDaBusca(busca);
  const s = Math.max(0.01, (performance.now() - t0) / 1000).toFixed(2).replace(".", ",");
  const r = cx.live?.termo === busca ? cx.live : null;
  const doIndice = r && !r.vivo && Object.values(r.pcs || {}).some(p => p.fonte === "indice");
  const montando = r && Object.values(r.pcs || {}).some(p => p.ok && p.fonte === "indice" && p.completo === false);
  const seg = r?.segundos != null ? ` · ${r.segundos.toFixed(2).replace(".", ",")} s` : "";
  const vivo = cx.buscando === busca ? `<span class="ch esp">procurando nos 4 PCs…</span>`
    : r ? `<span class="ch viv" title="${r.vivo ? "Procurado direto no Outlook de cada PC" : "Procurado no índice de e-mails de cada PC (12 meses)"}">${r.vivo ? "Outlook ao vivo" : doIndice ? "índice" : "Outlook"}${seg}</span>`
      + (montando ? ` <span class="ch mem" title="O índice de algum PC ainda está sendo montado (do mais novo pro mais velho)">montando</span>` : "")
    : `<span class="ch mem">já no Painel</span>`;
  const botao = r && !r.vivo && cx.buscando !== busca
    ? `<div class="cx-vivo-l"><button type="button" class="cx-vivo" data-busca-vivo title="Procura direto no Outlook de cada PC (demora alguns segundos)">Procurar também direto no Outlook</button></div>` : "";
  return (peds.length ? `<div class="cx-sec">Pedidos do formulário <span class="ch mem">${s} s · na hora</span></div>` + peds.map(p => linhaPedidoBusca(p, busca)).join("") : "")
    + `<div class="cx-sec">E-mails ${vivo}</div>` + botao;
}
function statusBusca(busca) {
  if (!busca) return "";
  if (cx.buscando === busca) return " · procurando nos PCs…";
  const r = cx.live;
  if (!r || r.termo !== busca) return "";
  const falhou = Object.entries(r.pcs || {}).filter(([pc, s]) => !s.ok && pcOnline(pc)).map(([pc]) => r.agentes?.[pc] || pc);
  return falhou.length ? ` · <span class="alerta-txt">sem resposta de ${esc(falhou.join(", "))}</span>` : "";
}

// Filtro de hotel: pecas/filtro_hoteis.js (vários hotéis, prioridade pela quantidade de e-mails, Meus hotéis neste PC)

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
      <div class="ind"><b>${(cx.dados?.enviados || []).filter(e => doEscopo(e)).length.toLocaleString("pt-BR")}</b><small>enviados nas últimas 72 h</small></div>
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
      ${(e.classes || []).length || (enviado && e.ligacao) ? `<div class="linha-et">${(e.classes || []).map(etiqueta).join("")}${enviado && e.ligacao ? pecaLigacao() : ""}</div>` : ""}</div>
    <div class="botoes">${noEspelho && !cinza ? "" : botoes}<button class="fechar" id="cx-fechar" aria-label="Fechar o e-mail" title="Fechar (Esc)">×</button></div>
    ${noEspelho && !cinza ? `<span class="dica-prof so-texto" style="flex-basis:100%">Atalhos: Ctrl+R responder · Ctrl+Shift+R com NF · Ctrl+F encaminhar · Delete excluir · Ctrl+U não lido</span>` : ""}`;
}

// Lista limpa (usuário, 11/10/2026: "muita informação dentro de uma só"): 2 linhas como o Outlook — quem mandou e a
// hora; o assunto e o hotel pequeno. Prazo, etiquetas, análise da NF e prévia ficam no e-mail aberto.
function linhaEmail(e) {   // igual à prévia aprovada (15/10/2026): quem, assunto, hora, prévia e etiquetas
  const enviado = e.pasta === "enviado";
  const cinza = !!cx.resolvendo[e.id], sel = cx.sel === e.id, naoLido = !enviado && e.lido === false && !cinza;
  const form = !!e.classes?.includes("formulario"), urg = e.urgente && !cinza;
  // como o Outlook mostra (Prévia 5, 20/10/2026): o nome de quem mandou, também no e-mail do formulário
  const quem = enviado ? "Para: " + (e.para || "") : e.nome || e.de || (e.classes?.includes("aviso") ? "Aviso do Outlook" : "(sem remetente)");
  const situacao = cinza || e.respondido ? "respondido · " : e.pasta === "excluido" ? "excluído · " : "";
  const previa = situacao + (e.hotel ? e.hotel + " · " : "") + (e.previa || "");
  const clip = (e.anexos || []).length ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-label="tem anexo"><path d="M21 11l-9 9a6 6 0 01-8-8l9-9a4 4 0 016 6l-9 9a2 2 0 01-3-3l8-8"/></svg>` : "";
  return `<div class="cx-l ${naoLido ? "nao-lido" : ""} ${sel ? "sel" : ""} ${cinza ? "cinza" : ""} ${urg ? "urgente" : ""}" role="option" tabindex="0"
      aria-selected="${sel}" data-id="${esc(e.id)}" title="${e.urgente ? esc(e.motivo_urgencia || "Urgente") : ""}">
    <span class="it-de">${esc(quem)}</span><span class="it-ic">${clip}${urg ? `<svg class="band" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-label="urgente"><path d="M5 21V4h11l-2 4 2 4H5"/></svg>` : ""}${form ? `<i class="pin" aria-label="formulário"></i>` : ""}</span>
    <span class="it-as">${esc(e.assunto || "(sem assunto)")}</span><time>${horaCurta(e.quando)}</time>
    <span class="it-pv">${esc(previa)}</span>${tagsEmail(e, cinza)}${naoLido ? `<span class="so-leitor">não lido</span>` : ""}</div>`;
}
// Tags da repaginação v2 (usuário, 14/10/2026): só urgência, nota dividida e falta de dados
function pedidoDoEmail(e) {
  return e.solicitacao && typeof acharPedido === "function" ? acharPedido(e.solicitacao.chave) : null;
}
function tagsEmail(e, cinza) {   // a peça única das etiquetas (pecas/etiqueta.js); respondido não muda a situação (21/10/2026)
  if (e.pasta === "enviado") return e.ligacao ? `<div class="it-tg">${pecaLigacao()}</div>` : "";   // Itens Enviados: só a Ligação
  if ((e.pasta && e.pasta !== "entrada") || cinza) return "";
  const form = (e.classes || []).includes("formulario") ? `<span class="tg t-form">Formulário</span>` : "";
  return `<div class="it-tg">${etiquetasDoEmail(e)}${form}</div>`;
}
document.addEventListener("click", ev => {
  const b = ev.target.closest("[data-abrir-ficha]");
  if (!b || typeof abrirHospede !== "function") return;
  const chave = b.dataset.abrirFicha;
  api("/api/acesso", { tipo: "ficha", item: chave }).catch(() => {});   // LGPD: quem abriu a ficha (sem nome nem CPF)
  const termo = $("busca").value.trim();
  abrirHospede(chave, { lista: termo.length >= 3 ? pedidosDaBusca(termo).map(p => p.chave).slice(0, 6) : [] });   // a ficha do hóspede (hospede.js)
});

// ---------- busca: direto no Outlook dos 4 PCs ----------
function agendarBusca() {
  clearTimeout(cx.timerBusca);
  const busca = $("busca").value.trim();
  cx.sel = null;   // pesquisa nova: fecha o e-mail que estava aberto
  if (busca.length < 3) { cx.live = null; cx.buscando = ""; return desenharCorreio(); }
  cx.timerBusca = setTimeout(() => buscarNoOutlook(busca), 250);   // índice local: responde na hora (20/10/2026)
  desenharCorreio();
}
async function buscarNoOutlook(busca, vivo = false) {
  cx.buscando = busca; desenharCorreio();
  const t0 = performance.now();
  const r = await api("/api/correio/buscar?q=" + encodeURIComponent(busca) + (vivo ? "&vivo=1" : ""));
  r.segundos = (performance.now() - t0) / 1000;
  if ($("busca").value.trim() !== busca) return;   // já digitaram outra coisa
  cx.buscando = "";
  if (r.erro) { toast(r.erro, true); cx.live = null; } else cx.live = r;
  desenharCorreio();
  $("anuncio").textContent = r.resultados ? `${r.resultados.length} e-mails achados` : "";
}
// Índice local (20/10/2026): a pesquisa responde pelo índice de cada PC; o botão procura direto no Outlook, como antes
document.addEventListener("click", ev => {
  if (!ev.target.closest?.("[data-busca-vivo]")) return;
  const busca = $("busca").value.trim();
  if (busca.length >= 3) buscarNoOutlook(busca, true);
});
