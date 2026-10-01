// Visão geral e Hotéis. Usa api/$/esc/toast/st/NOMES do script da fila (mesmo escopo global).
const PERIODOS = [["mes", "Este mês"], ["7", "Últimos 7 dias"], ["30", "Últimos 30 dias"], ["tudo", "Desde 01/09"]];
const MEDIDAS = {
  nf: { nome: "Solicitações × NFs", chaves: [{ k: "solicitacoes", nome: "Solicitações recebidas" }, { k: "nfs", nome: "NFs emitidas" }] },
  email: { nome: "E-mails", chaves: [{ k: "recebidos", nome: "E-mails recebidos" }, { k: "enviados", nome: "E-mails enviados" }] },
  outros: { nome: "Ligações × Cancelamentos", chaves: [{ k: "ligacoes", nome: "Ligações" }, { k: "cancelamentos", nome: "Cancel./Subst." }] },
};
let pn = { vista: "visao", periodo: "30", ini: "", fim: "", medida: "nf", tabela: false, dados: null,
           ordem: { campo: "pendentes", desc: true }, buscaHotel: "", hotelAberto: null, ficha: null, timer: null };

const hojeIso = () => new Date().toLocaleDateString("sv-SE");
function periodoAtual() {
  const hoje = new Date(hojeIso() + "T12:00");
  const iso = d => d.toLocaleDateString("sv-SE");
  if (pn.periodo === "custom") return [pn.ini, pn.fim];
  if (pn.periodo === "mes") return [iso(new Date(hoje.getFullYear(), hoje.getMonth(), 1)), iso(hoje)];
  if (pn.periodo === "tudo") return ["", iso(hoje)];
  const ini = new Date(hoje); ini.setDate(ini.getDate() - (Number(pn.periodo) - 1));
  return [iso(ini), iso(hoje)];
}

async function carregarPainel() {
  const [ini, fim] = periodoAtual();
  const j = await api(`/api/painel?ini=${ini}&fim=${fim}`).catch(() => null);
  if (j && !j.erro) { pn.dados = j; desenharVisao(); desenharHoteis(); }
  if (pn.hotelAberto) abrirHotel(pn.hotelAberto, true);
  clearTimeout(pn.timer);
  pn.timer = setTimeout(carregarPainel, 60000);
}

function trocarVista(v) {
  pn.vista = v;
  document.querySelectorAll("#abas button").forEach(b => b.classList.toggle("sel", b.dataset.vista === v));
  for (const id of ["visao", "fila", "hoteis"]) $("v-" + id).classList.toggle("oculta", id !== v);
  if (v === "visao") desenharVisao();
  if (v === "hoteis") desenharHoteis();
}

// ---------- Visão geral ----------
function filtrosHtml(titulo) {
  const [ini, fim] = periodoAtual();
  return `<div class="filtros"><div class="titulo">${titulo}</div>
    <div class="seg">${PERIODOS.map(([k, n]) => `<button data-p-periodo="${k}" class="${pn.periodo === k ? "sel" : ""}">${n}</button>`).join("")}</div>
    <input type="date" data-p-data="ini" value="${ini || (pn.dados?.desde ?? "")}" min="${pn.dados?.desde ?? ""}" max="${hojeIso()}">
    <span style="color:var(--suave)">até</span>
    <input type="date" data-p-data="fim" value="${fim}" min="${pn.dados?.desde ?? ""}" max="${hojeIso()}"></div>`;
}

function saudeHtml(d) {
  const s = d.saude || {}, cards = [];
  const robo = st.status || {};
  cards.push(card(robo.ligado ? "bom" : "ruim", `${robo.ligado ? "✔" : "✖"} Robô de NF`,
    robo.ligado ? `ligado · última execução ${robo.ultima_execucao || "—"}` : "desligado na aba Status", robo.resumo));
  const e = s.escutar_comando;
  if (e) {
    const cls = !e.online ? "ruim" : e.desatualizado ? "alerta" : "bom";
    const txt = !e.online ? "parado — abra o escutar_comando.bat" : e.desatualizado ? "rodando com código velho — reinicie" : "online";
    cards.push(card(cls, `${cls === "bom" ? "✔" : cls === "alerta" ? "⚠" : "✖"} Mail Analytics`,
      `${txt} · consolidado de ${e.ultimo_consolidado || "—"}`, e.status));
  }
  for (const o of s.operadores || []) {
    const cls = o.ontem === "nao_puxado" ? "ruim" : o.status === "ATENCAO" ? "alerta" : "bom";
    const ontem = o.ontem === "puxado" ? "dados de ontem puxados" : o.ontem === "guardado"
      ? `ontem guardado pra somar em ${dataBr(o.domingo)}` : "dados de ontem NÃO chegaram";
    cards.push(card(cls, `${cls === "bom" ? "✔" : cls === "alerta" ? "⚠" : "✖"} ${o.operador}`,
      `${ontem} · ${o.ultima_execucao || "nunca rodou"}`, o.detalhe));
  }
  return `<div class="saude">${cards.join("")}</div>`;
  function card(cls, titulo, linha, dica) {
    return `<div class="c ${cls}" title="${esc(dica || linha)}"><b>${esc(titulo)}</b><span>${esc(linha)}</span></div>`;
  }
}

