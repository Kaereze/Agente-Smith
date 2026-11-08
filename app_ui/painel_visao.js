// painel_visao.js: parte de painel.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// ---------- Visão geral: só os dados do próprio Painel (pedidos da Central + e-mails dos hóspedes) ----------
// Pedido do usuário (08/10/2026): menos informação, nada de comparar com o Mail Analytics, gráficos concretos.
const JANELAS = [7, 15, 30, 45];
// cores validadas (dataviz, tema claro e escuro) na ordem em que aparecem empilhadas
// validadas (dataviz) contra o branco e o verde-petróleo do tema escuro (#ffffff e #1b3a34)
// paleta fiscal (11/10/2026): verde da marca = emitida; âmbar = pendente; cinza-azulado = em andamento; vermelho = sem NF
const COR_VIZ = { emitida: "#2b7a5f", envio: "#c08a2b", andamento: "#7d8896", sem_nf: "#c4473c", email: "#aab3be" };
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
  el.innerHTML = `<div class="cartao ger-v2" id="ger-relatorio">${REL.html || `<div class="vazio">Carregando o relatório…</div>`}</div>
    <div class="cartao"><h3>Equipe agora</h3><div class="sub">O que cada um tem pra fazer neste momento e o que saiu hoje</div>
      <div class="tabela-wrap"><table class="ger-tab"><thead><tr><th>Agente</th><th>PC</th><th class="num">NFs pra emitir</th><th class="num">E-mails na entrada</th>
        <th class="num">Urgência</th><th class="num">Enviados 72 h</th><th>Painel</th></tr></thead><tbody>
        ${Object.entries(porAgente).map(([a, x]) => `<tr><td><b>${esc(a)}</b></td><td>${x.p.online ? '<span class="dot on"></span> no ar' : '<span class="dot"></span> desligado'}</td>
          <td class="num">${n(x.notas)}</td><td class="num">${n(x.entrada)}</td><td class="num">${x.urg ? `<span class="ruim-txt">${n(x.urg)}</span>` : "0"}</td>
          <td class="num">${n(x.env)}</td><td>${String(x.p.uso || "").startsWith("aberto") ? "aberto · " + esc(String(x.p.uso).split("|")[1] || "") : "fechado"}</td></tr>`).join("")}
      </tbody></table></div></div>`;
  carregarRelatorio();
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
    { ir: "correio:enviados", rot: "Enviados · 72 h", v: enviados.length, cor: COR_VIZ.emitida,
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

// Resumo do dia (repaginação v2, usuário 14/10/2026): a Visão geral abre em "ontem" — o que chegou, o que foi
// resolvido, o que ficou para hoje — comparado com o mesmo dia da semana anterior.
function resumoDiaHtml() {
  const isoDe = d => d.toLocaleDateString("sv-SE");
  const base = new Date(hojeIso() + "T12:00");
  if (pn.resumo === "ontem") base.setDate(base.getDate() - 1);
  const dia = isoDe(base), antes = new Date(base); antes.setDate(antes.getDate() - 7);
  const diaAntes = isoDe(antes);
  const agenteDe = s => AG[String(s.hotel || "").split(" / ")[0]] || s.dono || "Sem agente";
  const isoEnvio = q => { const m = String(q || "").match(/(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})/); return m ? `${m[3]}-${m[2]}-${m[1]}T${m[4]}:${m[5]}` : ""; };
  const chegada = s => new Date(`${s.data}T${horaDoCarimbo(s.carimbo) || "12:00"}`);
  function numeros(d) {
    const recebidos = st.fila.filter(s => s.data === d);
    const envios = [];
    st.fila.forEach(s => (s.envios || []).forEach(v => { const iso = isoEnvio(v.quando); if (iso.slice(0, 10) === d) envios.push({ s, iso, n: (v.nfs || []).length || 1 }); }));
    const nfs = envios.reduce((a, e) => a + e.n, 0);
    // no prazo = NF enviada até 48 h depois da chegada (o prazo do pedido some quando a nota sai)
    envios.forEach(e => { e.h = (new Date(e.iso) - chegada(e.s)) / 36e5; });
    const validos = envios.filter(e => e.h >= 0);
    const noPrazo = validos.length ? Math.round(100 * validos.filter(e => e.h <= 48).length / validos.length) : null;
    const horas = validos.map(e => e.h).sort((a, b) => a - b);
    const mediana = horas.length ? horas[Math.floor(horas.length / 2)] : null;
    return { recebidos, envios, nfs, noPrazo, mediana };
  }
  const a = numeros(dia), b = numeros(diaAntes);
  const abertos = TODOS.filter(it => it.tipo === "form" && it.s.situacao !== "concluida" && it.s.data <= dia);
  const vencidos = abertos.filter(it => (prazoInfo(it.s.prazo)?.resta ?? 1) <= 0).length;
  // Comparação em quantidade (24/10/2026: "▲ 908% · eram 12" parecia alarme). % só com base de 20 ou mais.
  // bom: +1 = subir é bom (verde), -1 = descer é bom, 0 = neutro
  const diaPassado = (() => { const n = new Date(diaAntes + "T12:00").toLocaleDateString("pt-BR", { weekday: "long" }).split("-")[0];
    return /sábado|domingo/.test(n) ? `no ${n} passado` : `na ${n} passada`; })();
  const varN = (x, y, bom) => {
    if (!x && !y) return "";
    const d = x - y;
    if (!d) return `igual ${diaPassado.startsWith("no") ? "ao" : "à"} ${diaPassado.slice(3)} (${y})`;
    const cls = !bom ? "neutro" : (d > 0) === (bom > 0) ? "sobe" : "desce";
    const pct = y >= 20 ? ` (${d > 0 ? "+" : "−"}${Math.abs(Math.round(100 * d / y))}%)` : "";
    return `<em class="${cls}">${d > 0 ? "+" : "−"}${Math.abs(d)}${pct}</em> que ${diaPassado} (${y})`;
  };
  const fmtH = h => h == null ? "—" : h < 1 ? Math.round(h * 60) + " min" : Math.round(h) + " h";
  const nomeDia = base.toLocaleDateString("pt-BR", { weekday: "long", day: "2-digit", month: "2-digit" });
  const porAgente = {};
  const somar = (ag, k, v = 1) => { (porAgente[ag] ||= { rec: 0, nfs: 0, prazo: [0, 0], pend: 0 })[k] = (k === "prazo" ? porAgente[ag][k] : (porAgente[ag][k] || 0) + v); };
  a.recebidos.forEach(s => somar(agenteDe(s), "rec"));
  a.envios.forEach(e => { const ag = agenteDe(e.s); somar(ag, "nfs", e.n); if (e.h >= 0) { const p = porAgente[ag].prazo; p[1]++; if (e.h <= 48) p[0]++; } });
  abertos.forEach(it => somar(agentesDo(it)[0] || agenteDe(it.s), "pend"));
  const atencao = TODOS.filter(it => it.tipo === "form" && (motivoUrgente(it.s) || faltaDados(it.s).length))
    .sort((x, y) => String(x.s.prazo?.vence || "9") < String(y.s.prazo?.vence || "9") ? -1 : 1).slice(0, 6);
  // --- dados para a peça (pecas/resumo_dia.js) ---
  const horaDe = h => parseInt(String(h).slice(0, 2), 10);
  const evHoras = [...a.recebidos.map(s => horaDe(horaDoCarimbo(s.carimbo) || "12:00")), ...a.envios.map(e => horaDe(e.iso.slice(11, 13)))].filter(h => h >= 0 && h <= 23);
  const h0 = Math.min(8, ...evHoras), h1 = Math.max(19, ...evHoras);
  const horas = Array.from({ length: h1 - h0 + 1 }, (_, i) => ({ h: h0 + i, ped: 0, nfs: 0 }));
  a.recebidos.forEach(s => { const x = horas[horaDe(horaDoCarimbo(s.carimbo) || "12:00") - h0]; if (x) x.ped++; });
  a.envios.forEach(e => { const x = horas[horaDe(e.iso.slice(11, 13)) - h0]; if (x) x.nfs += e.n; });
  // os 7 dias até o dia do resumo, para o risquinho de cada cartão
  const ultimos = Array.from({ length: 7 }, (_, i) => { const x = new Date(base); x.setDate(x.getDate() - (6 - i)); return numeros(isoDe(x)); });
  const serie = f => { const v = ultimos.map(f); let ult = null; const lis = v.map(x => x == null ? ult : (ult = x)); return lis.filter(x => x != null).length >= 2 ? lis.map(x => x ?? 0) : null; };
  const kpis = [
    { r: "Pedidos recebidos", v: a.recebidos.length, fmt: "n", delta: varN(a.recebidos.length, b.recebidos.length, 0) || "pelo formulário", spark: serie(n => n.recebidos.length) },
    { r: "NFs enviadas", v: a.nfs, fmt: "n", delta: varN(a.nfs, b.nfs, 1) || "pelo Painel e Outlook", spark: serie(n => n.nfs) },
    { r: "Enviadas no prazo", v: a.noPrazo, fmt: "p", spark: serie(n => n.noPrazo),
      delta: b.noPrazo == null || a.noPrazo == null ? "prazo de 48 h" : a.noPrazo === b.noPrazo ? `igual (era ${b.noPrazo}%)`
        : `<em class="${a.noPrazo > b.noPrazo ? "sobe" : "desce"}">${a.noPrazo > b.noPrazo ? "+" : "−"}${Math.abs(a.noPrazo - b.noPrazo)} pontos</em> (era ${b.noPrazo}%)` },
    { r: "Tempo até a NF", v: a.mediana == null ? null : Math.round(a.mediana), fmt: "h", spark: serie(n => n.mediana),
      delta: a.mediana == null || b.mediana == null || Math.round(a.mediana) === Math.round(b.mediana) ? `mediana${b.mediana != null ? ` · era ${fmtH(b.mediana)}` : ""}`
        : `<em class="${a.mediana < b.mediana ? "sobe" : "desce"}">${fmtH(Math.abs(b.mediana - a.mediana))} ${a.mediana < b.mediana ? "mais rápido" : "mais lento"}</em> (era ${fmtH(b.mediana)})` },
    { r: `Ficaram para ${pn.resumo === "ontem" ? "hoje" : "amanhã"}`, v: abertos.length, fmt: "n", spark: null,
      delta: `<span class="${vencidos ? "desce" : ""}">${vencidos ? vencidos + " já vencido" + (vencidos > 1 ? "s" : "") : "nenhum vencido"}</span>` },
  ];
  const noPrazoOk = a.envios.filter(e => e.h >= 0 && e.h <= 48).length, validosN = a.envios.filter(e => e.h >= 0).length;
  const prontas = TODOS.filter(it => it.tipo === "form" && it.s.situacao === "concluida" && it.s.envio_pendente).length;
  const faltaN = abertos.filter(it => faltaDados(it.s).length).length;
  const porHotel = {};
  a.recebidos.forEach(s => { const h = String(s.hotel || "—").split(" / ")[0]; porHotel[h] = (porHotel[h] || 0) + 1; });
  const dados = {
    kpis, horas, tabela: !!pn.rsTabela,
    prazo: { pct: a.noPrazo, ok: noPrazoOk, total: validosN },
    abertos: [{ nome: "Sem NF", n: abertos.length - faltaN, k: "a" }, { nome: "Falta dado", n: faltaN, k: "c" }, { nome: "NF pronta, falta enviar", n: prontas, k: "b" }],
    vencidos,
    equipe: Object.entries(porAgente).filter(([ag]) => ag !== "Sem agente").sort((x, y) => x[0].localeCompare(y[0])).map(([nome, v]) => ({ nome, rec: v.rec || 0, nfs: v.nfs || 0 })),
    hoteis: Object.entries(porHotel).sort((x, y) => y[1] - x[1] || x[0].localeCompare(y[0])).slice(0, 6).map(([nome, n]) => ({ nome, n })),
    titulos: { equipe: `Equipe ${pn.resumo === "ontem" ? "ontem" : "hoje"}`, atencao: `Precisa de atenção ${pn.resumo === "ontem" ? "hoje" : "agora"}`,
               abertos: pn.resumo === "ontem" ? "O que ficou para hoje" : "O que está em aberto" },
    atencao: atencao.length ? atencao.map(it => `<button type="button" class="rd-lin" data-abrir-ficha="${esc(it.s.chave)}">
          <span class="rd-nome"><b>${esc(it.s.nome)}</b><small>${esc(it.s.hotel)} · ${esc(agentesDo(it)[0] || "")}</small></span>
          <span class="tags-nf">${tagsPedido(it.s)}</span><span class="rd-pz">${it.s.prazo ? prazoHtml(it.s.prazo) : ""}</span></button>`).join("")
      : `<div class="vazio">Nada urgente nem com dado faltando.</div>`,
  };
  dados.kpis[4].mini = dados.abertos;   // o último cartão não tem série de 7 dias: mostra a divisão do que ficou em aberto
  // a animação roda quando os números mudam ou a tela acabou de abrir (mais de 20 s sem desenhar); no refresh de 15 s, não repete
  const assinatura = JSON.stringify([pn.resumo, kpis.map(k => k.v), horas, dados.abertos, dados.equipe, dados.hoteis]);
  pn.rsAnimar = assinatura !== pn.rsAssinatura || Date.now() - (pn.rsDesenhado || 0) > 20000;
  pn.rsAssinatura = assinatura; pn.rsDesenhado = Date.now();
  return `<section class="resumo-dia" aria-label="Resumo do dia">
    <div class="rd-cab"><h1>${pn.resumo === "ontem" ? "Resumo de ontem" : "Resumo de hoje"}</h1>
      <span class="sub">${esc(nomeDia)} · comparado com o mesmo dia da semana anterior</span>
      <div class="rs-acoes"><button type="button" class="rs-btn" data-rs-tabela aria-pressed="${!!pn.rsTabela}">${pn.rsTabela ? "Ver os gráficos" : "Ver como tabela"}</button>
      <div class="seg-rd" role="group" aria-label="Dia do resumo">
        <button type="button" data-rd="ontem" aria-pressed="${pn.resumo === "ontem"}">Ontem</button>
        <button type="button" data-rd="hoje" aria-pressed="${pn.resumo === "hoje"}">Hoje</button></div></div></div>
    ${resumoDiaPeca(dados)}</section>`;
}
document.addEventListener("click", e => { const b = e.target.closest("[data-rd]"); if (b) { pn.resumo = b.dataset.rd; desenharVisao(); } });
document.addEventListener("click", e => { if (e.target.closest("[data-rs-tabela]")) { pn.rsTabela = !pn.rsTabela; pn.rsAnimar = false; pn.rsAssinatura = ""; desenharVisao(); } });

