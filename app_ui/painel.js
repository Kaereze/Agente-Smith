// Visão geral, Log, Máquinas e as janelas de envio. Usa api/$/esc/toast/st/desenhar e o estado da tela de notas
// (mesmo escopo global).
let pn = { vista: "visao", janela: 30, rz: null, tabela: {} };   // tabela: gráfico mostrado como tabela
const hojeIso = () => new Date().toLocaleDateString("sv-SE");

const TITULOS = { visao: "Visão geral", fila: "Notas fiscais", log: "Log do robô", maquinas: "Máquinas", correio: "E-mails",
                  gerencia: "Gerência (em teste)" };
function trocarVista(v) {
  if (!TITULOS[v]) v = "fila";
  pn.vista = v;
  for (const id of Object.keys(TITULOS)) $("v-" + id).classList.toggle("oculta", id !== v);
  $("trilha").textContent = v === "correio" ? "E-mails / " + CAIXAS[cx.caixa] : TITULOS[v];
  document.querySelectorAll(".ln[data-vista]").forEach(b =>
    b.setAttribute("aria-current", String(b.dataset.vista === v && (v !== "log" || b.dataset.log === at.aba)
                                          && (v !== "correio" || b.dataset.caixa === cx.caixa))));
  $("busca").placeholder = "Pesquisar no Outlook dos 4 PCs: hóspede, CPF/CNPJ, nº da NF, frase…";
  if (v !== "correio") $("topo-filtro").innerHTML = "";   // o filtro do topo é dos e-mails
  if (v === "correio") { desenharCorreio(); return; }
  desenhar();
  if (v === "visao") { pn.animar = true; desenharVisao(); }
  if (v === "gerencia") desenharGerencia();
  clearTimeout(at.timer);
  if (v === "log" || v === "maquinas") carregarAtividade();
}

// ---------- Log e Máquinas: o que os robôs de todos os PCs fizeram ----------
const TIPOS_ATIV = {NOVA_SOLICITACAO: "Pedido novo", EMAIL_RECEBIDO: "E-mail recebido", NF_ENVIADA: "NF enviada",
  NF_DROPBOX: "NF no Dropbox", TRATATIVA: "Tratativa", NOTA_UNICA: "Nota única", OUTLOOK_FECHADO: "Outlook fechado",
  OUTLOOK_ABERTO: "Outlook aberto", ATUALIZADO: "Atualizado", FALHA: "Falha"};
// entrada = o que chegou · saída = o que a equipe/robô mandou ou confirmou · atualizações · Outlook e PCs
const SENTIDO = {NOVA_SOLICITACAO: "entrada", EMAIL_RECEBIDO: "entrada", NF_ENVIADA: "saida", NF_DROPBOX: "saida",
  TRATATIVA: "saida", NOTA_UNICA: "saida", ATUALIZADO: "sistema", FALHA: "sistema", OUTLOOK_FECHADO: "maquina", OUTLOOK_ABERTO: "maquina"};
const ABAS_LOG = [["tudo", "Tudo"], ["entrada", "Entradas"], ["saida", "Saídas"], ["sistema", "Atualizações"], ["maquina", "Outlook e PCs"]];
let at = { dados: null, aba: "tudo", pc: "", timer: null };

async function carregarAtividade() {
  const j = await api("/api/atividade").catch(() => null);
  if (j && !j.erro) { at.dados = j; desenharLog(); desenharMaquinas(); }
  clearTimeout(at.timer);
  if (pn.vista === "log" || pn.vista === "maquinas") at.timer = setTimeout(carregarAtividade, 20000);
}

function haQuanto(iso) {
  if (!iso) return "nunca";
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  return min < 1 ? "agora" : min < 60 ? `há ${min} min` : min < 1440 ? `há ${Math.round(min / 60)} h` : `há ${Math.round(min / 1440)} d`;
}

