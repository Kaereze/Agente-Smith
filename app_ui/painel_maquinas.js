// painel_maquinas.js: parte de painel.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// ---------- Log e Máquinas: o que os robôs de todos os PCs fizeram ----------
const TIPOS_ATIV = {NOVA_SOLICITACAO: "Pedido novo", EMAIL_RECEBIDO: "E-mail recebido", NF_ENVIADA: "NF enviada",
  NF_DROPBOX: "NF no Dropbox", TRATATIVA: "Tratativa", NOTA_UNICA: "Nota única", OUTLOOK_FECHADO: "Outlook fechado",
  OUTLOOK_ABERTO: "Outlook aberto", ATUALIZADO: "Atualizado", FALHA: "Falha"};
// entrada = o que chegou · saída = o que a equipe/robô mandou ou confirmou · atualizações · Outlook e PCs
const SENTIDO = {NOVA_SOLICITACAO: "entrada", EMAIL_RECEBIDO: "entrada", NF_ENVIADA: "saida", NF_DROPBOX: "saida",
  TRATATIVA: "saida", NOTA_UNICA: "saida", ATUALIZADO: "sistema", FALHA: "sistema", OUTLOOK_FECHADO: "maquina", OUTLOOK_ABERTO: "maquina"};
let at = { dados: null, aba: "tudo", pc: "", timer: null };

async function carregarAtividade() {
  const j = await api("/api/atividade").catch(() => null);
  if (j && !j.erro) { at.dados = j; desenharMaquinas(); }
  clearTimeout(at.timer);
  if (pn.vista === "log" || pn.vista === "maquinas") at.timer = setTimeout(carregarAtividade, (globalThis.aj?.("tela.registro_atualiza_segundos") ?? 20) * 1000);
}

function haQuanto(iso) {
  if (!iso) return "nunca";
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  return min < 1 ? "agora" : min < 60 ? `há ${min} min` : min < 1440 ? `há ${Math.round(min / 60)} h` : `há ${Math.round(min / 1440)} d`;
}