function desenharVisao() {
  const d = pn.dados, el = $("visao");
  if (!d) { el.innerHTML = `<div class="vazio">Carregando…</div>`; return; }
  const k = d.visao.kpis, n = v => (v ?? 0).toLocaleString("pt-BR");
  const med = MEDIDAS[pn.medida];
  const fds = d.visao.serie.some(p => p.fim_de_semana.length);
  el.innerHTML = filtrosHtml("Visão geral") + saudeHtml(d) +
    (d.fi_erro ? `<div class="avisos ruim-txt">⚠ Não consegui ler o Fiscal Intelligence: ${esc(d.fi_erro)}</div>` : "") +
    `<div class="kpis">
      <div class="kpi hero"><div class="r">Pendentes agora</div><div class="v">${n(k.pendentes_agora)}</div>
        <div class="s">${n(k.pendentes_7d)} há mais de 7 dias · <button class="link" data-p-ir="fila">ver fila</button></div></div>
      <div class="kpi"><div class="r">Solicitações recebidas</div><div class="v">${n(k.solicitacoes)}</div><div class="s">no período</div></div>
      <div class="kpi"><div class="r">Com NF emitida</div><div class="v">${n(k.concluidas)}</div>
        <div class="s">${k.taxa_atendimento == null ? "—" : k.taxa_atendimento + "% das solicitações"}</div></div>
      <div class="kpi"><div class="r">NFs emitidas (Mail Analytics)</div><div class="v">${n(k.nfs)}</div><div class="s">contadas nos e-mails</div></div>
      <div class="kpi"><div class="r">Cancelamentos/substituições</div><div class="v">${n(k.cancelamentos)}</div>
        <div class="s">${k.nfs ? Math.round(100 * k.cancelamentos / k.nfs) + "% das NFs" : "—"}</div></div>
      <div class="kpi"><div class="r">E-mails recebidos</div><div class="v">${n(k.recebidos)}</div></div>
      <div class="kpi"><div class="r">E-mails enviados</div><div class="v">${n(k.enviados)}</div></div>
      <div class="kpi"><div class="r">Ligações</div><div class="v">${n(k.ligacoes)}</div></div>
      <div class="kpi"><div class="r">Período</div><div class="v" style="font-size:18px">${dataBr(d.ini)} a ${dataBr(d.fim)}</div>
        <div class="s">Mail Analytics lido ${quando(d.fi_lido_em)}</div></div>
    </div>
    <div class="cartao"><div class="cartao-topo"><div><h3>${med.nome} por dia</h3>
      <div class="sub">${fds ? "Domingos marcados incluem sexta/sábado somados pelo Mail Analytics (passe o mouse)" : "Passe o mouse para ver cada dia"}</div></div>
      <div class="seg">${Object.entries(MEDIDAS).map(([c, m]) => `<button data-p-medida="${c}" class="${pn.medida === c ? "sel" : ""}">${m.nome}</button>`).join("")}</div>
      <button class="link" data-p-tabela="1">${pn.tabela ? "ver gráfico" : "ver tabela"}</button></div>
      <div id="leg-dia" style="margin-bottom:6px"></div><div id="graf-dia"></div></div>
    <div class="grade2">
      <div class="cartao"><h3>Pendentes por idade</h3><div class="sub">Solicitações sem NF desde ${dataBr(d.desde)}, pelo tempo de espera</div><div id="graf-idade"></div></div>
      <div class="cartao"><h3>Hotéis com mais pendentes</h3><div class="sub">Clique para abrir a ficha do hotel</div><div id="graf-top"></div></div>
    </div>`;
  legenda($("leg-dia"), med.chaves);
  if (pn.tabela) {
    $("graf-dia").innerHTML = `<table class="tabela"><thead><tr><th>Dia</th>${med.chaves.map(c => `<th class="num">${c.nome}</th>`).join("")}<th>Observação</th></tr></thead>
      <tbody>${d.visao.serie.map(p => `<tr><td>${dataBr(p.data)}</td>${med.chaves.map(c => `<td class="num">${p[c.k] == null ? "—" : n(p[c.k])}</td>`).join("")}
      <td>${esc(p.fim_de_semana.join(" · "))}</td></tr>`).join("")}</tbody></table>`;
  } else {
    graficoLinhas($("graf-dia"), d.visao.serie, med.chaves, { notaDoDia: p => p.fim_de_semana.map(esc).join("<br>") });
  }
  graficoBarrasH($("graf-idade"), d.visao.idade.map(i => ({ rotulo: i.faixa, n: i.n })));
  graficoBarrasH($("graf-top"), d.visao.top_pendentes.map(h => ({ rotulo: h.hotel, n: h.n })),
                 { aoClicar: it => { trocarVista("hoteis"); abrirHotel(it.rotulo); } });
}

