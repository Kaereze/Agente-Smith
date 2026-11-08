// telas_dados.js: parte de telas.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// soSeMudou (velocidade 3): volta automática — pedidos e e-mails iguais aos que a tela já tem = não redesenha.
// Quem chama depois de uma ação (marcar, excluir...) usa carregar() e a tela redesenha sempre, como antes.
let emCarga = 0;
async function carregar(soSeMudou = false) { emCarga++; try { return await carregarJa(soSeMudou); } finally { emCarga--; } }
async function carregarJa(soSeMudou){
  try {
    // dias: o dobro da janela da Visão geral (o resumo compara com o período anterior inteiro)
    const dias = periodo === "0" ? 0 : Math.max(typeof pn !== "undefined" && pn.vista === "gerencia" ? 75 : 45, 2 * (typeof pn !== "undefined" ? pn.janela : 30));
    const j = await api("/api/estado?dias=" + dias + "&vista=" + (typeof pn !== "undefined" ? pn.vista : ""));   // período menor é filtrado aqui
    ultimoOk = Date.now();
    if (j.erro === "não autorizado") { location.reload(); return; }   // servidor reiniciado (atualização): pega a sessão nova
    // tela nova no disco (atualização sem reinício): recarrega, mas nunca com uma mensagem sendo escrita
    if (j.pagina && j.pagina !== PAGINA && !document.querySelector(".modal-fundo") && !(typeof envNF !== "undefined" && envNF)) {
      location.reload(); return;
    }
    let em = null;
    if (soSeMudou && j.__igual) {   // pedidos iguais: e os e-mails? iguais também = a tela fica como está
      try { em = await api("/api/emails"); } catch (e) { em = {}; }
      if (em.__igual) {   // só o cabeçalho muda: hora da leitura e PCs no ar
        st = {...st, atualizado_em: j.atualizado_em, pcs: j.pcs || st.pcs};
        if (!j.erro) $("sync-txt").textContent = "Central sincronizada " + quando(j.atualizado_em).slice(-5);
        desenharPcsCabecalho(st.pcs);
        carregarCorreio(true); avisoParado(); clearTimeout(timer); timer = setTimeout(() => carregar(true), intervalo * 1000); return;
      }
    }
    const roboAntes = JSON.stringify(st.status || {});
    st = {...st, ...j}; intervalo = j.atualizar_segundos || 15;
    // pedido repetido (Etapa 2): conta 1 vez só; o repetido fica ligado ao principal e abre pelo detalhe dele
    if (j.fila) { st.filaRep = j.fila.filter(s => s.repetido_de); st.fila = j.fila.filter(s => !s.repetido_de); }

    desenharOperador(j.agente, j.operadores || [], j.pc);
    $("pill-demo").classList.toggle("oculta", !j.demo);
    $("pill-casa").classList.toggle("oculta", !j.so_ver);
    document.documentElement.classList.toggle("e-admin", !!j.admin);
    if (j.tema !== undefined && j.tema !== temaServidor) { temaServidor = j.tema; if (j.tema !== (document.documentElement.dataset.theme || "")) aplicarTema(j.tema); }
    if (!j.atualizado_em && !j.erro) {   // primeira leitura da planilha ainda em andamento
      $("sync-txt").textContent = "lendo a planilha…"; $("lista").innerHTML = `<div class="vazio">Carregando solicitações…</div>`;
      clearTimeout(timer); timer = setTimeout(carregar, 2000); return;
    }
    const ok = !j.erro;
    $("sync-dot").className = "dot " + (ok ? "on" : "off");
    $("sync-txt").textContent = ok ? "Central sincronizada " + quando(j.atualizado_em).slice(-5) : "sem conexão com a planilha";
    const s = j.status || {};
    if (typeof rbChip === "function") rbChip();   // o chip do robô (robo.js) mostra o estado, o resumo e a resposta
    desenharPcsCabecalho(j.pcs || []);
    desenharSaude(j.saude || []);
    window.caixasProblema?.(j.saude || []);   // botão de caixas com problema (pecas/caixas.js)
    // pedidos aparecem já; os e-mails (outra rota) entram em seguida, sem segurar a tela
    montarTodos();
    try { if (!em) em = await api("/api/emails"); if (em.emails) { st.emails = em.emails; st.este_pc = em.este_pc; } } catch(e) {}
    montarTodos();
    carregarCorreio(soSeMudou);
    if (pn.vista === "visao") desenharVisao();
    if (pn.vista === "gerencia") desenharGerencia();
    if (typeof rbVigiar === "function") rbVigiar();   // chip do robô na barra de baixo (robo.js)
  } catch(e) {
    $("sync-dot").className = "dot off"; $("sync-txt").textContent = "app desconectado";
  }
  avisoParado();
  clearTimeout(timer); timer = setTimeout(() => carregar(true), intervalo * 1000);
}

