// hospede.js: Ficha do hóspede (João, 09/11/2026, desenho aprovado no Artifact "Ficha do Hóspede").
// Quando chega um FORMULÁRIO (e-mail do Emissor Automático, ou o pedido que aparece na pesquisa), o Painel abre esta página no lugar
// do leitor de e-mail: os campos que o hóspede preencheu, na ordem do formulário, cada um com Copiar, a situação do pedido, o que o
// Painel conferiu, os e-mails e os outros pedidos dele(a). E-mail normal segue pela leitura de sempre (correio_leitura.js).
// A aba "Notas fiscais" ficou reservada para a emissão automática: nada daqui manda para ela.
//
// "Copiar tudo para a emissão" abre uma janelinha EDITÁVEL só com o texto que o João cola na emissão (textoEmissao). Regra dele:
// nada é inventado. Diária e valor total só entram se o hóspede informou; a quantidade de diárias é só a conta das datas; o número
// da estada só se o hóspede escreveu "Estada 2202"; o nome é o do próprio hóspede.
// Usa $/esc/api/toast, regras_nf.js (campoDoPedido, faltaDados, cpfValido), etapas.js e etiqueta.js (mesmo escopo global).
const hp = { chave: "", dados: null, emailId: "", lista: [], carregando: false };

// ---------- o texto da emissão (puro: testado em testes/test_hospede.py) ----------
// "28/10/2026", "28/10/26", "2026-10-28" -> { txt: "28/10/2026", ms }; outra coisa fica como o hóspede escreveu (ms = NaN)
function hpData(v) {
  const t = String(v || "").trim();
  let m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (!m && (m = t.match(/^(\d{4})-(\d{2})-(\d{2})/))) m = [t, m[3], m[2], m[1]];
  if (!m && (m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2})$/))) m = [t, m[1], m[2], "20" + m[3]];
  if (!m) return { txt: t, ms: NaN };
  const [, d, mes, a] = m;
  return { txt: `${d.padStart(2, "0")}/${mes.padStart(2, "0")}/${a}`, ms: Date.UTC(+a, +mes - 1, +d) };
}
const hpDiarias = (ci, co) => { const n = Math.round((co.ms - ci.ms) / 864e5); return Number.isFinite(n) && n > 0 ? n : 0; };
function hpEstada(d) {   // só o que o hóspede escreveu: "Estada 2202", "estada nº 2202", ou um campo chamado Estada com número
  const re = /estada\s*(?:n[º°o.]*\s*)?[:\-]?\s*(\d{2,})/i;
  for (const [k, v] of d.campos || []) {
    const m = re.exec(String(v || ""));
    if (m) return m[1];
    if (/^((numero|n[º°o.]*)\s*(da\s+)?)?estada\b/.test(regrasSemAcento(k)) && /^\d{2,}$/.test(String(v || "").trim())) return String(v).trim();
  }
  return "";
}
function textoEmissao(d) {
  const c = (...t) => campoDoPedido(d, ...t);
  const ci = hpData(c(/check.?in/)), co = hpData(c(/check.?out/)), n = hpDiarias(ci, co);
  const valor = c(/valor.*nota/);   // só se o hóspede informou; a diária fica sempre para ele conferir à mão
  const nome = c(/nome.*titular/, /nome do hospede/) || c(...CAMPO_NOME) || String(d.nome || "").trim();
  const estada = hpEstada(d);
  return ["DATA DE CHECK-IN : " + ci.txt, "DATA DE CHECK-OUT : " + co.txt, "QUANTIDADE DE DIÁRIAS : " + (n || ""),
    "VALOR DA DIÁRIA :", "", "VALOR TOTAL :" + (valor ? " " + valor : ""), nome + (estada ? " - ESTADA " + estada : "")].join("\n");
}

