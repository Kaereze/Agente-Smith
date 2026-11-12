// correio_acoes.js: parte de correio.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
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

// Acha o e-mail em qualquer lista da tela: Caixa de entrada, Itens enviados (72 h) e resultado de pesquisa (29/10/2026).
function achaEmail(id) {
  return (cx.dados?.emails || []).find(x => x.id === id) || (cx.dados?.enviados || []).find(x => x.id === id)
    || (cx.live?.resultados || []).find(x => x.id === id) || null;
}
const souAdmin = () => document.documentElement.classList.contains("e-admin");   // João no PC principal (o servidor também confere)
// O que o servidor precisa para excluir um e-mail que só está no índice do PC dono (resultado de pesquisa).
const dadosDaExclusao = e => ({ entry: e.entry || "", caixa: e.caixa || "", de: e.de || "", nome: e.nome || "", hotel: e.hotel || "", assunto: e.assunto || "" });

// Administrador: Delete exclui direto, sem janela (o "Desfazer" de 10 s continua). Os outros agentes veem a janela de confirmação.
function excluirDireto(id) {
  const e = achaEmail(id);
  if (!e || document.querySelector(".modal-fundo")) return;
  excluirAgora(e);
}

function excluirAgora(e) {
  const id = e.id;
  cx.escondidos[id] = true; if (cx.sel === id) cx.sel = null;
  desenharCorreio();
  mostrarDesfazer("E-mail excluído", () => { delete cx.escondidos[id]; desenharCorreio(); }, async () => {
    const r = await api("/api/correio/excluir", { id, ...dadosDaExclusao(e) });
    if (!r.ok) { delete cx.escondidos[id]; desenharCorreio(); toast(r.motivo || "Não deu pra excluir", true); }
    else if (r.aviso) toast(r.aviso);
    carregarCorreio();
  });
}

function excluir(id) {
  const e = achaEmail(id);
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
  $("exc-sim").onclick = () => { fundo.remove(); excluirAgora(e); };
}