// Tela que se atualiza sozinha (velocidade 3, 21/10/2026): a cada 3 s pergunta ao Painel deste PC se tem dado novo
// (leitura da Central, NF do Dropbox, envio que terminou). Só relê quando tem; a volta de 15 s continua de garantia.
let marcaTela = null;
setInterval(async () => {
  if (document.visibilityState !== "visible" || emCarga) return;
  try {
    const r = await fetch("/api/versao", {headers: {"X-Token": TOKEN}});
    const j = await r.json();
    if (!j.v) return;
    if (marcaTela !== null && j.v !== marcaTela) { clearTimeout(timer); carregar(true); }
    marcaTela = j.v;
  } catch (e) { /* a volta de 15 s cobre */ }
}, 3000);

// Tela que não trava (usuário, 21/10/2026, desenho Pr6): 1 min sem resposta do servidor com a tela à vista acende a faixa
// laranja; F5 recarrega (a janela do app desliga as teclas do navegador; Ctrl+R continua sendo Responder, correio.js);
// a janela (app_janela) pergunta se a tela
// está viva por window.__painelVivo.
let ultimoOk = Date.now(), f5Pedido = 0;
window.__painelVivo = () => Date.now() - ultimoOk;
function avisoParado() {
  const parado = Date.now() - ultimoOk > 60000 && document.visibilityState === "visible";
  if (parado) $("aviso-parado-txt").textContent = `há ${Math.max(1, Math.round((Date.now() - ultimoOk) / 60000))} min`;
  $("aviso-parado").classList.toggle("oculta", !parado);
}
function recarregarTela() {   // com mensagem sendo escrita, pede o 2º aperto (não perde o texto sem querer)
  const escrevendo = document.querySelector(".modal-fundo") || (typeof envNF !== "undefined" && envNF);
  if (escrevendo && Date.now() - f5Pedido > 3000) { f5Pedido = Date.now(); toast("Tem mensagem sendo escrita. Aperte F5 de novo para recarregar mesmo assim.", true); return; }
  location.reload();
}
document.addEventListener("keydown", e => {
  if (e.key === "F5" && !e.ctrlKey && !e.altKey && !e.shiftKey) { e.preventDefault(); recarregarTela(); }
});
$("aviso-parado-bt").addEventListener("click", recarregarTela);
document.addEventListener("visibilitychange", () => {   // janela mostrada de novo: dados na hora, sem esperar os 15 s
  if (document.visibilityState === "visible" && Date.now() - ultimoOk > 20000) { clearTimeout(timer); carregar(); }
});

function montarTodos() {
    AG = {}; (st.hoteis || []).forEach(h => AG[h.hotel] = h.agente);
    // Hóspede respondeu dizendo que falta nota/diária: o pedido dele não está resolvido, mesmo com NF
    const faltas = {};
    st.emails.forEach(m => { if (m.falta_nota && m.solicitacao) faltas[m.solicitacao.chave] = m.falta_nota; });
    st.fila.forEach(s => { s.falta_nota = faltas[s.chave] || ""; if (s.falta_nota && s.situacao === "concluida") s.situacao = "nf_parcial"; });
    TODOS = espelhoCaixa().map(s => ({tipo: "form", id: s.chave, s, hoteis: [s.hotel],
                                      quando: s.na_caixa?.recebido || (s.data + "T" + horaDoCarimbo(s.carimbo))}))
      .concat(st.emails.map(m => ({tipo: "email", id: m.id, m, hoteis: m.hotel.split(" / "), quando: m.recebido || ""})))
      .sort((a, b) => b.quando.localeCompare(a.quando));
    desenhar();
}