// ---------- achar de onde vêm os dados ----------
// O Painel já liga cada e-mail de formulário ao pedido (na_caixa.id = id do e-mail): é por aí que a ficha abre NA HORA, sem esperar o
// texto do e-mail vir do PC dono da caixa (isso podia levar dezenas de segundos; João, 09/11/2026).
const hpPedidoDoEmailId = id => id ? (st.fila || []).find(s => s.na_caixa?.id === id) || null : null;
const hpEmailDoPedido = s => (cx.dados?.emails || []).find(e => (s?.na_caixa?.id && e.id === s.na_caixa.id) || (e.solicitacao?.chave && e.solicitacao.chave === s?.chave));
function hpNomeDe(d) {
  return campoDoPedido(d, /nome.*titular/, /nome do hospede/) || campoDoPedido(d, ...CAMPO_NOME) || String(d.nome || "").trim() || "Hóspede do formulário";
}
function hpEmailsDele(d) {
  const mail = String(d.email || "").trim().toLowerCase();
  return (cx.dados?.emails || []).filter(e => e.id === hp.emailId || (d.chave && e.solicitacao?.chave === d.chave) || (mail && String(e.de || "").toLowerCase() === mail))
    .sort((a, b) => String(b.quando).localeCompare(String(a.quando))).slice(0, 6);
}
function hpOutrosPedidos(d) {
  const mail = String(d.email || "").trim().toLowerCase(), doc = (campoDoPedido(d, ...CAMPO_DOC) || "").replace(/\D/g, "");
  return (st.fila || []).filter(o => o.chave !== d.chave && ((mail && String(o.email || "").toLowerCase() === mail)
    || (doc.length >= 11 && campoDoPedido(o, ...CAMPO_DOC).replace(/\D/g, "") === doc)))
    .sort((a, b) => String(b.data).localeCompare(String(a.data))).slice(0, 5);
}

// ---------- abrir ----------
function abrirHospede(chave, { lista = [], emailId = "" } = {}) {
  const s = acharPedido(chave);
  if (!s) return;
  Object.assign(hp, { chave: s.chave, dados: s, emailId: emailId || hpEmailDoPedido(s)?.id || "", lista: lista.length > 1 ? lista : [], carregando: false });
  trocarVista("hospede");
}
const emailEhFormulario = e => !!e && e.pasta !== "enviado" && (e.classes || []).includes("formulario");
// O e-mail do Emissor Automático vem do remetente do Emissor, então o Painel nem sempre o liga ao pedido: procura o pedido pelo e-mail do
// hóspede e pelo carimbo do formulário; não achando, a ficha sai dos campos do próprio texto do e-mail.
function hpPedidoDoFormulario(f) {
  const mail = String(f?.email || "").trim().toLowerCase(), carimbo = String(f?.carimbo || "").trim();
  return !mail || !carimbo ? null : (st.fila || []).find(s => String(s.email || "").trim().toLowerCase() === mail && String(s.carimbo || "").trim() === carimbo) || null;
}
function abrirHospedeDoEmail(e) {
  const s = pedidoDoEmail(e) || hpPedidoDoEmailId(e.id) || hpPedidoDoFormulario(formDoTexto(cx.textos[e.id]?.texto));
  if (s) return abrirHospede(s.chave, { emailId: e.id });
  const f = formDoTexto(cx.textos[e.id]?.texto);
  Object.assign(hp, { chave: "", dados: f ? { ...f, hotel: e.hotel || "", nome: e.nome || "" } : null, emailId: e.id, lista: [],
    carregando: !f && (!cx.textos[e.id] || !!cx.textos[e.id].carregando) });   // texto que falhou ou não é formulário: avisa, não fica "lendo" para sempre
  trocarVista("hospede");
  if (hp.carregando) setTimeout(() => {   // o PC dono da caixa não respondeu: 5 s e vira aviso, com o botão "Abrir o e-mail"
    if (hp.carregando && hp.emailId === e.id && !hp.dados) { hp.carregando = false; if (pn.vista === "hospede") desenharHospede(); }
  }, 5000);
}
function hospedeTextoChegou(id) {   // o texto do e-mail terminou de carregar
  if (pn.vista !== "hospede" || hp.emailId !== id || hp.chave) return;
  const e = (cx.dados?.emails || []).find(x => x.id === id);
  if (e) abrirHospedeDoEmail(e);
}

