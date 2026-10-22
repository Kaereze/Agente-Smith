// Tela do robô (22/10/2026, desenho "Painel do robô v3" aprovado pelo João). Uma janela grande (quase a tela toda, o Painel
// aparece atrás) que substitui a tela de Log e a aba Robô: Agora (frase, barra da rodada, avisos, pedidos por situação e o
// resumo do dia) e Registro (o log em frases). Clicar num pedido abre o caminho dele. Fechar não para nada: o robô segue
// e um chip na barra de baixo mostra o andamento. Usa st (pedidos, status, saúde), at.dados (/api/atividade) e /api/envio.
// Nomes todos com prefixo rb (test_previa5 barra nome repetido nos arquivos da tela).
const rbz = { aberta: false, aba: "agora", filtro: "tudo", busca: "", vivo: true, foto: null, env: null, sel: null, abertos: {},
  ajuda: {}, timer: null, timerAt: null, gaveta: false, rodou: false, fimAte: 0, todosDias: false, copiado: "" };

(() => {   // ícones desenhados, um traço só (nada de glifo solto)
  const s = document.createElement("div");
  s.style.cssText = "position:absolute;width:0;height:0;overflow:hidden";
  s.innerHTML = `<svg width="0" height="0" aria-hidden="true"><defs>
<symbol id="rbi-ok" viewBox="0 0 16 16"><path d="M3 8.5l3.2 3L13 4.5"/></symbol>
<symbol id="rbi-al" viewBox="0 0 16 16"><path d="M8 2.5l6 10.5H2z"/><path d="M8 7v2.8M8 11.8v.1"/></symbol>
<symbol id="rbi-x" viewBox="0 0 16 16"><path d="M3.5 3.5l9 9M12.5 3.5l-9 9"/></symbol>
<symbol id="rbi-min" viewBox="0 0 16 16"><path d="M3 12h10"/></symbol>
<symbol id="rbi-busca" viewBox="0 0 16 16"><circle cx="7" cy="7" r="4.2"/><path d="M10.2 10.2L14 14"/></symbol>
<symbol id="rbi-cp" viewBox="0 0 16 16"><rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/><path d="M10.5 3.5h-6a1.5 1.5 0 0 0-1.5 1.5v6"/></symbol>
<symbol id="rbi-ch" viewBox="0 0 16 16"><path d="M5 6.5l3 3 3-3"/></symbol>
<symbol id="rbi-cr" viewBox="0 0 16 16"><path d="M6.5 5l3 3-3 3"/></symbol>
<symbol id="rbi-rel" viewBox="0 0 16 16"><circle cx="8" cy="8" r="5.2"/><path d="M8 5v3.2l2 1.3"/></symbol>
<symbol id="rbi-env" viewBox="0 0 16 16"><path d="M2.5 8.5L13.5 3 9 13.5 7.5 9z"/></symbol>
<symbol id="rbi-off" viewBox="0 0 16 16"><path d="M8 2.5v5"/><path d="M4.6 4.6a5.2 5.2 0 1 0 6.8 0"/></symbol>
</defs></svg>`;
  document.body.appendChild(s);
})();
const rbIc = (n, tam = 16, cls = "") => `<svg class="rb-i ${cls}" width="${tam}" height="${tam}" aria-hidden="true"><use href="#rbi-${n}"/></svg>`;
const rbGira = (tam = 14) => `<span class="rb-gira" style="width:${tam}px;height:${tam}px"></span>`;
const rbHora = d => (d instanceof Date && !isNaN(d)) ? d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "";
function rbDataStatus(txt) {   // "22/10/2026 09:31:02" (aba Status) -> Date
  const m = String(txt || "").match(/(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2}):(\d{2})/);
  return m ? new Date(+m[3], +m[2] - 1, +m[1], +m[4], +m[5], +m[6]) : null;
}