// Notas fiscais = o que está na Caixa de Entrada do Outlook dos 4 PCs (usuário, 11/10/2026): a solicitação do robô
// saiu da caixa (movida ou excluída), sai daqui. Pedido repetido: se só o repetido está na caixa, aparece ele.
function espelhoCaixa() {
  const principais = new Set(st.fila.filter(s => s.na_caixa).map(s => s.chave));
  return st.fila.filter(s => s.na_caixa).concat((st.filaRep || []).filter(s => s.na_caixa && !principais.has(s.repetido_de)));
}
const nomePc = pc => (st.pcs || []).find(p => p.pc === pc)?.agente || pc;
// bolinha com a inicial e a cor do operador dono da caixa (só no "Todos": com um operador escolhido é redundante)
const opMini = nome => nome && escopoAtual() === "todos"
  ? `<span class="op-mini" style="background:${corOp(nome)}" title="Caixa de ${esc(nome)}">${esc(inicial(nome))}</span>` : "";
function agentesDo(it) {
  if (it.tipo === "form" && it.s.na_caixa?.pc) return [nomePc(it.s.na_caixa.pc)];   // quem tem a caixa no Outlook
  const a = it.hoteis.map(h => AG[h]).filter(Boolean);
  return a.length ? a : it.tipo === "email" ? [it.m.agente_pc] : [];
}
function passaSit(it, f) {
  if (it.tipo === "email") {
    const m = it.m;
    return f === "todos" ? true : f === "sem_nf" ? !m.notas?.length : f === "com_nf" ? !!m.notas?.length
      : f === "falta_nota" ? !!m.falta_nota : f === "dividida" ? m.quartos >= 2 : true;
  }
  const s = it.s;
  if (f === "todas") return true;
  if (f === "envio_pendente") return !!s.envio_pendente;
  if (f === "aberto") return s.situacao !== "concluida";
  if (f === "atrasadas") return s.situacao !== "concluida" && diasDesde(s.data) > PRAZO.med;
  if (f === "doc_diferente") return !!(s.alerta_doc && s.alerta_doc.length);
  if (f === "minhas") return s.dono === st.agente && s.situacao !== "concluida";
  if (f === "urgentes") return !!motivoUrgente(s);
  if (f === "falta_dado") return faltaDados(s).length > 0;
  if (f === "dividida") return !!s.dividida;
  if (f === "concluida") return s.situacao === "concluida" && !s.envio_pendente;   // "NF enviada": só a que saiu (21/10/2026)
  return s.situacao === f;
}
// O que é preciso pra emitir (campoDoPedido, faltaDados, faltaExtras): pecas/regras_nf.js
// Urgência (usuário, 14/10/2026): prazo perto de vencer (ou vencido) ou o hóspede cobrou de novo
function motivoUrgente(s) {
  if (s.situacao === "concluida") return "";
  if ((st.filaRep || []).some(r => r.repetido_de === s.chave)) return "Cobrou de novo";
  const i = prazoInfo(s.prazo);
  return !i ? "" : i.resta <= 0 ? "Prazo vencido" : i.resta <= 6 ? "Vence em " + i.tempo : "";
}
function tagsPedido(s) { return etiquetasDoPedido(s); }   // a peça única das etiquetas (pecas/etiqueta.js)
function faltaBanner(s) {
  const falta = faltaDados(s);
  if (!falta.length) return "";
  const txt = { "nome": "o nome de quem vai na nota", "CPF/CNPJ": "o CPF ou CNPJ", "o que quer na nota": "o que entra na nota (diárias, consumo ou estacionamento)" };
  return `<div class="falta-banner" role="status"><div><b>Falta ${falta.length} dado${falta.length > 1 ? "s" : ""} para emitir</b>
    <span>O hóspede não informou ${esc(falta.map(f => txt[f] || f).join(", "))}.</span></div>
    <button type="button" class="dest" data-pedir-dados="${esc(s.chave)}">Pedir o que falta</button></div>`;
}
// Prazo de atendimento: quantos dias o pedido (ou o e-mail) espera
// Pedidos dos últimos 45 dias (os contadores de sempre); st.fila pode trazer mais, pra comparar períodos
const filaBase = () => { const d = new Date(); d.setDate(d.getDate() - 45); const c = d.toLocaleDateString("sv-SE"); return st.fila.filter(s => !s.data || s.data >= c); };
const diasDesde = iso => Math.max(0, Math.round((new Date(hojeIsoF() + "T12:00") - new Date(String(iso).slice(0, 10) + "T12:00")) / 864e5));
const PRAZO = { ok: 2, med: 7 };   // até 2 dias verde, até 7 âmbar, acima vermelho
// Prazo (SLA) da Etapa 2 (usuário, 09/10/2026): correção e cobrança 24 h, pedido 48 h, dias corridos. O servidor manda
// quando vence; o que falta é contado aqui, então o selo anda sozinho entre as atualizações.
function prazoInfo(p) {
  if (!p || !p.vence) return null;
  const resta = (new Date(p.vence) - Date.now()) / 36e5, h = Math.abs(resta);
  const nivel = resta <= 0 ? "vencido" : resta <= p.horas / 2 ? "perto" : "ok";
  const tempo = h < 1 ? Math.max(1, Math.round(h * 60)) + " min" : h < 48 ? Math.round(h) + " h" : Math.round(h / 24) + " dias";
  return { nivel, resta, tempo, texto: resta <= 0 ? "venceu há " + tempo : "vence em " + tempo };
}
function prazoHtml(p, mini = false, semPrazo = "—") {
  const i = prazoInfo(p);
  if (!i) return `<span class="prazo fim">${semPrazo}</span>`;
  return `<span class="prazo ${i.nivel} ${mini ? "mini" : ""}" title="Prazo de ${esc(p.nome)}: ${p.horas} h, dias corridos (${i.texto})">${
    mini ? "⏱ " + (i.resta <= 0 ? "venceu" : i.tempo) : i.texto}</span>`;
}
function esperaHtml(it) {
  if (it.tipo === "form") return prazoHtml(it.s.prazo, false, it.s.situacao === "tratativa" ? "com o hóspede" : "—");
  const resolvido = false;
  if (resolvido) return `<span class="espera fim">—</span>`;
  const d = diasDesde(it.quando);
  const cls = d <= PRAZO.ok ? "ok" : d <= PRAZO.med ? "med" : "alto";
  return `<span class="espera ${cls}" title="Esperando desde ${dataBr(it.quando.slice(0, 10))}">${d === 0 ? "hoje" : d === 1 ? "1 dia" : d + " dias"}</span>`;
}
function corteDoPeriodo() {
  if (periodo === "0") return "";
  const d = new Date(); d.setDate(d.getDate() - Number(periodo));   // igual ao corte do servidor (dias=45)
  return d.toLocaleDateString("sv-SE");
}
// Busca do jeito do Outlook: sem acento e sem maiúscula ("Corné" acha "CORNELIO"), pedaço de palavra, cada
// palavra digitada em qualquer campo (nome, e-mail, assunto, corpo, anexos, NF, CPF/CNPJ com ou sem pontuação)
const semAcento = s => String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
const soDigitos = s => s.replace(/(\d)[.\-\/\s](?=\d)/g, "$1");
function textoDo(it) {
  if (!it._t) {
    const t = semAcento((it.tipo === "form"
      ? [it.s.nome, it.s.email, it.s.hotel, it.s.carimbo, it.s.nfs.map(n => "nf " + n).join(" "), it.s.dono,
         it.s.falta_nota, ...it.s.campos.map(c => c[0] + " " + c[1])]
      : [it.m.nome, it.m.de, it.m.assunto, it.m.hotel, it.m.caixa, it.m.agente_pc, it.m.texto, (it.m.anexos || []).join(" "),
         (it.m.hospedes_quartos || []).join(" "), it.m.falta_nota]).join(" \n "));
    it._t = t + " \n " + soDigitos(t);
  }
  return it._t;
}
// "NF 196" é o número exato da nota (não acha 1960 nem o 196 de um telefone); o resto é pedaço de palavra
let _termos = ["", []];
const escRe = s => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
function termosDaBusca(busca) {
  if (_termos[0] === busca) return _termos[1];
  const termos = [];
  const resto = semAcento(busca).replace(/\bnfs?-?e?\s*(?:n[º°o]\.?\s*)?(\d+)\b/g, (_, n) => {
    termos.push(new RegExp(`nf\\S*\\s*(?:n[º°o]\\.?\\s*)?${n}(?!\\d)`)); return " ";
  });
  resto.split(/\s+/).filter(Boolean).map(soDigitos).forEach(p => termos.push(new RegExp(escRe(p))));
  _termos = [busca, termos];
  return termos;
}
function passa(it, ignorar = "", busca) {   // ignorar: "origem|sit"...
  if (!ignorar.includes("origem") && it.tipo !== origem) return false;
  // pesquisando, procura na aba inteira: situação, hotel, agente e período não escondem o que bate
  if (busca) return termosDaBusca(busca).every(re => re.test(textoDo(it)));
  if (!ignorar.includes("sit") && !passaSit(it, it.tipo === "form" ? filtro : filtroEmail)) return false;
  if (!ignorar.includes("agente") && agenteF && !agentesDo(it).includes(agenteF)) return false;
  if (!ignorar.includes("escopo") && !doAgente(agentesDo(it))) return false;
  if (!ignorar.includes("hotel") && !fhPassa(it.hoteis)) return false;
  if (it.tipo === "form") return true;   // espelho da caixa: sem período nem "e-mail ao hotel" (está tudo no Outlook)
  if (!ignorar.includes("envio") && it.tipo === "form" && !ENVIO[envio][1](it.s)) return false;
  const corte = ignorar.includes("periodo") ? "" : corteDoPeriodo();
  if (corte && it.quando.slice(0, 10) < corte) return false;
  return true;
}
const ln = (attrs, rotulo, n, atual, bola) =>
  `<button class="ln ${n === 0 ? "vazio-n" : ""}" ${attrs} aria-current="${atual}">${bola ? `<span class="bola" style="background:${bola}"></span>` : ""}${esc(rotulo)}${n !== "" ? `<span class="n">${n.toLocaleString("pt-BR")}</span>` : ""}</button>`;