// ---------- tela ----------
const HP_CP = '<svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linejoin="round" aria-hidden="true"><path d="M8 8h11v12H8zM5 16V4h11"/></svg>';
function hpCampo(rot, valor, { mono = false, selo = null, inteiro = false, longo = false } = {}) {
  const vazio = !String(valor || "").trim();
  return `<div class="${inteiro ? "hp-inteiro" : ""}"><span class="hp-rot">${esc(rot)}</span><div class="hp-campo${vazio ? " vazio" : ""}${longo ? " longo" : ""}">
    <span class="hp-v${mono ? " mono" : ""}">${vazio ? "Não informado" : esc(valor)}</span>${selo && !vazio ? `<span class="hp-selo ${selo[1] ? "ok" : "mau"}">${esc(selo[0])}</span>` : ""}
    ${vazio ? "" : `<button type="button" class="hp-cp" data-hp-copiar="${esc(valor)}" aria-label="Copiar ${esc(rot)}">Copiar</button>`}</div></div>`;
}
function hpSeloDoc(v) {
  const dig = String(v || "").replace(/\D/g, "");
  if (!dig) return null;
  const [, obs] = valorDoForm("CPF/CNPJ", v);
  if (dig.length === 11) return cpfValido(v) ? ["CPF válido", true] : ["CPF com dígito errado", false];
  if (dig.length === 14) return cnpjValido(v) ? ["CNPJ válido", true] : ["CNPJ com dígito errado", false];
  return [obs || "Documento incompleto", false];
}
function hpConferencia(d, ci, co) {
  const itens = [], c = (...t) => campoDoPedido(d, ...t);
  const doc = c(...CAMPO_DOC);
  itens.push(!doc.replace(/\D/g, "") ? ["mau", "Documento do tomador não informado"] : (cpfValido(doc) || cnpjValido(doc)) ? ["ok", "CPF/CNPJ do tomador confere"] : ["mau", "CPF/CNPJ do tomador com dígito errado"]);
  itens.push(c(...CAMPO_NOME) ? ["ok", "Nome do tomador preenchido"] : ["mau", "Nome do tomador não informado"]);
  const cep = c(/^cep/, /\bcep\b/);
  itens.push(!cep.replace(/\D/g, "") ? ["mau", "CEP não informado"] : cepValido(cep) ? ["ok", "CEP preenchido"] : ["mau", "CEP incompleto"]);
  const n = hpDiarias(ci, co);
  if (!ci.txt || !co.txt) itens.push(["mau", "Datas da hospedagem não informadas"]);
  else if (!Number.isFinite(ci.ms) || !Number.isFinite(co.ms)) itens.push(["mau", "Não consegui ler as datas da hospedagem"]);
  else itens.push(n ? ["ok", `Datas coerentes (${n} diária${n > 1 ? "s" : ""})`] : ["mau", "Check-out não vem depois do check-in"]);
  for (const x of typeof faltaExtras === "function" ? faltaExtras(d) : []) itens.push(["mau", `${x[0].toUpperCase() + x.slice(1)} não informado`]);
  return itens;
}
function hpLinhaEmail(e) {
  const form = (e.classes || []).includes("formulario");
  return `<li><time>${esc(horaCurta(e.quando))}</time><button type="button" class="hp-link as" data-hp-email="${esc(e.id)}" title="${esc(e.assunto || "")}">${esc(e.assunto || "(sem assunto)")}</button>
    <span class="hp-chip${form ? "" : e.respondido ? " ok" : ""}">${form ? "Formulário" : e.respondido ? "Respondido" : "Recebido"}</span></li>`;
}
function desenharHospede() {
  const el = $("hp");
  if (!el) return;
  const d = hp.dados;
  const voltar = `<button type="button" class="hp-voltar" data-hp-voltar>‹ Voltar</button>`;
  if (!d) {
    const abrir = hp.emailId ? `<p><button type="button" class="hp-bt" data-hp-abrir-email><svg class="ic"><use href="#i-mail"/></svg>Abrir o e-mail</button></p>` : "";
    el.innerHTML = `<div class="hp-janela"><div class="hp-faixa">${voltar}</div><div class="hp-vazio">${hp.carregando ? "Lendo o formulário no PC dono da caixa…" :
      "Não consegui ler os dados do formulário agora."}${abrir}</div></div>`;
    return;
  }
  const c = (...t) => campoDoPedido(d, ...t);
  const ci = hpData(c(/check.?in/)), co = hpData(c(/check.?out/)), n = hpDiarias(ci, co);
  const doc = c(...CAMPO_DOC), docF = doc ? valorDoForm("CPF/CNPJ", doc)[0] : "", cpfT = c(/cpf.*titular/);
  const cepF = valorDoForm("CEP", c(/^cep/, /\bcep\b/))[0], telF = valorDoForm("Telefone", c(/telefone|celular|whatsapp/))[0];
  const falta = faltaDados(d), sit = situacaoDoPedido(d), ehPedido = !!d.chave;
  const hotel = d.hotel || (cx.dados?.emails || []).find(e => e.id === hp.emailId)?.hotel || "";
  const pz = d.prazo ? prazoInfo(d.prazo) : null;
  const m = etapasModelo({ hora: String(d.carimbo || d.data || "").slice(0, 16), falta, semFormulario: false, notas: [], nfsEnviadas: d.nfs?.length ? d.nfs.map(nf => ({ nf })) : [],
    situacaoPedido: ehPedido ? sit : "", temPedido: ehPedido, reconhece: RECONHECE_NF });
  const usados = new Set();
  const pega = (...t) => { const k = (d.campos || []).find(([r]) => t.some(x => x.test(regrasSemAcento(r)))); if (k) usados.add(k); return k ? String(k[1] || "").trim() : ""; };
  const f = { doc: pega(...CAMPO_DOC), tom: pega(...CAMPO_NOME), cep: pega(/^cep/, /\bcep\b/), tel: pega(/telefone|celular|whatsapp/), cpfT: pega(/cpf.*titular/),
    nomeT: pega(/nome.*titular/, /nome do hospede/), ci: pega(/check.?in/), co: pega(/check.?out/), info: pega(/informac/, /o que.*nota/, /itens/),
    div: pega(/^nota dividida/), divEm: pega(/dividida em|quantas vezes/), valor: pega(/valor.*nota/) };
  const semAc = regrasSemAcento;
  const resto = (d.campos || []).filter(k => !usados.has(k) && String(k[1] || "").trim() && !OCULTOS_FORM.test(semAc(k[0])) && !/^termos/.test(semAc(k[0])));
  const termos = (d.campos || []).find(([k]) => /^termos/.test(semAc(k)));
  const dividida = f.div ? (f.divEm && /^sim/i.test(f.div) ? `${f.div}, em ${f.divEm}` : f.div) : "";
  const pils = hp.lista.length > 1 ? `<div class="hp-pils" role="group" aria-label="Hóspedes encontrados">${hp.lista.map(k => { const o = acharPedido(k); return o ? `<button type="button" class="hp-pil" data-hp-abrir="${esc(k)}" aria-pressed="${k === hp.chave}"><b>${esc(hpNomeDe(o))}</b><span>${esc(o.hotel)} · ${esc(dataBr(o.data).slice(0, 5))} · ${esc(nomeSituacao(o))}</span></button>` : ""; }).join("")}</div>` : `<div class="hp-pils"></div>`;
  const principal = m.principal.acao === "pedir" && d.email ? `<button type="button" class="hp-bt prim" data-hp-pedir>Pedir o que falta</button>`
    : m.principal.acao === "nf" && hp.emailId ? `<button type="button" class="hp-bt prim" data-hp-enviar-nf><svg class="ic"><use href="#i-enviar"/></svg>Enviar NF</button>` : "";
  const mails = hpEmailsDele(d), outros = ehPedido ? hpOutrosPedidos(d) : [];
  const dataPedido = d.data ? dataBr(d.data) : "", horaPedido = String(d.carimbo || "").trim();
  el.innerHTML = `<div class="hp-janela">
    <div class="hp-faixa">${voltar}${pils}<button type="button" class="hp-mails" data-hp-mails>E-mails dele(a)</button></div>
    <div class="hp-cab"><div><h2>${esc(hpNomeDe(d))}</h2><div class="hp-sub">${hotel ? `<span class="hp-chip">${esc(hotel)}</span>` : ""}
        ${pecaSituacao(sit, { texto: sit === "falta" ? `Falta dado: ${falta.join(", ")}` : "" })}${pz ? `<span class="hp-chip ${pz.nivel === "vencido" ? "mau" : pz.nivel === "perto" ? "med" : ""}">Prazo ${esc(pz.texto)}</span>` : ""}
        ${dataPedido || horaPedido ? `<span>Pedido de ${esc(horaPedido || dataPedido)}</span>` : ""}</div></div>
      <div class="hp-acoes"><button type="button" class="hp-bt" data-hp-emissao>${HP_CP}Copiar tudo para a emissão</button>
        ${hp.emailId ? `<button type="button" class="hp-bt" data-hp-abrir-email><svg class="ic"><use href="#i-mail"/></svg>Abrir e-mail do pedido</button>` : ""}${principal}</div></div>
    <div class="hp-miolo"><div class="hp-form">
      <section class="hp-sec"><div class="hp-sec-t"><h3>Quem vai receber a nota</h3><small>Documento Tomador · Nome Tomador</small></div><div class="hp-campos">
        ${hpCampo("Documento do tomador (CPF/CNPJ)", docF || f.doc, { mono: true, selo: hpSeloDoc(f.doc) })}${hpCampo("Nome do tomador", f.tom)}
        ${hpCampo("E-mail", d.email || "")}${hpCampo("Telefone para contato", telF || f.tel, { mono: true })}${hpCampo("CEP", cepF || f.cep, { mono: true })}</div></section>
      <section class="hp-sec"><div class="hp-sec-t"><h3>Titular da reserva</h3></div><div class="hp-campos">
        ${hpCampo("CPF do titular da reserva", cpfT ? valorDoForm("CPF", cpfT)[0] : "", { mono: true, selo: hpSeloDoc(cpfT) })}${hpCampo("Nome do titular da reserva", f.nomeT)}
        ${hpCampo("Check-in da hospedagem", ci.txt, { mono: true })}${hpCampo("Check-out da hospedagem", co.txt ? co.txt + (n ? ` · ${n} diária${n > 1 ? "s" : ""}` : "") : "", { mono: true })}</div></section>
      <section class="hp-sec"><div class="hp-sec-t"><h3>O que o hóspede pediu</h3></div><div class="hp-campos">
        ${hpCampo("Informações necessárias na nota fiscal", f.info, { inteiro: true, longo: true })}${hpCampo("Nota dividida", dividida)}${f.valor ? hpCampo("Valor da nota", f.valor, { mono: true }) : ""}
        ${hpCampo("Enviado pelo formulário em", String(d.carimbo || "").trim() || dataPedido, { mono: true })}</div></section>
      ${resto.length || termos ? `<section class="hp-sec"><div class="hp-sec-t"><h3>Outros campos</h3></div><div class="hp-campos">${resto.map(([k, v]) => hpCampo(k, v, { inteiro: String(v).length > 60, longo: true })).join("")}
        ${termos ? hpCampo("Termos de aceite", termos[1], { inteiro: true }) : ""}</div></section>` : ""}
    </div><div class="hp-lado">
      <section class="hp-card"><h3>Situação</h3><p class="hp-situ">${esc(hpSituacaoFrase(sit, falta, pz, d))}</p><ol class="hp-et">${m.passos.map(p =>
        `<li class="${/feita/.test(p.cls) ? "feito" : /atual/.test(p.cls) ? "agora" : "falta"}">${esc(p.nome)}${p.sub ? `<small>${esc(p.sub)}</small>` : ""}</li>`).join("")}</ol></section>
      <section class="hp-card"><h3>O Painel conferiu</h3><ul class="hp-conf">${hpConferencia(d, ci, co).map(([t, x]) => `<li><span class="m ${t}">${t === "ok" ? "✓" : "!"}</span><span>${esc(x)}</span></li>`).join("")}</ul></section>
      <section class="hp-card"><h3>E-mails dele(a)</h3><ul class="hp-lst">${mails.length ? mails.map(hpLinhaEmail).join("") : `<li class="vazio">Nenhum e-mail ligado.</li>`}</ul></section>
      ${ehPedido ? `<section class="hp-card"><h3>Outros pedidos</h3><ul class="hp-lst">${outros.length ? outros.map(o =>
        `<li><time>${esc(dataBr(o.data).slice(0, 5))}</time><button type="button" class="hp-link as" data-hp-abrir="${esc(o.chave)}">${esc(o.hotel)}</button><span class="hp-chip">${esc(nomeSituacao(o))}</span></li>`).join("") : `<li class="vazio">Só este pedido.</li>`}</ul></section>` : ""}
    </div></div></div>`;
}
function hpSituacaoFrase(sit, falta, pz, d) {
  if (sit === "enviada") return "Concluído" + (d.nfs?.length ? `. NF ${d.nfs.join(", ")} enviada.` : ".");
  if (sit === "pronta") return "A nota existe, mas falta enviar ao hóspede.";
  if (sit === "falta") return "Falta dado para emitir: " + falta.join(", ") + ".";
  return "Falta emitir a nota." + (pz ? " Prazo " + pz.texto + "." : "");
}