function mostrarDesfazer(msg, desfazer, confirmar, aviso = "Exclusão desfeita") {   // 10 s pra desfazer: só depois disso o pedido sai daqui
  if (cx.desfazer) { clearTimeout(cx.desfazer.timer); clearInterval(cx.desfazer.tique); cx.desfazer.confirmar(); }
  const bar = $("cx-desfazer");
  let s = 10;
  const pintar = () => { bar.innerHTML = `<span>${esc(msg)} · ${s}s</span><button id="cx-desfazer-btn">Desfazer</button>`;
    $("cx-desfazer-btn").onclick = () => { clearInterval(cx.desfazer.tique); clearTimeout(cx.desfazer.timer); cx.desfazer = null;
      bar.classList.add("oculta"); desfazer(); toast(aviso); }; };
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
  fhAtualizarContagem();
  const entrada = emailsDa("entrada").filter(e => fhPassa(e.hotel)), nl = {};   // os números acompanham os hotéis marcados
  entrada.forEach(e => { if (e.lido === false) { const c = String(e.caixa || "").toLowerCase(); nl[c] = (nl[c] || 0) + 1; } });
  // Pastas redesenhadas (usuário, 20/10/2026: "informações muito juntas"): título pequeno por grupo, cabeçalho de cada PC
  // (pessoa, ligado/desligado, nome do PC, total), caixa em 2 linhas (hotel; e-mail) com o número numa pílula
  const n = (v, cls = "") => v ? `<em class="${cls}">${v.toLocaleString("pt-BR")}</em>` : "";
  const chev = `<svg class="chev" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M6 9l6 6 6-6"/></svg>`;
  const favAberto = !cx.fechados.__fav;
  const fav = (k, ic, txt, v, on, cls) => `<button type="button" class="ol-fav ${on ? "on" : ""}" data-ol-fav="${k}">${SVG(IC[ic])}<span class="tx">${txt}</span>${n(v, cls)}</button>`;
  const semPasta = !cx.caixaSel;
  let h = `<button type="button" class="ol-gr" data-cx-grupo="__fav" aria-expanded="${favAberto}">${chev}Favoritos</button>` +
    (favAberto ? fav("entrada", "caixa", "Caixa de Entrada (todas)", entrada.filter(e => e.lido === false).length, semPasta && cx.caixa === "entrada" && !cx.soForm) +
      fav("urgencia", "alerta", "Urgência", emailsDa("urgencia").length, semPasta && cx.caixa === "urgencia", "r") +
      fav("form", "form", "Formulários do robô", entrada.filter(e => (e.classes || []).includes("formulario") && e.lido === false).length, semPasta && cx.soForm) +
      fav("enviados", "env", "Itens Enviados", 0, semPasta && cx.caixa === "enviados") : "");
  h += `<hr class="ol-hr">`;
  const pcs = (st.pcs || []).filter(p => doAgente([p.agente]));
  const meu = cx.dados?.este_pc || "";
  for (const p of pcs.sort((a, b) => (a.pc === meu ? -1 : b.pc === meu ? 1 : String(a.agente).localeCompare(String(b.agente), "pt")))) {
    const contas = [...new Set((p.contas_lista || []).map(c => String(c).toLowerCase()))]
      .map(c => ({ c, hotel: nomeDaCaixa(c), n: nl[c] || 0 })).sort((a, b) => a.hotel.localeCompare(b.hotel, "pt"));
    if (!contas.length) continue;   // PC sem caixa de hotel (o de casa, por exemplo) não entra na lista de caixas (João, 07/11/2026)
    const aberto = cx.pcsAbertos[p.pc] ?? (p.pc === meu || contas.some(x => x.c === cx.caixaSel) || pcs.length === 1);
    const soma = contas.reduce((s, x) => s + x.n, 0);
    h += `<button type="button" class="ol-pc2 ${aberto ? "" : "fechado"}" data-ol-pc="${esc(p.pc)}" aria-expanded="${aberto}" title="${p.online ? "PC ligado" : "PC desligado"}">
      ${chev}<span class="quem"><b>${esc(p.agente || p.pc)}</b><small><i class="${p.online ? "on" : "off"}"></i>${esc(p.pc)} · ${contas.length} caixas</small></span>${n(soma)}</button>`;
    if (!aberto) continue;
    const todas = cx.pcsTodas[p.pc] || contas.length <= 6;
    const mostrar = todas ? contas : contas.filter((x, i) => i < 4 || x.c === cx.caixaSel);   // como a prévia: 4 e "+ N caixas"
    for (const x of mostrar) {
      const on = x.c === cx.caixaSel;
      h += `<button type="button" class="ol-cx ${x.n ? "tem" : ""} ${on ? "sel" : ""}" data-ol-caixa="${esc(x.c)}" aria-expanded="${on}" title="${esc(x.c)}">${chev}
        <span class="nm"><b>${esc(x.hotel)}</b><small>${esc(x.c)}</small></span>${n(x.n)}</button>`;
      if (on) h += `<button type="button" class="ol-sub ${cx.caixa !== "enviados" ? "on" : ""}" data-ol-sub="entrada">Caixa de Entrada${n(x.n)}</button>
        <button type="button" class="ol-sub ${cx.caixa === "enviados" ? "on" : ""}" data-ol-sub="enviados">Itens Enviados</button>`;
    }
    if (mostrar.length < contas.length) h += `<button type="button" class="ol-mais-cx" data-ol-todas="${esc(p.pc)}">Mostrar mais ${contas.length - mostrar.length} caixas</button>`;
  }
  el.innerHTML = h;
}
try { cx.fechados = JSON.parse(localStorage.getItem("painel.caixasFechadas") || "{}") || {}; } catch (e) {}
document.addEventListener("click", ev => {
  const t = ev.target.closest("[data-ol-fav],[data-ol-caixa],[data-ol-sub],[data-ol-pc],[data-ol-todas],[data-cx-grupo],[data-cx-filtro],[data-cx-rapido],[data-cx-faixa],[data-ol-aba],[data-ol-acao],[data-ol-menu]");
  if (!t) { if (cx.menu && !ev.target.closest(".ol-menu")) { cx.menu = false; desenharLeituraCorreio(); } return; }
  const d = t.dataset;
  if (d.olAba) { cx.aba = d.olAba; desenharFaixaGlobal(); return desenharFaixa(); }
  if (d.olAcao) {
    if (d.olAcao === "sync") enviarReceberTodas();
    if (d.olAcao === "pendentes") $("btn-enviar")?.click();
    if (d.olAcao === "pastas") { cx.semPastas = !cx.semPastas; desenharCorreio(); }
    if (d.olAcao === "tema") $("btn-tema")?.click();
    if (d.olAcao === "prof") $("btn-prof")?.click();
    return;
  }
  if (d.olMenu !== undefined) { cx.menu = !cx.menu; return desenharLeituraCorreio(); }
  if (d.olFav) {
    cx.caixaSel = ""; cx.soForm = d.olFav === "form"; cx.caixa = d.olFav === "form" ? "entrada" : d.olFav; cx.sel = null;
    return trocarVista("correio");
  }
  if (d.olCaixa) { cx.caixaSel = cx.caixaSel === d.olCaixa && cx.caixa === "entrada" ? "" : d.olCaixa; cx.caixa = "entrada"; cx.soForm = false; cx.sel = null; return trocarVista("correio"); }
  if (d.olSub) { cx.caixa = d.olSub; cx.sel = null; return trocarVista("correio"); }
  if (d.olTodas) { cx.pcsTodas[d.olTodas] = true; return desenharPastas(); }
  if (d.olPc) { cx.pcsAbertos[d.olPc] = t.getAttribute("aria-expanded") !== "true"; return desenharPastas(); }
  if (d.cxGrupo !== undefined) {
    cx.fechados[d.cxGrupo] = !cx.fechados[d.cxGrupo];
    try { localStorage.setItem("painel.caixasFechadas", JSON.stringify(cx.fechados)); } catch (e) {}
    return desenharPastas();
  }
  if (d.cxFiltro) { cx.soNaoLidos = d.cxFiltro === "naolidos"; cx.rapido = ""; cx.sel = null; return desenharCorreio(); }
  if (d.cxRapido) { cx.rapido = cx.rapido === d.cxRapido ? "" : d.cxRapido; cx.sel = null; return desenharCorreio(); }
  const id = cx.sel;
  cx.menu = false;
  if (!id || t.disabled) return;
  if (d.cxFaixa === "resp") return escrever(id, "resp");
  if (d.cxFaixa === "nf") return escrever(id, "nf");
  if (d.cxFaixa === "enc") return escrever(id, "enc");
  if (d.cxFaixa === "exc") return souAdmin() ? excluirDireto(id) : excluir(id);
  if (d.cxFaixa === "naolido") return marcarNaoLido(id);
  if (d.cxFaixa === "lido") {
    const x = (cx.dados?.emails || []).find(m => m.id === id);
    if (x && x.lido === false) { api("/api/correio/evento", { ids: [id], acao: "LIDO" }); x.lido = true; desenharLateralCorreio(); desenharCorreio(); return toast("Marcado como lido para a equipe"); }
    return marcarNaoLido(id);
  }
});