// Cartão Ligações (usuário, 22/10/2026): o que foi marcado no botão "Ligação" ao enviar ou depois em Itens Enviados
function cartaoLigacoes() {
  const L = st.ligacoes;
  if (!L) return "";
  const n = v => (v ?? 0).toLocaleString("pt-BR");
  const vista = pn.ligVista === "agente" ? "agente" : "hotel";
  let linhas = vista === "agente" ? L.por_agente : L.por_hotel;
  if (vista === "hotel" && linhas.length > 6) {   // os 5 que mais ligaram e o resto junto
    const resto = linhas.slice(5);
    linhas = [...linhas.slice(0, 5), [`Outros ${resto.length} hotéis`, resto.reduce((a, x) => a + x[1], 0), true]];
  }
  const max = Math.max(1, ...linhas.map(x => x[1]));
  const corpo = !L.semana ? `<div class="lig-vazio">Nenhuma ligação marcada nos últimos 7 dias. Ao enviar, clique em <b>Ligação</b> embaixo do Enviar quando o hóspede pediu por telefone.</div>`
    : `<div class="lig-barras" role="list">${linhas.map(([nome, q, outros]) => `<div class="lig-bl" role="listitem"><span class="nm" title="${esc(nome)}">${esc(nome)}</span>
        <span class="tr"><i style="width:${Math.max(2, Math.round(q / max * 100))}%${outros ? ";opacity:.55" : ""}"></i></span><span class="q">${n(q)}</span></div>`).join("")}</div>`;
  return `<div class="sec-tit" style="margin-top:4px">Ligações</div>
    <div class="cartao lig-cartao"><div class="cartao-topo"><div><h3>Pedidos que vieram por telefone</h3>
      <div class="sub">Marcados no botão Ligação ao enviar (ou depois, no botão direito em Itens Enviados). Os 4 PCs.</div></div>
      <div class="seg" role="group" aria-label="Ligações por" style="margin-left:auto">${[["hotel", "Por hotel"], ["agente", "Por agente"]].map(([k, t]) =>
        `<button data-lig-vista="${k}" aria-pressed="${vista === k}">${t}</button>`).join("")}</div></div>
      <div class="lig-num">
        <div><b>${n(L.hoje)}</b><span>hoje</span><small>${L.envios_hoje ? `de ${n(L.envios_hoje)} envios pelo Painel` : "marcadas hoje"}</small></div>
        <div><b>${n(L.semana)}</b><span>7 dias</span><small>média de ${(L.semana / 7).toLocaleString("pt-BR", { maximumFractionDigits: 1 })} por dia</small></div>
        <div><b>${n(L.mes)}</b><span>${new Date().toLocaleDateString("pt-BR", { month: "long" })}</span><small>até hoje</small></div>
      </div>
      <div class="lig-t">Últimos 7 dias, ${vista === "agente" ? "por quem enviou" : "por hotel"}</div>${corpo}</div>`;
}
document.addEventListener("click", ev => {
  const b = ev.target.closest("[data-lig-vista]");
  if (b) { pn.ligVista = b.dataset.ligVista; desenharVisao(); }
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
  // tabela por operador (organização, 11/10/2026): o que cada caixa tem agora, numa grade só
  const todosMails = cx.dados?.emails || [], todosEnv = cx.dados?.enviados || [];
  const linhaOp = v => {
    const s = TODOS.filter(it => it.tipo === "form" && doAgente(agentesDo(it), v));
    const m = todosMails.filter(e => doEscopo(e, v));
    return [s.length, s.filter(it => ["na_fila", "aguardando_envio"].includes(it.s.situacao)).length,
            s.filter(it => it.s.situacao !== "concluida" && diasAtras(it.s.data) > 7).length,
            m.length, m.filter(e => e.lido === false).length, m.filter(e => e.urgente).length,
            todosEnv.filter(e => doEscopo(e, v)).length];
  };
  const tabOp = `<div class="tabela-wrap"><table class="ger-tab tab-op"><thead><tr><th>Operador</th><th class="num">Solicitações</th>
      <th class="num">Sem NF</th><th class="num">Atrasadas</th><th class="num">E-mails</th><th class="num">Não lidos</th><th class="num">Urgentes</th>
      <th class="num">Enviados 72 h</th></tr></thead><tbody>${[...agentesEquipe(), "todos"].map(v => {
        const c = linhaOp(v);
        return `<tr data-escopo="${esc(v)}" class="${escopoAtual() === v ? "sel" : ""}"><td>${v === "todos" ? "Total" : esc(v)}</td>${c.map((x, k) =>
          `<td class="num">${(k === 2 || k === 5) && x ? `<span class="ruim-txt">${n(x)}</span>` : n(x)}</td>`).join("")}</tr>`; }).join("")}</tbody></table></div>`;
  el.innerHTML = resumoDiaHtml() + `<div class="cab-pagina"><div style="display:flex;flex-direction:column;gap:4px;margin-right:auto"><h1>Visão geral</h1>
      <span class="resumo-tela">Agora, no Outlook · ${esc(quem)}</span></div>
      <div class="grupo" style="display:flex;align-items:center;gap:10px">
        <div class="seg-op" role="group" aria-label="Operador">${segOperadores(null)}</div></div></div>
    <p class="dica-prof" style="margin:0 0 14px">Como estamos agora? Os números são os mesmos das telas Notas fiscais e Caixa de entrada: o que está no Outlook neste momento. Clique num indicador pra abrir a lista.</p>
    <div class="sec-tit">Agora</div>
    ${faixaAgora(sol, mails, enviados)}
    <div class="sec-tit" style="margin-top:18px">Por operador</div>
    <div class="grade2">
      <div class="cartao"><div class="cartao-topo"><div><h3>O que cada caixa tem agora</h3><div class="sub">Clique numa linha pra ver só a caixa daquele operador</div></div></div>
        ${tabOp}</div>
      <div class="cartao"><div class="cartao-topo"><div><h3>Há quanto tempo esperam</h3><div class="sub">Solicitações sem NF e e-mails na caixa, pelo dia em que chegaram</div></div>
        ${botaoTabela("idade")}</div>
        <div id="graf-idade" style="margin-top:14px"></div></div>
    </div>
    ${cartaoLigacoes()}
    <div class="sec-tit" style="margin-top:4px">Histórico</div>
    <div class="cartao"><div class="cartao-topo"><div><h3>Pedidos de cada dia e o que aconteceu com eles</h3>
      <div class="sub">Formulários da Planilha Central (inclui os já resolvidos e fora do Outlook). Cada coluna é o dia em que o hóspede pediu.</div></div>
      <div style="display:flex;gap:10px;align-items:center"><div class="seg" role="group" aria-label="Período">${JANELAS.map(j =>
        `<button data-vj="${j}" aria-pressed="${pn.janela === j}">${j} dias</button>`).join("")}</div>${botaoTabela("dias")}</div></div>
      <div id="leg-dias" style="margin:4px 0 10px"></div><div id="graf-dias"></div></div>`;
  if (pn.rsAnimar) resumoDiaAnimar(el);   // Resumo do dia (pecas/resumo_dia.js): números sobem e gráficos entram só quando mudou ou a tela abriu
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
  if (pn.tabela.idade) $("graf-idade").innerHTML = tabela(["Espera", "Pedidos em aberto"], idade.map(i => [i.rotulo, i.n]));
  else graficoBarrasH($("graf-idade"), idade, { aoClicar: it => abrirNotas({ filtro: it.atrasada ? "atrasadas" : "aberto",
    agente: escopoAtual() === "todos" ? "" : escopoAtual() }) });
}