// ---------- a janelinha editável ----------
function copiarTexto(txt) {
  return (navigator.clipboard?.writeText(txt) || Promise.reject()).then(() => true, () => false);
}
function abrirJanelaEmissao(d) {
  if (document.querySelector(".hp-pop-fundo")) return;
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo hp-pop-fundo";
  fundo.innerHTML = `<div class="modal hp-pop" role="dialog" aria-modal="true" aria-labelledby="hp-pop-t">
    <div class="hp-pop-cab"><div><h3 id="hp-pop-t">Dados para a emissão</h3><small>${esc(hpNomeDe(d))}${d.hotel ? " · " + esc(d.hotel) : ""}</small></div>
      <button type="button" class="hp-pop-x" data-hp-pop-fechar aria-label="Fechar">×</button></div>
    <textarea class="hp-pop-txt" id="hp-pop-txt" rows="7" spellcheck="false" aria-label="Texto para a emissão (pode editar)"></textarea>
    <p class="hp-pop-dica" id="hp-pop-dica">Pode editar antes de copiar. Isso não muda a ficha.</p>
    <div class="hp-pop-ac"><button type="button" class="hp-bt prim" id="hp-pop-copiar">Copiar</button><button type="button" class="hp-bt" data-hp-pop-fechar>Fechar</button></div></div>`;
  document.body.appendChild(fundo);
  const txt = $("hp-pop-txt"), dica = $("hp-pop-dica"), bt = $("hp-pop-copiar");
  let editado = false;
  const fechar = () => { document.removeEventListener("keydown", tecla, true); fundo.remove(); };
  const tecla = e => { if (e.key === "Escape" && !editado) { e.stopPropagation(); fechar(); } };   // editou: só Fechar e × (não perde o que digitou)
  document.addEventListener("keydown", tecla, true);
  const copiar = async () => {
    const ok = await copiarTexto(txt.value);
    bt.textContent = ok ? "Copiado" : "Não copiou: selecione e copie"; setTimeout(() => { bt.textContent = "Copiar"; }, 1500);
    if (!ok) txt.select();
  };
  txt.value = textoEmissao(d);
  txt.addEventListener("input", () => { editado = true; dica.textContent = "Editado. Clique em Copiar para levar a sua versão."; dica.classList.add("editado"); });
  bt.onclick = copiar;
  fundo.addEventListener("click", e => { if (e.target.closest("[data-hp-pop-fechar]") || (e.target === fundo && !editado)) fechar(); });
  copiar();   // já copia ao abrir; o botão Copiar repete se precisar
  bt.focus();
}