// "aberto|E-mails|14:32": o Painel está aberto nesse PC agora, nessa tela
function usoHtml(p) {
  if (!p.online) return "";
  const [estado, tela] = String(p.uso || "").split("|");
  return estado === "aberto" ? `<div class="maq-uso ativo"><span class="dot on"></span>Painel aberto agora${tela ? " · em " + esc(tela) : ""}</div>`
    : `<div class="maq-uso"><span class="dot"></span>${p.uso ? "Painel fechado (o robô segue trabalhando)" : "sem informação de uso (versão antiga)"}</div>`;
}
function logDoPc(d, p) {
  const ev = (d.eventos || []).filter(x => x.pc === p.pc).slice(0, 4);
  if (!ev.length) return "";
  return `<div class="maq-log"><span class="rot">O que fez por último</span>${ev.map(x => `<div><span>${esc(String(x.quando).slice(11, 16))}</span>
    <span title="${esc([TIPOS_ATIV[x.tipo] || x.tipo, x.hotel, x.pedido, x.detalhe].filter(Boolean).join(" · "))}">${esc(TIPOS_ATIV[x.tipo] || x.tipo)}${x.hotel ? " · " + esc(x.hotel) : ""}${x.pedido ? " · " + esc(x.pedido) : ""}</span></div>`).join("")}</div>`;
}
// "Atualizar PC" com animação simples (29/10/2026, pecas/atualizar_pc.js): o estado de cada pedido fica em atz (a página se redesenha a
// cada poucos segundos e não pode perder o andamento). Um clique só enquanto anda; se o pedido falhar, o botão continua livre.
const atz = {};   // "TODOS" ou o nome do PC -> acompanhamento
let atzTimer = null;
function botaoAtz(para, rotulo, d, extra = "") {
  const a = atz[para], sit = a ? atzSituacao(a, d) : null;
  const emTodos = para !== "TODOS" && atz.TODOS && atzSituacao(atz.TODOS, d).estado === "andando";   // "todos" em andamento já inclui este PC
  const ocupado = (sit && sit.estado === "andando") || emTodos;
  const botao = `<button type="button" data-at-atualizar="${esc(para)}" class="btn-atz${sit ? " " + sit.estado : ""}" ${ocupado ? 'disabled aria-busy="true"' : ""} ${extra}>
    <svg class="ic"><use href="#i-sync"/></svg>${esc(sit ? sit.botao : rotulo)}</button>`;
  const linha = sit ? `<div class="atz-linha ${sit.estado}" role="status"><i class="atz-barra"></i><span>${esc(sit.linha)}</span></div>` : "";
  return para === "TODOS" ? `<span class="atz-grupo">${botao}${linha}</span>` : botao + linha;
}
function acompanharAtz() {
  clearInterval(atzTimer);
  atzTimer = setInterval(() => {
    let pendente = false;
    for (const [k, a] of Object.entries(atz)) { if (atzTerminou(a, atzSituacao(a, at.dados))) delete atz[k]; else pendente = true; }
    if (!pendente) clearInterval(atzTimer);
    carregarAtividade();   // traz as versões novas e redesenha as Máquinas
  }, 3000);
}
function desenharMaquinas() {
  const d = at.dados, el = $("maquinas");
  carregarCadastro();
  if (!d) { el.innerHTML = `<div class="vazio">Carregando…</div>`; return; }
  const a = d.atualizacao || {};
  const cards = d.pcs.map(p => {
    const antigo = !p.versao;   // PC com o código de antes da página Atividade: não publica Outlook nem versão
    const cls = !p.online ? "off" : p.outlook === "fechado" ? "ruim" : (p.conferencia_atrasada || p.versao !== d.versao) ? "alerta" : "";
    const ponto = !p.online ? "" : p.outlook === "fechado" ? "off" : cls === "alerta" ? "warn" : "on";
    const versao = antigo ? `<span class="ruim-txt">código antigo, atualize</span>`
      : p.versao === d.versao ? `<span class="dado">${esc(p.versao)}</span> · igual a este PC` : `<span class="dado">${esc(p.versao)}</span> · <span class="alerta-txt">diferente deste PC</span>`;
    const conf = antigo ? "sem informação" : p.conferencia_atrasada ? `<span class="ruim-txt">parada (${haQuanto(p.conferencia)})</span>`
      : p.conferencia ? haQuanto(p.conferencia) : "aguardando a primeira volta";
    return `<article class="maq ${cls}"><div class="maq-cab"><div><b><span class="op-av" style="background:${corOp(p.agente)}">${esc(inicial(p.agente))}</span>${esc(p.agente || "?")}</b><span class="dado">${esc(p.pc)}${p.pc === d.este_pc ? " · este PC" : ""}</span></div>
        <span class="pill"><span class="dot ${ponto}"></span>${p.online ? "No ar" : "Desligado"}</span></div>
      <dl><dt>Visto</dt><dd>${haQuanto(p.visto.replace(" ", "T"))}</dd>
        <dt>Outlook</dt><dd>${antigo ? "sem informação" : p.outlook === "aberto" ? `<span style="color:var(--ok)">aberto</span>` : `<span class="ruim-txt">${esc(p.outlook || "?")}</span>`}</dd>
        <dt>Conferência</dt><dd>${conf}${p.conferencia_resumo ? `<div class="dica">${esc(p.conferencia_resumo)}</div>` : ""}</dd>
        <dt>Versão</dt><dd>${versao}</dd>
        <dt>Caixas</dt><dd class="dado">${p.caixas}</dd><dt>Papel</dt><dd>${esc(p.papel || "")}</dd></dl>
      ${usoHtml(p)}${logDoPc(d, p)}
      ${p.online || atz[p.pc] ? botaoAtz(p.pc, "Atualizar este PC", d) : ""}</article>`;
  }).join("");
  el.innerHTML = `<p class="dica-prof" style="margin-bottom:12px">Os 4 PCs da equipe: quem está ligado, se o Outlook está aberto (o robô precisa dele), se o Painel está aberto e o que cada um fez por último. "Atualizar" puxa a versão nova do GitHub.</p><div class="cab-pagina"><h1>Máquinas da equipe</h1>
      <span class="dica">${d.pcs.filter(p => p.online).length} de ${d.pcs.length} PCs no ar · atualiza sozinho a cada 20 s</span></div>
    <div class="versao-ref"><span class="rot">Este PC</span><span class="dado">${esc(d.versao)}</span>
      <span class="dica">${a.atras ? `o GitHub tem ${a.atras} commit(s) novo(s)` : esc(a.motivo || "")}${a.verificado_em ? " · conferido " + haQuanto(a.verificado_em) : ""}</span>
      ${botaoAtz("TODOS", "Atualizar todos os PCs", d, 'title="Cada PC puxa a versão nova do GitHub e reinicia"')}</div>
    <div class="cartao" id="cad-faltando">${CAD.html}</div>
    <div class="maquinas">${cards || `<div class="vazio">Nenhum PC publicou ainda.</div>`}</div>`;
}

document.addEventListener("click", async e => {
  const b = e.target.closest("[data-at-aba],[data-at-atualizar]");
  if (!b) return;
  if (b.dataset.atAba) { at.aba = b.dataset.atAba; trocarVista("log"); return; }
  const para = b.dataset.atAtualizar;
  if (b.disabled || (atz[para] && atzSituacao(atz[para], at.dados).estado === "andando")) return;   // um clique só enquanto anda
  if (!confirm(para === "TODOS" ? "Pedir pra TODOS os PCs puxarem a versão nova do GitHub e reiniciarem?" : `Pedir pro PC ${para} atualizar e reiniciar?`)) return;
  const r = await api("/api/comando", { para, comando: "atualizar" });
  if (!r.ok) return toast(r.motivo || r.erro || "falhou", true);   // não deu: nada fica travado, o botão segue livre
  const d = at.dados || { pcs: [] };
  atz[para] = atzNovo(para, para === "TODOS" ? d.pcs.filter(p => p.online) : d.pcs.filter(p => p.pc === para));
  toast("Pedido enviado");
  desenharMaquinas(); acompanharAtz();
});