function desenharLog() {
  const d = at.dados, el = $("log");
  if (!d) { el.innerHTML = `<div class="vazio">Carregando…</div>`; return; }
  const hoje = d.eventos.filter(e => e.quando.slice(0, 10) === hojeIso());
  const nHoje = (...tipos) => hoje.filter(e => tipos.includes(e.tipo)).length;
  const alertas = d.pcs.filter(p => !p.online || p.outlook === "fechado" || p.conferencia_atrasada);
  const evs = d.eventos.filter(e => (at.aba === "tudo" || SENTIDO[e.tipo] === at.aba) && (!at.pc || e.pc === at.pc));
  const pcsLista = [...new Set(d.eventos.map(e => e.pc))].sort();
  el.innerHTML = `<div class="cab-pagina"><h1>Log do robô</h1>
      <span class="dica">Tudo o que entrou e saiu em todos os PCs · atualiza sozinho a cada 20 s</span></div>
    <div class="contas">
      <div class="conta"><span class="rot">Entraram hoje</span><span class="v">${nHoje("NOVA_SOLICITACAO", "EMAIL_RECEBIDO")}</span>
        <span class="s">${nHoje("NOVA_SOLICITACAO")} pelo formulário · ${nHoje("EMAIL_RECEBIDO")} por e-mail</span></div>
      <div class="conta"><span class="rot">NFs hoje</span><span class="v">${nHoje("NF_ENVIADA", "NF_DROPBOX")}</span>
        <span class="s">${nHoje("NF_ENVIADA")} enviadas por e-mail · ${nHoje("NF_DROPBOX")} achadas no Dropbox</span></div>
      <div class="conta"><span class="rot">Tratativas hoje</span><span class="v">${nHoje("TRATATIVA")}</span><span class="s">e-mails ao hóspede sem nota</span></div>
      <div class="conta"><span class="rot">Máquinas com alerta</span><span class="v" style="color:${alertas.length ? "var(--erro)" : "var(--ok)"}">${alertas.length}</span>
        <span class="s">${alertas.length ? alertas.map(p => esc(p.agente || p.pc) + (!p.online ? " desligado" : p.outlook === "fechado" ? " com Outlook fechado" : " com conferência parada")).join(" · ")
          : "todos os PCs no ar"}</span></div>
    </div>
    <div class="abas-log" role="tablist">${ABAS_LOG.map(([v, n]) => `<button class="aba ${at.aba === v ? "sel" : ""}" role="tab" aria-selected="${at.aba === v}" data-at-aba="${v}">${n}</button>`).join("")}
      <label class="sel sel-pc"><select id="at-pc" aria-label="PC"><option value="">Todos os PCs</option>${pcsLista.map(p => `<option ${p === at.pc ? "selected" : ""}>${esc(p)}</option>`).join("")}</select></label></div>
    <div class="tabela-wrap"><table class="ativ-tab"><thead><tr><th>Quando</th><th>O quê</th><th>Máquina</th><th>Hotel / pedido</th><th>Detalhe</th></tr></thead>
      <tbody>${evs.slice(0, 300).map(e => `<tr>
        <td class="q">${esc(e.quando.slice(8, 10) + "/" + e.quando.slice(5, 7) + " " + e.quando.slice(11, 16))}</td>
        <td><span class="tipo t-${esc(e.tipo)}">${esc(TIPOS_ATIV[e.tipo] || e.tipo)}</span></td>
        <td>${esc(e.agente || "")}<div class="dica">${esc(e.pc)}</div></td>
        <td>${esc(e.hotel || "")}<div class="dica">${esc(e.pedido || "")}</div></td>
        <td>${esc(e.detalhe || "")}</td></tr>`).join("") || `<tr><td colspan="5" class="vazio">Nada por aqui ainda.</td></tr>`}</tbody></table></div>
    <p class="dica">Mostra os ${d.eventos.length} registros mais recentes da aba Atividade_Robo da Planilha Central.</p>`;
  const sel = $("at-pc");
  if (sel) sel.onchange = () => { at.pc = sel.value; desenharLog(); };
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
function desenharMaquinas() {
  const d = at.dados, el = $("maquinas");
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
      ${p.online ? `<button data-at-atualizar="${esc(p.pc)}"><svg class="ic"><use href="#i-sync"/></svg>Atualizar este PC</button>` : ""}</article>`;
  }).join("");
  el.innerHTML = `<p class="dica-prof" style="margin-bottom:12px">Os 4 PCs da equipe: quem está ligado, se o Outlook está aberto (o robô precisa dele), se o Painel está aberto e o que cada um fez por último. "Atualizar" puxa a versão nova do GitHub.</p><div class="cab-pagina"><h1>Máquinas da equipe</h1>
      <span class="dica">${d.pcs.filter(p => p.online).length} de ${d.pcs.length} PCs no ar · atualiza sozinho a cada 20 s</span></div>
    <div class="versao-ref"><span class="rot">Este PC</span><span class="dado">${esc(d.versao)}</span>
      <span class="dica">${a.atras ? `o GitHub tem ${a.atras} commit(s) novo(s)` : esc(a.motivo || "")}${a.verificado_em ? " · conferido " + haQuanto(a.verificado_em) : ""}</span>
      <button data-at-atualizar="TODOS" title="Cada PC puxa a versão nova do GitHub e reinicia"><svg class="ic"><use href="#i-sync"/></svg>Atualizar todos os PCs</button></div>
    <div class="maquinas">${cards || `<div class="vazio">Nenhum PC publicou ainda.</div>`}</div>`;
}

document.addEventListener("click", async e => {
  const b = e.target.closest("[data-at-aba],[data-at-atualizar]");
  if (!b) return;
  if (b.dataset.atAba) { at.aba = b.dataset.atAba; trocarVista("log"); return; }
  const para = b.dataset.atAtualizar;
  if (!confirm(para === "TODOS" ? "Pedir pra TODOS os PCs puxarem a versão nova do GitHub e reiniciarem?" : `Pedir pro PC ${para} atualizar e reiniciar?`)) return;
  const r = await api("/api/comando", { para, comando: "atualizar" });
  toast(r.ok ? "Pedido enviado — o PC responde em até 1 minuto (veja o Log)." : (r.motivo || r.erro || "falhou"), !r.ok);
});

// ---------- Visão geral: só os dados do próprio Painel (pedidos da Central + e-mails dos hóspedes) ----------
// Pedido do usuário (08/10/2026): menos informação, nada de comparar com o Mail Analytics, gráficos concretos.
const JANELAS = [7, 15, 30, 45];
// cores validadas (dataviz, tema claro e escuro) na ordem em que aparecem empilhadas
// validadas (dataviz) contra o branco e o verde-petróleo do tema escuro (#ffffff e #1b3a34)
const COR_VIZ = { emitida: "#1f9d6b", envio: "#b97a12", andamento: "#3987e5", sem_nf: "#e04f43", email: "#8b6fd6" };
const SERIES_DIA = [
  { k: "emitida", nome: "NF emitida e enviada", cor: COR_VIZ.emitida },
  { k: "envio", nome: "NF emitida, envio pendente", cor: COR_VIZ.envio },
  { k: "andamento", nome: "Em andamento", cor: COR_VIZ.andamento },
  { k: "sem_nf", nome: "Sem NF", cor: COR_VIZ.sem_nf },
];
const SERIES_AGENTE = [
  { k: "email", nome: "E-mail sem resposta", cor: COR_VIZ.email },
  { k: "sem_nf", nome: "Sem NF", cor: COR_VIZ.sem_nf },
  { k: "andamento", nome: "Em andamento", cor: COR_VIZ.andamento },
  { k: "envio", nome: "Envio pendente", cor: COR_VIZ.envio },
];
function categoriaVisao(s) {
  if (s.envio_pendente) return "envio";
  if (s.situacao === "concluida") return "emitida";
  if (["tratativa", "em_tratamento", "nf_parcial"].includes(s.situacao)) return "andamento";
  return "sem_nf";
}
const diasAtras = iso => Math.round((new Date(hojeIso() + "T12:00") - new Date(String(iso).slice(0, 10) + "T12:00")) / 86400000);

// ---------- Gerência (em teste) — pedido do usuário, 08/10/2026 ----------
// O gerente vê tudo o que a equipe está fazendo, em tempo real: o dia de hoje (pedidos e e-mails recebidos, e-mails
// enviados, NFs emitidas e o cruzamento dos três) e cada PC. Depois: só o gerente acessa (login), ligações e
// canceladas/substituídas do dia.
function desenharGerencia() {
  const el = $("gerencia");
  if (!el || !st.atualizado_em) return;
  const n = v => (v ?? 0).toLocaleString("pt-BR"), hoje = hojeIso();
  const base = filaBase();
  const pedidosHoje = base.filter(s => s.data === hoje).length;
  const nfsHoje = base.reduce((t, s) => t + (s.historico || []).filter(h => h.acao === "NF" && String(h.quando).slice(0, 10) === hoje).length, 0);
  const emails = cx.dados?.emails || [], enviados = cx.dados?.enviados || [];
  const recebidosHoje = emails.filter(e => String(e.quando).slice(0, 10) === hoje).length;
  const enviadosHoje = enviados.filter(e => String(e.quando).slice(0, 10) === hoje).length;
  const entrou = pedidosHoje + recebidosHoje, saiu = nfsHoje + enviadosHoje;
  const taxa = entrou ? Math.round(100 * saiu / entrou) : 0;   // pode passar de 100%: saiu mais do que entrou (atrasados)
  const porAgente = {};
  (st.pcs || []).forEach(p => { porAgente[p.agente || p.pc] = { p, notas: 0, entrada: 0, urg: 0, env: 0 }; });
  base.forEach(s => { const a = AG[s.hotel]; if (a && porAgente[a] && ["na_fila", "aguardando_envio"].includes(s.situacao)) porAgente[a].notas++; });
  emails.forEach(e => { const a = Object.values(porAgente).find(x => x.p.pc === e.pc); if (a) { a.entrada++; if (e.urgente) a.urg++; } });
  enviados.forEach(e => { const a = Object.values(porAgente).find(x => x.p.pc === e.pc); if (a) a.env++; });
  el.innerHTML = `<div class="cab-pagina"><h1>Gerência</h1><span class="dica">Tudo o que a equipe está fazendo agora · atualiza sozinho</span></div>
    <p class="dica-prof" style="margin:-8px 0 14px">A equipe está dando conta? "Andamento do dia" = o que saiu (NFs e e-mails enviados) dividido pelo que entrou (pedidos e e-mails recebidos). Acima de 100% = estamos tirando atraso.</p>
    <div class="ger-aviso" role="note"><svg aria-hidden="true"><use href="#i-cadeado"/></svg><span><b>Página em construção.</b> Por enquanto todos veem;
      depois só o gerente terá acesso (com login). Os números abaixo já são reais.</span></div>
    <div class="ger-dia" role="group" aria-label="Hoje">
      <div><small>Pedidos recebidos hoje</small><b>${n(pedidosHoje)}</b><small>formulários</small></div>
      <div><small>E-mails recebidos hoje</small><b>${n(recebidosHoje)}</b><small>sem resposta ainda: ${n(emails.length)}</small></div>
      <div><small>E-mails enviados hoje</small><b>${n(enviadosHoje)}</b><small>pelas caixas dos hotéis</small></div>
      <div><small>NFs emitidas hoje</small><b>${n(nfsHoje)}</b><small>registradas hoje (inclui as achadas pelo robô)</small></div>
      <div class="taxa"><small>Andamento do dia</small><b>${taxa}%</b><div class="ger-barra"><i style="width:${Math.min(100, taxa)}%"></i></div>
        <small>saiu (NFs + e-mails enviados) ÷ entrou (pedidos + e-mails)</small></div></div>
    <div class="cartao"><h3>Por PC / agente</h3><div class="sub">O que cada um tem pra fazer agora e o que já saiu hoje</div>
      <div class="tabela-wrap"><table class="ger-tab"><thead><tr><th>Agente</th><th>PC</th><th class="num">NFs pra emitir</th><th class="num">E-mails na entrada</th>
        <th class="num">Urgência</th><th class="num">Enviados 24 h</th><th>Painel</th></tr></thead><tbody>
        ${Object.entries(porAgente).map(([a, x]) => `<tr><td><b>${esc(a)}</b></td><td>${x.p.online ? '<span class="dot on"></span> no ar' : '<span class="dot"></span> desligado'}</td>
          <td class="num">${n(x.notas)}</td><td class="num">${n(x.entrada)}</td><td class="num">${x.urg ? `<span class="ruim-txt">${n(x.urg)}</span>` : "0"}</td>
          <td class="num">${n(x.env)}</td><td>${String(x.p.uso || "").startsWith("aberto") ? "aberto · " + esc(String(x.p.uso).split("|")[1] || "") : "fechado"}</td></tr>`).join("")}
      </tbody></table></div></div>
    <div class="ger-breve">
      <div><b>Canceladas e substituídas do dia</b><span>Em construção: vem das NFs marcadas (CANCELADA)/(SUBSTITUÍDA) no Dropbox.</span></div>
      <div><b>Ligações do dia</b><span>Em construção: precisa ligar o Painel ao sistema de telefone da empresa.</span></div>
      <div><b>Tempo médio de resposta</b><span>Em construção: do e-mail chegar até a resposta sair, por agente.</span></div></div>`;
}
function contarNumeros(el) {   // os números grandes sobem do zero até o valor (0,6 s)
  el.querySelectorAll(".kpi-v").forEach(n => {
    const alvo = Number(String(n.textContent).replace(/\./g, "").replace(",", "."));
    if (!isFinite(alvo) || alvo < 2) return;
    const ini = performance.now(), texto = n.textContent;
    const passo = t => { const k = Math.min(1, (t - ini) / 600), v = Math.round(alvo * (1 - Math.pow(1 - k, 3)));
      n.textContent = k < 1 ? v.toLocaleString("pt-BR") : texto; if (k < 1) requestAnimationFrame(passo); };
    requestAnimationFrame(passo);
  });
}
// Visão geral = o que está AGORA no Outlook dos 4 PCs (usuário, 11/10/2026), igual às telas Notas e Caixa de
// entrada (mesmos números, mesmo filtro de operador). O gráfico dos pedidos de cada dia fica como histórico.
function faixaAgora(sol, mails, enviados) {
  const n = v => (v ?? 0).toLocaleString("pt-BR");
  const abertas = sol.filter(it => it.s.situacao !== "concluida");
  const itens = [
    { ir: "notas:todas", rot: "Solicitações na caixa", v: sol.length, cor: COR_VIZ.andamento,
      sub: `<b>${n(sol.filter(it => ["na_fila", "aguardando_envio"].includes(it.s.situacao)).length)}</b> sem NF · ${n(sol.filter(it => !it.s.na_caixa?.lido).length)} não lidas` },
    { ir: "notas:atrasadas", rot: "Atrasadas +7 dias", v: abertas.filter(it => diasAtras(it.s.data) > 7).length, cor: COR_VIZ.sem_nf,
      sub: "solicitações sem NF há mais de 7 dias" },
    { ir: "correio:entrada", rot: "E-mails na caixa", v: mails.length, cor: COR_VIZ.email,
      sub: `<b>${n(mails.filter(e => e.lido === false).length)}</b> não lidos` },
    { ir: "correio:urgencia", rot: "Urgentes", v: mails.filter(e => e.urgente).length, cor: COR_VIZ.sem_nf,
      sub: "correção de NF ou +7 dias sem resposta" },
    { ir: "correio:enviados", rot: "Enviados · 24 h", v: enviados.length, cor: COR_VIZ.emitida,
      sub: "o que saiu das caixas dos hotéis" },
  ];
  return `<div class="faixa-resumo" role="group" aria-label="Agora, no Outlook dos 4 PCs">${itens.map(i => `
    <button class="fr-item" data-ir-agora="${i.ir}" style="--cor:${i.cor}" title="Abrir: ${esc(i.rot)}">
      <span class="fr-rot">${esc(i.rot)}</span>
      <span class="fr-num"><span class="kpi-v">${n(i.v)}</span></span>
      <span class="fr-sub">${i.sub}</span></button>`).join("")}</div>`;
}
document.addEventListener("click", e => {
  const b = e.target.closest("[data-ir-agora]");
  if (!b) return;
  const [tela, qual] = b.dataset.irAgora.split(":");
  if (tela === "notas") return abrirNotas({ filtro: qual, agente: escopoAtual() === "todos" ? "" : escopoAtual() });
  trocarVista("correio"); abrirCaixa(qual);
});

function desenharVisao() {
  const el = $("visao");
  if (!st.atualizado_em) { el.innerHTML = `<div class="vazio">Carregando…</div>`; return; }
  const n = v => (v ?? 0).toLocaleString("pt-BR");
  const hoje = new Date(hojeIso() + "T12:00"), ini = new Date(hoje);
  ini.setDate(ini.getDate() - (pn.janela - 1));
  const corte = ini.toLocaleDateString("sv-SE");
  const pedidos = st.fila.filter(s => s.data >= corte);   // histórico: pedidos dos formulários no período
  // agora, no Outlook: solicitações da Caixa de Entrada (Notas) e e-mails (Caixa de entrada), do operador escolhido
  const sol = TODOS.filter(it => it.tipo === "form" && doAgente(agentesDo(it)));
  const mails = (cx.dados?.emails || []).filter(e => doEscopo(e));
  const enviados = (cx.dados?.enviados || []).filter(e => doEscopo(e));
  // gráfico 1: os pedidos de cada dia e o que aconteceu com eles
  const porDia = {};
  for (const d = new Date(ini); d <= hoje; d.setDate(d.getDate() + 1)) porDia[d.toLocaleDateString("sv-SE")] = {};
  pedidos.forEach(s => { const p = porDia[s.data]; if (p) { const c = categoriaVisao(s); p[c] = (p[c] || 0) + 1; } });
  const dias = Object.entries(porDia).map(([data, partes]) => ({
    rotulo: data.slice(8, 10) + "/" + data.slice(5, 7), partes,
    titulo: new Date(data + "T12:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" }) }));
  // gráfico 2: o que está na Caixa de Entrada de cada operador (clicar abre as notas dele)
  const ag = {};
  const somar = (a, k) => { (ag[a] ||= {})[k] = (ag[a][k] || 0) + 1; };
  sol.forEach(it => { if (it.s.situacao !== "concluida" || it.s.envio_pendente) somar(agentesDo(it)[0] || "Sem agente", categoriaVisao(it.s)); });
  mails.forEach(m => somar(nomeAgente(m.pc) || "Sem agente", "email"));
  const total = p => SERIES_AGENTE.reduce((a, s) => a + (p[s.k] || 0), 0);
  const porAgente = Object.entries(ag).map(([rotulo, partes]) => ({ rotulo, partes })).sort((a, b) => total(b.partes) - total(a.partes));
  // espera dos pedidos em aberto
  const faixas = [["Até 2 dias", 0, 2], ["3 a 7 dias", 3, 7], ["8 a 15 dias", 8, 15], ["Mais de 15 dias", 16, 1e9]];
  // cores do prazo (as mesmas da coluna Espera): até 2 dias verde, até 7 âmbar, acima vermelho
  const corFaixa = [COR_VIZ.emitida, COR_VIZ.envio, COR_VIZ.sem_nf, COR_VIZ.sem_nf];
  const esperando = [...sol.filter(it => it.s.situacao !== "concluida").map(it => it.s.data), ...mails.map(e => e.quando)];
  const idade = faixas.map(([rotulo, a, b], k) => ({ rotulo, cor: corFaixa[k], atrasada: a > 7,
    n: esperando.filter(q => { const d = diasAtras(q); return d >= a && d <= b; }).length }));
  const botaoTabela = id => `<button class="link" data-vt="${id}">${pn.tabela[id] ? "Ver gráfico" : "Ver em tabela"}</button>`;
  const kpi = (alvo, rot, v, sub, cor) => `<button class="kpi-b" data-ir="${alvo}" style="--cor:${cor}">
      <span class="kpi-r">${rot}</span><span class="kpi-v">${n(v)}</span><span class="kpi-s">${sub}</span></button>`;
  const quem = escopoAtual() === "todos" ? "nas caixas dos 4 PCs" : "na Caixa de Entrada de " + escopoAtual();
  el.innerHTML = `<div class="cab-pagina"><div style="display:flex;flex-direction:column;gap:4px;margin-right:auto"><h1>Visão geral</h1>
      <span class="dica">Agora, no Outlook · ${esc(quem)} · atualiza sozinho</span></div></div>
    <div class="op-cartoes" role="group" aria-label="Caixa de Entrada de cada operador" style="margin-bottom:14px">${cartoesOperadores()}</div>
    <p class="dica-prof" style="margin:0 0 14px">Como estamos agora? Os números são os mesmos das telas Notas fiscais e Caixa de entrada: o que está no Outlook neste momento. Clique num operador pra ver só a caixa dele, ou num indicador pra abrir a lista.</p>
    ${faixaAgora(sol, mails, enviados)}
    <div class="grade2">
      <div class="cartao"><div class="cartao-topo"><div><h3>Na Caixa de Entrada, por operador</h3><div class="sub">Solicitações e e-mails esperando. Clique num operador para ver as notas dele</div></div>
        ${botaoTabela("agentes")}</div>
        <div id="leg-agentes" style="margin:4px 0 10px"></div><div id="graf-agentes"></div></div>
      <div class="cartao"><div class="cartao-topo"><div><h3>Há quanto tempo esperam</h3><div class="sub">Solicitações sem NF e e-mails na caixa, pelo dia em que chegaram</div></div>
        ${botaoTabela("idade")}</div>
        <div id="graf-idade" style="margin-top:14px"></div></div>
    </div>
    <div class="cartao"><div class="cartao-topo"><div><h3>Histórico: pedidos de cada dia e o que aconteceu com eles</h3>
      <div class="sub">Formulários da Planilha Central (inclui os já resolvidos e fora do Outlook). Cada coluna é o dia em que o hóspede pediu.</div></div>
      <div style="display:flex;gap:10px;align-items:center"><div class="seg" role="group" aria-label="Período">${JANELAS.map(j =>
        `<button data-vj="${j}" aria-pressed="${pn.janela === j}">${j} dias</button>`).join("")}</div>${botaoTabela("dias")}</div></div>
      <div id="leg-dias" style="margin:4px 0 10px"></div><div id="graf-dias"></div></div>`;
  if (pn.animar && !matchMedia("(prefers-reduced-motion: reduce)").matches) { pn.animar = false; el.classList.add("anima"); contarNumeros(el); }
  else el.classList.remove("anima");
  // cada gráfico também como tabela (leitor de tela, teclado e quem prefere números)
  const tabela = (cab, linhas) => `<div style="overflow-x:auto"><table class="tabela"><thead><tr>${cab.map((c, i) =>
    `<th class="${i ? "num" : ""}">${esc(c)}</th>`).join("")}</tr></thead><tbody>${linhas.map(l => `<tr>${l.map((v, i) =>
    `<td class="${i ? "num" : ""}">${typeof v === "number" ? n(v) : esc(v)}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
  const somaSeries = (partes, series) => series.reduce((a, s) => a + (partes[s.k] || 0), 0);
  legendaCores($("leg-dias"), SERIES_DIA);
  if (pn.tabela.dias) $("graf-dias").innerHTML = tabela(["Dia", ...SERIES_DIA.map(s => s.nome), "Total"],
    dias.map(d => [d.titulo, ...SERIES_DIA.map(s => d.partes[s.k] || 0), somaSeries(d.partes, SERIES_DIA)]));
  else graficoColunas($("graf-dias"), dias, SERIES_DIA);
  legendaCores($("leg-agentes"), SERIES_AGENTE);
  if (pn.tabela.agentes) $("graf-agentes").innerHTML = tabela(["Agente", ...SERIES_AGENTE.map(s => s.nome), "Total"],
    porAgente.map(a => [a.rotulo, ...SERIES_AGENTE.map(s => a.partes[s.k] || 0), somaSeries(a.partes, SERIES_AGENTE)]));
  else graficoBarrasEmpilhadas($("graf-agentes"), porAgente, SERIES_AGENTE, {
    aoClicar: it => { abrirNotas({ agente: it.rotulo === "Sem agente" ? "" : it.rotulo, filtro: "todas" }); } });
  if (pn.tabela.idade) $("graf-idade").innerHTML = tabela(["Espera", "Pedidos em aberto"], idade.map(i => [i.rotulo, i.n]));
  else graficoBarrasH($("graf-idade"), idade, { aoClicar: it => abrirNotas({ filtro: it.atrasada ? "atrasadas" : "aberto",
    agente: escopoAtual() === "todos" ? "" : escopoAtual() }) });
}

// ---------- Enviar pendentes: o caminho que o robô faz, com as linhas reais do log ----------
// Cada etapa acende quando aparece no log uma linha dela (main.py); a linha vira o detalhe da etapa.
const ETAPAS_ENVIO = [
  ["Pedido ao robô", "o PC principal recebe o pedido", /Pedido entregue|início|DESLIGADO/i],
  ["Planilha Central", "abas de respostas de cada hotel", /aba\(s\) de respostas/i],
  ["Solicitações pendentes", "o que ainda não foi pra caixa do hotel", /pendente\(s\) lida|já tratada|esperando a vez/i],
  ["Montando os e-mails", "um e-mail por operador, com as solicitações", /montado/i],
  ["Enviando às caixas dos hotéis", "pelo Outlook do PC principal", /Enviando|SAIU/i],
  ["Marcando a planilha", "Enviado = TRUE e aviso ao conferente de NF", /marcada|anotado/i],
  ["Concluído", "", null],
];
let envioTimer = null;
async function abrirEnvio() {
  if (document.querySelector(".modal-fundo")) return;
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `<div class="modal proc" role="dialog" aria-modal="true" aria-labelledby="env-titulo">
    <div class="proc-cab"><div class="anel" id="env-anel"></div>
      <div><h3 id="env-titulo">Enviar solicitações pendentes</h3><div class="sub" id="env-sub">Confirme para o robô começar</div></div></div>
    <div class="proc-barra" id="env-barra"><i></i></div>
    <div class="proc-corpo">
      <ol class="etapas" id="env-etapas">${ETAPAS_ENVIO.map(([t, s], k) =>
        `<li class="etapa" id="env-et-${k}"><span class="marco">${k + 1}</span><span><b>${esc(t)}</b><small>${esc(s)}</small></span></li>`).join("")}</ol>
      <div class="trilha" id="env-trilha"><div class="vazio" style="padding:30px;font-family:var(--f-texto)">O robô lê as pendentes da Planilha Central,
        monta um e-mail por operador e envia pra caixa de cada hotel. Nada é enviado ao hóspede.</div></div>
    </div>
    <div class="modal-rodape"><span class="res" id="env-res"></span>
      <span style="display:flex;gap:8px"><button id="env-fechar">Cancelar</button><button class="creme" id="env-ir">Enviar agora</button></span></div></div>`;
  document.body.appendChild(fundo);
  $("env-anel").style.animationPlayState = "paused";
  $("env-fechar").onclick = () => { clearTimeout(envioTimer); fundo.remove(); };
  $("env-ir").onclick = async () => {
    $("env-ir").disabled = true;
    const r = await api("/api/enviar", {});
    if (!r.ok) { $("env-ir").disabled = false; return toast(r.motivo || "Não deu certo", true); }
    $("env-ir").style.display = "none";
    $("env-fechar").textContent = "Fechar (continua em segundo plano)";
    $("env-anel").style.animationPlayState = "running";
    $("env-titulo").textContent = "O robô está enviando as pendentes";
    $("env-sub").textContent = r.modo === "local" ? "Rodando neste PC" : "Pedido entregue ao PC principal";
    $("env-trilha").innerHTML = "";
    acompanharEnvio(r.modo === "local" ? 700 : 2500);
  };
}

function marcarEtapas(linhas, rodando, ok) {
  let atual = 0;
  const detalhe = {};
  linhas.forEach(l => ETAPAS_ENVIO.forEach(([, , re], k) => { if (re && re.test(l.texto)) { atual = Math.max(atual, k); detalhe[k] = l.texto; } }));
  if (!rodando) atual = ETAPAS_ENVIO.length - 1;
  ETAPAS_ENVIO.forEach((et, k) => {
    const li = $("env-et-" + k);
    if (!li) return;
    li.classList.toggle("feita", k < atual || (!rodando && ok));
    li.classList.toggle("agora", rodando && k === atual);
    if (detalhe[k]) li.querySelector("small").textContent = detalhe[k].replace(/^\W+\s*/u, "");
  });
  $("env-barra").querySelector("i").style.width = Math.round(100 * (rodando ? atual + .5 : ETAPAS_ENVIO.length) / ETAPAS_ENVIO.length) + "%";
}

async function acompanharEnvio(ms) {
  const e = await api("/api/envio").catch(() => null);
  if (!$("env-trilha")) return;   // janela fechada: o envio segue sozinho
  if (e) {
    const trilha = $("env-trilha"), noFim = trilha.scrollTop + trilha.clientHeight >= trilha.scrollHeight - 30;
    const existentes = trilha.children.length;
    e.linhas.slice(existentes).forEach(l => {
      const div = document.createElement("div");
      div.className = "passo" + (l.nivel === "WARNING" ? " aviso" : l.nivel === "ERROR" ? " erro" : "");
      div.innerHTML = `<span class="m"></span><span class="h">${esc(l.hora)}</span><span class="t">${esc(l.texto)}</span>`;
      trilha.appendChild(div);
    });
    [...trilha.children].forEach((d, i) => {
      const atual = e.rodando && i === trilha.children.length - 1;
      d.classList.toggle("atual", atual);
      d.querySelector(".m").textContent = atual ? "" : "✓";
    });
    if (noFim) trilha.scrollTop = trilha.scrollHeight;
    const terminou = !e.rodando && e.modo, ok = e.codigo === 0;
    marcarEtapas(e.linhas, !terminou, ok);
    if (terminou) {
      $("env-anel").className = "anel " + (ok ? "ok" : "ruim");
      $("env-anel").textContent = ok ? "✓" : "!";
      $("env-barra").classList.add("fim");
      $("env-titulo").textContent = ok ? "Envio concluído" : "Envio terminou com aviso";
      $("env-sub").textContent = e.resumo || "";
      $("env-et-" + (ETAPAS_ENVIO.length - 1)).querySelector("small").textContent = e.resumo || "";
      $("env-res").textContent = e.resumo || "";
      $("env-fechar").textContent = "Fechar";
      carregar();
      return;
    }
  }
  envioTimer = setTimeout(() => acompanharEnvio(ms), ms);
}

// ---------- Enviar NF ao hóspede (janela no estilo do Outlook) ----------
let envNF = null;
function assuntoDoArquivo(nomeArquivo, nome) {
  const base = (nomeArquivo || "").replace(/\.[^.]+$/, "").replace(/\s+/g, " ").trim();
  if (/^\s*nf-?e?\s*[-:nº°#]*\s*\d+\s*-\s*\S/i.test(base)) return base;
  const num = (base.match(/\d{2,}/) || [""])[0];
  return (num ? `NF ${num} - ` : "NF - ") + nome.toUpperCase();
}
const tamanho = b => b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB";

// Escrever (responder, responder com NF, encaminhar, enviar NF). Com `alvo`, igual ao Outlook (usuário, 09/10/2026): abre
// DENTRO do painel de leitura, com o e-mail original citado embaixo — sem janela por cima. Sem alvo: janela (como antes).
async function abrirEnvioNF(chave, resp = null, alvo = null) {
  if (document.querySelector(".modal-fundo")) return;
  if (envNF && envNF.alvo) { $("nf-msg")?.focus(); toast("Termine ou descarte a mensagem que está escrevendo", true); return; }
  const enc = !!resp?.encaminhar;
  const titulo = enc ? "↗ Encaminhar" : resp ? (resp.comNF ? "↩ Responder com a NF" : "↩ Responder") : "✉ Nova mensagem · Nota Fiscal";
  const miolo = `
    <div class="compor-topo"><span>${titulo}</span><span id="nf-sub" class="compor-quem">carregando…</span>
      ${alvo ? `<button class="descartar" id="nf-fechar" title="Descartar e voltar">Descartar</button>` : `<button class="fechar" id="nf-fechar" title="Descartar">×</button>`}</div>
    <div class="barra-prog" id="nf-barra" style="visibility:hidden"><i></i></div>
    <div class="compor-corpo" id="nf-corpo"><div class="vazio">Carregando…</div></div>
    <div class="compor-rodape"><div class="anel" id="nf-anel" style="width:22px;height:22px;border-width:2px;visibility:hidden"></div>
      <span class="res" id="nf-res"></span></div>`;
  let fundo = null;
  if (alvo) {
    alvo.innerHTML = `<div class="compor-inline">${miolo}</div>`;
    alvo.classList.add("compondo");
  } else {
    fundo = document.createElement("div");
    fundo.className = "modal-fundo";
    fundo.innerHTML = `<div class="modal compor">${miolo}</div>`;
    document.body.appendChild(fundo);
  }
  const fechar = () => {
    clearTimeout(envNF?.timer); envNF = null;
    if (fundo) fundo.remove();
    if (alvo) { alvo.classList.remove("compondo"); alvo.id === "cx-leitura" ? desenharLeituraCorreio() : desenharDetalhe(); }
  };
  envNF = { chave, resp, alvo, fechar, anexos: [], carregando: true };   // já reserva: a atualização de 15 s não apaga o que se escreve
  $("nf-fechar").onclick = fechar;
  const o = await api(resp ? `/api/email/opcoes?id=${encodeURIComponent(resp.id)}` : `/api/envio_nf/opcoes?chave=${encodeURIComponent(chave)}`);
  if (!envNF) return;
  if (o.erro) { $("nf-corpo").innerHTML = `<div class="vazio">${esc(o.erro)}</div>`; return; }
  if (enc) {   // encaminhar: pra quem a pessoa escolher, com o original anexado embaixo; sem anexo de NF nem selo
    const orig = o.email?.assunto || "";
    o.assunto = /^(enc|fw|fwd):/i.test(orig) ? orig : "ENC: " + orig;
    o.para = []; o.sugestoes = []; o.selos = []; o.assinatura = ""; o.corpo = "";
  }
  envNF = { chave, resp, alvo, fechar, o, anexos: [], assuntoAuto: !resp };
  $("nf-sub").textContent = `${o.nome} · ${o.hotel}`;
  const de = o.destino
    ? `<div class="campo-txt"><b>${esc(o.conta_de)}</b> <span class="dica">${o.destino === o.este_pc ? "· por este PC" : "· pelo PC " + esc(o.destino)}</span></div>`
    : `<div class="campo-txt alerta">⚠ ${esc(o.motivo)} Enviar por:
         <select id="nf-conta">${o.contas_locais.map(c => `<option>${esc(c)}</option>`).join("")}</select></div>`;
  $("nf-corpo").innerHTML = `
    <div class="compor-cab">
      <button class="btn-enviar" id="nf-ir" disabled><span class="ic">➤</span>Enviar</button>
      <div class="campos-cab">
        <div class="linha-cab"><span class="rot">De</span>${de}</div>
        <div class="linha-cab"><span class="rot">Para</span><input id="nf-para" list="nf-paras" value="${esc(o.para[0] || "")}">
          <datalist id="nf-paras">${o.para.map(p => `<option value="${esc(p)}">`).join("")}</datalist></div>
        <div class="linha-cab"><span class="rot">Cc</span><input id="nf-cc" placeholder="opcional"></div>
        <div class="linha-cab"><span class="rot">Assunto</span><input id="nf-assunto" placeholder="NF 1212 - NOME DO HÓSPEDE"></div>
      </div>
    </div>
    <div class="soltar ${enc ? "oculta" : ""}" id="nf-soltar"><input type="file" id="nf-arq" accept=".pdf,.xml" multiple hidden>
      <div class="soltar-txt">📎 <b>Arraste a nota fiscal aqui</b> ou <u>clique para escolher</u> · PDF ou XML · pode mais de um (nota dividida)${resp ? " · opcional numa resposta" : ""}</div>
      <div class="chips-anexo" id="nf-anexos"></div></div>
    ${o.sugestoes.length ? `<div class="sug-linha"><span class="dica">Do Dropbox:</span>${o.sugestoes.map((a, i) =>
      `<button class="sug forte" data-nf-sug="${i}" title="${esc(a.prova || "")}">📄 ${esc(a.nome)}</button>`).join("")}</div>` : ""}
    <div class="editor ${o.assinatura_com_mensagem ? "curto" : ""}" id="nf-msg" contenteditable="true" spellcheck="true"
      data-dica="${o.assinatura_com_mensagem ? "Escreva aqui só se quiser acrescentar algo — a mensagem padrão já vem na assinatura abaixo." : ""}"></div>
    ${o.selos.length ? `<div class="selo-previa"><img id="nf-selo-img" alt="Selo"></div>
      <div class="selos"><span class="dica">Assinatura:</span>${o.selos.map(s =>
        `<button class="selo-op" data-nf-selo="${esc(s.id)}">${esc(s.nome)}</button>`).join("")}</div>`
    : o.assinatura ? `<iframe class="assinatura" id="nf-ass" sandbox="allow-same-origin"></iframe>
      <div class="dica">Mensagem padrão e selo da caixa ${esc(o.conta_de)}, como no Outlook (prévia deste PC; sai a do PC que enviar)</div>`
      : enc ? "" : `<div class="dica">Sem assinatura do Outlook para ${esc(o.conta_de)} neste PC.</div>`}
    ${resp?.citacao ? `<div class="cx-citacao" aria-label="Mensagem original">${resp.citacao}</div>` : ""}`;
  if (enc) $("nf-msg").dataset.dica = "Escreva uma mensagem (opcional) — o e-mail original vai junto, embaixo.";
  $("nf-msg").innerText = resp && resp.comNF ? o.corpo_nf : o.corpo;
  if (resp) { $("nf-assunto").value = o.assunto; $("nf-msg").addEventListener("input", validarEnvioNF); }
  if (o.selos.length) {
    let salvo = null;
    try { salvo = localStorage.getItem("selo_nf"); } catch (e) { }
    escolherSelo(o.selos.some(s => s.id === salvo) ? salvo : o.selo || o.selos[0].id);
  } else if (o.assinatura) {
    const ifr = $("nf-ass");
    ifr.srcdoc = `<html><body style="margin:0;background:#fff">${o.assinatura}</body></html>`;
    ifr.onload = () => { try { ifr.style.height = (ifr.contentDocument.body.scrollHeight + 8) + "px"; } catch (e) { ifr.style.height = "230px"; } };
  }
  const zona = $("nf-soltar");
  zona.addEventListener("click", e => { if (!e.target.closest("[data-tirar]")) $("nf-arq").click(); });
  ["dragenter", "dragover"].forEach(t => zona.addEventListener(t, e => { e.preventDefault(); zona.classList.add("sobre"); }));
  ["dragleave", "drop"].forEach(t => zona.addEventListener(t, e => { e.preventDefault(); zona.classList.remove("sobre"); }));
  zona.addEventListener("drop", e => adicionarArquivos(e.dataTransfer.files));
  $("nf-arq").onchange = e => { adicionarArquivos(e.target.files); e.target.value = ""; };
  $("nf-assunto").addEventListener("input", () => { envNF.assuntoAuto = !$("nf-assunto").value.trim(); validarEnvioNF(); });
  $("nf-para").addEventListener("input", validarEnvioNF);
  $("nf-ir").onclick = () => enviarNF();
  if (o.sugestoes.length === 1) escolherSugestao(0);   // nota confirmada pelo conteúdo: já vem anexada
  desenharAnexos();
  validarEnvioNF();
  setTimeout(() => (enc ? $("nf-para") : $("nf-msg"))?.focus(), 50);
}

function escolherSelo(id) {
  envNF.selo = id;
  $("nf-selo-img").src = `/assinaturas/${encodeURIComponent(id)}.png`;
  document.querySelectorAll("[data-nf-selo]").forEach(b => b.classList.toggle("sel", b.dataset.nfSelo === id));
  try { localStorage.setItem("selo_nf", id); } catch (e) { }
}

function adicionarArquivos(lista) {
  for (const f of lista) {
    if (!/\.(pdf|xml)$/i.test(f.name)) { toast(`${f.name}: só PDF ou XML`, true); continue; }
    if (!envNF.anexos.some(a => a.nome === f.name)) envNF.anexos.push({ tipo: "arquivo", nome: f.name, file: f, bytes: f.size });
  }
  desenharAnexos();
}

function escolherSugestao(i) {
  const a = envNF.o.sugestoes[i];
  if (!envNF.anexos.some(x => x.rel === a.rel)) envNF.anexos.push({ tipo: "dropbox", rel: a.rel, nome: a.nome });
  desenharAnexos();
}

function desenharAnexos() {
  $("nf-anexos").innerHTML = envNF.anexos.map((a, i) =>
    `<span class="chip-anexo">📄 ${esc(a.nome)}<span class="dica">${a.bytes ? tamanho(a.bytes) : "Dropbox"}</span>
      <button class="x" data-tirar="${i}" title="Tirar">×</button></span>`).join("");
  $("nf-soltar").classList.toggle("tem", envNF.anexos.length > 0);
  if (envNF.assuntoAuto && envNF.anexos.length) $("nf-assunto").value = assuntoDoArquivo(envNF.anexos[0].nome, envNF.o.nome);
  if (!envNF.anexos.length && envNF.assuntoAuto) $("nf-assunto").value = "";
  validarEnvioNF();
}

function validarEnvioNF() {
  const conteudo = envNF && envNF.o && (envNF.anexos.length || envNF.resp?.encaminhar || (envNF.resp && $("nf-msg").innerText.trim()));
  const ok = envNF && conteudo && $("nf-assunto").value.trim() && $("nf-para").value.includes("@") && (envNF.o.destino || $("nf-conta"));
  $("nf-ir").disabled = !ok;
}

const lerBase64 = f => new Promise((ok, erro) => {
  const r = new FileReader();
  r.onload = () => ok(String(r.result).split(",")[1]); r.onerror = erro; r.readAsDataURL(f);
});

async function enviarNF(contaForcada) {
  $("nf-ir").disabled = true;
  const anexos = await Promise.all(envNF.anexos.map(async a => a.tipo === "arquivo"
    ? { tipo: "arquivo", nome: a.nome, b64: await lerBase64(a.file) } : { tipo: "dropbox", rel: a.rel, nome: a.nome }));
  const conta = contaForcada || ($("nf-conta") ? $("nf-conta").value : "");
  const r = envNF.resp?.encaminhar
    ? await api("/api/correio/encaminhar", { id: envNF.resp.id, para: $("nf-para").value.trim(), corpo: $("nf-msg").innerText })
    : await api(envNF.resp ? "/api/email/responder" : "/api/envio_nf", {
    chave: envNF.chave || undefined, id: envNF.resp ? envNF.resp.id : undefined, para: $("nf-para").value.trim(),
    cc: $("nf-cc").value.trim(), assunto: $("nf-assunto").value.trim(), corpo: $("nf-msg").innerText, anexos,
    conta_de: conta || undefined, selo: envNF.selo || undefined });
  if (!r.ok) { $("nf-ir").disabled = false; return mostrarFalhaNF(r.motivo || r.erro, r.contas_locais); }
  $("nf-anel").className = "anel"; $("nf-anel").textContent = ""; $("nf-anel").style.visibility = "visible";
  $("nf-barra").style.visibility = "visible"; $("nf-barra").classList.remove("fim");
  $("nf-res").textContent = r.destino === envNF.o.este_pc ? "Enviando por este PC…" : `Pedido entregue ao PC ${r.destino}…`;
  acompanharNF(r.id);
}

async function acompanharNF(id) {
  if (!envNF) return;
  const s = await api(`/api/envio_nf/status?id=${id}`).catch(() => ({ estado: "aguardando" }));
  if (!envNF) return;
  if (s.estado === "enviado") {
    $("nf-anel").className = "anel ok"; $("nf-anel").textContent = "✓"; $("nf-barra").classList.add("fim");
    const enc = envNF.resp?.encaminhar;
    $("nf-res").textContent = enc ? `Encaminhado${s.pc ? " pelo Outlook do PC " + s.pc : ""}.`
      : envNF.resp ? `Resposta enviada${s.pc ? " pelo Outlook do PC " + s.pc : ""}. O e-mail fica cinza e sai da caixa em seguida.`
      : `NF enviada ao hóspede${s.pc ? " pelo PC " + s.pc : ""}. Ela já ficou marcada no pedido.`;
    $("nf-ir").style.display = "none";
    if (envNF.resp && !enc) correioRespondido(envNF.resp.id);
    if (envNF.alvo) { const fim = envNF.fechar; setTimeout(() => fim(), 2200); }   // igual ao Outlook: volta pro e-mail
    carregar(); return;
  }
  if (s.estado === "falhou" || s.estado === "sem_resposta") return mostrarFalhaNF(s.detalhe, s.contas_locais);
  $("nf-res").textContent = s.estado === "enviando" ? `O PC ${s.pc || ""} está enviando…` : `Aguardando o PC ${s.pc || ""}…`;
  envNF.timer = setTimeout(() => acompanharNF(id), 2000);
}

function mostrarFalhaNF(motivo, contas) {
  $("nf-anel").className = "anel ruim"; $("nf-anel").textContent = "!"; $("nf-anel").style.visibility = "visible";
  $("nf-barra").style.visibility = "hidden";
  $("nf-res").innerHTML = `<b>Não deu pra enviar pela caixa do hotel.</b> ${esc(motivo || "")}` + ((contas || []).length
    ? ` <span style="white-space:nowrap">Enviar por: <select id="nf-conta-alt">${contas.map(c => `<option>${esc(c)}</option>`).join("")}</select>
       <button class="creme" id="nf-alt">Enviar por esta</button></span>` : "");
  if ($("nf-alt")) $("nf-alt").onclick = () => enviarNF($("nf-conta-alt").value);
}

document.addEventListener("click", e => {
  const b = e.target.closest("[data-envnf],[data-nf-sug],[data-tirar],[data-nf-selo]");
  if (!b) return;
  if (b.dataset.envnf) return abrirEnvioNF(b.dataset.envnf, null, $("detalhe"));
  if (!envNF) return;
  if (b.dataset.nfSug !== undefined) return escolherSugestao(Number(b.dataset.nfSug));
  if (b.dataset.nfSelo) return escolherSelo(b.dataset.nfSelo);
  if (b.dataset.tirar !== undefined) { e.stopPropagation(); envNF.anexos.splice(Number(b.dataset.tirar), 1); desenharAnexos(); }
});
// arquivo solto fora da área de anexo não pode abrir no lugar do Painel
["dragover", "drop"].forEach(t => window.addEventListener(t, e => { if (!e.target.closest?.("#nf-soltar")) e.preventDefault(); }));

// ---------- Eventos ----------
document.addEventListener("click", e => {
  const t = e.target.closest("[data-vista],[data-vj],[data-ir],[data-vt]");
  if (!t) return;
  const ds = t.dataset;
  if (ds.vista) { if (ds.log) at.aba = ds.log; return trocarVista(ds.vista); }
  if (ds.vj) { pn.janela = Number(ds.vj); return desenharVisao(); }
  if (ds.vt) { pn.tabela[ds.vt] = !pn.tabela[ds.vt]; return desenharVisao(); }
  if (ds.ir) return abrirNotas({ filtro: ds.ir });
});
window.addEventListener("resize", () => { clearTimeout(pn.rz); pn.rz = setTimeout(() => pn.vista === "visao" && desenharVisao(), 200); });
trocarVista(location.hash.slice(1) || "visao");