// ---------- o que a tela mostra, calculado dos dados que o Painel já tem ----------
const rbConcl = x => x.situacao === "concluida";
function rbTrilha(x) {   // 4 passos: recebido · enviado ao hotel · NF emitida · NF enviada ao hóspede
  const f = [true, !!x.enviado, (x.nfs || []).length > 0, rbConcl(x) || (x.envios || []).length > 0];
  const i = f.indexOf(false);
  return f.map((v, k) => v ? "f" : k === i ? "a" : "p");
}
function rbEtapaDaRodada(env) {   // mesmas linhas do log que a janela antiga usava (ETAPAS_ENVIO)
  const linhas = env?.linhas || [];
  let atual = -1;
  const horas = {};
  linhas.forEach(l => ETAPAS_ENVIO.forEach(([, , re], k) => { if (re && re.test(l.texto)) { atual = Math.max(atual, k); horas[k] ||= l.hora; } }));
  if (!env?.rodando) atual = env?.codigo === 0 ? ETAPAS_ENVIO.length : Math.max(atual, 0);
  return { atual: Math.max(atual, 0), horas, tudo: !env?.rodando && env?.codigo === 0 };
}
function rbModelo() {
  const s = st.status || {}, env = rbz.env || {}, hoje = hojeIso(), hojeBr = new Date().toLocaleDateString("pt-BR");
  const fila = (st.fila || []).filter(x => !x.repetido_de);
  const rodando = !!env.rodando, ligado = s.ligado !== false;
  const esperando = fila.filter(x => !x.enviado && x.situacao === "aguardando_envio");
  const hojeEnviados = fila.filter(x => x.enviado && x.data === hoje).length;
  const nfHoje = fila.reduce((n, x) => n + (x.envios || []).filter(e => String(e.quando || "").startsWith(hojeBr)).length, 0);
  const ultima = rbDataStatus(s.ultima_execucao), proxima = ultima ? new Date(ultima.getTime() + 10 * 60000) : null;
  const concluidos = fila.filter(x => rbConcl(x) && ((x.envios || []).some(e => String(e.quando || "").startsWith(hojeBr)) || x.data === hoje));
  const sete = new Date(Date.now() - 7 * 86400000).toLocaleDateString("sv-SE");   // só a última semana: o resto fica em Notas fiscais
  const abertos = fila.filter(x => x.enviado && !rbConcl(x));
  const espNF = abertos.filter(x => !x.data || x.data >= sete);
  return { s, env, rodando, ligado, esperando, hojeEnviados, nfHoje, ultima, proxima, concluidos, espNF, antigos: abertos.length - espNF.length, avisos: st.saude || [],
    carregando: !st.atualizado_em && !st.erro };
}

