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
    // ATENÇÃO: o motivo (1º aviso do Mail Analytics) aparece no cartão; o texto completo fica no tooltip
    const motivo = o.status === "ATENCAO" && o.detalhe ? o.detalhe.split(/;\s*/)[0].split(" — ")[0] : "";
    cards.push(card(cls, `${cls === "bom" ? "✔" : cls === "alerta" ? "⚠" : "✖"} ${o.operador}`,
      `${ontem} · ${o.ultima_execucao || "nunca rodou"}`, o.detalhe, motivo));
  }
  return `<div class="saude">${cards.join("")}</div>`;
  function card(cls, titulo, linha, dica, motivo) {
    return `<div class="c ${cls}" title="${esc(dica || linha)}"><b>${esc(titulo)}</b><span>${esc(linha)}</span>` +
           (motivo ? `<span class="motivo">${esc(motivo)}</span>` : "") + `</div>`;
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

// ---------- Enviar pendentes (janela com o andamento ao vivo) ----------
let envioTimer = null;
async function abrirEnvio() {
  if (document.querySelector(".modal-fundo")) return;
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `<div class="modal"><div class="modal-topo"><div class="anel" id="env-anel"></div>
      <div><h3 id="env-titulo">Enviar solicitações pendentes</h3><div class="sub" id="env-sub">Confirme para o robô começar</div></div></div>
    <div class="barra-prog" id="env-barra" style="visibility:hidden"><i></i></div>
    <div class="trilha" id="env-trilha"><div class="vazio" style="padding:30px">O robô lê as pendentes da Planilha Central, monta um e-mail
      por solicitação e envia pra caixa de cada hotel. Nada é enviado ao hóspede.</div></div>
    <div class="modal-rodape"><span class="res" id="env-res"></span>
      <span><button id="env-fechar">Cancelar</button> <button class="creme" id="env-ir">Enviar agora</button></span></div></div>`;
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
    $("env-barra").style.visibility = "visible";
    $("env-titulo").textContent = "Enviando pendentes…";
    $("env-sub").textContent = r.modo === "local" ? "Rodando neste PC" : "Pedido enviado ao PC principal";
    $("env-trilha").innerHTML = "";
    acompanharEnvio(r.modo === "local" ? 700 : 2500);
  };
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
    if (!e.rodando && e.modo) {
      const ok = e.codigo === 0;
      $("env-anel").className = "anel " + (ok ? "ok" : "ruim");
      $("env-anel").textContent = ok ? "✓" : "!";
      $("env-barra").classList.add("fim");
      $("env-titulo").textContent = ok ? "Envio concluído" : "Envio terminou com aviso";
      $("env-res").textContent = e.resumo || "";
      $("env-fechar").textContent = "Fechar";
      carregar(); carregarPainel();
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

async function abrirEnvioNF(chave) {
  if (document.querySelector(".modal-fundo")) return;
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `<div class="modal compor">
    <div class="compor-topo"><span>✉ Nova mensagem · Nota Fiscal</span><span id="nf-sub" class="compor-quem">carregando…</span>
      <button class="fechar" id="nf-fechar" title="Descartar">×</button></div>
    <div class="barra-prog" id="nf-barra" style="visibility:hidden"><i></i></div>
    <div class="compor-corpo" id="nf-corpo"><div class="vazio">Carregando…</div></div>
    <div class="compor-rodape"><div class="anel" id="nf-anel" style="width:22px;height:22px;border-width:2px;visibility:hidden"></div>
      <span class="res" id="nf-res"></span></div></div>`;
  document.body.appendChild(fundo);
  $("nf-fechar").onclick = () => { clearTimeout(envNF?.timer); fundo.remove(); envNF = null; };
  const o = await api(`/api/envio_nf/opcoes?chave=${encodeURIComponent(chave)}`);
  if (o.erro) { $("nf-corpo").innerHTML = `<div class="vazio">${esc(o.erro)}</div>`; return; }
  envNF = { chave, o, anexos: [], assuntoAuto: true };
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
    <div class="soltar" id="nf-soltar"><input type="file" id="nf-arq" accept=".pdf,.xml" multiple hidden>
      <div class="soltar-txt">📎 <b>Arraste a nota fiscal aqui</b> ou <u>clique para escolher</u> · PDF ou XML · pode mais de um (nota dividida)</div>
      <div class="chips-anexo" id="nf-anexos"></div></div>
    ${o.sugestoes.length ? `<div class="sug-linha"><span class="dica">Do Dropbox:</span>${o.sugestoes.map((a, i) =>
      `<button class="sug ${a.forte ? "forte" : ""}" data-nf-sug="${i}" title="${a.forte ? "" : "Confira se é desta pessoa"}">📄 ${esc(a.nome)}${a.forte ? "" : " ⚠"}</button>`).join("")}</div>` : ""}
    <div class="editor ${o.assinatura_com_mensagem ? "curto" : ""}" id="nf-msg" contenteditable="true" spellcheck="true"
      data-dica="${o.assinatura_com_mensagem ? "Escreva aqui só se quiser acrescentar algo — a mensagem padrão já vem na assinatura abaixo." : ""}"></div>
    ${o.assinatura ? `<iframe class="assinatura" id="nf-ass" sandbox="allow-same-origin"></iframe>
      <div class="dica">Mensagem padrão e selo da caixa ${esc(o.conta_de)}, como no Outlook (prévia deste PC; sai a do PC que enviar)</div>`
      : `<div class="dica">Sem assinatura do Outlook para ${esc(o.conta_de)} neste PC.</div>`}`;
  $("nf-msg").innerText = o.corpo;
  if (o.assinatura) {
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
  if (o.sugestoes.length && o.sugestoes[0].forte) escolherSugestao(0);   // só quando o nome bate inteiro
  desenharAnexos();
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
  const ok = envNF && envNF.anexos.length && $("nf-assunto").value.trim() && $("nf-para").value.includes("@") && (envNF.o.destino || $("nf-conta"));
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
  const r = await api("/api/envio_nf", { chave: envNF.chave, para: $("nf-para").value.trim(), cc: $("nf-cc").value.trim(),
                                          assunto: $("nf-assunto").value.trim(), corpo: $("nf-msg").innerText, anexos,
                                          conta_de: conta || undefined });
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
    $("nf-res").textContent = `NF enviada ao hóspede${s.pc ? " pelo PC " + s.pc : ""}. Ela já ficou marcada no pedido.`;
    $("nf-ir").style.display = "none"; carregar(); return;
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
  const b = e.target.closest("[data-envnf],[data-nf-sug],[data-tirar]");
  if (!b) return;
  if (b.dataset.envnf) return abrirEnvioNF(b.dataset.envnf);
  if (!envNF) return;
  if (b.dataset.nfSug !== undefined) return escolherSugestao(Number(b.dataset.nfSug));
  if (b.dataset.tirar !== undefined) { e.stopPropagation(); envNF.anexos.splice(Number(b.dataset.tirar), 1); desenharAnexos(); }
});
// arquivo solto fora da área de anexo não pode abrir no lugar do Painel
["dragover", "drop"].forEach(t => window.addEventListener(t, e => { if (!e.target.closest?.("#nf-soltar")) e.preventDefault(); }));

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