// ---------- Hotéis ----------
const COLS = [["hotel", "Hotel"], ["agente", "Agente"], ["solicitacoes", "Solicitações", 1], ["concluidas", "Com NF", 1],
  ["taxa_atendimento", "Atendimento", 1, "%"], ["pendentes", "Pendentes", 1], ["mais_antigo", "Mais antigo", 1, " d"],
  ["nfs", "NFs (MA)", 1], ["cancelamentos", "Cancel./Subst.", 1], ["taxa_cancelamento", "Cancel. %", 1, "%"],
  ["recebidos", "E-mails rec.", 1], ["enviados", "E-mails env.", 1], ["ligacoes", "Ligações", 1]];

function desenharHoteis() {
  const d = pn.dados, el = $("hoteis");
  if (!d) { el.innerHTML = `<div class="vazio">Carregando…</div>`; return; }
  const busca = pn.buscaHotel.toLowerCase(), { campo, desc } = pn.ordem;
  let linhas = d.hoteis.filter(h => !busca || (h.hotel + " " + h.agente).toLowerCase().includes(busca));
  linhas = linhas.slice().sort((a, b) => {
    const va = a[campo] ?? -1, vb = b[campo] ?? -1;
    return (typeof va === "string" ? va.localeCompare(vb) : va - vb) * (desc ? -1 : 1);
  });
  const foco = document.activeElement?.id === "busca-hotel";
  el.innerHTML = filtrosHtml("Hotéis") +
    `<div class="barra"><input id="busca-hotel" placeholder="Filtrar por hotel ou agente…" value="${esc(pn.buscaHotel)}"></div>
    <div class="cartao" style="padding:0;overflow:auto"><table class="tabela"><thead><tr>${COLS.map(([c, nome, num]) =>
      `<th class="${num ? "num" : ""}" data-p-ordem="${c}">${nome}${campo === c ? (desc ? " ▾" : " ▴") : ""}</th>`).join("")}</tr></thead>
    <tbody>${linhas.map(h => `<tr data-p-hotel="${esc(h.hotel)}">${COLS.map(([c, , num, suf]) => {
      const v = h[c];
      if (!num) return `<td>${esc(v)}</td>`;
      const cls = (v == null || v === 0) ? "zero" : (c === "mais_antigo" && v > 15) || (c === "taxa_cancelamento" && v > 30) ? "ruim-txt"
        : (c === "mais_antigo" && v > 7) ? "alerta-txt" : "";
      return `<td class="num ${cls}">${v == null ? "—" : v.toLocaleString("pt-BR") + (suf || "")}</td>`;
    }).join("")}</tr>`).join("")}</tbody></table></div>
    <div class="avisos">${linhas.length} hotéis · NFs (MA) e cancelamentos vêm do Mail Analytics; solicitações e pendentes, da Planilha Central${d.avisos.length ? " · " + esc(d.avisos.join(" · ")) : ""}</div>`;
  if (foco) { const i = $("busca-hotel"); i.focus(); i.setSelectionRange(i.value.length, i.value.length); }
}

