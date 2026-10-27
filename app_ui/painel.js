// Visão geral, Log, Máquinas e as janelas de envio. Usa api/$/esc/toast/st/desenhar e o estado da tela de notas
// (mesmo escopo global).
let pn = { vista: "visao", janela: 30, rz: null, tabela: {}, resumo: "ontem" };   // resumo: a Visão geral abre no dia anterior   // tabela: gráfico mostrado como tabela
const hojeIso = () => new Date().toLocaleDateString("sv-SE");

const TITULOS = { visao: "Visão geral", fila: "Notas fiscais", log: "Monitoramento / Log do robô", maquinas: "Monitoramento / Máquinas", correio: "E-mails",
                  gerencia: "Gerência (em teste)" };
function trocarVista(v) {
  // o log do robô agora é a janela grande do robô (robo.js, 22/10/2026): quem pedia a tela de Log abre ela
  if (v === "log") { if (typeof rbAbrir === "function") rbAbrir("reg"); return; }
  if (!TITULOS[v]) v = "fila";
  pn.vista = v;
  for (const id of Object.keys(TITULOS)) $("v-" + id).classList.toggle("oculta", id !== v);
  // E-mails igual ao Outlook (usuário, 15/10/2026): só ícones na esquerda e as cores da prévia aprovada
  // ... e em todas as páginas (usuário, 15/10/2026 à noite: "o mesmo layout da caixa de entrada para todas")
  const app = document.querySelector(".app");
  app.classList.add("modo-ol");   // só ícones ou com os nomes: o botão do pé da barra decide (aplicarMenu, 22/10/2026)
  app.classList.toggle("vista-correio", v === "correio");
  if (typeof desenharFaixaGlobal === "function") desenharFaixaGlobal();
  $("trilha").textContent = v === "correio" ? "E-mails / " + CAIXAS[cx.caixa] : TITULOS[v];
  document.querySelectorAll(".abas-monit").forEach(n => { n.innerHTML = [["maquinas", "", "Máquinas"], ["log", "tudo", "Registro do robô"]].map(([vv, lg, nome]) =>
      `<button type="button" data-vista="${vv}" ${lg ? `data-log="${lg}"` : ""} aria-current="${vv === v && (vv !== "log" || lg === at.aba)}">${nome}</button>`).join("") +
      `<span class="adm">Só o administrador vê</span>`; });
  document.querySelectorAll(".ln[data-vista]").forEach(b =>
    b.setAttribute("aria-current", String(b.dataset.vista === v && (v !== "log" || b.dataset.log === at.aba)
                                          && (v !== "correio" || b.dataset.caixa === cx.caixa))));
  if (v === "log") $("nav-maquinas")?.setAttribute("aria-current", "true");   // Log e Máquinas = uma entrada no menu
  $("seletor-caixa")?.classList.toggle("oculta", !["fila", "correio"].includes(v));   // "Caixa de" só onde filtra (usuário, 14/10/2026)
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
</div>
    <div class="log-filtros">${menuPcLog(d, pcsLista)}</div>
    <div class="tabela-wrap"><table class="ativ-tab"><thead><tr><th>Quando</th><th>O quê</th><th>Máquina</th><th>Hotel / pedido</th><th>Detalhe</th></tr></thead>
      <tbody>${evs.slice(0, 300).map(e => `<tr>
        <td class="q">${esc(e.quando.slice(8, 10) + "/" + e.quando.slice(5, 7) + " " + e.quando.slice(11, 16))}</td>
        <td><span class="tipo t-${esc(e.tipo)}">${esc(TIPOS_ATIV[e.tipo] || e.tipo)}</span></td>
        <td>${esc(e.agente || "")}<div class="dica">${esc(e.pc)}</div></td>
        <td>${esc(e.hotel || "")}<div class="dica">${esc(e.pedido || "")}</div></td>
        <td>${esc(e.detalhe || "")}</td></tr>`).join("") || `<tr><td colspan="5" class="vazio">Nada por aqui ainda.</td></tr>`}</tbody></table></div>
    <p class="dica">Mostra os ${d.eventos.length} registros mais recentes da aba Atividade_Robo da Planilha Central.</p>`;
}
// Escolher o PC do log: a peça única do Filtro (pecas/filtro.js), com a bolinha de ligado/desligado
function menuPcLog(d, pcsLista) {
  const info = p => d.pcs.find(x => x.pc === p) || {};
  return pecaFiltro({ id: "log-pc", rotulo: "PC", valor: at.pc || "", nomePadrao: "Todos",
    opcoes: [{ v: "", nome: "Todos os PCs", n: d.pcs.filter(x => x.online).length + " ligados" },
             ...pcsLista.map(p => ({ v: p, nome: info(p).agente || p, n: info(p).online ? p : "desligado", bolinha: info(p).online ? "on" : "off" }))] });
}
registrarFiltro("log-pc", { escolher: v => { at.pc = v; desenharLog(); }, redesenhar: () => desenharLog() });

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
      ${p.online ? `<button data-at-atualizar="${esc(p.pc)}"><svg class="ic"><use href="#i-sync"/></svg>Atualizar este PC</button>` : ""}</article>`;
  }).join("");
  el.innerHTML = `<p class="dica-prof" style="margin-bottom:12px">Os 4 PCs da equipe: quem está ligado, se o Outlook está aberto (o robô precisa dele), se o Painel está aberto e o que cada um fez por último. "Atualizar" puxa a versão nova do GitHub.</p><div class="cab-pagina"><h1>Máquinas da equipe</h1>
      <span class="dica">${d.pcs.filter(p => p.online).length} de ${d.pcs.length} PCs no ar · atualiza sozinho a cada 20 s</span></div>
    <div class="versao-ref"><span class="rot">Este PC</span><span class="dado">${esc(d.versao)}</span>
      <span class="dica">${a.atras ? `o GitHub tem ${a.atras} commit(s) novo(s)` : esc(a.motivo || "")}${a.verificado_em ? " · conferido " + haQuanto(a.verificado_em) : ""}</span>
      <button data-at-atualizar="TODOS" title="Cada PC puxa a versão nova do GitHub e reinicia"><svg class="ic"><use href="#i-sync"/></svg>Atualizar todos os PCs</button></div>
    <div class="cartao" id="cad-faltando">${CAD.html}</div>
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
  return `<section class="resumo-dia" aria-label="Resumo do dia">
    <div class="rd-cab"><h1>${pn.resumo === "ontem" ? "Resumo de ontem" : "Resumo de hoje"}</h1>
      <span class="sub">${esc(nomeDia)} · comparado com o mesmo dia da semana anterior</span>
      <div class="seg-rd" role="group" aria-label="Dia do resumo">
        <button type="button" data-rd="ontem" aria-pressed="${pn.resumo === "ontem"}">Ontem</button>
        <button type="button" data-rd="hoje" aria-pressed="${pn.resumo === "hoje"}">Hoje</button></div></div>
    <div class="rd-kpis">
      <div class="rd-kpi"><small>Pedidos recebidos</small><b>${a.recebidos.length}</b><span>${varN(a.recebidos.length, b.recebidos.length, 0) || "pelo formulário"}</span></div>
      <div class="rd-kpi"><small>NFs enviadas</small><b>${a.nfs}</b><span>${varN(a.nfs, b.nfs, 1) || "pelo Painel e Outlook"}</span></div>
      <div class="rd-kpi"><small>Enviadas no prazo</small><b>${a.noPrazo == null ? "—" : a.noPrazo + "%"}</b><span>${b.noPrazo == null || a.noPrazo == null ? "prazo de 48 h" : a.noPrazo === b.noPrazo ? `igual (era ${b.noPrazo}%)`
        : `<em class="${a.noPrazo > b.noPrazo ? "sobe" : "desce"}">${a.noPrazo > b.noPrazo ? "+" : "−"}${Math.abs(a.noPrazo - b.noPrazo)} pontos</em> (era ${b.noPrazo}%)`}</span></div>
      <div class="rd-kpi"><small>Tempo até a NF</small><b>${fmtH(a.mediana)}</b><span>${a.mediana == null || b.mediana == null || Math.round(a.mediana) === Math.round(b.mediana) ? `mediana${b.mediana != null ? ` · era ${fmtH(b.mediana)}` : ""}`
        : `<em class="${a.mediana < b.mediana ? "sobe" : "desce"}">${fmtH(Math.abs(b.mediana - a.mediana))} ${a.mediana < b.mediana ? "mais rápido" : "mais lento"}</em> (era ${fmtH(b.mediana)})`}</span></div>
      <div class="rd-kpi"><small>Ficaram para ${pn.resumo === "ontem" ? "hoje" : "amanhã"}</small><b>${abertos.length}</b><span class="${vencidos ? "desce" : ""}">${vencidos ? vencidos + " já vencido" + (vencidos > 1 ? "s" : "") : "nenhum vencido"}</span></div>
    </div>
    <div class="rd-grade">
      <div class="rd-painel"><div class="rd-tit"><b>Precisa de atenção ${pn.resumo === "ontem" ? "hoje" : "agora"}</b><small>urgentes e com dado faltando</small></div>
        ${atencao.length ? atencao.map(it => `<button type="button" class="rd-lin" data-abrir-ficha="${esc(it.s.chave)}">
          <span class="rd-nome"><b>${esc(it.s.nome)}</b><small>${esc(it.s.hotel)} · ${esc(agentesDo(it)[0] || "")}</small></span>
          <span class="tags-nf">${tagsPedido(it.s)}</span><span class="rd-pz">${it.s.prazo ? prazoHtml(it.s.prazo) : ""}</span></button>`).join("")
          : `<div class="vazio">Nada urgente nem com dado faltando.</div>`}</div>
      <div class="rd-painel"><div class="rd-tit"><b>Equipe ${pn.resumo === "ontem" ? "ontem" : "hoje"}</b><small>pedidos e notas</small></div>
        <table class="rd-tab"><thead><tr><th>Agente</th><th class="n">Recebidos</th><th class="n">NFs</th><th class="n">No prazo</th><th class="n">Pendentes</th></tr></thead>
        <tbody>${Object.entries(porAgente).filter(([ag]) => ag !== "Sem agente").sort((x, y) => x[0].localeCompare(y[0])).map(([ag, v]) =>
          `<tr><td>${esc(ag)}</td><td class="n">${v.rec || 0}</td><td class="n">${v.nfs || 0}</td><td class="n">${v.prazo[1] ? Math.round(100 * v.prazo[0] / v.prazo[1]) + "%" : "—"}</td><td class="n">${v.pend || 0}</td></tr>`).join("")
          || `<tr><td colspan="5" class="vazio">Sem movimento.</td></tr>`}</tbody></table></div>
    </div></section>`;
}
document.addEventListener("click", e => { const b = e.target.closest("[data-rd]"); if (b) { pn.resumo = b.dataset.rd; desenharVisao(); } });

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
// Ação longa (27/10/2026): toda ação que passa de LIMITE_ACAO_LONGA_MS avisa a tela com um evento. A tela de carregamento
// (pecas/carregando.js: o K do João sendo desenhado) escuta "painel:acao-longa" e "painel:acao-longa-fim".
// detail: { id, titulo, inicio, progresso(): 0..1, eta(): segundos, itens(): [{pc, agente, estado, res, aviso}] } e, no fim,
// { id, ok, texto, duracao }. O api() liga isto sozinho em todo POST. `estado.limiteMs` troca os 3 s (0 = na hora).
const LIMITE_ACAO_LONGA_MS = 3000;
let acaoLongaSeq = 0;
function acaoLonga(titulo, estado = {}) {
  const acao = { id: "acao-" + (++acaoLongaSeq), titulo, inicio: Date.now(), progresso: () => null, eta: () => null, itens: () => [], ...estado };
  let avisou = false;
  const timer = setTimeout(() => { avisou = true; window.dispatchEvent(new CustomEvent("painel:acao-longa", { detail: acao })); }, acao.limiteMs ?? LIMITE_ACAO_LONGA_MS);
  return { acao, fim(ok = true, texto = "") {
    clearTimeout(timer);
    if (avisou) window.dispatchEvent(new CustomEvent("painel:acao-longa-fim", { detail: { id: acao.id, ok, texto, duracao: Date.now() - acao.inicio } }));
  } };
}
const tamanho = b => b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB";

// Escrever (responder, responder com NF, encaminhar, enviar NF). Com `alvo`, igual ao Outlook (usuário, 09/10/2026): abre
// DENTRO do painel de leitura, com o e-mail original citado embaixo — sem janela por cima. Sem alvo: janela (como antes).
async function abrirEnvioNF(chave, resp = null, alvo = null) {
  if (document.querySelector(".modal-fundo")) return;
  if (envNF && envNF.alvo) { $("nf-msg")?.focus(); toast("Termine ou descarte a mensagem que está escrevendo", true); return; }
  const enc = !!resp?.encaminhar, novo = !!resp?.novo;
  const titulo = novo ? "✉ Novo e-mail" : enc ? "↗ Encaminhar" : resp ? (resp.comNF ? "↩ Responder com a NF" : "↩ Responder") : "✉ Nova mensagem · Nota Fiscal";
  const miolo = `
    <div class="compor-topo"><span>${titulo}</span>${enc ? "" : pecaLigacao({ id: "nf-lig-etq", oculta: true })}<span id="nf-sub" class="compor-quem">carregando…</span>
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
  const o = await api(novo ? "/api/email/novo" : resp ? `/api/email/opcoes?id=${encodeURIComponent(resp.id)}` : `/api/envio_nf/opcoes?chave=${encodeURIComponent(chave)}`);
  if (!envNF) return;
  if (o.erro) { $("nf-corpo").innerHTML = `<div class="vazio">${esc(o.erro)}</div>`; return; }
  if (enc) {   // encaminhar: pra quem a pessoa escolher, com o original anexado embaixo; sem anexo de NF nem selo
    const orig = o.email?.assunto || "";
    o.assunto = /^(enc|fw|fwd):/i.test(orig) ? orig : "ENC: " + orig;
    o.para = []; o.sugestoes = []; o.corpo = "";   // assinatura padrão continua (13/10/2026: em todo tipo de envio)
  }
  envNF = { chave, resp, alvo, fechar, o, anexos: [], assuntoAuto: !resp };
  $("nf-sub").textContent = novo ? "sai da caixa do hotel, pelo Outlook do PC dono" : `${o.nome} · ${o.hotel}`;
  const de = novo
    ? `<div class="de-novo"><div class="combo-de">
          <input id="nf-de-txt" autocomplete="off" spellcheck="false" placeholder="Digite o nome do hotel…" aria-label="Caixa do hotel de onde o e-mail sai (digite para filtrar)">
          <input type="hidden" id="nf-de" value="${esc(o.conta_de)}">
          <div class="combo-lista oculta" id="nf-de-lista" role="listbox"></div></div>
        <span class="dica" id="nf-de-pc">${o.destino === o.este_pc ? "· por este PC" : o.destino ? "· pelo PC " + esc(o.destino) : ""}</span></div>`
    : o.destino
    ? `<div class="campo-txt"><b>${esc(o.conta_de)}</b> <span class="dica">${o.destino === o.este_pc ? "· por este PC" : "· pelo PC " + esc(o.destino)}</span></div>`
    : `<div class="campo-txt alerta">⚠ ${esc(o.motivo)} Enviar por:
         <select id="nf-conta">${o.contas_locais.map(c => `<option>${esc(c)}</option>`).join("")}</select></div>`;
  $("nf-corpo").innerHTML = `
    <div class="compor-cab">
      <div class="env-col"><button class="btn-enviar" id="nf-ir" disabled><span class="ic">➤</span>Enviar</button>
        ${enc ? "" : `<button type="button" class="btn-lig" id="nf-lig" aria-pressed="false" title="O hóspede pediu por telefone? Marque aqui (Alt+L). Não vai no e-mail, só conta no Painel.">
          <svg class="tel" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ETQ_IC.tel}</svg><span class="ok" aria-hidden="true">✓</span>Ligação</button>`}</div>
      <div class="campos-cab">
        <div class="linha-cab"><span class="rot">De</span>${de}</div>
        <div class="linha-cab"><span class="rot">Para</span><input id="nf-para" list="nf-paras" value="${esc(o.para[0] || "")}">
          <datalist id="nf-paras">${o.para.map(p => `<option value="${esc(p)}">`).join("")}</datalist></div>
        <div class="linha-cab"><span class="rot">Cc</span><input id="nf-cc" placeholder="opcional"></div>
        <div class="linha-cab"><span class="rot">Assunto</span><input id="nf-assunto" placeholder="NF 1212 - NOME DO HÓSPEDE"></div>
      </div>
    </div>
    <div class="soltar ${enc ? "oculta" : ""}" id="nf-soltar"><input type="file" id="nf-arq" accept=".pdf,.xml" multiple hidden>
      <div class="soltar-txt">${novo ? "📎 Anexar arquivo <b>(opcional)</b> · arraste aqui ou <u>clique para escolher</u>"
        : `📎 <b>Arraste a nota fiscal aqui</b> ou <u>clique para escolher</u> · PDF ou XML · pode mais de um (nota dividida)${resp ? " · opcional numa resposta" : ""}`}</div>
      <div class="chips-anexo" id="nf-anexos"></div></div>
    ${o.sugestoes.length ? `<div class="sug-linha"><span class="dica">Do Dropbox:</span>${o.sugestoes.map((a, i) =>
      `<button class="sug forte" data-nf-sug="${i}" title="${esc(a.prova || "")}">📄 ${esc(a.nome)}</button>`).join("")}</div>` : ""}
    <div class="quadro-e2 erro oculta" id="nf-conferir" role="alert"></div>
    ${enc ? "" : linhaModelos()}
    <div class="editor ${o.assinatura_com_mensagem ? "curto" : ""}" id="nf-msg" contenteditable="true" spellcheck="true"
      data-dica="${o.assinatura_com_mensagem ? "Escreva aqui só se quiser acrescentar algo — a mensagem padrão já vem na assinatura abaixo." : ""}"></div>
    ${o.selos.length ? `<div class="selo-previa"><img id="nf-selo-img" alt="Selo"></div>
      <div class="selos"><span class="dica">Assinatura:</span>${o.selos.map(s =>
        `<button class="selo-op" data-nf-selo="${esc(s.id)}">${esc(s.nome)}</button>`).join("")}</div>`
    : o.assinatura ? `<iframe class="assinatura" id="nf-ass" sandbox="allow-same-origin"></iframe>
      <div class="dica">Mensagem padrão e selo da caixa ${esc(o.conta_de)}, como no Outlook (prévia deste PC; sai a do PC que enviar)</div>`
      : enc ? "" : `<div class="dica">Sem assinatura do Outlook para ${esc(o.conta_de)} neste PC.</div>`}
    ${resp?.citacao ? `<div class="cx-citacao" aria-label="Mensagem original">${resp.citacao}</div>` : ""}`;
  if (enc) $("nf-msg").dataset.dica = "Mensagem (dá pra editar) — o e-mail original vai junto, embaixo.";
  // responder e encaminhar já vêm com a mensagem padrão da NF (usuário, 13/10/2026: "qualquer coisa eu altero no meio do caminho")
  // todo envio abre com a mensagem padrão (usuário, 13/10/2026); a solicitação de dados fica no botão das Respostas prontas
  $("nf-msg").innerText = resp ? (o.corpo_nf || o.corpo) : o.corpo;
  if (resp) { $("nf-assunto").value = novo ? `Nota Fiscal - ${o.hotel}` : o.assunto; $("nf-msg").addEventListener("input", validarEnvioNF); }
  // resposta a um formulário (20/10/2026): o Para é quem preencheu ("Enviado por"), nunca o Emissor Automático;
  // sem o e-mail no texto, fica vazio pra quem envia preencher
  const emForm = resp && !novo && !enc && typeof emailDoFormulario === "function" ? (cx.dados?.emails || []).find(x => x.id === resp.id) : null;
  if (emForm && (emForm.classes || []).includes("formulario")) $("nf-para").value = emailDoFormulario(emForm);
  if (novo) comboDe(o);
  if (novo && resp.para) $("nf-para").value = resp.para;
  if (novo && resp.solicitar) {
    $("nf-msg").innerText = resp.faltas?.length ? modeloPedirFalta(resp.faltas) : modeloSolicitacaoDados();
    $("nf-assunto").value = `Solicitação de dados - Nota Fiscal ${o.hotel}`;
  }
  if (novo) envNF.escolherDe = async conta => {   // trocou a caixa: de qual PC sai e o hotel do assunto
    $("nf-de").value = conta;
    const n = await api("/api/email/novo?conta=" + encodeURIComponent(conta));
    if (!envNF || n.erro) return;
    const prefixo = $("nf-assunto").value.startsWith("Solicitação de dados") ? "Solicitação de dados - Nota Fiscal " : "Nota Fiscal - ";
    const assuntoPadrao = prefixo + envNF.o.hotel;   // assunto ainda o automático: acompanha o hotel novo
    Object.assign(envNF.o, { conta_de: n.conta_de, destino: n.destino, motivo: n.motivo, hotel: n.hotel });
    $("nf-de-pc").textContent = n.destino === n.este_pc ? "· por este PC" : n.destino ? "· pelo PC " + n.destino : "";
    if ($("nf-assunto").value === assuntoPadrao) $("nf-assunto").value = prefixo + n.hotel;
    validarEnvioNF();
  };
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
  $("nf-lig")?.addEventListener("click", () => alternarLigacao());
  if (o.sugestoes.length === 1) escolherSugestao(0);   // nota confirmada pelo conteúdo: já vem anexada
  desenharAnexos();
  validarEnvioNF();
  if (novo && resp.conta && resp.conta !== o.conta_de && o.contas.some(c => c.conta === resp.conta)) {   // a caixa do hotel do pedido
    envNF.escolherDe(resp.conta).then(() => { if (resp.solicitar) $("nf-assunto").value = `Solicitação de dados - Nota Fiscal ${envNF.o.hotel}`;
      const c = envNF.o.contas.find(x => x.conta === resp.conta); if (c) $("nf-de-txt").value = `${c.hotel} · ${c.conta} · ${c.pc === envNF.o.este_pc ? "este PC" : "PC de " + c.agente}`; });
  }
  setTimeout(() => (enc || (novo && !resp.para) ? $("nf-para") : $("nf-msg"))?.focus(), 50);
}