// ---------- peças ----------
function rbLinha(x, tipo) {
  const t = rbTrilha(x), agente = (typeof AG !== "undefined" && AG[x.hotel]) || "";
  const ultimoEnvio = (x.envios || []).slice(-1)[0]?.quando || "";
  const onde = tipo === "and" ? `<b>Enviando agora</b>${agente ? ` pelo PC de ${esc(agente)}` : ""}`
    : tipo === "env" ? `<b>Esperando o envio ao hotel</b>`
    : tipo === "ok" ? `Concluído${ultimoEnvio ? " às " + esc(ultimoEnvio.slice(11, 16)) : ""}`
    : (x.nfs || []).length ? `<b>NF emitida</b> · falta enviar ao hóspede` : `Enviado ao hotel · <b>esperando a NF</b>`;
  const icone = tipo === "and" ? rbGira(14) : tipo === "ok" ? rbIc("ok", 16, "rb-ok") : rbIc("rel", 16, "rb-cz");
  const trilha = `<span class="rb-tri" title="Recebido · Enviado ao hotel · NF emitida · NF enviada ao hóspede">${t.map(c => `<i class="${c}"></i>`).join("")}</span>`;
  return `<div class="rb-l ${rbz.sel === x.chave ? "sel" : ""}" role="button" tabindex="0" data-rb-ped="${esc(x.chave)}">${icone}
    <div class="rb-nm"><div class="rb-nome">${esc(x.hotel)} <span>· ${esc(x.nome || "")}</span></div><div class="rb-onde">${onde}</div></div>
    ${trilha}<span class="rb-hr">${esc(horaDoCarimbo(x.carimbo) || "")}</span></div>`;
}
function rbGrupo(id, titulo, lista, tipo, mostrar, extra = "") {
  if (!lista.length) return "";
  const aberto = !!rbz.abertos[id], vistas = aberto ? lista.slice(0, 80) : lista.slice(0, mostrar);
  const mais = lista.length > mostrar ? `<button type="button" class="rb-mais" data-rb-mais="${id}">${aberto ? "Ver menos" : `Ver os outros ${lista.length - mostrar}`}</button>` : "";
  return `<section class="rb-grupo"><h4>${esc(titulo)} <em>${lista.length}</em>${mais}</h4>${vistas.map(x => rbLinha(x, tipo)).join("")}${extra}</section>`;
}
function rbAjuda(texto) {   // o que fazer, por tipo de aviso (mantém simples: 3 casos conhecidos)
  if (/Caixa de Sa[ií]da/i.test(texto)) return { passos: ["No PC dessa pessoa, abra o Outlook e vá em <b>Caixa de Saída</b>.", "Apague ou reenvie o e-mail que está parado.",
    "O Painel confere sozinho em até 1 minuto e este aviso some."] };
  if (/Outlook (fechado|aberto sem janela)/i.test(texto)) return { passos: ["No PC dessa pessoa, abra o Outlook (com a janela).", "O robô volta a ler os e-mails sozinho em instantes."] };
  if (/sem envio ao hotel/i.test(texto)) return { ver: true };
  return {};
}
function rbAvisos(m) {
  return m.avisos.slice(0, 4).map((a, i) => {
    const mt = String(a.texto || "").match(/^(.*?)(?:: |\. )(.*)$/), titulo = mt ? mt[1] : a.texto, sub = mt ? mt[2] : "", aj = rbAjuda(a.texto || "");
    const aberta = !!rbz.ajuda[i];
    const botao = aj.passos ? `<button type="button" class="rb-bt" data-rb-ajuda="${i}" aria-expanded="${aberta}">Como resolver ${rbIc("ch", 14)}</button>`
      : aj.ver ? `<button type="button" class="rb-bt" data-rb-ver-pedidos>Ver os pedidos</button>`
      : `<button type="button" class="rb-bt so-admin" data-rb-monit>Ver no Monitoramento</button>`;
    const passos = aj.passos && aberta ? `<div class="rb-passo"><ol>${aj.passos.map(p => `<li>${p}</li>`).join("")}</ol>
      <button type="button" class="rb-bt" data-rb-copiar-ajuda="${i}">${rbIc("cp", 14)}Copiar instruções</button></div>` : "";
    return `<div class="rb-aviso">${rbIc("al", 18, "rb-vm")}<p>${esc(titulo)}${sub ? `<small>${esc(sub)}</small>` : ""}</p>${botao}${passos}</div>`;
  }).join("");
}
function rbRodada(m) {
  if (!m.env.modo) {
    const t = m.ultima ? `Terminou às ${rbHora(m.ultima)}${m.s.resumo ? ". " + esc(String(m.s.resumo).replace(/^\W+\s*/u, "")) : "."}` : "Ainda não há rodada registrada neste PC.";
    return `<div class="rb-bloco"><h4>Última rodada</h4><p class="rb-txt">${t}</p></div>`;
  }
  const e = rbEtapaDaRodada(m.env);
  const li = ETAPAS_ENVIO.map(([nome], k) => {
    const f = k < e.atual || e.tudo, a = m.rodando && k === e.atual;
    const det = a ? esc((m.env.linhas || []).slice(-1)[0]?.texto?.replace(/^\W+\s*/u, "") || "") : "";
    return `<li class="${f ? "f" : a ? "a" : "p"}"><span class="rb-bola">${f ? rbIc("ok", 11) : a ? rbGira(10) : k + 1}</span>
      <div>${esc(nome)}${det ? `<small>${det}</small>` : ""}</div><time>${esc(f || a ? (e.horas[k] || (a ? "agora" : "")) : "")}</time></li>`;
  }).join("");
  return `<div class="rb-bloco"><h4>Rodada</h4><ol class="rb-passos">${li}</ol></div>`;
}
function rbLado(m) {
  return `<aside class="rb-lado"><div class="rb-bloco"><h4>Hoje</h4><dl class="rb-fatos"><dt>Enviados ao hotel</dt><dd>${m.hojeEnviados}</dd>
    <dt>NF enviadas aos hóspedes</dt><dd>${m.nfHoje}</dd><dt>Próximo envio automático</dt><dd>${m.ligado && m.proxima ? rbHora(m.proxima) : "—"}</dd></dl></div>${rbRodada(m)}</aside>`;
}
function rbSeg(m) {
  const e = rbEtapaDaRodada(m.env), n = ETAPAS_ENVIO.length;
  return `<div class="rb-seg" aria-hidden="true">${ETAPAS_ENVIO.map((_, i) => `<i class="${e.tudo || i < e.atual ? "f" : m.rodando && i === e.atual ? "a" : ""}"></i>`).join("")}</div>
    <div class="rb-segtxt"><span><b>${esc(m.rodando ? ETAPAS_ENVIO[e.atual][0] : (e.tudo ? "Rodada concluída" : (m.env.resumo || "Rodada terminada")))}</b>${m.rodando ? " · " + esc((m.env.linhas || []).slice(-1)[0]?.texto?.replace(/^\W+\s*/u, "") || "") : ""}</span>
    <span>${m.rodando ? `passo ${e.atual + 1} de ${n}` : esc(rbHora(m.ultima))}</span></div>`;
}
function rbEstado(m) {
  if (!m.ligado) return `<span class="rb-estado vm">${rbIc("off", 14)}Robô desligado</span>`;
  if (m.rodando) return `<span class="rb-estado">${rbGira(12)}Enviando ${m.esperando.length || ""} ${m.esperando.length === 1 ? "pedido" : "pedidos"}</span>`;
  if (m.avisos.length) return `<span class="rb-estado vm">${rbIc("al", 14)}${m.avisos.length} ${m.avisos.length === 1 ? "precisa" : "precisam"} de você</span>`;
  return `<span class="rb-estado ok">${rbIc("ok", 14)}Tudo certo</span>`;
}
function rbSkeleton() {
  return [1, 2, 3, 4].map(() => `<div class="rb-sk"><span class="sk" style="width:16px;height:16px;border-radius:50%"></span><div><div class="sk" style="width:62%;margin-bottom:8px"></div><div class="sk" style="width:40%;height:8px"></div></div><div class="sk" style="height:4px"></div></div>`).join("");
}