function abrirCaixa(caixa) {
  cx.caixa = caixa; cx.sel = null; cx.caixaSel = ""; cx.soForm = false;
  try { localStorage.setItem("painel.caixaEmail", caixa); } catch (e) {}
}
try { const c = localStorage.getItem("painel.caixaEmail"); if (CAIXAS[c]) cx.caixa = c; } catch (e) {}

document.addEventListener("click", e => {
  const t = e.target.closest(".cx-l,[data-cx-hist],[data-cx-resp],[data-cx-resp-nf],[data-cx-enc],[data-cx-excluir],[data-cx-naolido],#cx-fechar,[data-caixa]");
  if (!t) return;
  const d = t.dataset;
  if (d.caixa) { abrirCaixa(d.caixa); return; }   // o trocarVista do data-vista desenha
  if (t.classList.contains("cx-l")) return d.abrirFicha ? undefined : abrirEmail(d.id);   // linha de pedido: o ouvinte de data-abrir-ficha abre a ficha
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
  if (d.cxExcluir) return souAdmin() ? excluirDireto(d.cxExcluir) : excluir(d.cxExcluir);
  if (d.cxNaolido) marcarNaoLido(d.cxNaolido);
});
// Novo e-mail (João, 09/11/2026): botão na faixa de comandos; a janela de escrever abre sozinha por cima, com a tela de trás desfocada,
// e a caixa que envia se escolhe nela (DE). Vale em qualquer tela; não depende de e-mail aberto.
document.addEventListener("click", ev => {
  if (!ev.target.closest("[data-cx-novo]")) return;
  abrirEnvioNF(null, { novo: true });
});
// Botão direito no e-mail (usuário, 20/10/2026): lido/não lido e urgência. Shift+F10 ou a tecla de menu abrem também.
function abrirMenuEmail(id, x, y) {
  const env = cx.caixa === "enviados" ? (cx.dados?.enviados || []).find(m => m.id === id) : null;
  const e = env || (cx.dados?.emails || []).find(m => m.id === id);
  fecharMenuEmail();
  if (!e) return;   // linha já respondida (cinza) também abre o menu: lá só a ação de tirar da entrada
  const travada = !!cx.resolvendo[id];
  const m = document.createElement("div");
  m.id = "cx-ctx"; m.className = "cx-ctx"; m.setAttribute("role", "menu");
  const ic = d => `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${d}</svg>`;
  const tirar = `<button type="button" role="menuitem" data-ctx="tirar" title="Move este e-mail para a pasta NF enviada da caixa do hotel. Nada é apagado.">${ic('<path d="M3 7h7l2 2h9v10H3z"/><path d="M9 14l2 2 4-4"/>')}Tirar da caixa de entrada</button>`;
  // Itens Enviados (22/10/2026): esqueceu de marcar a ligação no envio? marca aqui
  m.innerHTML = env ? `<div class="cx-ctx-t">Para: ${esc(e.para || "")}</div>
    <button type="button" role="menuitem" data-ctx="${e.ligacao ? "semlig" : "lig"}">${ic(ETQ_IC.tel)}${e.ligacao ? "Tirar marca de ligação" : "Marcar como ligação"}</button>`
  : travada ? `<div class="cx-ctx-t">${esc(e.nome || e.de || "")}</div>${tirar}`
  : `<div class="cx-ctx-t">${esc(e.nome || e.de || "")}</div>
    <button type="button" role="menuitem" data-ctx="${e.lido === false ? "lido" : "naolido"}">${ic('<path d="M3 9l9-6 9 6v10H3z"/><path d="M3 9l9 6 9-6"/>')}${e.lido === false ? "Marcar como lido" : "Marcar como não lido"}</button>
    <button type="button" role="menuitem" data-ctx="${e.urgente ? "normal" : "urgente"}" class="${e.urgente ? "" : "urg"}">${ic('<path d="M5 21V4h11l-2 4 2 4H5"/>')}${e.urgente ? "Tirar urgência" : "Marcar como urgente"}</button>
    ${e.urgente && e.motivo_urgencia ? `<div class="cx-ctx-n">${esc(e.motivo_urgencia)}</div>` : ""}
    ${tirar}`;
  document.body.appendChild(m);
  m.dataset.id = id;
  const r = m.getBoundingClientRect();
  m.style.left = Math.min(x, innerWidth - r.width - 8) + "px";
  m.style.top = Math.min(y, innerHeight - r.height - 8) + "px";
  m.querySelector("button")?.focus({ preventScroll: true });
}
function fecharMenuEmail() { document.getElementById("cx-ctx")?.remove(); }
// Tirar da caixa de entrada (27/10/2026): a entrada é só dos que esperam resposta. Move ESTE e-mail para a pasta "NF enviada"
// (Outlook do PC dono), mesmo já respondido; some na hora, tem "Desfazer" de 10 s e nada é apagado.
function tirarDaEntrada(id) {
  const e = (cx.dados?.emails || []).find(x => x.id === id);
  if (!e) return;
  cx.escondidos[id] = true; if (cx.sel === id) cx.sel = null;
  desenharCorreio();
  mostrarDesfazer("E-mail movido para “NF enviada”", () => { delete cx.escondidos[id]; desenharCorreio(); }, async () => {
    const r = await api("/api/correio/mover_nf", { id });
    if (!r.ok) { delete cx.escondidos[id]; toast(r.motivo || "Não deu pra mover", true); }
    else if (r.aviso) toast(r.aviso);
    carregarCorreio();
  }, "Movimento desfeito");
}
async function acaoMenuEmail(id, acao) {
  fecharMenuEmail();
  if (acao === "tirar") return tirarDaEntrada(id);
  if (acao === "lig" || acao === "semlig") return marcarLigacao(id, acao === "lig");
  const e = (cx.dados?.emails || []).find(m => m.id === id);
  if (!e) return;
  if (acao === "naolido") return marcarNaoLido(id);
  if (acao === "lido") {
    api("/api/correio/evento", { ids: [id], acao: "LIDO" }); e.lido = true;
    if (cx.dados?.contagem) cx.dados.contagem.entrada_nao_lidos = Math.max(0, cx.dados.contagem.entrada_nao_lidos - 1);
    desenharLateralCorreio(); desenharCorreio(); return toast("Marcado como lido para a equipe");
  }
  const antes = [e.urgente, e.motivo_urgencia];
  e.urgente = acao === "urgente"; e.motivo_urgencia = e.urgente ? "Marcado como urgente" : "";
  desenharLateralCorreio(); desenharCorreio();
  const r = await api("/api/correio/urgencia", { id, marcar: acao });
  if (!r.ok) { [e.urgente, e.motivo_urgencia] = antes; desenharLateralCorreio(); desenharCorreio(); return toast(r.motivo || r.erro || "Não deu pra marcar agora", true); }
  toast(e.urgente ? "Marcado como urgente para a equipe (fica no Outlook do PC dono)" : "Urgência tirada para a equipe");
}
async function marcarLigacao(id, marcar) {
  const e = (cx.dados?.enviados || []).find(m => m.id === id);
  if (!e) return;
  e.ligacao = marcar; desenharCorreio();
  const r = await api("/api/ligacao", { id, marcar });
  if (!r.ok) { e.ligacao = !marcar; desenharCorreio(); return toast(r.motivo || r.erro || "Não deu pra marcar agora", true); }
  toast(marcar ? "Marcado como ligação: já conta na Visão geral dos 4 PCs" : "Marca de ligação tirada");
}
document.addEventListener("contextmenu", ev => {
  const l = ev.target.closest?.("#cx-lista .cx-l");
  if (!l || !l.dataset.id) return;
  ev.preventDefault();
  abrirMenuEmail(l.dataset.id, ev.clientX, ev.clientY);
});
document.addEventListener("click", ev => {
  const b = ev.target.closest?.("#cx-ctx [data-ctx]");
  if (b) return acaoMenuEmail(b.closest("#cx-ctx").dataset.id, b.dataset.ctx);
  if (!ev.target.closest?.("#cx-ctx")) fecharMenuEmail();
});
document.addEventListener("keydown", ev => {
  if (ev.key === "Escape") fecharMenuEmail();
  const l = ev.target.closest?.("#cx-lista .cx-l");
  if (l?.dataset.id && (ev.key === "ContextMenu" || (ev.shiftKey && ev.key === "F10"))) {
    ev.preventDefault(); const r = l.getBoundingClientRect(); abrirMenuEmail(l.dataset.id, r.left + 40, r.top + r.height / 2);
  }
});
["scroll", "resize"].forEach(t => window.addEventListener(t, fecharMenuEmail, true));
window.addEventListener("blur", fecharMenuEmail);   // só a janela: o foco indo pro menu não pode fechá-lo

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
  if (e.key === "Delete") {   // vale também no resultado de pesquisa e nos itens enviados (29/10/2026)
    e.preventDefault();
    const alvo = cx.sel && !cx.resolvendo[cx.sel] ? achaEmail(cx.sel) : null;
    return alvo ? (souAdmin() ? excluirDireto(alvo.id) : excluir(alvo.id)) : precisa();
  }
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
    prox?.focus(); if (prox?.dataset.id) abrirEmail(prox.dataset.id, true);   // como no Outlook: a seta já abre o e-mail
  }
  if (e.key === "Escape" && !document.querySelector(".modal-fundo") && cx.sel && !(typeof envNF !== "undefined" && envNF && envNF.alvo)) { cx.sel = null; desenharCorreio(); }
});