// Botão "Ligação" (usuário, 22/10/2026, opção B): começa desligado em todo e-mail; ligado, a etiqueta aparece no topo
function alternarLigacao(ligar) {
  if (!envNF || !$("nf-lig")) return;
  envNF.ligacao = ligar ?? !envNF.ligacao;
  $("nf-lig").setAttribute("aria-pressed", String(envNF.ligacao));
  $("nf-lig-etq")?.classList.toggle("oculta", !envNF.ligacao);
}
document.addEventListener("keydown", ev => {
  if (ev.altKey && !ev.ctrlKey && !ev.metaKey && (ev.key === "l" || ev.key === "L") && $("nf-lig")) { ev.preventDefault(); alternarLigacao(); }
});

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
  trocarParaMensagemDaNF();
  desenharAnexos();
}

// Novo e-mail: anexou a NF e o texto ainda é a solicitação de dados intacta -> vira a mensagem padrão da NF (13/10/2026)
function trocarParaMensagemDaNF() {
  if (!envNF?.resp?.novo || !envNF.anexos.length || !envNF.o?.corpo_nf) return;
  const atual = $("nf-msg").innerText.trim().replace(/^(Bom dia|Boa tarde|Boa noite)!/, "");
  if (atual !== modeloSolicitacaoDados().trim().replace(/^(Bom dia|Boa tarde|Boa noite)!/, "")) return;   // já mexeu: não troca
  $("nf-msg").innerText = envNF.o.corpo_nf;
  toast("NF anexada: a mensagem virou a de envio da NF (dá pra editar)");
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

// Respostas prontas (usuário, 11/10/2026): um clique preenche a mensagem com o nome, o hotel e o nº da NF
// "De" do Novo e-mail com busca (usuário, 13/10/2026): digita parte do hotel, da caixa ou do agente; sem acento
function comboDe(o) {
  const rot = c => `${c.hotel} · ${c.conta} · ${c.pc === o.este_pc ? "este PC" : "PC de " + c.agente}${c.online ? "" : " (desligado: sai quando ligar)"}`;
  const semAcento = s => String(s).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const txt = $("nf-de-txt"), lista = $("nf-de-lista");
  const atual = () => o.contas.find(c => c.conta === $("nf-de").value) || o.contas[0];
  const fechar = () => lista.classList.add("oculta");
  const mostrar = () => {
    const termos = semAcento(txt.value).split(/\s+/).filter(Boolean);
    const achados = o.contas.filter(c => termos.every(q => semAcento(rot(c)).includes(q)));
    lista.innerHTML = achados.length
      ? achados.map((c, i) => `<button type="button" role="option" class="${i === 0 ? "ativo" : ""}" data-de="${esc(c.conta)}">${esc(rot(c))}</button>`).join("")
      : `<div class="combo-vazio">Nenhuma caixa com “${esc(txt.value)}”</div>`;
    lista.classList.remove("oculta");
  };
  const escolher = conta => { fechar(); txt.value = rot(o.contas.find(c => c.conta === conta) || atual()); envNF?.escolherDe?.(conta); };
  txt.value = rot(atual());
  txt.addEventListener("focus", () => { txt.select(); txt.value = ""; mostrar(); });
  txt.addEventListener("input", mostrar);
  txt.addEventListener("keydown", e => {
    const itens = [...lista.querySelectorAll("[data-de]")], i = itens.findIndex(b => b.classList.contains("ativo"));
    if (e.key === "ArrowDown" || e.key === "ArrowUp") {
      e.preventDefault();
      const j = Math.max(0, Math.min(itens.length - 1, i + (e.key === "ArrowDown" ? 1 : -1)));
      itens.forEach((b, k) => b.classList.toggle("ativo", k === j)); itens[j]?.scrollIntoView({ block: "nearest" });
    } else if (e.key === "Enter") {
      e.preventDefault(); if (itens[Math.max(0, i)]) escolher(itens[Math.max(0, i)].dataset.de);
    } else if (e.key === "Escape") {
      e.preventDefault(); e.stopPropagation(); fechar(); txt.value = rot(atual()); txt.blur();
    }
  });
  lista.addEventListener("mousedown", e => { const b = e.target.closest("[data-de]"); if (b) { e.preventDefault(); escolher(b.dataset.de); } });
  txt.addEventListener("blur", () => setTimeout(() => { fechar(); txt.value = rot(atual()); }, 120));
}

// Solicitação de dados (texto do João, 13/10/2026). A saudação acompanha a hora: Bom dia / Boa tarde / Boa noite.
function modeloSolicitacaoDados() {
  const h = new Date().getHours();
  const saudacao = h < 12 ? "Bom dia!" : h < 18 ? "Boa tarde!" : "Boa noite!";
  return `${saudacao}

Prezado(a),

Preciso de algumas informações, por gentileza:

CPF do hóspede:

Nome completo:

A nota deve incluir apenas diárias ou também consumos extras e estacionamento (se houver)?

Emitir em CPF ou CNPJ?

Alguma observação ou informação extra para constar na nota?

E-mail para envio da nota:

Qual a data do check-in?

Qual o CEP deve constar na NF?`;
}
// "Pedir o que falta" (usuário, 14/10/2026): a mensagem pede só o que o robô viu que falta; revisar e enviar
function modeloPedirFalta(faltas) {
  const h = new Date().getHours();
  const saudacao = h < 12 ? "Bom dia!" : h < 18 ? "Boa tarde!" : "Boa noite!";
  const pergunta = { "nome": "Nome completo (ou razão social) que deve constar na nota:",
    "CPF/CNPJ": "CPF ou CNPJ que deve constar na nota:",
    "o que quer na nota": "A nota deve incluir apenas as diárias ou também consumos e estacionamento (se houver)?" };
  return `${saudacao}

Prezado(a),

Recebemos o seu pedido de nota fiscal. Para emitir, só precisamos de:

${faltas.map(f => pergunta[f] || f).join("\n\n")}

Assim que responder, emitimos e enviamos a nota para este e-mail.`;
}
const MODELOS_RESPOSTA = [
  ["Solicitação de dados", () => modeloSolicitacaoDados()],
  ["Segue a NF", d => `Olá, ${d.nome}! Segue em anexo a nota fiscal${d.nf ? " " + d.nf : ""} da sua hospedagem no ${d.hotel}. Qualquer dúvida, estamos à disposição.`],
  ["NF corrigida", d => `Olá, ${d.nome}! Segue em anexo a nota fiscal${d.nf ? " " + d.nf : ""} corrigida, conforme solicitado. Pedimos desculpas pelo transtorno.`],
  ["Pedir CPF/CNPJ", d => `Olá, ${d.nome}! Para emitir a nota fiscal da sua hospedagem no ${d.hotel}, precisamos do CPF ou CNPJ correto do tomador (e a razão social, se for empresa). Pode nos enviar?`],
  ["Pedir dados da reserva", d => `Olá, ${d.nome}! Para localizar sua hospedagem no ${d.hotel}, pode nos informar as datas de check-in e check-out e o nome do titular da reserva?`],
  ["NF sai até amanhã", d => `Olá, ${d.nome}! Recebemos seu pedido. A nota fiscal da sua hospedagem no ${d.hotel} será emitida e enviada até amanhã.`],
];
function dadosDoModelo() {
  const o = envNF?.o || {};
  const nome = String(o.nome || "").trim().split(/\s+/)[0] || "";
  const nf = (envNF?.anexos || []).map(a => (String(a.nome).match(/NF\s*(\d+)/i) || [])[1]).filter(Boolean);
  return { nome: nome ? nome.charAt(0).toUpperCase() + nome.slice(1).toLowerCase() : "", hotel: o.hotel || "o hotel",
           nf: nf.length ? (nf.length > 1 ? "s " : "") + nf.join(", ") : "" };
}
function linhaModelos() {
  return `<div class="sug-linha modelos"><span class="dica">Respostas prontas:</span>${MODELOS_RESPOSTA.map(([rot], i) =>
    `<button class="sug" data-modelo="${i}" title="Preenche a mensagem (dá pra editar depois)">${esc(rot)}</button>`).join("")}</div>`;
}
document.addEventListener("click", e => {
  const b = e.target.closest("[data-modelo]");
  if (!b || !envNF) return;
  const d = dadosDoModelo();
  $("nf-msg").innerText = MODELOS_RESPOSTA[Number(b.dataset.modelo)][1](d).replace("Olá, !", "Olá!");
  if (envNF.resp?.novo && Number(b.dataset.modelo) === 0 && $("nf-assunto").value === `Nota Fiscal - ${envNF.o.hotel}`)
    $("nf-assunto").value = `Solicitação de dados - Nota Fiscal ${envNF.o.hotel}`;   // solicitação de dados: assunto combina
  $("nf-msg").dispatchEvent(new Event("input")); $("nf-msg").focus();
  if (typeof validarEnvioNF === "function") validarEnvioNF();
});

async function enviarNF(contaForcada, jaConferido = false) {
  $("nf-ir").disabled = true;
  const anexos = await Promise.all(envNF.anexos.map(async a => a.tipo === "arquivo"
    ? { tipo: "arquivo", nome: a.nome, b64: await lerBase64(a.file) } : { tipo: "dropbox", rel: a.rel, nome: a.nome }));
  // confere a NF anexada com o pedido antes de mandar (CPF/CNPJ, valor, nome) — avisa e deixa a pessoa decidir
  if (!jaConferido && !envNF.resp?.encaminhar && !envNF.resp?.novo && anexos.length) {
    $("nf-res").textContent = "Conferindo a NF com o pedido…";
    const c = await api("/api/envio_nf/conferir", { chave: envNF.chave || undefined, id: envNF.resp ? envNF.resp.id : undefined, anexos });
    $("nf-res").textContent = c.conferidas ? `NF conferida com o pedido${c.avisos?.length ? "" : " ✓"}` : "";
    if (c.avisos?.length) {
      $("nf-ir").disabled = false;
      const box = $("nf-conferir");
      // prévia v2: só aparece quando tem problema; o que está certo não ocupa espaço
      box.innerHTML = `<b>${c.avisos.length} ponto${c.avisos.length > 1 ? "s" : ""} para conferir antes de enviar</b>${c.avisos.map(a => `<div>${esc(a)}</div>`).join("")}
        <div class="acoes-q"><button class="dest" id="nf-enviar-mesmo">Conferi, pode enviar</button><button id="nf-corrigir">Voltar e corrigir</button></div>`;
      box.classList.remove("oculta"); box.scrollIntoView({ block: "nearest" });
      $("nf-enviar-mesmo").onclick = () => { box.classList.add("oculta"); enviarNF(contaForcada, true); };
      $("nf-corrigir").onclick = () => box.classList.add("oculta");
      return;
    }
  }
  const conta = contaForcada || ($("nf-conta") ? $("nf-conta").value : "");
  const r = envNF.resp?.novo
    ? await api("/api/email/novo", { conta_de: $("nf-de").value, para: $("nf-para").value.trim(), cc: $("nf-cc").value.trim(),
        assunto: $("nf-assunto").value.trim(), corpo: $("nf-msg").innerText, anexos, selo: envNF.selo || undefined,
        ligacao: envNF.ligacao || undefined })
    : envNF.resp?.encaminhar
    ? await api("/api/correio/encaminhar", { id: envNF.resp.id, para: $("nf-para").value.trim(), corpo: $("nf-msg").innerText,
        selo: envNF.selo || undefined })
    : await api(envNF.resp ? "/api/email/responder" : "/api/envio_nf", {
    chave: envNF.chave || undefined, id: envNF.resp ? envNF.resp.id : undefined, para: $("nf-para").value.trim(),
    cc: $("nf-cc").value.trim(), assunto: $("nf-assunto").value.trim(), corpo: $("nf-msg").innerText, anexos,
    conta_de: conta || undefined, selo: envNF.selo || undefined, ligacao: envNF.ligacao || undefined });
  if (!r.ok) { $("nf-ir").disabled = false; return mostrarFalhaNF(r.motivo || r.erro, r.contas_locais); }
  if (r.aviso_ligacao) toast(r.aviso_ligacao, true);
  // Envio sem espera (Prévia 5, 20/10/2026: "estamos em ligação com o hóspede"): a janela fecha na hora e o aviso no
  // canto acompanha (entregue · saindo · conferido). Falhou: o aviso diz o porquê e reabre a mensagem com o texto.
  const ctx = { chave: envNF.chave, resp: envNF.resp, alvo: envNF.alvo, pc: r.destino === envNF.o.este_pc ? "" : r.destino,
    rascunho: { para: $("nf-para")?.value || "", cc: $("nf-cc")?.value || "", assunto: $("nf-assunto")?.value || "", msg: $("nf-msg")?.innerHTML || "",
      ligacao: !!envNF.ligacao } };
  envNF.fechar();
  seguirEnvio(r.id, ctx);
}

const andamento = {};
function seguirEnvio(id, ctx) {
  if (!$("envios-andamento")) {
    const box = document.createElement("div");
    box.id = "envios-andamento"; box.setAttribute("aria-live", "polite");
    document.body.appendChild(box);
  }
  andamento[id] = { ctx, estado: "entregue" };
  desenharEnvio(id);
  verEnvio(id);
}
async function verEnvio(id) {
  const a = andamento[id];
  if (!a) return;
  const s = await api(`/api/envio_nf/status?id=${id}`).catch(() => ({ estado: "aguardando" }));
  if (!andamento[id]) return;
  a.s = s;
  if (s.estado === "enviado") {
    a.estado = "enviado"; a.fim = new Date();
    const resp = a.ctx.resp;
    if (resp && !resp.encaminhar && !resp.novo) correioRespondido(resp.id);
    carregar(); desenharEnvio(id);
    a.timer = setTimeout(() => fecharEnvio(id), 3500);   // a pílula some sozinha
    return;
  }
  if (s.estado === "falhou" || s.estado === "sem_resposta") { a.estado = "falhou"; return desenharEnvio(id); }
  a.estado = s.estado === "enviando" ? "saindo" : "entregue";
  desenharEnvio(id);
  a.timer = setTimeout(() => verEnvio(id), 2000);
}
function desenharEnvio(id) {
  // Aviso em pílula (22/10/2026, desenho "Aviso de envio", Opção B): uma linha só. Erro não some: vira pílula vermelha
  // e, clicando em "Ver", abre o cartão completo (motivo + Escrever de novo).
  const a = andamento[id], box = $("envios-andamento");
  if (!a || !box) return;
  const falhou = a.estado === "falhou", cartao = falhou && a.aberto;
  let card = box.querySelector(`[data-env="${id}"]`);
  if (card && card.dataset.forma !== (cartao ? "cartao" : "pilula")) { card.remove(); card = null; }
  if (!card) {
    card = document.createElement("div"); card.dataset.env = id; card.dataset.forma = cartao ? "cartao" : "pilula";
    card.setAttribute("role", "status"); box.appendChild(card);
  }
  const { resp, pc } = a.ctx;
  const oque = resp?.novo ? "e-mail" : resp?.encaminhar ? "mensagem" : resp ? (resp.comNF ? "resposta com a NF" : "resposta") : "NF";
  const hora = a.fim ? a.fim.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "";
  const onde = pc ? `<small>· PC de ${esc(nomeAgente(pc))}</small>` : "";
  let html;
  if (cartao) {
    card.className = "env-card";
    html = `<div class="tt"><i class="ruim">!</i>Não deu para enviar a ${esc(oque)}</div><div class="det">${esc(a.s?.detalhe || "o PC dono não respondeu")}</div>
       <div class="bt"><button type="button" data-env-fechar="${id}">Fechar</button><button type="button" data-env-reabrir="${id}">Escrever de novo</button></div>`;
  } else if (falhou) {
    card.className = "env-pilula erro"; card.removeAttribute("title");
    html = `<button type="button" data-env-ver="${id}" aria-label="Não enviou a ${esc(oque)}. Ver o motivo"><i class="env-ex">!</i>Não enviou <u>Ver</u></button>`;
  } else if (a.estado === "enviado") {
    card.className = "env-pilula sai"; card.title = "Conferido em Itens Enviados";
    html = `<i class="env-ok">✓</i>Enviado ${hora}`;
  } else {
    card.className = "env-pilula";
    card.title = (pc ? `Entregue ao PC de ${nomeAgente(pc)}` : "Entregue ao Outlook deste PC") + " → saindo pela caixa do hotel → conferido em Itens Enviados";
    html = `<i class="env-gira"></i>Enviando ${esc(oque)} ${onde}`;
  }
  if (card._html !== html) { card.innerHTML = html; card._html = html; }   // não refaz igual: o círculo não reinicia a cada 2 s
}
function fecharEnvio(id) {
  clearTimeout(andamento[id]?.timer);
  delete andamento[id];
  document.querySelector(`[data-env="${id}"]`)?.remove();
}
document.addEventListener("click", async ev => {
  const ver = ev.target.closest("[data-env-ver]");
  if (ver && andamento[ver.dataset.envVer]) { andamento[ver.dataset.envVer].aberto = true; return desenharEnvio(ver.dataset.envVer); }
  const f = ev.target.closest("[data-env-fechar]");
  if (f) return fecharEnvio(f.dataset.envFechar);
  const b = ev.target.closest("[data-env-reabrir]");
  if (!b || !andamento[b.dataset.envReabrir]) return;
  const { chave, resp, alvo, rascunho } = andamento[b.dataset.envReabrir].ctx;
  fecharEnvio(b.dataset.envReabrir);
  if (alvo?.id === "cx-leitura" && resp?.id && cx.sel !== resp.id) { cx.sel = resp.id; desenharCorreio(); }
  await abrirEnvioNF(chave, resp, alvo && document.body.contains(alvo) ? alvo : null);
  const por = (i, v) => { const x = $(i); if (x && v) x.value = v; };
  por("nf-para", rascunho.para); por("nf-cc", rascunho.cc); por("nf-assunto", rascunho.assunto);
  if ($("nf-msg") && rascunho.msg) $("nf-msg").innerHTML = rascunho.msg;
  if (rascunho.ligacao) alternarLigacao(true);   // o envio que falhou teve a marca retirada: o reenvio marca de novo
  toast("Mensagem reaberta com o texto. Se tinha anexo, anexe de novo.");
});

async function acompanharNF(id) {
  if (!envNF) return;
  const s = await api(`/api/envio_nf/status?id=${id}`).catch(() => ({ estado: "aguardando" }));
  if (!envNF) return;
  if (s.estado === "enviado") {
    $("nf-anel").className = "anel ok"; $("nf-anel").textContent = "✓"; $("nf-barra").classList.add("fim");
    const enc = envNF.resp?.encaminhar, novo = envNF.resp?.novo;
    $("nf-res").textContent = novo ? `E-mail enviado${s.pc ? " pelo Outlook do PC " + s.pc : ""}. Ele aparece em Itens enviados.`
      : enc ? `Encaminhado${s.pc ? " pelo Outlook do PC " + s.pc : ""}.`
      : envNF.resp ? `Resposta enviada${s.pc ? " pelo Outlook do PC " + s.pc : ""}. O e-mail fica cinza e sai da caixa em seguida.`
      : `NF enviada ao hóspede${s.pc ? " pelo PC " + s.pc : ""}. Ela já ficou marcada no pedido.`;
    $("nf-ir").style.display = "none";
    if (envNF.resp && !enc && !novo) correioRespondido(envNF.resp.id);
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
  if ($("nf-alt")) $("nf-alt").onclick = () => enviarNF($("nf-conta-alt").value, true);   // já conferida na 1ª tentativa
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

// Arrastar o PDF da NF em cima de uma solicitação da lista (usuário, 11/10/2026): seleciona, abre o envio ali mesmo e
// já anexa a nota (o envio confere a NF com o pedido antes de sair, como sempre)
document.addEventListener("dragover", e => {
  const l = e.target.closest?.("#lista .nf-l");
  if (!l || !Array.from(e.dataTransfer?.types || []).includes("Files")) return;
  e.preventDefault();
  document.querySelectorAll("#lista .soltar-aqui").forEach(x => x !== l && x.classList.remove("soltar-aqui"));
  l.classList.add("soltar-aqui");
});
document.addEventListener("dragleave", e => { const l = e.target.closest?.("#lista .nf-l"); if (l && !l.contains(e.relatedTarget)) l.classList.remove("soltar-aqui"); });
document.addEventListener("drop", async e => {
  const l = e.target.closest?.("#lista .nf-l");
  if (!l || !e.dataTransfer?.files?.length) return;
  e.preventDefault();
  l.classList.remove("soltar-aqui");
  const arquivos = Array.from(e.dataTransfer.files);   // o navegador esvazia a lista depois do evento
  if (envNF && envNF.alvo) { toast("Termine ou descarte a mensagem que está escrevendo", true); return; }
  sel = l.dataset.k; emailSel = null; desenhar();
  await abrirEnvioNF(sel, null, $("detalhe"));
  if (envNF && $("nf-soltar")) adicionarArquivos(arquivos);
});

// ---------- Relatório do dia e da semana (Gerência) — dados do Mail Analytics, só leitura (usuário, 11/10/2026) ----------
const REL = { tipo: "mes", desl: 0, html: "", chave: "", em: 0, texto: "" };   // repaginação v2: mês × mês anterior; dia -1 = último dia com dados
const COLS_REL = [["pedidos", "Pedidos (formulário)"], ["recebidos", "E-mails recebidos"], ["enviados", "E-mails enviados"],
                  ["nfs", "NFs emitidas"], ["subst_canc", "Subst./canc."], ["ligacoes", "Ligações"]];
async function carregarRelatorio(forcar = false) {
  const chave = REL.tipo + ":" + REL.desl;
  if (!forcar && REL.chave === chave && Date.now() - REL.em < 5 * 60 * 1000) return;
  REL.chave = chave; REL.em = Date.now();
  const r = await api(`/api/relatorio_semana?tipo=${REL.tipo}&deslocamento=${REL.desl}`);
  if (!r.erro && REL.desl < 0) { REL.desl = r.deslocamento; REL.chave = REL.tipo + ":" + REL.desl; }
  REL.html = r.erro ? `<div class="vazio">${esc(r.erro)}</div>` : htmlRelatorio(r);
  REL.texto = r.texto || "";
  if ($("ger-relatorio")) $("ger-relatorio").innerHTML = REL.html;
}
// Gerência v2 (usuário, 14/10/2026): relatório que o gerente lê em 1 minuto — volume e variação, canceladas/refeitas,
// onde as solicitações se perdem e "O que melhorar". Mail Analytics (só leitura) + o que o Painel/Outlook sabem.
function numerosPainel(ini, fim) {
  const agenteDe = s => AG[String(s.hotel || "").split(" / ")[0]] || s.dono || "Sem agente";
  const chegada = s => new Date(`${s.data}T${horaDoCarimbo(s.carimbo) || "12:00"}`);
  const isoEnvio = q => { const m = String(q || "").match(/(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})/); return m ? `${m[3]}-${m[2]}-${m[1]}T${m[4]}:${m[5]}` : ""; };
  const pedidos = st.fila.filter(s => s.data >= ini && s.data <= fim);
  const envios = [];
  st.fila.forEach(s => (s.envios || []).forEach(v => { const iso = isoEnvio(v.quando); if (iso.slice(0, 10) >= ini && iso.slice(0, 10) <= fim)
    envios.push({ s, h: (new Date(iso) - chegada(s)) / 36e5, ag: agenteDe(s) }); }));
  const validos = envios.filter(e => e.h >= 0);
  const pct = l => l.length ? Math.round(100 * l.filter(e => e.h <= 48).length / l.length) : null;
  const porAg = {};
  validos.forEach(e => (porAg[e.ag] ||= []).push(e));
  const abertos = pedidos.filter(s => s.situacao !== "concluida");
  const vencidos = abertos.filter(s => (prazoInfo(s.prazo)?.resta ?? 1) <= 0);
  const comNf = pedidos.filter(s => s.situacao === "concluida" || s.nfs?.length).length;
  const enviados = pedidos.filter(s => s.envios?.length).length;
  const fds = s => { const d = chegada(s); return d.getDay() === 0 || d.getDay() === 6 || (d.getDay() === 5 && d.getHours() >= 18); };
  return { pedidos, noPrazo: pct(validos), porAgPrazo: Object.fromEntries(Object.entries(porAg).map(([a, l]) => [a, pct(l)])),
    perdidas: vencidos.length, vencidos, comNf, enviados,
    faltaDado: abertos.filter(s => faltaDados(s).length).length, esperando: vencidos.filter(s => s.situacao === "tratativa").length,
    fimDeSemana: vencidos.filter(fds).length, agenteDe };
}
function htmlRelatorio(r) {
  const n = v => (v ?? 0).toLocaleString("pt-BR");
  const dt = iso => iso.slice(8, 10) + "/" + iso.slice(5, 7);
  const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  const nomeMes = MESES[Number(r.ini.slice(5, 7)) - 1];
  const titulo = r.tipo === "mes" ? `Relatório de ${nomeMes}` : r.tipo === "dia" ? `Relatório do dia ${dt(r.ini)}` : `Relatório da semana`;
  const contra = r.tipo === "mes" ? "mês anterior" : r.tipo === "dia" ? "dia anterior" : "semana anterior";
  const pa = numerosPainel(r.ini, r.ate), pb = numerosPainel(r.ini_anterior || r.ini, r.fim_anterior || r.ini);
  const BOM_SUBIR = { nfs: true, enviados: true, noprazo: true, subst_canc: false, perdidas: false };
  const varTxt = (x, y, k, pts) => { if (y == null || (!y && !pts)) return `<span class="var-n">sem comparação</span>`;
    const d = pts ? x - y : Math.round(100 * (x - y) / y); if (!d) return `<span class="var-n">igual · era ${y}${pts ? "%" : ""}</span>`;
    const cls = BOM_SUBIR[k] === undefined ? "neutro" : (d > 0) === BOM_SUBIR[k] ? "bom" : "ruim";
    return `<span class="var-n"><em class="${cls}">${d > 0 ? "▲" : "▼"} ${Math.abs(d)}${pts ? " pts" : "%"}</em> · era ${y}${pts ? "%" : ""}</span>`; };
  const kpi = (rot, v, sub) => `<div class="g-kpi"><small>${rot}</small><b>${v}</b>${sub}</div>`;
  const T = r.total, A = r.total_anterior;
  const hot = (r.hoteis_todos || []);
  const canc = hot.filter(h => h.subst_canc).sort((x, y) => y.subst_canc - x.subst_canc).slice(0, 6);
  const maxCanc = Math.max(1, ...canc.map(h => h.subst_canc));
  const mudaram = hot.filter(h => h.recebidos + h.recebidos_ant >= 5).map(h => ({ ...h, d: h.recebidos_ant ? (h.recebidos - h.recebidos_ant) / h.recebidos_ant : 1 }))
    .sort((x, y) => Math.abs(y.d) - Math.abs(x.d)).slice(0, 6);
  // O que melhorar: regras simples sobre os números acima (sem IA)
  const ideias = [];
  if (canc.length && T.subst_canc) ideias.push(["Notas refeitas concentradas", `<em>${esc(canc[0].hotel)}</em> teve ${canc[0].subst_canc} de ${T.subst_canc} substituições/cancelamentos do período. Conferir o tomador antes de emitir para esse hotel.`]);
  const piorAg = Object.entries(pa.porAgPrazo).filter(([a, v]) => v != null && a !== "Sem agente").sort((x, y) => x[1] - y[1])[0];
  if (piorAg && piorAg[1] < 90) ideias.push([`${esc(piorAg[0])} abaixo da meta de prazo`, `<em>${piorAg[1]}%</em> das notas enviadas em até 48 h (meta: 90%). Ver se a carteira de hotéis está pesada.`]);
  const venc = {}; pa.vencidos.forEach(s => venc[s.hotel] = (venc[s.hotel] || 0) + 1);
  const piorHotel = Object.entries(venc).sort((x, y) => y[1] - x[1])[0];
  if (piorHotel && piorHotel[1] >= 2) ideias.push([`${esc(piorHotel[0])} acumula pedidos vencidos`, `<em>${piorHotel[1]} pedidos</em> do período passaram do prazo sem NF.`]);
  if (pa.faltaDado) ideias.push(["Pedidos parados por falta de dado", `<em>${pa.faltaDado}</em> pedidos sem nome, CPF/CNPJ ou o que entra na nota. Usar "Pedir o que falta" logo que o pedido chega.`]);
  if (pa.fimDeSemana && pa.perdidas && pa.fimDeSemana / pa.perdidas >= 0.25) ideias.push(["Fim de semana acumula", `<em>${Math.round(100 * pa.fimDeSemana / pa.perdidas)}% dos vencidos</em> chegaram entre sexta 18 h e domingo. Vale um plantão no sábado de manhã.`]);
  if (A.ligacoes && T.ligacoes > A.ligacoes * 1.15) ideias.push(["Ligações subindo", `As ligações subiram <em>${Math.round(100 * (T.ligacoes - A.ligacoes) / A.ligacoes)}%</em>. Em geral é hóspede cobrando nota: responder primeiro quem cobrou de novo.`]);
  const agentes = Object.keys(r.por_agente).sort((a, b) => r.por_agente[b].nfs - r.por_agente[a].nfs);
  const atrasados = Object.entries(r.ultimo_dia || {}).filter(([, d]) => d && d < r.ate).map(([a, d]) => `${a} (até ${dt(d)})`);
  return `<div class="g-cab"><div><h3>${titulo}</h3><div class="sub">${dt(r.ini)} a ${dt(r.ate)} comparado com ${dt(r.ini_anterior || r.ini)} a ${dt(r.fim_anterior || r.ini)} · fontes: Mail Analytics (só leitura) e Painel</div></div>
      <div class="g-ferr"><div class="seg" role="group" aria-label="Comparação">
        <button data-rel-tipo="mes" aria-pressed="${r.tipo === "mes"}">Mês × mês anterior</button><button data-rel-tipo="semana" aria-pressed="${r.tipo === "semana"}">Semana</button><button data-rel-tipo="dia" aria-pressed="${r.tipo === "dia"}">Dia</button></div>
        <button class="btn-ic" data-rel-mover="1" title="Período anterior" aria-label="Período anterior">◀</button>
        <button class="btn-ic" data-rel-mover="-1" title="Próximo período" aria-label="Próximo período" ${REL.desl <= 0 ? "disabled" : ""}>▶</button>
        <button data-rel-copiar="1" title="Copia o resumo em texto pra colar no WhatsApp ou no e-mail"><svg class="ic"><use href="#i-copiar"/></svg>Copiar resumo</button></div></div>
    <div class="g-kpis">
      ${kpi("Solicitações", n(T.pedidos), varTxt(T.pedidos, A.pedidos, "pedidos"))}
      ${kpi("NFs emitidas", n(T.nfs), varTxt(T.nfs, A.nfs, "nfs"))}
      ${kpi("Enviadas no prazo", pa.noPrazo == null ? "—" : pa.noPrazo + "%", pa.noPrazo == null ? `<span class="var-n">até 48 h</span>` : varTxt(pa.noPrazo, pb.noPrazo, "noprazo", true))}
      ${kpi("Canceladas ou refeitas", n(T.subst_canc), varTxt(T.subst_canc, A.subst_canc, "subst_canc"))}
      ${kpi("Perdidas", n(pa.perdidas), varTxt(pa.perdidas, pb.perdidas, "perdidas"))}
      ${kpi("Ligações", n(T.ligacoes), varTxt(T.ligacoes, A.ligacoes, "ligacoes"))}
    </div>
    <div class="g-grade">
      <section class="g-painel"><div class="g-tit"><b>Canceladas ou refeitas · onde</b><small>${n(T.subst_canc)} no período</small></div>
        ${canc.length ? `<div class="g-barras">${canc.map(h => `<div class="g-br"><span>${esc(h.hotel)}</span><span class="g-trilho"><i style="width:${Math.round(100 * h.subst_canc / maxCanc)}%"></i></span><span class="g-n">${h.subst_canc}</span></div>`).join("")}</div>
          <p class="g-nota">O Mail Analytics conta as substituições e cancelamentos, mas não grava o motivo.</p>` : `<div class="vazio">Nenhuma nota cancelada ou refeita no período.</div>`}</section>
      <section class="g-painel"><div class="g-tit"><b>Solicitações perdidas · onde se perdem</b><small>pedidos do formulário no período</small></div>
        <div class="g-funil">${[["Recebidas", pa.pedidos.length], ["Com NF", pa.comNf], ["NF enviada", pa.enviados]].map(([rot, v]) =>
          `<div class="g-fl"><span>${rot}</span><span class="g-trilho"><i class="v" style="width:${pa.pedidos.length ? Math.round(100 * v / pa.pedidos.length) : 0}%"></i></span><span class="g-n">${n(v)}</span></div>`).join("")}</div>
        <div class="g-perdas"><div><b>${n(pa.perdidas - pa.esperando - Math.min(pa.faltaDado, pa.perdidas))}</b><span>sem NF e com o prazo vencido</span></div>
          <div><b>${n(pa.esperando)}</b><span>esperando o hóspede responder</span></div><div><b>${n(pa.faltaDado)}</b><span>com dado faltando para emitir</span></div></div></section>
    </div>
    <section class="g-painel"><div class="g-tit"><b>O que melhorar</b><small>gerado a partir dos números acima</small></div>
      ${ideias.length ? `<div class="g-ideias">${ideias.slice(0, 4).map(([t1, t2], i) => `<div class="g-ideia"><i>${i + 1}</i><div><b>${t1}</b><span>${t2}</span></div></div>`).join("")}</div>`
        : `<div class="vazio">Nada fora do normal no período. 👍</div>`}</section>
    <div class="g-grade">
      <section class="g-painel"><div class="g-tit"><b>Por agente</b><small>${contra}</small></div>
        <div class="tabela-wrap"><table class="ger-tab"><thead><tr><th>Agente</th><th class="num">Pedidos</th><th class="num">E-mails</th><th class="num">NFs</th><th class="num">No prazo</th><th class="num">Refeitas</th><th class="num">Variação NFs</th></tr></thead><tbody>
          ${agentes.map(a => { const d = r.por_agente[a], b = r.anterior[a] || {};
            return `<tr><td><b>${esc(a)}</b></td><td class="num">${d.dias || d.pedidos ? n(d.pedidos) : "—"}</td><td class="num">${d.dias ? n(d.recebidos) : `<span class="dica">sem dados</span>`}</td>
              <td class="num">${d.dias ? n(d.nfs) : "—"}</td><td class="num">${pa.porAgPrazo[a] == null ? "—" : pa.porAgPrazo[a] + "%"}</td><td class="num">${d.dias ? n(d.subst_canc) : "—"}</td>
              <td class="num">${d.dias && b.nfs ? varTxt(d.nfs, b.nfs, "nfs").replace(/ · era \d+/, "") : "—"}</td></tr>`; }).join("")}
        </tbody></table></div></section>
      <section class="g-painel"><div class="g-tit"><b>Hotéis que mais mudaram</b><small>e-mails recebidos · ${contra}</small></div>
        ${mudaram.length ? `<div class="tabela-wrap"><table class="ger-tab"><thead><tr><th>Hotel</th><th class="num">Agora</th><th class="num">Antes</th><th class="num">Variação</th><th class="num">NFs</th></tr></thead><tbody>
          ${mudaram.map(h => `<tr><td>${esc(h.hotel)}</td><td class="num">${n(h.recebidos)}</td><td class="num">${n(h.recebidos_ant)}</td>
            <td class="num"><em class="${h.d > 0 ? "neutro" : "neutro"}">${h.d > 0 ? "▲" : "▼"} ${Math.abs(Math.round(100 * h.d))}%</em></td><td class="num">${n(h.nfs)}</td></tr>`).join("")}
        </tbody></table></div>` : `<div class="vazio">Pouco movimento para comparar.</div>`}</section>
    </div>
    ${r.contado_painel?.length ? `<p class="dica">${esc(r.contado_painel.join(" e "))}: sexta a domingo contados pelo Painel (o Mail Analytics grava o fim de semana na segunda de manhã; nada é somado duas vezes).</p>` : ""}
    ${atrasados.length ? `<p class="dica">⚠ O Mail Analytics ainda não gravou todos os dias de: ${esc(atrasados.join(", "))}. Os números desses agentes podem estar incompletos.</p>` : ""}`;
}
document.addEventListener("click", async e => {
  const t = e.target.closest("[data-rel-tipo],[data-rel-mover],[data-rel-copiar]");
  if (!t) return;
  if (t.dataset.relTipo) { REL.tipo = t.dataset.relTipo; REL.desl = REL.tipo === "dia" ? -1 : 0; }
  if (t.dataset.relMover) REL.desl = Math.max(0, REL.desl + Number(t.dataset.relMover));
  if (t.dataset.relCopiar) {
    try { await navigator.clipboard.writeText(REL.texto); toast("Resumo copiado: é só colar no WhatsApp ou no e-mail"); }
    catch (er) { toast("Não consegui copiar", true); }
    return;
  }
  $("ger-relatorio").innerHTML = `<div class="vazio">Carregando o relatório…</div>`;
  carregarRelatorio(true);
});

// ---------- Cadastro completo (Máquinas): caixas e planilhas de hotel que faltam no Cadastro_Hoteis ----------
const CAD = { html: "", em: 0, dados: null };
async function carregarCadastro(forcar = false) {
  if (!forcar && Date.now() - CAD.em < 60 * 1000) return;
  CAD.em = Date.now();
  const r = await api("/api/cadastro/faltando");
  CAD.dados = r;
  CAD.html = htmlCadastro(r);
  if ($("cad-faltando")) $("cad-faltando").innerHTML = CAD.html;
}
function htmlCadastro(r) {
  const lista = r.faltando || [];
  if (!lista.length) return `<div class="cartao-topo"><div><h3>Cadastro de hotéis</h3><div class="sub">Toda caixa de hotel do Outlook e toda planilha de formulário estão no Cadastro_Hoteis ✓</div></div></div>`;
  const ops = a => (r.agentes || []).map(x => `<option ${x === a ? "selected" : ""}>${esc(x)}</option>`).join("");
  return `<div class="cartao-topo"><div><h3>Cadastro de hotéis · ${lista.length} faltando</h3>
      <div class="sub">Sem cadastro, a planilha do hotel não é copiada e a caixa fica sem agente. Confira o nome (igual ao da planilha) e cadastre.</div></div></div>
    <div class="cad-lista">${lista.map((x, i) => `<div class="cad-linha" data-cad="${i}">
      <input class="cad-hotel" value="${esc(x.hotel)}" aria-label="Nome do hotel" title="Nome do hotel (igual ao da planilha do formulário)">
      <input class="cad-email" value="${esc(x.email)}" placeholder="caixa notafiscal@… (se tiver)" aria-label="E-mail da caixa">
      <select class="cad-agente" aria-label="Agente">${x.agente ? "" : "<option value=''>Agente…</option>"}${ops(x.agente)}</select>
      <button class="prim" data-cad-salvar="${i}">Cadastrar</button>
      <span class="dica">${esc(x.motivo)}</span></div>`).join("")}</div>`;
}
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-cad-salvar]");
  if (!b) return;
  const l = b.closest(".cad-linha");
  const corpo = { hotel: l.querySelector(".cad-hotel").value, email: l.querySelector(".cad-email").value, agente: l.querySelector(".cad-agente").value };
  if (!corpo.agente) return toast("Escolha o agente", true);
  b.disabled = true;
  const r = await api("/api/cadastro/adicionar", corpo);
  if (r.ok) { toast(`${corpo.hotel} cadastrado ✓ (a cópia dos hotéis pega na próxima volta)`); carregarCadastro(true); }
  else { b.disabled = false; toast(r.motivo || r.erro || "Não deu certo", true); }
});