// ---------- aba Agora ----------
function rbAgora(m) {
  if (m.carregando) return `<div class="rb-corpo"><div class="rb-main"><p class="rb-frase">Lendo os pedidos…</p>${rbSkeleton()}</div></div>`;
  if (!m.ligado) return `<div class="rb-corpo"><div class="rb-main"><div class="rb-vazio" style="padding-top:88px"><b>O robô está desligado.</b>Ele parou de copiar e enviar os pedidos. Os pedidos que chegarem ficam esperando.
    <div class="rb-leg">Avise o João para ligar o robô.</div></div></div></div>`;
  const n = m.esperando.length;
  let frase;
  if (m.rodando) frase = `${rbGira(20)}<span>O robô está enviando ${n ? `<b>${n} ${n === 1 ? "pedido" : "pedidos"}</b>` : "os pedidos"} agora.</span>`;
  else if (m.avisos.length) frase = `${m.avisos.length === 1 ? "Um problema precisa" : m.avisos.length + " problemas precisam"} de você.`;
  else if (n) frase = `<span><b>${n} ${n === 1 ? "pedido" : "pedidos"}</b> esperando o próximo envio.</span>`;
  else frase = "Tudo certo. Nenhum pedido esperando.";
  const sub = [m.ultima ? `Última rodada às ${rbHora(m.ultima)}` : "", m.rodando && m.env.inicio ? `começou às ${rbHora(new Date(m.env.inicio))}` : "",
    !m.rodando && m.proxima ? `próxima por volta das ${rbHora(m.proxima)}` : ""].filter(Boolean).join(" · ");
  const grupos = rbGrupo("and", m.rodando ? "Em andamento" : "Esperando o envio ao hotel", m.esperando, m.rodando ? "and" : "env", m.rodando ? 12 : 8)
    + rbGrupo("nf", "Esperando a NF", m.espNF, "nf", 5, m.antigos ? `<button type="button" class="rb-mais rb-antigos" data-rb-ver-pedidos>${m.antigos} mais antigos (mais de 7 dias) ficam em Notas fiscais ${rbIc("cr", 14)}</button>` : "")
    + rbGrupo("ok", "Concluídos hoje", m.concluidos, "ok", 3);
  const vazio = !grupos ? `<div class="rb-vazio"><b>Nenhum pedido hoje até agora.</b>Quando chegar um formulário, ele aparece aqui sozinho, com o caminho completo.</div>` : "";
  return `<div class="rb-corpo"><div class="rb-main"><p class="rb-frase">${frase}</p><p class="rb-fsub">${esc(sub)}</p>${m.env.modo ? rbSeg(m) : ""}
    ${rbAvisos(m)}${grupos || vazio}</div>${rbLado(m)}</div>`;
}

// ---------- aba Registro: o log em frases ----------
const RB_FRASE = {
  NOVA_SOLICITACAO: e => `Pedido novo de <b>${esc(e.pedido || "hóspede")}</b>`, EMAIL_RECEBIDO: e => `E-mail recebido de <b>${esc(e.pedido || "hóspede")}</b>`,
  NF_ENVIADA: e => `NF de <b>${esc(e.pedido || "hóspede")}</b> enviada ao hóspede`, NF_DROPBOX: e => `NF de <b>${esc(e.pedido || "hóspede")}</b> achada no Dropbox`,
  TRATATIVA: e => `E-mail ao hóspede <b>${esc(e.pedido || "")}</b> (falta a nota)`, NOTA_UNICA: e => `Nota única: <b>${esc(e.pedido || "")}</b>`,
  OUTLOOK_FECHADO: e => `Outlook fechado no PC de <b>${esc(e.agente || e.pc)}</b>`, OUTLOOK_ABERTO: e => `Outlook aberto de novo no PC de <b>${esc(e.agente || e.pc)}</b>`,
  ATUALIZADO: () => "Atualização do Painel", FALHA: () => "<b>Problema</b>" };