// ---------- cliques ----------
document.addEventListener("click", e => {
  const t = e.target.closest("#v-hospede [data-hp-voltar],#v-hospede [data-hp-abrir],#v-hospede [data-hp-copiar],#v-hospede [data-hp-emissao],#v-hospede [data-hp-abrir-email],"
    + "#v-hospede [data-hp-enviar-nf],#v-hospede [data-hp-pedir],#v-hospede [data-hp-email],#v-hospede [data-hp-mails]");
  if (!t) return;
  const d = t.dataset;
  if ("hpVoltar" in d) { cx.sel = null; return trocarVista("correio"); }
  if (d.hpAbrir) return abrirHospede(d.hpAbrir, { lista: hp.lista });
  if ("hpCopiar" in d) return void copiarTexto(d.hpCopiar).then(ok => toast(ok ? `Copiado: ${d.hpCopiar.length > 40 ? d.hpCopiar.slice(0, 40) + "…" : d.hpCopiar}` : "Não deu pra copiar agora", !ok));
  if ("hpEmissao" in d) return abrirJanelaEmissao(hp.dados);
  if ("hpAbrirEmail" in d) return hpAbrirEmailNormal(hp.emailId);
  if ("hpEnviarNf" in d) return abrirEnvioNF(null, { id: hp.emailId, comNF: true });
  if ("hpPedir" in d) return abrirEnvioNF(null, { novo: true, para: hp.dados.email, conta: hp.dados.na_caixa?.caixa || "", solicitar: true, faltas: [...faltaDados(hp.dados), ...faltaExtras(hp.dados)] });
  if (d.hpEmail) {
    const x = (cx.dados?.emails || []).find(m => m.id === d.hpEmail);
    return x && (emailEhFormulario(x) ? abrirHospedeDoEmail(x) : hpAbrirEmailNormal(x.id));
  }
  if ("hpMails" in d) {   // os e-mails dele(a) na lista: a pesquisa pelo e-mail (ou pelo nome)
    $("busca").value = hp.dados?.email || hpNomeDe(hp.dados || {}); cx.sel = null; trocarVista("correio"); agendarBusca();
  }
});
function hpAbrirEmailNormal(id) {   // "Abrir e-mail do pedido": a leitura de sempre, sem voltar para a ficha
  cx.caixa = "entrada"; cx.soForm = false; cx.semFicha = true;
  trocarVista("correio");
  abrirEmail(id);
  cx.semFicha = false;
}
