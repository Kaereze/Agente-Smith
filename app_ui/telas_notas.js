// telas_notas.js: parte de telas.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// "Equipe toda" (padrão) ou "Meus hotéis" — vale pra Notas, E-mails e os números da lateral; lembrado neste PC
// Filtro dos 4 agentes (usuário, 11/10/2026): Todos · João · Clara · Cristian · Bernardo. Cada um vê a própria
// Caixa de Entrada do Outlook (o agente do PC dono da caixa). Abre no agente deste PC; a escolha fica guardada.
let escopo = "";
try { escopo = localStorage.getItem("painel.agenteFiltro") || ""; } catch (e) {}
const ORDEM_AGENTES = ["João", "Clara", "Cristian", "Bernardo"];
const agentesEquipe = () => { const da = (st.pcs || []).filter(p => p.papel !== "so_painel").map(p => p.agente).filter(Boolean);   // PC só com o Painel (Ingrid) não tem caixa: fora do filtro, e ela abre em "Todos"
  return [...ORDEM_AGENTES.filter(a => da.includes(a)), ...da.filter(a => !ORDEM_AGENTES.includes(a)).sort()]; };
const escopoAtual = () => { const e = escopo || st.agente || "todos"; return e === "todos" || agentesEquipe().includes(e) ? e : "todos"; };
const doAgente = (agentes, alvo = escopoAtual()) => alvo === "todos" || agentes.includes(alvo);
const meuHotel = h => String(h || "").split(" / ").some(x => AG[x] === st.agente);
// Operador em botões compactos (organização, 11/10/2026): na Notas conta solicitações; nos E-mails, e-mails
function segOperadores(contar) {
  const atual = escopoAtual();
  return [["todos", "Todos"], ...agentesEquipe().map(a => [a, a])].map(([v, rotulo]) =>
    `<button role="tab" aria-selected="${atual === v}" data-escopo="${esc(v)}" aria-pressed="${atual === v}" title="${v === "todos" ? "As caixas dos 4 PCs" : "A Caixa de Entrada do PC de " + esc(v)}">${esc(rotulo)}${contar ? `<span class="qt">${contar(v).toLocaleString("pt-BR")}</span>` : ""}</button>`).join("");
}
// Cartões dos operadores: solicitações (Notas fiscais) e e-mails da Caixa de Entrada de cada um, nas duas telas
// abas de operador (11/10/2026): só nome + número; os detalhes do escolhido ficam numa linha embaixo
function detalheOperador() {
  const v = escopoAtual(), temCx = typeof emailsDa === "function";
  if (v === "todos") return "";   // usuário: os detalhes aparecem quando clica no agente
  const solic = TODOS.filter(it => it.tipo === "form" && doAgente(agentesDo(it), v)).length;
  const meus = temCx ? emailsDa("entrada", v) : [], urg = temCx ? emailsDa("urgencia", v).length : 0;
  const naoLidos = meus.filter(e => e.lido === false).length, fmt = x => x.toLocaleString("pt-BR");
  return `<span class="det-quem">Caixa de ${esc(v)}</span>` +
    `<span><b>${fmt(solic)}</b> ${solic === 1 ? "solicitação" : "solicitações"}</span>` +
    `<span><b>${fmt(meus.length)}</b> e-mails na caixa</span><span><b>${fmt(naoLidos)}</b> não lidos</span>` +
    `<span class="${urg ? "urg" : ""}"><b>${fmt(urg)}</b> urgente${urg === 1 ? "" : "s"}</span>`;
}
// Seletor "Caixa de" no topo (Figma aprovado em 14/10/2026): substitui as abas de agente; vale para todas as telas
function resumoCaixa(v) {
  const sol = TODOS.filter(it => it.tipo === "form" && doAgente(agentesDo(it), v));
  const semNf = sol.filter(it => ["na_fila", "aguardando_envio"].includes(it.s.situacao)).length;
  const atras = sol.filter(it => it.s.situacao !== "concluida" && diasDesde(it.s.data) > PRAZO.med).length;
  const emails = typeof emailsDa === "function" ? emailsDa("entrada", v).length : 0;
  return { n: sol.length, semNf, atras, emails };
}
function desenharSeletorCaixa() {
  if (!$("sc-botao")) return;
  const v = escopoAtual(), r = resumoCaixa(v), fmt = x => x.toLocaleString("pt-BR");
  $("sc-nome").textContent = v === "todos" ? "Todos os agentes" : v === st.agente ? `${v} (minha)` : v;
  $("sc-qt").textContent = fmt(r.n);
  const q = semAcentoSC($("sc-busca").value);
  const linha = (valor, nome, sub, n, ok) => {
    if (q && !semAcentoSC(nome + " " + sub).includes(q)) return "";
    return `<button type="button" role="option" class="sc-item ${valor === v ? "ativo" : ""}" aria-selected="${valor === v}" data-escopo="${esc(valor)}">
      <span class="sc-txt"><b>${esc(nome)}</b><small class="${ok ? "ok" : ""}">${esc(sub)}</small></span><span class="sc-n">${fmt(n)}</span></button>`;
  };
  const sub = x => x.n === 0 && x.emails === 0 ? "caixa em dia" : `${fmt(x.semNf)} sem NF · ${fmt(x.atras)} atrasada${x.atras === 1 ? "" : "s"} · ${fmt(x.emails)} e-mail${x.emails === 1 ? "" : "s"}`;
  const meu = st.agente && agentesEquipe().includes(st.agente) ? st.agente : "";
  const atalhos = (meu ? linha(meu, "Minha caixa", `${meu} · ${sub(resumoCaixa(meu))}`, resumoCaixa(meu).n) : "") +
    linha("todos", "Todos os agentes", "toda a equipe", resumoCaixa("todos").n);
  const equipe = agentesEquipe().map(a => { const x = resumoCaixa(a); return linha(a, a, sub(x), x.n, x.n === 0 && x.emails === 0); }).join("");
  $("sc-itens").innerHTML = (atalhos ? `<div class="sc-grupo">Atalhos</div>${atalhos}` : "") +
    (equipe ? `<div class="sc-grupo">Equipe Fiscal</div>${equipe}` : "") ||
    `<div class="sc-vazio">Ninguém com “${esc($("sc-busca").value)}”</div>`;
}
const semAcentoSC = s => String(s || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
function abrirSeletorCaixa(abrir) {
  const lista = $("sc-lista"), aberto = abrir ?? lista.classList.contains("oculta");
  lista.classList.toggle("oculta", !aberto);
  $("sc-botao").setAttribute("aria-expanded", aberto);
  if (aberto) { $("sc-busca").value = ""; desenharSeletorCaixa(); setTimeout(() => $("sc-busca").focus(), 20); }
}
document.addEventListener("click", e => {
  if (e.target.closest("#sc-botao")) { abrirSeletorCaixa(); return; }
  if (e.target.closest("#sc-lista [data-escopo]")) { abrirSeletorCaixa(false); setTimeout(desenharSeletorCaixa, 0); return; }
  if (!e.target.closest("#seletor-caixa")) abrirSeletorCaixa(false);
});
document.addEventListener("input", e => { if (e.target.id === "sc-busca") desenharSeletorCaixa(); });
document.addEventListener("keydown", e => {
  if (e.target.id !== "sc-busca") return;
  if (e.key === "Escape") { e.stopPropagation(); abrirSeletorCaixa(false); $("sc-botao").focus(); }
  if (e.key === "Enter") { e.preventDefault(); $("sc-itens").querySelector("[data-escopo]")?.click(); }
});
function desenharAbasNotas() {
  desenharSeletorCaixa();
  if (!$("op-cartoes-notas")) return;
  $("op-cartoes-notas").innerHTML = segOperadores(v => TODOS.filter(it => it.tipo === "form" && doAgente(agentesDo(it), v)).length);
  $("det-op-notas").innerHTML = detalheOperador();
}
function desenharLateral() {   // como o Outlook: o número é de solicitações não lidas na Caixa de Entrada
  const n = TODOS.filter(it => it.tipo === "form" && !it.s.na_caixa?.lido && doAgente(agentesDo(it))).length;
  $("nav-notas-n").textContent = n ? n.toLocaleString("pt-BR") : "";
  $("nav-notas-n").title = "Solicitações não lidas na Caixa de Entrada";
}

const HISTORICO = ["concluida"];   // o que já terminou fica discreto, ao lado da fila
const conta = (ign, f, busca) => TODOS.reduce((n, it) => n + (passa(it, ign, busca) && f(it) ? 1 : 0), 0);
function situacoesDaAba(busca) {
  if (origem === "email") return SIT_EMAIL.map(([f, nome, cor]) => [f, nome, cor, conta("sit", it => passaSit(it, f), busca)]);
  // repaginação v2 (usuário, 14/10/2026): todo e-mail já é pedido de NF; os filtros são só o que ajuda a agir
  const base = [["todas", "Todos", "var(--verde)"], ["urgentes", "Urgentes", "var(--erro)"], ["falta_dado", "Falta dado", "var(--atencao)"],
    ["dividida", "Nota dividida", "var(--info)"], ["doc_diferente", "CPF/CNPJ diferente", "var(--erro)"],
    ["envio_pendente", "NF pronta, falta enviar", "var(--atencao)"], ["concluida", "NF enviada", COR_SIT.concluida], ["minhas", "Minhas", "var(--roxo)"]];
  return base.map(([f, nome, cor]) => [f, nome, cor, conta("sit", it => passaSit(it, f), busca)])
    .filter(([f, , , n]) => n || f === filtro || f === "todas");   // o que é zero some (usuário, 09/10/2026)
}

const MAIS = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>';
const ICONE_FILTRO = { hotel: "i-hotel", agente: "i-gente", periodo: "i-cal", envio: "i-mail" };
const icF = campo => `<svg class="ic"><use href="#${ICONE_FILTRO[campo] || "i-busca"}"/></svg>`;
const SETA_F = '<svg class="seta-f"><use href="#i-seta"/></svg>';

function desenharFiltros(busca, total) {
  desenharAbasNotas();
  $("mesa").classList.toggle("um-op", escopoAtual() !== "todos");   // um agente escolhido: a coluna Operador só repetiria o nome
  // resumo de 1 linha (do operador escolhido)
  const minhas = TODOS.filter(it => it.tipo === "form" && doAgente(agentesDo(it)));
  const semNf = minhas.filter(it => ["na_fila", "aguardando_envio"].includes(it.s.situacao)).length;
  const atrasadas = minhas.filter(it => it.s.situacao !== "concluida" && diasDesde(it.s.data) > PRAZO.med).length;
  const quem = escopoAtual() === "todos" ? "nas caixas dos 4 PCs" : "na caixa de " + escopoAtual();
  $("notas-resumo").innerHTML = `<b>${minhas.length}</b> ${minhas.length === 1 ? "solicitação" : "solicitações"} ${esc(quem)} · <b>${semNf}</b> sem NF` +
    (atrasadas ? ` · <span class="ruim">${atrasadas} atrasada${atrasadas > 1 ? "s" : ""} (+7 dias)</span>` : "");
  $("abas-origem").innerHTML = ORIGENS.map(([o, nome]) =>
    `<button class="aba-o" role="tab" data-aba-o="${o}" aria-selected="${origem === o}">${nome}<span class="cnt">${
      conta("origem|sit", it => it.tipo === o, busca).toLocaleString("pt-BR")}</span></button>`).join("");
  const atual = origem === "form" ? filtro : filtroEmail;
  const todas = situacoesDaAba(busca);
  const semEspelho = Object.entries(st.caixa_pcs || {}).filter(([, p]) => !p.espelho).map(([pc, p]) => p.agente || pc);
  const desligados = Object.entries(st.caixa_pcs || {}).filter(([, p]) => p.espelho && !p.online).map(([pc, p]) => `${p.agente || pc} (de ${quando(p.atualizado).slice(-11)})`);
  $("notas-avisos").innerHTML = (semEspelho.length ? `<div class="aviso-linha">${esc(semEspelho.join(", "))} ainda sem a versão nova: as solicitações ${semEspelho.length > 1 ? "deles" : "dele"} aparecem quando o PC atualizar.</div>` : "") +
    (desligados.length ? `<div class="aviso-linha">PC desligado: ${esc(desligados.join(", "))} — mostrando a caixa como estava.</div>` : "");
  // Situação e Hotel: a peça única do Filtro (pecas/filtro.js), igual à caixa de entrada (usuário, 20/10/2026)
  const porF = Object.fromEntries(todas.map(x => [x[0], x]));
  const TOPO = ["todas", "todos", "minhas"], AGIR = ["urgentes", "atrasadas", "falta_dado", "doc_diferente", "dividida", "envio_pendente"];
  const grupos = [TOPO.filter(f => porF[f]),
    [...AGIR.filter(f => porF[f]), ...todas.map(x => x[0]).filter(f => !TOPO.includes(f) && !AGIR.includes(f) && !HISTORICO.includes(f))],
    HISTORICO.filter(f => porF[f])].filter(g => g.length);
  const padraoSit = origem === "form" ? "todas" : "todos";
  $("status-cards").innerHTML = pecaFiltro({ id: "nf-situacao", rotulo: "Situação", valor: atual === "aberto" ? padraoSit : atual, padrao: padraoSit,
    nomePadrao: "Todas", opcoes: grupos.flatMap((g, gi) => g.map((f, i) => ({ v: f, nome: ["todas", "todos"].includes(f) ? "Todas as solicitações" : porF[f][1],
      n: porF[f][3], sep: gi > 0 && i === 0, classe: ["atrasadas", "doc_diferente"].includes(f) && porF[f][3] ? "r" : "" }))) });
  const algum = FH.sel.size || agenteF;
  fhAtualizarContagem();
  $("filtros-linha").innerHTML = fhHtml() +
    (algum ? `<button class="fp-limpar" data-limpa="tudo">Limpar filtros</button>` : "") +
    (busca ? `<span class="aviso-busca">Buscando em toda a aba: situação e filtros não valem enquanto pesquisa</span>` : "") +
    `<span class="resultado">${total.toLocaleString("pt-BR")} ${total === 1 ? "resultado" : "resultados"}</span>`;
  $("notas-cab").classList.toggle("buscando", !!busca);
}

registrarFiltro("nf-situacao", { escolher: v => { if (origem === "form") filtro = v; else filtroEmail = v; ordem = ""; pagina = 0; guardarCaixa(); desenhar(); },
                                 redesenhar: () => desenhar() });
fhOuvir(() => { pagina = 0; if (typeof pn !== "undefined" && pn.vista === "fila") desenhar(); });   // Notas fiscais: vários hotéis (pecas/filtro_hoteis.js)

// Visão geral e outros atalhos: a aba "Notas fiscais" está reservada para a emissão automática (João, 07/11/2026) e nada manda mais
// para ela (09/11/2026). Quem pedia "as notas" abre a Caixa de Entrada em "Formulários do robô" (as atrasadas, a Urgência), com o agente
// escolhido. O nome continua abrirNotas só para não mexer em quem já chama.
function abrirNotas({ filtro: f = "aberto", agente = "" } = {}) {
  if (agente) { escopo = agente; guardarCaixa(); }
  FH.sel = new Set(); $("busca").value = "";
  cx.sel = null; cx.caixaSel = ""; cx.rapido = ""; cx.soNaoLidos = false;
  cx.caixa = f === "atrasadas" ? "urgencia" : "entrada"; cx.soForm = f !== "atrasadas";
  trocarVista("correio");
}

// Filtro de uma situação só: a coluna não repete a etiqueta, mostra quem está cuidando
const visaoMista = () => origem === "email" ? filtroEmail === "todos"
  : ["aberto", "todas", "minhas", "envio_pendente", "atrasadas", "doc_diferente"].includes(filtro);
function linhaHtml(it) {
  if (it.tipo === "form") {
    const s = it.s;
    // colunas alinhadas (design fiscal, 11/10/2026): hóspede · hotel · operador · situação · prazo · chegou
    const alerta = s.alerta_doc?.length || s.falta_nota || s.sem_formulario;
    const naoLido = s.na_caixa && !s.na_caixa.lido;
    return `<div class="linha nf-l col ${sel === s.chave ? "sel" : ""} ${naoLido ? "nao-lido" : ""}" role="option" tabindex="0" data-k="${esc(s.chave)}"
        title="${alerta ? "Tem um aviso: abra pra ver" : ""}">
      <span class="c-nome">${esc(s.nome)}${alerta ? `<span class="c-aviso" aria-label="tem aviso">●</span>` : ""}</span>
      <span class="c-hotel">${esc(s.hotel)}</span>
      <span class="c-op">${esc(agentesDo(it)[0] || "")}</span>
      <span class="c-sit tags-nf">${tagsPedido(s)}</span>
      <span class="c-prazo">${s.prazo ? prazoHtml(s.prazo) : `<span class="prazo fim">—</span>`}</span>
      <span class="c-hora">${chegou(it.quando)}</span>${naoLido ? `<span class="so-leitor">não lido</span>` : ""}</div>`;
  }
  const m = it.m;
  return `<div class="linha ${emailSel === m.id ? "sel" : ""}" role="option" tabindex="0" data-em="${esc(m.id)}">
    <span class="quem-linha"><b>${esc(m.nome || m.de)}${m.falta_nota ? pecaAlerta("nao_recebeu", { titulo: m.falta_nota }) : ""}${tagQuartos(m)}${m.anexos.length ? `<span class="tag">${m.anexos.length} anexo${m.anexos.length > 1 ? "s" : ""}</span>` : ""}${m.solicitacao ? '<span class="tag nf-ok">tem pedido</span>' : ""}</b>
      <small>${esc(m.assunto || "(sem assunto)")}</small></span>
    ${esperaHtml(it)}<span class="col-hotel">${esc(m.hotel)}<small>${m.pc_online ? "PC de " + esc(m.agente_pc || m.pc) : '<span class="erro-txt">PC desligado</span>'}</small></span>
    <span class="hora col-chegou">${chegou(it.quando)}</span>
    <span>${m.notas?.length ? pecaSituacao("pronta", { texto: "NF pronta, falta enviar · " + m.notas.map(n => n.nf).join(", "), titulo: m.notas.map(n => n.nome).join(" · ") })
      : pecaSituacao("sem_nf")}</span></div>`;
}

function desenhar(){
  const busca = $("busca").value.trim();
  desenharLateral();
  let lista = TODOS.filter(it => passa(it, "", busca));
  // o mais recente primeiro (usuário, 09/10/2026); "Prazo" vira pro mais atrasado primeiro
  const ord = ordem || "recente";
  if (ord === "antigo") lista = lista.slice().reverse();
  lista = fhAgrupar(lista, it => it.hoteis);   // prioridade do hotel primeiro (alta antes de baixa); a data segue a ordem escolhida acima
  const seta = o => ord === o ? (o === "antigo" ? " ↓" : " ↓") : "";
  $("linhas-cab").className = "nf-cab";
  $("linhas-cab").innerHTML = `<span class="c-nome">Hóspede</span><span class="c-hotel">Hotel</span><span class="c-op">Operador</span>
    <span class="c-sit">Avisos</span><span class="c-prazo">Prazo</span>
    <button class="ord c-hora" data-ordem="${ord === "recente" ? "antigo" : "recente"}" title="Inverter a ordem" style="justify-self:end;border:0;background:none;padding:0">Chegou ${ord === "recente" ? "↓" : "↑"}</button>`;
  desenharFiltros(busca, lista.length);
  const aviso = `${lista.length.toLocaleString("pt-BR")} ${lista.length === 1 ? "resultado" : "resultados"}`;
  if ($("anuncio").textContent !== aviso) $("anuncio").textContent = aviso;
  const paginas = Math.max(1, Math.ceil(lista.length / POR_PAGINA));
  pagina = Math.min(pagina, paginas - 1);
  $("titulo-caixa").textContent = busca ? `Busca: “${busca}”` : "Notas fiscais";
  $("titulo-n").textContent = "";
  const p = periodo === "0" ? "" : ` dos últimos ${periodo} dias`;
  $("lista").innerHTML = lista.length ? lista.slice(pagina * POR_PAGINA, (pagina + 1) * POR_PAGINA).map(linhaHtml).join("")
    : busca ? `<div class="vazio">Nada com “${esc(busca)}” ${origem === "form" ? "nos formulários" + (periodo === "0" ? "" : " carregados") : "nos e-mails sem resposta"}.<br>
        Veja a outra aba${origem === "email" ? "; e-mail já respondido só aparece no Outlook" : ""}.</div>`
    : filtro === "todas" && !FH.sel.size ? caixaEmDia(escopoAtual() === "todos"
      ? "Nenhuma solicitação na Caixa de Entrada dos 4 PCs." : `Nenhuma solicitação na Caixa de Entrada de ${escopoAtual()}.`)
    : `<div class="vazio">Nada com esses filtros.<br>Escolha outra situação ou tire um filtro.</div>`;
  const de = lista.length ? pagina * POR_PAGINA + 1 : 0, ate = Math.min(lista.length, (pagina + 1) * POR_PAGINA);
  $("pag-txt").textContent = `Mostrando ${de.toLocaleString("pt-BR")}–${ate.toLocaleString("pt-BR")} de ${lista.length.toLocaleString("pt-BR")}` +
    (busca ? " · busca na aba inteira" : FH.sel.size ? " · " + (FH.sel.size === 1 ? [...FH.sel][0] : FH.sel.size + " hotéis") : agenteF ? " · hotéis de " + agenteF : "");
  // páginas: primeira, vizinhas da atual e última
  const nums = [...new Set([0, pagina - 1, pagina, pagina + 1, paginas - 1])].filter(p => p >= 0 && p < paginas).sort((a, b) => a - b);
  $("pags").innerHTML = paginas < 2 ? "" : nums.map((p, i) => (i && p - nums[i - 1] > 1 ? `<span style="align-self:center">…</span>` : "") +
    `<button data-pag="${p}" aria-current="${p === pagina}">${p + 1}</button>`).join("");
  desenharDetalhe();
}

function desenharDetalhe() {
  const s = sel && acharPedido(sel), e = emailSel && st.emails.find(x => x.id === emailSel);
  const ol = !!document.querySelector(".app.modo-ol");   // igual à caixa de entrada: a ficha fica sempre à direita (17/10/2026)
  $("mesa").classList.toggle("com-leitura", !!(s || e) || ol);
  $("detalhe").classList.toggle("oculta", !(s || e) && !ol);
  if (e) return desenharDetalheEmail(e);
  if (!s) { $("detalhe").dataset.k = ""; $("detalhe").innerHTML = ol ? `<div class="ol-vazio"><svg aria-hidden="true"><use href="#i-nf"/></svg>
    <b>Selecione uma solicitação para abrir a ficha</b><span>Clique numa linha da lista · as setas ↑ ↓ andam pelas solicitações</span></div>` : ""; return; }
  if (typeof envNF !== "undefined" && envNF && envNF.alvo === $("detalhe")) return;   // escrevendo o e-mail da NF: não apaga
  // não redesenha enquanto alguém digita no painel de leitura (a lista atualiza sozinha a cada 15 s)
  const foco = document.activeElement;
  if (foco && $("detalhe").contains(foco) && /INPUT|TEXTAREA/.test(foco.tagName) && $("detalhe").dataset.k === s.chave) return;
  $("detalhe").dataset.k = s.chave;
  const meu = s.dono === st.agente, livre = !s.dono;
  const hist = s.historico.slice().reverse();
  $("detalhe").innerHTML = `
    <div class="acoes">
      <button class="prim" data-envnf="${esc(s.chave)}"><svg class="ic"><use href="#i-enviar"/></svg>Enviar NF</button>
      ${livre ? `<button data-a="ASSUMIR"><svg class="ic"><use href="#i-mao"/></svg>Assumir</button>` : ""}
      ${meu ? `<button data-a="LIBERAR">Liberar</button>` : ""}
      ${!livre && !meu ? `<button class="perigo" data-a="LIBERAR" data-v="forcar" title="Tira de ${esc(s.dono)}">Liberar à força</button>` : ""}
      <button data-pedir-dados="${esc(s.chave)}" class="${faltaDados(s).length ? "dest" : ""}" title="Novo e-mail ao hóspede, da caixa do hotel, pedindo só o que falta">Pedir o que falta</button>
      <button data-copiar="1"><svg class="ic"><use href="#i-copiar"/></svg>Copiar dados</button>
      <button data-a="DIVIDIDA" data-v="${s.dividida ? "nao" : "sim"}">${s.dividida ? "Não é dividida" : "Nota dividida"}</button>
      <button class="fechar" id="d-fechar" aria-label="Fechar leitura">×</button></div>
    <header class="cab-msg"><h2>${esc(s.nome)}</h2>
      <div class="remet"><div class="avatar">${esc((s.nome || "?").trim().charAt(0).toUpperCase())}</div><b>Solicitação pelo formulário · ${esc(s.hotel)}</b>
        <span class="quando">${esc(fmtCarimbo(s))}<br><span class="dado">linha ${s.linha}</span></span>
        <span class="de">&lt;${esc(s.email)}&gt;</span></div>
      <div class="etiquetas">${etiquetasDoPedido(s)}
        ${s.prazo ? prazoHtml(s.prazo) : ""}
        ${s.dono ? `<span class="etq">Com ${esc(s.dono)} desde ${quando(s.dono_desde)}</span>` : ""}
        ${s.dividida ? tagDivisao(s) : tagNotaUnica(s)}
        ${s.enviado ? "" : `<span class="etq ruim">E-mail ao hotel não enviado</span>`}</div></header>
    <div class="corpo-msg">${faltaBanner(s)}${fichaResumoHtml(s)}${quadrosEtapa2(s)}${quadroFalta(s.falta_nota)}
      <details class="ficha-form orig" data-dobra="form" ${DOBRA.form ? "open" : ""}><summary>Dúvida no que o hóspede digitou? <u>Ver respostas originais do formulário</u> <span class="dica">${dataBr(s.data)}</span></summary>
        <dl><dt>E-mail do hóspede</dt><dd>${esc(s.email)}</dd>${s.campos.map(c =>
          `<dt>${esc(c[0])}</dt><dd class="${/\d{3}[.\/-]\d/.test(c[1]) ? "dado" : ""}">${esc(c[1])}</dd>`).join("")}</dl></details>
      <section class="ficha ficha-nf"><div class="ficha-tit"><span class="rot">Nota fiscal ${s.partes > 1 || s.dividida ? `· dividida em ${Math.max(s.partes, 2)}` : ""}</span></div>
        <div class="ficha-corpo">
          ${s.nfs.length ? `<div class="etiquetas">${s.nfs.map(n => `<span class="nf-num">NF ${esc(n)}${s.nfs_conferente.includes(n) ? " · conferente"
            : ` <a href="#" data-desfaz="${esc(n)}" title="Desfazer">×</a>`}</span>`).join("")}</div>` : `<span class="dica">Nenhuma NF ainda.</span>`}
          ${s.nfs.length ? (s.envio_pendente
            ? `<div class="envio pend" style="font-size:11.5px">Envio pendente: a nota existe, mas nenhum e-mail com o PDF saiu para ${esc(s.email)}</div>`
            : s.envios?.length ? s.envios.map(v => `<div class="envio ok" style="font-size:11.5px">✓ ${esc(textoEnvio(v))}</div>`).join("")
            : `<span class="dica">Envio por e-mail não registrado (pedido de mais de 14 dias)</span>`) : ""}
          <div class="linha-form"><input id="d-nf" placeholder="Número da NF emitida" inputmode="numeric"><button class="prim" id="d-nf-ok">Marcar NF</button></div>
        </div></section>
      ${noOutlookHtml(s)}
      <details class="ficha ficha-trat dobra" data-dobra="trat" ${DOBRA.trat ? "open" : ""}><summary class="ficha-tit"><span class="rot">Anotar / registrar tratativa</span><span class="dica">clique pra abrir</span></summary>
        <div class="ficha-corpo"><textarea id="d-txt" placeholder="Ex.: pedi o CNPJ correto por e-mail"></textarea>
          <div class="linha-form" style="justify-content:flex-end"><button data-txt="OBS">Anotar</button><button class="creme" data-txt="TRATATIVA">Registrar tratativa</button></div></div></details>
      <details class="ficha dobra" data-dobra="hist" ${DOBRA.hist ? "open" : ""}><summary class="ficha-tit"><span class="rot">Histórico · ${hist.length}</span><span class="dica">quem fez o quê</span></summary>
        <div class="ficha-corpo">${hist.length ? `<div class="historico">${hist.map(h => `<div class="passo-h"><span class="dado">${quando(h.quando)}</span><b>${esc(h.agente)}</b> ${esc(rotulo(h))}</div>`).join("")}</div>`
          : `<span class="dica">Sem ações ainda.</span>`}</div></details>
    </div>`;
}

// Ficha-resumo (desenho aprovado no Figma, 14/10/2026): tudo que precisa pra emitir, sem rolar. O que falta fica em âmbar.
function fichaResumoHtml(s) {
  const semAc = x => String(x || "").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase();
  const campo = (...testes) => { const c = (s.campos || []).find(([k]) => testes.some(r => r.test(semAc(k)))); return c ? String(c[1]).trim() : ""; };
  const nomeTom = campo(/nome.*tomador/, /razao social/, /^nome( completo)?$/);
  const docTom = campo(/documento.*tomador/, /cpf.*cnpj|cnpj.*cpf/, /^cnpj/, /^cpf(?!.*titular)/);
  const cep = campo(/\bcep\b/), endereco = campo(/endereco/), fone = campo(/telefone|celular|whats/);
  const titular = campo(/nome.*titular/), cpfTit = campo(/cpf.*titular/);
  const entrada = campo(/check.?in|data de entrada|entrada/), saida = campo(/check.?out|data de saida|saida/);
  const info = campo(/informac/, /observac/), dividida = campo(/dividid/);
  const val = (v, dado) => v ? `<dd class="${dado ? "dado" : ""}">${esc(v)}</dd>` : `<dd class="falta">falta pedir</dd>`;
  const opc = (v, dado) => v ? `<dd class="${dado ? "dado" : ""}">${esc(v)}</dd>` : `<dd class="vazio-fr">—</dd>`;
  const hist = (s.historico || []).slice(-3).reverse();
  const sit = nomeSituacao(s);
  return `<section class="ficha-resumo" aria-label="Resumo do pedido">
    <div class="fr-grade">
      <div class="fr-bloco"><h4>Tomador da nota</h4><dl>
        <dt>Nome</dt>${val(nomeTom)}<dt>CPF/CNPJ</dt>${val(docTom && fmtDoc(docTom), true)}<dt>CEP</dt>${val(cep && fmtCep(cep), true)}
        ${endereco ? `<dt>Endereço</dt><dd>${esc(endereco)}</dd>` : ""}<dt>Telefone</dt>${opc(fone, true)}</dl></div>
      <div class="fr-bloco"><h4>Estadia</h4><dl>
        <dt>Hotel</dt><dd>${esc(s.hotel)}</dd><dt>Titular</dt>${opc(titular)}${cpfTit ? `<dt>CPF titular</dt><dd class="dado">${esc(fmtDoc(cpfTit))}</dd>` : ""}
        <dt>Datas</dt>${entrada || saida ? `<dd class="dado">${esc(entrada || "?")} → ${esc(saida || "?")}</dd>` : `<dd class="falta">falta pedir</dd>`}</dl></div>
      <div class="fr-bloco"><h4>Como quer a nota</h4><dl>
        <dt>Pedido</dt>${opc(info)}<dt>Dividida</dt><dd>${s.dividida ? `sim${s.partes > 1 ? ` · ${s.partes} notas` : ""}` : esc(dividida || "não")}</dd>
        <dt>Enviar para</dt><dd>${esc(s.email || "")}</dd></dl></div>
      <div class="fr-bloco"><h4>Situação e histórico</h4><dl>
        <dt>Situação</dt><dd>${esc(sit)}</dd><dt>Prazo</dt><dd>${s.prazo ? prazoHtml(s.prazo) : "—"}</dd>
        ${hist.length ? hist.map(h => `<dt class="dado">${esc(quando(h.quando))}</dt><dd>${esc(h.agente)} · ${esc(rotulo(h))}</dd>`).join("") : `<dt>Ações</dt><dd class="vazio-fr">nenhuma ainda</dd>`}</dl></div>
    </div></section>`;
}
// "Pedir dados": Novo e-mail ao hóspede, da caixa do hotel, com a solicitação de dados (assunto combina)
document.addEventListener("click", e => {
  const b = e.target.closest("[data-pedir-dados]");
  if (!b) return;
  const s = acharPedido(b.dataset.pedirDados);
  if (s) abrirEnvioNF(null, { novo: true, para: s.email, conta: s.na_caixa?.caixa || "", solicitar: true, faltas: [...faltaDados(s), ...faltaExtras(s)] });
});

// Etapa 2: CPF/CNPJ da NF diferente do pedido, pedido repetido e os outros pedidos do mesmo hóspede (e-mail ou CPF/CNPJ)
const linhaPedido = o => `<div class="outro-ped" data-k="${esc(o.chave)}" role="button" tabindex="0"><span class="dado">${dataBr(o.data)} ${esc(horaDoCarimbo(o.carimbo))}</span>
  <span>${esc(o.hotel)} · ${esc(o.nome)}${o.email ? ` <span class="dado">&lt;${esc(o.email)}&gt;</span>` : ""}</span>
  <span>${pecaSituacao(situacaoDoPedido(o), { texto: nomeSituacao(o) })}</span></div>`;
function caixaEmDia(texto) {
  return `<div class="vazio feliz"><b>Nada pendente</b><span>${esc(texto)}</span></div>`;
}
// seções que abrem e fecham (Anotar, Histórico): ficam como você deixou, mesmo com a lista atualizando a cada 15 s
const DOBRA = { trat: false, hist: false, form: false };
document.addEventListener("toggle", e => { const d = e.target; if (d.dataset?.dobra) DOBRA[d.dataset.dobra] = d.open; }, true);
function noOutlookHtml(s) {
  const c = s.na_caixa;
  if (!c) return `<div class="no-outlook"><span>Esta solicitação <b>não está</b> na Caixa de Entrada de nenhum PC (já foi tratada no Outlook).</span></div>`;
  return (s.sem_formulario ? `<div class="quadro-e2 atencao"><b>Formulário não achado na planilha</b><div>A solicitação está no Outlook, mas não achei a linha do formulário dela. Abra o e-mail no Outlook pra ver os dados.</div></div>` : "") +
    `<div class="no-outlook"><span>No Outlook: <b>Caixa de Entrada</b> de ${esc(c.caixa)}</span><span>PC de <b>${esc(nomePc(c.pc))}</b></span>
      <span>chegou ${esc(quando(c.recebido))}</span><span>${c.lido ? "lida" : "<b>não lida</b>"}</span>${c.emails > 1 ? `<span>${c.emails} e-mails do robô com este pedido</span>` : ""}</div>`;
}
function quadrosEtapa2(s) {
  let h = "";
  for (const a of s.alerta_doc || []) h += `<div class="quadro-e2 erro" role="alert"><b>⚠ NF ${esc(a.nf)}: CPF/CNPJ diferente do pedido</b>
    <div>${esc(a.texto)}</div><div class="dica">O robô abriu a nota e comparou com o formulário. Confira antes de enviar ao hóspede (ou refaça a NF).</div>
    <div class="acoes-q"><button data-doc-ok="${esc(a.nf)}">Está certo (o hóspede pediu assim)</button></div></div>`;
  for (const a of s.aviso_doc || []) h += `<div class="quadro-e2"><b>CPF/CNPJ do formulário digitado errado</b><div>NF ${esc(a.nf)}: ${esc(a.texto)}</div>
    <div class="dica">O documento do formulário não passa no dígito verificador; o da nota passa. A NF provavelmente saiu certa.</div></div>`;
  if (s.repetido_de) {
    const p = acharPedido(s.repetido_de);
    h += `<div class="quadro-e2 atencao"><b>Pedido repetido</b><div>O hóspede mandou este mesmo formulário de novo (mesmo CPF/CNPJ, estadia e valor). Ele conta como 1, junto com o principal:</div>
      ${p ? linhaPedido(p) : ""}</div>`;
  }
  if (s.repetidos?.length) h += `<div class="quadro-e2 atencao"><b>Pedido repetido · ${s.repetidos.length + 1}x</b>
    <div>O hóspede mandou o formulário ${s.repetidos.length + 1} vezes (mesmo CPF/CNPJ, estadia e valor). Conta como 1 pedido: trate só este.</div>
    ${s.repetidos.map(linhaPedido).join("")}</div>`;
  if (s.outros_pedidos?.length) h += `<section class="ficha"><div class="ficha-tit"><span class="rot">Outros pedidos deste hóspede · ${s.outros_total}</span>
    <span class="dica">mesmo e-mail ou mesmo CPF/CNPJ</span></div><div class="ficha-corpo" style="display:grid;gap:6px">${s.outros_pedidos.map(linhaPedido).join("")}
    ${s.outros_total > s.outros_pedidos.length ? `<span class="dica">e mais ${s.outros_total - s.outros_pedidos.length}</span>` : ""}</div></section>`;
  return h;
}

function desenharDetalheEmail(e) {
  $("detalhe").dataset.k = "";
  $("detalhe").innerHTML = `
    <div class="acoes">
      <button class="prim" data-resp-nf="${esc(e.id)}"><svg class="ic"><use href="#i-enviar"/></svg>Responder com a NF</button>
      <button data-resp="${esc(e.id)}"><svg class="ic"><use href="#i-resp"/></svg>Responder</button>
      ${e.solicitacao ? `<button data-ver-pedido="${esc(e.solicitacao.chave)}">Ver pedido do formulário (${dataBr(e.solicitacao.data)})</button>` : ""}
      <button class="fechar" id="d-fechar" aria-label="Fechar leitura">×</button></div>
    <header class="cab-msg"><h2>${esc(e.assunto || "(sem assunto)")}</h2>
      <div class="remet"><div class="avatar">${esc((e.nome || e.de || "?").trim().charAt(0).toUpperCase())}</div><b>${esc(e.nome || e.de)}</b>
        <span class="quando">${chegou(e.recebido) === "Ontem" ? "Ontem" : dataBr(e.recebido.slice(0, 10))}<br><span class="dado">${esc(e.recebido.slice(11, 16))}</span></span>
        <span class="de">&lt;${esc(e.de)}&gt; para ${esc(e.caixa)}</span></div>
      <div class="etiquetas">${e.notas?.length ? `<span class="pilula p-concluida">NF ${esc(e.notas.map(n => n.nf).join(", "))} emitida</span><span class="etq ruim">envio pendente</span>`
        : `<span class="pilula p-sem_resposta">Sem resposta</span>`}<span class="etq">E-mail direto</span>
        <span class="etq">${esc(e.hotel)}</span><span class="etq ${e.pc_online ? "" : "ruim"}">Caixa no PC de ${esc(e.agente_pc || e.pc)}${e.pc_online ? "" : " · desligado: a resposta sai quando ele ligar"}</span></div></header>
    <div class="corpo-msg">${quadroFalta(e.falta_nota)}
      ${e.notas?.length ? `<section class="ficha"><div class="ficha-tit"><span class="rot" style="color:var(--atencao)">NF já emitida · envio pendente</span>
        <span class="pilula p-concluida">NF ${esc(e.notas.map(n => n.nf).join(", "))}</span></div><dl>${e.notas.map(n =>
          `<dt>NF ${esc(n.nf)}</dt><dd>${esc(n.nome)}<div class="dica">salva no Dropbox em ${esc(n.modificado)} · ${esc(n.prova)}</div></dd>`).join("")}</dl></section>` : ""}
      ${e.quartos >= 2 ? `<section class="ficha"><div class="ficha-tit"><span class="rot">Nota dividida · voucher com ${e.quartos} quartos</span>
        <span class="tag">dividida</span></div><dl>${(e.hospedes_quartos.length ? e.hospedes_quartos : Array(e.quartos).fill("(nome não lido)"))
          .map((n, k) => `<dt>Quarto ${k + 1}</dt><dd>${esc(n)}</dd>`).join("")}</dl></section>` : ""}
      <div class="texto-email">${esc(e.texto || "(sem texto)")}</div>
      ${e.anexos.length ? `<div><div class="rot" style="margin-bottom:8px">Anexos</div><div class="anexos">${e.anexos.map(a =>
        `<div class="anexo"><span class="ext">${esc(String(a).split(".").pop().toUpperCase().slice(0, 4))}</span><span>${esc(a)}</span></div>`).join("")}</div></div>` : ""}
    </div>`;
}

function rotulo(h){
  const m = {ASSUMIR:"assumiu", LIBERAR: h.valor === "forcar" ? "liberou à força" : "liberou", NF:"marcou NF " + h.valor,
             DESFAZER_NF:"desfez NF " + h.valor, TRATATIVA:"tratativa: " + h.valor, OBS:"anotou: " + h.valor,
             DIVIDIDA: h.valor === "sim" ? "marcou nota dividida" : "tirou nota dividida"};
  return m[h.acao] || h.acao;
}

const acharPedido = k => st.fila.find(x => x.chave === k) || (st.filaRep || []).find(x => x.chave === k);
async function acao(a, valor){
  const s = acharPedido(sel); if (!s) return;
  document.querySelectorAll("#detalhe button").forEach(b => b.disabled = true);
  const r = await api("/api/acao", {chave: s.chave, acao: a, valor: valor || ""});
  if (r.ok) toast("Feito ✔"); else toast(r.motivo || "Não deu certo", true);
  $("detalhe").dataset.k = "";
  await carregar();
}

const irPraCaixa = () => { if (pn.vista !== "fila") trocarVista("fila"); };
document.addEventListener("click", async e => {
  const t = e.target.closest("[data-ordem],[data-aba-o],[data-st],[data-limpa],[data-pag],[data-k],[data-em],[data-a],[data-txt],[data-desfaz],[data-copiar],[data-resp],[data-resp-nf],[data-ver-pedido],[data-doc-ok],#d-fechar,#d-nf-ok");
  if (!t) return;
  const d = t.dataset;
  if (d.ordem) { ordem = d.ordem; pagina = 0; return desenhar(); }
  if (d.abaO) { origem = d.abaO; pagina = 0; sel = null; emailSel = null; guardarCaixa(); return desenhar(); }
  if (d.st) { if (origem === "form") filtro = d.st; else filtroEmail = d.st; ordem = ""; pagina = 0; guardarCaixa(); return desenhar(); }
  if (d.limpa) {
    if (d.limpa === "hotel" || d.limpa === "tudo") FH.sel = new Set();
    if (d.limpa === "agente" || d.limpa === "tudo") agenteF = "";
    if (d.limpa === "envio" || d.limpa === "tudo") envio = "todos";
    if ((d.limpa === "tudo" || d.limpa === "periodo") && periodo !== "45") { const antes = periodo; periodo = "45"; if (antes === "0") carregar(); }
    pagina = 0; guardarCaixa(); return desenhar();
  }
  if (d.pag) { pagina = Number(d.pag); desenhar(); $("lista").scrollTop = 0; return; }
  if (d.k) { sel = d.k; emailSel = null; return desenhar(); }
  if (d.em) { emailSel = d.em; sel = null; return desenhar(); }
  if (t.id === "d-fechar") { sel = null; emailSel = null; return desenhar(); }
  if (d.resp) return abrirEnvioNF(null, { id: d.resp, comNF: false });
  if (d.respNf) return abrirEnvioNF(null, { id: d.respNf, comNF: true });
  if (d.verPedido) { filtro = "todas"; origem = "form"; FH.sel = new Set(); agenteF = ""; sel = d.verPedido; emailSel = null; irPraCaixa(); return desenhar(); }
  if (d.a) {
    if (d.v === "forcar" && !confirm("Tirar esta solicitação de quem está tratando?")) return;
    return acao(d.a, d.v);
  }
  if (t.id === "d-nf-ok") { const n = $("d-nf").value.trim().replace(/\D/g, ""); if (!n) return toast("Digite o número da NF", true); return acao("NF", n); }
  if (d.docOk) { if (confirm("O CPF/CNPJ da NF " + d.docOk + " está certo? O alerta some pra equipe toda.")) return acao("OBS", `Conferido: CPF/CNPJ da NF ${d.docOk} está certo`); return; }
  if (d.desfaz) { e.preventDefault(); if (confirm("Desfazer a NF " + d.desfaz + "?")) return acao("DESFAZER_NF", d.desfaz); return; }
  if (d.txt) { const v = $("d-txt").value.trim(); if (!v) return toast("Escreva o texto primeiro", true); return acao(d.txt, v); }
  if (d.copiar) {
    const s = acharPedido(sel);
    try { await navigator.clipboard.writeText([`Hotel: ${s.hotel}`, `E-mail: ${s.email}`, ...s.campos.map(c => `${c[0]}: ${c[1]}`)].join("\n")); toast("Dados copiados"); }
    catch (err) { toast("Não consegui copiar", true); }
  }
});
document.addEventListener("keydown", e => {
  const l = e.target.closest?.(".linha");
  if (l && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); l.click(); }
});
$("busca").addEventListener("input", () => {
  // a busca de cima vai sempre direto ao Outlook dos 4 PCs (usuário, 11/10/2026). Só o histórico das últimas 24 h da caixa fica no
  // navegador deste PC (pecas/busca_recente.js, 28/10/2026); nada disso vai ao servidor
  if (pn.vista !== "correio" && $("busca").value.trim().length >= 3) trocarVista("correio");
  if (pn.vista === "correio") return agendarBusca();
  pagina = 0; desenhar();
});