const rbAviso = e => ["FALHA", "OUTLOOK_FECHADO"].includes(e.tipo);
const rbFiltros = { tudo: () => true, entrada: e => SENTIDO[e.tipo] === "entrada", saida: e => SENTIDO[e.tipo] === "saida", aviso: rbAviso };
function rbEventos() {
  const d = rbz.vivo ? at.dados : (rbz.foto || at.dados);
  if (!d) return null;
  const hoje = hojeIso();
  const base = d.eventos.filter(e => rbz.todosDias || e.quando.slice(0, 10) === hoje);
  const q = rbz.busca.trim().toLowerCase();
  return { base, lista: base.filter(rbFiltros[rbz.filtro] || rbFiltros.tudo).filter(e => !q || [e.hotel, e.pedido, e.detalhe, e.agente, e.tipo].join(" ").toLowerCase().includes(q)) };
}
const rbCru = e => `${e.quando.replace("T", " ")}  ${e.pc}  ${e.agente || "-"}  ${e.tipo}  ${e.hotel || "-"}  ${e.pedido || "-"}  ${e.detalhe || ""}`;
function rbRegistro(m) {
  const r = rbEventos();
  if (!r) return `<div class="rb-corpo"><div class="rb-main rb-largo">${rbSkeleton()}</div></div>`;
  const cont = f => r.base.filter(rbFiltros[f]).length;
  const chip = (id, nome) => `<button type="button" class="rb-chip-f ${rbz.filtro === id ? "on" : ""}" data-rb-filtro="${id}">${nome} <small>${cont(id)}</small></button>`;
  const agora = (m.env.linhas || []).slice(-3).reverse().map((l, i) => `<div class="rb-reg"><time>${esc(l.hora)}</time>${i === 0 && m.rodando ? rbGira(14) : rbIc(l.nivel === "ERROR" ? "al" : "ok", 16, l.nivel === "ERROR" ? "rb-vm" : "rb-ok")}
    <div>${esc(l.texto.replace(/^\W+\s*/u, ""))}<small>rodada deste PC</small></div><span></span></div>`).join("");
  const linhas = r.lista.slice(0, 200).map((e, i) => {
    const f = (RB_FRASE[e.tipo] || (() => esc(TIPOS_ATIV[e.tipo] || e.tipo)))(e), aberta = rbz.abertaReg === i;
    const icone = rbAviso(e) ? rbIc("al", 16, "rb-vm") : SENTIDO[e.tipo] === "sistema" ? rbIc("rel", 16, "rb-cz") : rbIc("ok", 16, "rb-ok");
    return `<div class="rb-reg ${aberta ? "aberta" : ""}" data-rb-reg="${i}" role="button" tabindex="0"><time>${esc(e.quando.slice(11, 16))}</time>${icone}
      <div>${f}<small>${esc(e.detalhe || "")}${e.agente ? ` · PC de ${esc(e.agente)}` : ""}</small></div>${e.hotel ? `<span class="rb-h">${esc(e.hotel.slice(0, 22))}</span>` : "<span></span>"}
      ${aberta ? `<div class="rb-log rb-cru">${esc(rbCru(e))}<br><button type="button" class="rb-bt peq" data-rb-copiar-cru="${i}">${rbIc("cp", 13)}Copiar</button></div>` : ""}</div>`;
  }).join("");
  return `<div class="rb-corpo"><div class="rb-main rb-largo"><div class="rb-filtros">${chip("tudo", "Tudo")}${chip("entrada", "Entradas")}${chip("saida", "Saídas")}${chip("aviso", "Avisos e erros")}
    <label class="rb-busca">${rbIc("busca", 14)}<input id="rb-busca" type="search" placeholder="Procurar hotel, hóspede ou texto" value="${esc(rbz.busca)}" aria-label="Procurar no registro"></label>
    <button type="button" class="rb-chave ${rbz.vivo ? "" : "off"}" role="switch" aria-checked="${rbz.vivo}" data-rb-vivo><i></i>Seguir ao vivo</button></div>
    ${agora}${linhas || `<div class="rb-vazio"><b>Nada por aqui.</b>${rbz.busca || rbz.filtro !== "tudo" ? "Tente tirar o filtro ou a busca." : "Ainda não há registros hoje."}</div>`}
    <div class="rb-rodape-reg"><span>Arquivo no PC: <code>logs/solicitacoes_nf.log</code></span>
      <button type="button" class="rb-bt fant" data-rb-dias>${rbz.todosDias ? "Só hoje" : "Ver dias anteriores"}</button><button type="button" class="rb-bt fant" data-rb-copiar-dia>Copiar a lista</button></div></div></div>`;
}

// ---------- gaveta do pedido: o caminho completo ----------
function rbGavetaPedido(m) {
  const x = (st.fila || []).find(y => y.chave === rbz.sel);
  if (!x) return "";
  const t = rbTrilha(x), cont = (st.fila || []).find(y => y.chave === x.chave);
  const envio = (x.envios || []).slice(-1)[0];
  const passo = (i, nome, sub, hora) => `<li class="${t[i] === "f" ? "f" : t[i] === "a" ? "a" : "p"}"><span class="rb-bola">${t[i] === "f" ? rbIc("ok", 11) : t[i] === "a" ? (m.rodando && i === 1 ? rbGira(10) : i + 1) : i + 1}</span>
    <div>${esc(nome)}${sub ? `<small>${sub}</small>` : ""}</div><time>${esc(hora || "")}</time></li>`;
  const nomeBusca = String(x.nome || "").toLowerCase();
  const eventos = ((at.dados?.eventos || []).filter(e => nomeBusca && String(e.pedido || "").toLowerCase().includes(nomeBusca))).slice(0, 5);
  const daRodada = (m.env.linhas || []).filter(l => String(l.texto).toLowerCase().includes(String(x.hotel || "").toLowerCase().split(" ")[0])).slice(-3);
  const linhasLog = [...daRodada.map(l => `<span>${esc(l.hora)}</span> ${esc(l.texto.replace(/^\W+\s*/u, ""))}`),
    ...eventos.map(e => `<span>${esc(e.quando.slice(11, 19))}</span> ${esc(TIPOS_ATIV[e.tipo] || e.tipo)}${e.detalhe ? ": " + esc(e.detalhe) : ""}`)];
  const agente = (typeof AG !== "undefined" && AG[x.hotel]) || "";
  return `<div class="rb-gaveta-ped" role="dialog" aria-label="Caminho do pedido" id="rb-gaveta-ped"><div class="rb-gp-cab"><div><h5>${esc(x.hotel)}</h5>
      <div class="rb-cod">${esc(x.nome || "")}${x.data ? " · recebido " + esc(dataBr(x.data)) + " " + esc(horaDoCarimbo(x.carimbo)) : ""}</div></div>
      <button type="button" class="rb-bt ic fant" data-rb-fechar-ped aria-label="Fechar o pedido">${rbIc("x")}</button></div>
    <h4>Caminho do pedido</h4><ol class="rb-passos grande">${passo(0, "Formulário recebido", agente ? `caixa do hotel no PC de ${esc(agente)}` : "", horaDoCarimbo(x.carimbo))}
      ${passo(1, "Enviado ao hotel", x.enviado ? "e-mail do robô na caixa do hotel" : (m.rodando ? "saindo agora pelo Outlook" : "esperando a próxima rodada"), "")}
      ${passo(2, "NF emitida", (x.nfs || []).length ? "NF " + esc((x.nfs || []).join(", ")) : "esperando a emissão", "")}
      ${passo(3, "NF enviada ao hóspede", envio ? "para " + esc(envio.para || "") : "", envio ? String(envio.quando || "").slice(11, 16) : "")}</ol>
    <h4>No log <span>· logs/solicitacoes_nf.log</span></h4>
    <div class="rb-log">${linhasLog.join("<br>") || "<span>Nenhuma linha deste pedido nos últimos registros.</span>"}</div>
    <div class="rb-gp-acoes"><button type="button" class="rb-bt" data-rb-copiar-ped>${rbIc("cp", 14)}Copiar linhas</button>
      <button type="button" class="rb-bt fant" data-rb-no-registro>Ver no Registro ${rbIc("cr", 14)}</button></div></div>`;
}