async function abrirHotel(nome, silencioso) {
  pn.hotelAberto = nome;
  $("v-hoteis").classList.add("ficha-aberta");
  const [ini, fim] = periodoAtual();
  if (!silencioso) $("ficha-hotel").innerHTML = `<div class="vazio">Carregando ${esc(nome)}…</div>`;
  const f = await api(`/api/hotel?nome=${encodeURIComponent(nome)}&ini=${ini}&fim=${fim}`);
  if (pn.hotelAberto !== nome) return;
  const t = f.totais, n = v => (v ?? 0).toLocaleString("pt-BR");
  $("ficha-hotel").innerHTML = `<button class="fechar" data-p-fechar="1">×</button>
    <h2>${esc(nome)}</h2><div class="sub">${esc(f.email || "")} · agente ${esc(f.agente || "—")}</div>
    <div class="kpis" style="grid-template-columns:repeat(3,1fr)">
      <div class="kpi"><div class="r">Pendentes</div><div class="v">${n(f.pendentes.length)}</div></div>
      <div class="kpi"><div class="r">NFs (MA)</div><div class="v">${n(t.nfs)}</div></div>
      <div class="kpi"><div class="r">Cancel./Subst.</div><div class="v">${n(t.cancelamentos)}</div></div>
      <div class="kpi"><div class="r">E-mails rec.</div><div class="v">${n(t.recebidos)}</div></div>
      <div class="kpi"><div class="r">E-mails env.</div><div class="v">${n(t.enviados)}</div></div>
      <div class="kpi"><div class="r">Ligações</div><div class="v">${n(t.ligacoes)}</div></div>
    </div>
    <div class="cartao"><h3>Solicitações × NFs por dia</h3><div id="leg-hotel" style="margin:6px 0"></div><div id="graf-hotel"></div></div>
    <div class="cartao"><h3>Pendentes por idade</h3><div id="idade-hotel" style="margin-top:8px"></div></div>
    <div class="cartao"><h3>Pendentes (${f.pendentes.length})</h3><div class="sub">Clique para abrir na fila de solicitações</div>
      <table class="tabela"><tbody>${f.pendentes.map(p => `<tr data-p-sol="${esc(p.chave)}"><td>${dataBr(p.data)}</td>
      <td>${esc(p.nome)}</td><td>${p.dono ? "👤 " + esc(p.dono) : ""}</td><td class="num ${p.idade > 15 ? "ruim-txt" : p.idade > 7 ? "alerta-txt" : ""}">${p.idade} d</td></tr>`).join("") ||
      `<tr><td class="zero">Nenhuma pendente 🎉</td></tr>`}</tbody></table></div>`;
  legenda($("leg-hotel"), MEDIDAS.nf.chaves);
  graficoLinhas($("graf-hotel"), f.serie, MEDIDAS.nf.chaves, { altura: 200, notaDoDia: p => p.fim_de_semana.map(esc).join("<br>") });
  graficoBarrasH($("idade-hotel"), f.idade.map(i => ({ rotulo: i.faixa, n: i.n })));
}

// ---------- Eventos ----------
document.addEventListener("click", e => {
  const t = e.target.closest("[data-vista],[data-p-periodo],[data-p-medida],[data-p-tabela],[data-p-ordem],[data-p-hotel],[data-p-fechar],[data-p-sol],[data-p-ir]");
  if (!t) return;
  const ds = t.dataset;
  if (ds.vista) return trocarVista(ds.vista);
  if (ds.pPeriodo) { pn.periodo = ds.pPeriodo; return carregarPainel(); }
  if (ds.pMedida) { pn.medida = ds.pMedida; return desenharVisao(); }
  if (ds.pTabela) { pn.tabela = !pn.tabela; return desenharVisao(); }
  if (ds.pOrdem) { pn.ordem = { campo: ds.pOrdem, desc: pn.ordem.campo === ds.pOrdem ? !pn.ordem.desc : ds.pOrdem !== "hotel" && ds.pOrdem !== "agente" }; return desenharHoteis(); }
  if (ds.pHotel) return abrirHotel(ds.pHotel);
  if (ds.pFechar) { pn.hotelAberto = null; $("v-hoteis").classList.remove("ficha-aberta"); return; }
  if (ds.pIr) { filtro = "na_fila"; hotel = ""; trocarVista("fila"); return desenhar(); }
  if (ds.pSol) {
    const s = st.fila.find(x => x.chave === ds.pSol);
    filtro = "todas"; hotel = pn.hotelAberto || ""; sel = ds.pSol;
    if (!s) { $("dias").value = "0"; carregar(); }
    trocarVista("fila"); desenhar();
  }
});
document.addEventListener("change", e => {
  const campo = e.target.dataset?.pData;
  if (!campo) return;
  const [ini, fim] = periodoAtual();
  pn.ini = campo === "ini" ? e.target.value : (ini || pn.dados?.desde || "");
  pn.fim = campo === "fim" ? e.target.value : fim;
  pn.periodo = "custom";
  carregarPainel();
});
document.addEventListener("input", e => {
  if (e.target.id === "busca-hotel") { pn.buscaHotel = e.target.value; desenharHoteis(); }
});
$("btn-atualizar").addEventListener("click", () => setTimeout(carregarPainel, 1500));
window.addEventListener("resize", () => { clearTimeout(pn.rz); pn.rz = setTimeout(() => pn.vista === "visao" && desenharVisao(), 200); });
trocarVista(["visao", "fila", "hoteis"].includes(location.hash.slice(1)) ? location.hash.slice(1) : "visao");
carregarPainel();