// Nota dividida: quantas das partes já têm NF ("Dividida em quantas vezes"; sem número = 2)
function tagDivisao(s) {
  const partes = Math.max(s.partes || 1, 2), feitas = s.nfs.length, falta = partes - feitas;
  if (!feitas) return "";
  return feitas >= partes ? `<span class="tag nf-ok" title="NF ${esc(s.nfs.join(", "))}">NF emitida</span>`
    : `<span class="tag nf-parc" title="NF ${esc(s.nfs.join(", "))} · ${feitas} de ${partes}">falta ${falta} nota${falta > 1 ? "s" : ""}</span>`;
}
// NF emitida x e-mail com a NF enviado ao hóspede (a colega emite e esquece de mandar)
const textoEnvio = v => `NF ${v.nfs.join(", ")} enviada para ${v.para} em ${v.quando}`;
const marcaEnvio = s => s.envio_pendente ? `<span class="envio pend" title="A NF existe, mas nenhum e-mail com ela saiu para o hóspede">envio pendente</span>`
  : s.envios?.length && s.nfs.length ? `<span class="envio ok" title="${esc(s.envios.map(textoEnvio).join("\n"))}">enviada ✓</span>` : "";
// Hóspede diz que ainda falta nota/diária (frase dele na dica)
const tagFalta = frase => frase ? `<span class="tag falta" title="${esc(frase)}">falta nota</span>` : "";
const quadroFalta = frase => frase ? `<section class="ficha"><div class="ficha-tit"><span class="rot" style="color:var(--erro)">O hóspede diz que ainda falta nota</span>
  <span class="tag falta">falta nota</span></div><div class="ficha-corpo">“${esc(frase)}”</div></section>` : "";
// Voucher anexado ao e-mail com 2+ quartos (um hóspede por quarto) = nota dividida
const tagQuartos = m => m.quartos >= 2
  ? `<span class="tag" title="${esc((m.hospedes_quartos || []).join(" · "))}">dividida · ${m.quartos} quartos</span>` : "";
// O hóspede pediu dividida e depois aceitou uma nota só: a frase dele fica no título
const tagNotaUnica = s => s.nota_unica ? `<span class="tag nf-ok" title="${esc(s.nota_unica)}">1 nota a pedido do hóspede</span>` : "";