// ---------- a janela ----------
function rbCabecalho(m) {
  return `<header class="rb-topo"><h3 id="rb-titulo">Robô</h3>${rbEstado(m)}<div class="rb-acoes">
    <button type="button" class="rb-bt pri" id="rb-agora" ${m.rodando || !m.ligado ? "disabled" : ""}>${m.rodando ? rbGira(13) + "Enviando…" : rbIc("env") + "Enviar agora"}</button>
    <span class="rb-sep"></span><button type="button" class="rb-bt ic fant" data-rb-minimizar aria-label="Minimizar" title="Minimizar: o robô segue trabalhando">${rbIc("min")}</button>
    <button type="button" class="rb-bt ic fant fechar" data-rb-fechar aria-label="Fechar" title="Fechar (Esc)">${rbIc("x")}</button></div></header>
    <nav class="rb-abas" role="tablist"><button type="button" role="tab" aria-selected="${rbz.aba === "agora"}" class="${rbz.aba === "agora" ? "on" : ""}" data-rb-aba="agora">Agora</button>
    <button type="button" role="tab" aria-selected="${rbz.aba === "reg"}" class="${rbz.aba === "reg" ? "on" : ""}" data-rb-aba="reg">Registro<small>${(at.dados?.eventos || []).filter(e => e.quando.slice(0, 10) === hojeIso()).length || ""}</small></button></nav>`;
}
function rbRender() {
  const fundo = document.getElementById("rb-fundo");
  if (!fundo) return;
  const m = rbModelo(), jan = fundo.querySelector(".rb-sheet");
  const foco = document.activeElement?.id === "rb-busca" ? { sel: document.activeElement.selectionStart } : null;
  const rolagem = jan.querySelector(".rb-main")?.scrollTop || 0;
  jan.innerHTML = rbCabecalho(m) + (rbz.aba === "reg" ? rbRegistro(m) : rbAgora(m)) + (rbz.sel ? rbGavetaPedido(m) : "");
  const nova = jan.querySelector(".rb-main");
  if (nova) nova.scrollTop = rolagem;
  if (foco) { const i = document.getElementById("rb-busca"); i?.focus(); try { i.setSelectionRange(foco.sel, foco.sel); } catch (e) {} }
}
function rbAbrir(aba = "agora", filtro = "") {
  if (rbz.aberta) { rbz.aba = aba; if (filtro) rbz.filtro = filtro; rbRender(); return; }
  if (document.querySelector(".modal-fundo")) return;   // outra janela aberta (mensagem sendo escrita): não atropela
  rbz.aberta = true; rbz.aba = aba; rbz.sel = null; rbz.gaveta = false; if (filtro) rbz.filtro = filtro;
  document.getElementById("rb-gaveta")?.remove();
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo rb-fundo"; fundo.id = "rb-fundo";
  fundo.innerHTML = `<div class="modal rb-sheet" aria-labelledby="rb-titulo"></div>`;
  fundo.addEventListener("mousedown", ev => { if (ev.target === fundo) rbFechar(); });
  document.body.appendChild(fundo);
  rbRender();
  rbCarregarAtividade();
  rbVigiar();
}
function rbFechar(paraGaveta = false) {
  if (!rbz.aberta) return;
  rbz.aberta = false; rbz.sel = null;
  clearTimeout(rbz.timerAt);
  document.getElementById("rb-fundo")?.remove();
  if (paraGaveta) { rbz.gaveta = true; rbRenderGaveta(); }
  rbAgendar();
}
async function rbCarregarAtividade() {
  clearTimeout(rbz.timerAt);
  const j = await api("/api/atividade").catch(() => null);
  if (j && !j.erro) { at.dados = j; if (rbz.vivo) rbz.foto = null; }
  if (rbz.aberta) { rbRender(); rbz.timerAt = setTimeout(rbCarregarAtividade, 20000); }
}

