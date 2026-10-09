// Visão geral, Log, Máquinas e as janelas de envio. Usa api/$/esc/toast/st/desenhar e o estado da tela de notas
// (mesmo escopo global).
let pn = { vista: "visao", janela: 30, rz: null, tabela: {} };   // tabela: gráfico mostrado como tabela
const hojeIso = () => new Date().toLocaleDateString("sv-SE");

const TITULOS = { visao: "Visão geral", fila: "Notas fiscais", log: "Log do robô", maquinas: "Máquinas", correio: "E-mails" };
function trocarVista(v) {
  if (!TITULOS[v]) v = "fila";
  pn.vista = v;
  for (const id of Object.keys(TITULOS)) $("v-" + id).classList.toggle("oculta", id !== v);
  $("trilha").textContent = v === "correio" ? "E-mails / " + CAIXAS[cx.caixa] : TITULOS[v];
  document.querySelectorAll(".ln[data-vista]").forEach(b =>
    b.setAttribute("aria-current", String(b.dataset.vista === v && (v !== "log" || b.dataset.log === at.aba)
                                          && (v !== "correio" || b.dataset.caixa === cx.caixa))));
  $("busca").placeholder = v === "correio" ? "Buscar hóspede, CPF/CNPJ, sobrenome, frase… (Enter procura no Outlook dos 4 PCs)"
    : "Buscar hóspede, e-mail, CPF/CNPJ, nº da NF, hotel…";
  if (v === "correio") { desenharCorreio(); return; }
  desenhar();
  if (v === "visao") desenharVisao();
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
    return `<article class="maq ${cls}"><div class="maq-cab"><div><b>${esc(p.agente || "?")}</b><span class="dado">${esc(p.pc)}${p.pc === d.este_pc ? " · este PC" : ""}</span></div>
        <span class="pill"><span class="dot ${ponto}"></span>${p.online ? "No ar" : "Desligado"}</span></div>
      <dl><dt>Visto</dt><dd>${haQuanto(p.visto.replace(" ", "T"))}</dd>
        <dt>Outlook</dt><dd>${antigo ? "sem informação" : p.outlook === "aberto" ? `<span style="color:var(--ok)">aberto</span>` : `<span class="ruim-txt">${esc(p.outlook || "?")}</span>`}</dd>
        <dt>Conferência</dt><dd>${conf}${p.conferencia_resumo ? `<div class="dica">${esc(p.conferencia_resumo)}</div>` : ""}</dd>
        <dt>Versão</dt><dd>${versao}</dd>
        <dt>Caixas</dt><dd class="dado">${p.caixas}</dd><dt>Papel</dt><dd>${esc(p.papel || "")}</dd></dl>
      ${p.online ? `<button data-at-atualizar="${esc(p.pc)}"><svg class="ic"><use href="#i-sync"/></svg>Atualizar este PC</button>` : ""}</article>`;
  }).join("");
  el.innerHTML = `<div class="cab-pagina"><h1>Máquinas da equipe</h1>
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

function desenharVisao() {
  const el = $("visao");
  if (!st.atualizado_em) { el.innerHTML = `<div class="vazio">Carregando…</div>`; return; }
  const n = v => (v ?? 0).toLocaleString("pt-BR");
  const hoje = new Date(hojeIso() + "T12:00"), ini = new Date(hoje);
  ini.setDate(ini.getDate() - (pn.janela - 1));
  const corte = ini.toLocaleDateString("sv-SE");
  const pedidos = st.fila.filter(s => s.data >= corte);
  const abertos = st.fila.filter(s => s.situacao !== "concluida");
  const emailsSem = st.emails.filter(m => !m.notas?.length);
  const naoEmitida = st.fila.filter(s => ["na_fila", "aguardando_envio"].includes(s.situacao)).length;
  const envioPend = st.fila.filter(s => s.envio_pendente).length;
  const tratativas = st.fila.filter(s => s.situacao === "tratativa").length;   // mesmo critério do cartão "Tratativa"
  const velhos = abertos.filter(s => diasAtras(s.data) > 7).length;
  const comNf = pedidos.filter(s => s.nfs.length).length;
  // gráfico 1: os pedidos de cada dia e o que aconteceu com eles
  const porDia = {};
  for (const d = new Date(ini); d <= hoje; d.setDate(d.getDate() + 1)) porDia[d.toLocaleDateString("sv-SE")] = {};
  pedidos.forEach(s => { const p = porDia[s.data]; if (p) { const c = categoriaVisao(s); p[c] = (p[c] || 0) + 1; } });
  const dias = Object.entries(porDia).map(([data, partes]) => ({
    rotulo: data.slice(8, 10) + "/" + data.slice(5, 7), partes,
    titulo: new Date(data + "T12:00").toLocaleDateString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit" }) }));
  // gráfico 2: o que está em aberto, por agente (clicar abre as notas dele)
  const ag = {};
  const somar = (a, k) => { (ag[a] ||= {})[k] = (ag[a][k] || 0) + 1; };
  st.fila.forEach(s => { if (s.situacao !== "concluida" || s.envio_pendente) somar(AG[s.hotel] || "Sem agente", categoriaVisao(s)); });
  emailsSem.forEach(m => somar(m.hotel.split(" / ").map(h => AG[h]).find(Boolean) || m.agente_pc || "Sem agente", "email"));
  const total = p => SERIES_AGENTE.reduce((a, s) => a + (p[s.k] || 0), 0);
  const porAgente = Object.entries(ag).map(([rotulo, partes]) => ({ rotulo, partes })).sort((a, b) => total(b.partes) - total(a.partes));
  // espera dos pedidos em aberto
  const faixas = [["Até 2 dias", 0, 2], ["3 a 7 dias", 3, 7], ["8 a 15 dias", 8, 15], ["Mais de 15 dias", 16, 1e9]];
  // cores do prazo (as mesmas da coluna Espera): até 2 dias verde, até 7 âmbar, acima vermelho
  const corFaixa = [COR_VIZ.emitida, COR_VIZ.envio, COR_VIZ.sem_nf, COR_VIZ.sem_nf];
  const idade = faixas.map(([rotulo, a, b], k) => ({ rotulo, cor: corFaixa[k], atrasada: a > 7,
    n: abertos.filter(s => { const d = diasAtras(s.data); return d >= a && d <= b; }).length }));
  const botaoTabela = id => `<button class="link" data-vt="${id}">${pn.tabela[id] ? "Ver gráfico" : "Ver em tabela"}</button>`;
  const kpi = (alvo, rot, v, sub, cor) => `<button class="kpi-b" data-ir="${alvo}" style="--cor:${cor}">
      <span class="kpi-r">${rot}</span><span class="kpi-v">${n(v)}</span><span class="kpi-s">${sub}</span></button>`;
  el.innerHTML = `<div class="cab-pagina"><div style="display:flex;flex-direction:column;gap:4px;margin-right:auto"><h1>Visão geral</h1>
      <span class="dica">Pedidos da Planilha Central e e-mails dos hóspedes · atualiza sozinho</span></div>
      <div class="seg" role="group" aria-label="Período">${JANELAS.map(j =>
        `<button data-vj="${j}" aria-pressed="${pn.janela === j}">${j} dias</button>`).join("")}</div></div>
    <div class="kpis-v">
      <button class="kpi-hero" data-ir="aberto"><span class="kpi-r">Em aberto agora</span>
        <span class="kpi-v">${n(abertos.length + emailsSem.length)}</span>
        <span class="kpi-s">${n(abertos.length)} pedidos e ${n(emailsSem.length)} e-mails · <b>${n(velhos)}</b> esperando há mais de 7 dias</span></button>
      ${kpi("na_fila", "NF não emitida", naoEmitida, "pedidos sem nota", "var(--erro)")}
      ${kpi("envio_pendente", "Envio pendente", envioPend, "nota pronta, e-mail não saiu", "var(--atencao)")}
      ${kpi("tratativa", "Tratativas", tratativas, "esperando resposta do hóspede", "var(--info)")}
      ${kpi("concluida", `NFs nos últimos ${pn.janela} dias`, comNf,
        pedidos.length ? `${Math.round(100 * comNf / pedidos.length)}% dos ${n(pedidos.length)} pedidos` : "sem pedidos no período", "var(--ok)")}
    </div>
    <div class="cartao"><div class="cartao-topo"><div><h3>Pedidos de cada dia e o que aconteceu com eles</h3>
      <div class="sub">Cada coluna é o dia em que o hóspede pediu; as cores mostram a situação da nota hoje. Passe o mouse.</div></div>
      ${botaoTabela("dias")}</div>
      <div id="leg-dias" style="margin:4px 0 10px"></div><div id="graf-dias"></div></div>
    <div class="grade2">
      <div class="cartao"><div class="cartao-topo"><div><h3>Em aberto por agente</h3><div class="sub">Clique num agente para ver as notas dele</div></div>
        ${botaoTabela("agentes")}</div>
        <div id="leg-agentes" style="margin:4px 0 10px"></div><div id="graf-agentes"></div></div>
      <div class="cartao"><div class="cartao-topo"><div><h3>Há quanto tempo esperam</h3><div class="sub">Pedidos em aberto, pelo dia em que foram feitos. Clique para ver.</div></div>
        ${botaoTabela("idade")}</div>
        <div id="graf-idade" style="margin-top:14px"></div></div>
    </div>`;
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
    aoClicar: it => { abrirNotas({ agente: it.rotulo === "Sem agente" ? "" : it.rotulo, filtro: "aberto" }); } });
  if (pn.tabela.idade) $("graf-idade").innerHTML = tabela(["Espera", "Pedidos em aberto"], idade.map(i => [i.rotulo, i.n]));
  else graficoBarrasH($("graf-idade"), idade, { aoClicar: it => abrirNotas({ filtro: it.atrasada ? "atrasadas" : "aberto" }) });
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

async function abrirEnvioNF(chave, resp = null) {
  if (document.querySelector(".modal-fundo")) return;
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `<div class="modal compor">
    <div class="compor-topo"><span>${resp ? "↩ Resposta ao hóspede" : "✉ Nova mensagem · Nota Fiscal"}</span><span id="nf-sub" class="compor-quem">carregando…</span>
      <button class="fechar" id="nf-fechar" title="Descartar">×</button></div>
    <div class="barra-prog" id="nf-barra" style="visibility:hidden"><i></i></div>
    <div class="compor-corpo" id="nf-corpo"><div class="vazio">Carregando…</div></div>
    <div class="compor-rodape"><div class="anel" id="nf-anel" style="width:22px;height:22px;border-width:2px;visibility:hidden"></div>
      <span class="res" id="nf-res"></span></div></div>`;
  document.body.appendChild(fundo);
  $("nf-fechar").onclick = () => { clearTimeout(envNF?.timer); fundo.remove(); envNF = null; };
  const o = await api(resp ? `/api/email/opcoes?id=${encodeURIComponent(resp.id)}` : `/api/envio_nf/opcoes?chave=${encodeURIComponent(chave)}`);
  if (o.erro) { $("nf-corpo").innerHTML = `<div class="vazio">${esc(o.erro)}</div>`; return; }
  envNF = { chave, resp, o, anexos: [], assuntoAuto: !resp };
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
      : `<div class="dica">Sem assinatura do Outlook para ${esc(o.conta_de)} neste PC.</div>`}`;
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
  const conteudo = envNF && (envNF.anexos.length || (envNF.resp && $("nf-msg").innerText.trim()));
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
  const r = await api(envNF.resp ? "/api/email/responder" : "/api/envio_nf", {
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
    $("nf-res").textContent = envNF.resp
      ? `Resposta enviada${s.pc ? " pelo PC " + s.pc : ""}. O e-mail sai da lista na próxima volta do robô (até 2 min).`
      : `NF enviada ao hóspede${s.pc ? " pelo PC " + s.pc : ""}. Ela já ficou marcada no pedido.`;
    $("nf-ir").style.display = "none"; if (envNF.resp) correioRespondido(envNF.resp.id); carregar(); return;
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
  if (b.dataset.envnf) return abrirEnvioNF(b.dataset.envnf);
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