// ---------- chip na barra de baixo, gaveta e aviso de rodada concluída ----------
function rbChip() {
  const el = document.getElementById("robo");
  if (!el) return;
  const m = rbModelo(), s = m.s;
  const ruim = !m.ligado || m.avisos.length;
  const txt = !m.ligado ? "Robô desligado" : m.rodando ? `Robô · enviando ${m.esperando.length || ""} ${m.esperando.length === 1 ? "pedido" : "pedidos"}`
    : m.avisos.length ? `Robô · ${m.avisos.length} ${m.avisos.length === 1 ? "problema" : "problemas"}` : m.esperando.length ? `Robô · ${m.esperando.length} esperando` : "Robô · tudo certo";
  el.className = "pill rb-chip " + (ruim ? "vm" : m.rodando ? "az" : "ok");
  el.setAttribute("role", "button"); el.tabIndex = 0;
  el.title = (s.resumo || "") + (s.resposta ? "\n" + s.resposta : "") + "\nClique para ver o que o robô está fazendo";
  const html = `${m.rodando ? rbGira(11) : ruim ? rbIc("al", 12) : rbIc("ok", 12)}${esc(txt)}`;
  if (el._html !== html) { el.innerHTML = html; el._html = html; }
}
function rbRenderGaveta() {
  let g = document.getElementById("rb-gaveta");
  if (!rbz.gaveta || rbz.aberta) { g?.remove(); return; }
  const m = rbModelo(), e = rbEtapaDaRodada(m.env);
  if (!g) { g = document.createElement("div"); g.id = "rb-gaveta"; g.className = "rb-gaveta"; g.setAttribute("role", "status"); document.body.appendChild(g); }
  const linhas = (m.env.linhas || []).slice(-2).map(l => `<span>${esc(l.hora)}</span> ${esc(l.texto.replace(/^\W+\s*/u, ""))}`).join("<br>");
  g.innerHTML = `<div class="rb-g-ct">${m.rodando ? rbGira(13) : rbIc(m.avisos.length || !m.ligado ? "al" : "ok", 14, m.avisos.length || !m.ligado ? "rb-vm" : "rb-ok")}
    <b>${m.rodando ? "Robô · enviando às caixas dos hotéis" : !m.ligado ? "Robô desligado" : m.avisos.length ? `Robô · ${m.avisos.length} precisam de você` : "Robô · tudo certo"}</b></div>
    <div class="rb-g-cx">${m.env.modo ? rbSeg(m) : `<p class="rb-txt">${m.esperando.length ? m.esperando.length + " pedido(s) esperando o próximo envio." : "Nenhum pedido esperando."}</p>`}
    ${linhas ? `<div class="rb-log" style="margin:0 0 12px">${linhas}</div>` : ""}
    <div class="rb-gp-acoes"><button type="button" class="rb-bt pri" data-rb-abrir-tudo>Abrir painel do robô</button><button type="button" class="rb-bt fant" data-rb-recolher>Recolher</button></div></div>`;
}
function rbMostrarFim() {
  document.getElementById("rb-fim")?.remove();
  const m = rbModelo(), ok = m.env.codigo === 0;
  const d = document.createElement("div");
  d.id = "rb-fim"; d.className = "rb-fim" + (ok ? "" : " ruim"); d.setAttribute("role", "status");
  d.innerHTML = `<b>${rbIc(ok ? "ok" : "al", 16, ok ? "rb-ok" : "rb-vm")}${ok ? "Rodada concluída às " : "Rodada terminou com aviso às "}${rbHora(new Date())}</b>
    <p>${esc(m.env.resumo || "Envio terminado.")}${ok ? " Nada foi enviado ao hóspede." : ""}</p>
    <div class="rb-gp-acoes" style="margin-left:26px"><button type="button" class="rb-bt pri" data-rb-abrir-tudo>Abrir o painel do robô</button><button type="button" class="rb-bt fant" data-rb-fim-x>Fechar</button></div>`;
  document.body.appendChild(d);
  clearTimeout(rbz.fimTimer);
  if (ok) rbz.fimTimer = setTimeout(() => d.remove(), 15000);   // com aviso, fica até a pessoa fechar
}
async function rbVigiar() {   // chamado a cada leitura da tela (carregar) e, com a janela aberta ou o robô rodando, a cada poucos segundos
  clearTimeout(rbz.timer);
  const r = await api("/api/envio").catch(() => null);
  if (r) rbz.env = r;
  const rodando = !!rbz.env?.rodando;
  if (rbz.rodou && !rodando && !rbz.aberta && !rbz.gaveta) rbMostrarFim();
  rbz.rodou = rodando;
  rbChip();
  if (rbz.aberta) rbRender();
  rbRenderGaveta();
  rbAgendar();
}
function rbAgendar() {
  clearTimeout(rbz.timer);
  const ms = rbz.env?.rodando ? 2500 : (rbz.aberta || rbz.gaveta) ? 8000 : 0;
  if (ms) rbz.timer = setTimeout(rbVigiar, ms);
}
async function rbEnviarAgora() {
  const b = document.getElementById("rb-agora");
  if (b) b.disabled = true;
  const r = await api("/api/enviar", {});
  if (!r.ok) { toast(r.motivo || "Não deu certo", true); if (b) b.disabled = false; return; }
  rbz.rodou = true;
  rbVigiar();
}
const rbCopiar = (txt, aviso) => navigator.clipboard?.writeText(txt).then(() => toast(aviso), () => toast("Não consegui copiar", true));

// ---------- cliques e teclado ----------
document.addEventListener("click", ev => {
  const alvo = ev.target.closest("[data-abrir-robo],[data-rb-fechar],[data-rb-minimizar],[data-rb-aba],[data-rb-filtro],[data-rb-vivo],[data-rb-ped],[data-rb-fechar-ped],[data-rb-mais],"
    + "[data-rb-ajuda],[data-rb-copiar-ajuda],[data-rb-ver-pedidos],[data-rb-monit],[data-rb-reg],[data-rb-copiar-cru],[data-rb-dias],[data-rb-copiar-dia],[data-rb-copiar-ped],"
    + "[data-rb-no-registro],[data-rb-abrir-tudo],[data-rb-recolher],[data-rb-fim-x],#rb-agora,#robo");
  if (!alvo) return;
  const d = alvo.dataset;
  if (alvo.id === "rb-agora") return rbEnviarAgora();
  if (alvo.id === "robo") { rbz.gaveta = !rbz.gaveta && !rbz.aberta; if (rbz.aberta) return; rbRenderGaveta(); rbAgendar(); if (rbz.gaveta) rbVigiar(); return; }
  if ("abrirRobo" in d) return rbAbrir(d.abrirRobo === "reg" ? "reg" : "agora");
  if ("rbFechar" in d) return rbFechar();
  if ("rbMinimizar" in d) return rbFechar(true);
  if ("rbAbrirTudo" in d) { document.getElementById("rb-fim")?.remove(); rbz.gaveta = false; document.getElementById("rb-gaveta")?.remove(); return rbAbrir("agora"); }
  if ("rbRecolher" in d) { rbz.gaveta = false; return rbRenderGaveta(); }
  if ("rbFimX" in d) return document.getElementById("rb-fim")?.remove();
  if (d.rbAba) { rbz.aba = d.rbAba; rbz.sel = null; return rbRender(); }
  if (d.rbFiltro) { rbz.filtro = d.rbFiltro; return rbRender(); }
  if ("rbVivo" in d) { rbz.vivo = !rbz.vivo; rbz.foto = rbz.vivo ? null : JSON.parse(JSON.stringify(at.dados || { eventos: [] })); return rbRender(); }
  if (d.rbPed) { rbz.sel = rbz.sel === d.rbPed ? null : d.rbPed; return rbRender(); }
  if ("rbFecharPed" in d) { rbz.sel = null; return rbRender(); }
  if (d.rbMais) { rbz.abertos[d.rbMais] = !rbz.abertos[d.rbMais]; return rbRender(); }
  if (d.rbAjuda) { rbz.ajuda[d.rbAjuda] = !rbz.ajuda[d.rbAjuda]; return rbRender(); }
  if (d.rbCopiarAjuda) { const aj = rbAjuda((st.saude || [])[+d.rbCopiarAjuda]?.texto || ""); return rbCopiar((aj.passos || []).map((p, i) => `${i + 1}. ${p.replace(/<[^>]+>/g, "")}`).join("\n"), "Instruções copiadas"); }
  if ("rbVerPedidos" in d) { rbFechar(); return trocarVista("fila"); }
  if ("rbMonit" in d) { rbFechar(); return trocarVista("maquinas"); }
  if (d.rbReg !== undefined) { rbz.abertaReg = rbz.abertaReg === +d.rbReg ? null : +d.rbReg; return rbRender(); }
  if (d.rbCopiarCru !== undefined) { const e = rbEventos()?.lista[+d.rbCopiarCru]; return e && rbCopiar(rbCru(e), "Linha copiada"); }
  if ("rbDias" in d) { rbz.todosDias = !rbz.todosDias; return rbRender(); }
  if ("rbCopiarDia" in d) return rbCopiar((rbEventos()?.lista || []).map(rbCru).join("\n"), "Lista copiada");
  if ("rbCopiarPed" in d) return rbCopiar([...document.querySelectorAll("#rb-gaveta-ped .rb-log")].map(l => l.innerText).join("\n"), "Linhas copiadas");
  if ("rbNoRegistro" in d) { const x = (st.fila || []).find(y => y.chave === rbz.sel); rbz.busca = x?.nome || ""; rbz.aba = "reg"; rbz.filtro = "tudo"; rbz.todosDias = true; rbz.sel = null; return rbRender(); }
});
document.addEventListener("input", ev => {
  if (ev.target.id !== "rb-busca") return;
  rbz.busca = ev.target.value;
  rbRender();
});
document.addEventListener("keydown", ev => {
  if (ev.key === "Escape" && rbz.aberta && rbz.sel) { ev.preventDefault(); ev.stopImmediatePropagation(); rbz.sel = null; rbRender(); return; }   // Esc fecha primeiro a gaveta do pedido
  const alvo = ev.target.closest?.("[data-rb-ped],[data-rb-reg],#robo");
  if (alvo && (ev.key === "Enter" || ev.key === " ")) { ev.preventDefault(); alvo.click(); }
}, true);
