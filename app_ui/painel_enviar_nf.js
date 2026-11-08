// painel_enviar_nf.js: parte de painel.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// ---------- Enviar NF ao hóspede (janela no estilo do Outlook) ----------
let envNF = null;
function assuntoDoArquivo(nomeArquivo, nome) {
  const base = (nomeArquivo || "").replace(/\.[^.]+$/, "").replace(/\s+/g, " ").trim();
  if (/^\s*nf-?e?\s*[-:nº°#]*\s*\d+\s*-\s*\S/i.test(base)) return base;
  const num = (base.match(/\d{2,}/) || [""])[0];
  return (num ? `NF ${num} - ` : "NF - ") + nome.toUpperCase();
}
// Assunto pelo arquivo da NF (João, 07/11/2026): ao anexar o PDF da nota, o assunto vira o nome do arquivo ("NF 1234 - NOME - 5678"), na
// resposta, no encaminhamento e no e-mail novo, em vez de "Re: Dados para emissão da NF". Tirou o anexo: volta o assunto de antes.
// Se a pessoa escrever o assunto à mão, o Painel não mexe mais.
function assuntoComAnexos() {
  if (envNF.assuntoManual) return;
  const nf = envNF.anexos.find(a => /\.pdf$/i.test(a.nome)) || envNF.anexos[0];
  if (nf) {
    if (envNF.assuntoAntes === null) envNF.assuntoAntes = $("nf-assunto").value;
    $("nf-assunto").value = assuntoDoArquivo(nf.nome, envNF.o.nome);
  } else if (envNF.assuntoAntes !== null) {
    $("nf-assunto").value = envNF.assuntoAntes;
    envNF.assuntoAntes = null;
  }
}
// Ação longa (27/10/2026): toda ação que passa de LIMITE_ACAO_LONGA_MS avisa a tela com um evento. A tela de carregamento
// (pecas/carregando.js: o K do João sendo desenhado) escuta "painel:acao-longa" e "painel:acao-longa-fim".
// detail: { id, titulo, inicio, progresso(): 0..1, eta(): segundos, itens(): [{pc, agente, estado, res, aviso}] } e, no fim,
// { id, ok, texto, duracao }. O api() liga isto sozinho em todo POST. `estado.limiteMs` troca os 3 s (0 = na hora).
const LIMITE_ACAO_LONGA_MS = (globalThis.aj?.("tela.acao_longa_segundos") ?? 3) * 1000;
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
  envNF = { chave, resp, alvo, fechar, o, anexos: [], assuntoManual: false, assuntoAntes: null };   // assunto: ver assuntoComAnexos
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
    ${(o.avisos_nf || []).map(t => `<div class="aviso-nf" role="note">${esc(t)}</div>`).join("")}
    ${o.sugestoes.length ? `<div class="sug-linha"><span class="dica">Do Dropbox:</span>${o.sugestoes.map((a, i) =>
      `<button class="sug ${a.outra || a.possivel ? "" : "forte"}" data-nf-sug="${i}" title="${esc(a.prova || "")}">📄 ${esc(a.nome)}${
        a.outra ? ' <b class="sug-tag am">outra nota</b>' : a.possivel ? ' <b class="sug-tag am">possível</b>' : a.mais_nova ? ' <b class="sug-tag">mais nova</b>' : ""}</button>`).join("")}</div>
      ${o.sugestoes.some(a => a.outra || a.possivel) ? `<div class="dica sug-aviso">${esc(o.sugestoes.filter(a => a.outra || a.possivel).map(a => (a.outra ? "Outra nota" : "Possível") + " · " + a.nome + ": " + (a.prova || "")).join(" | "))}. Clique para anexar; nada vem marcado.</div>` : ""}` : ""}
    <div class="quadro-e2 erro oculta" id="nf-conferir" role="alert"></div>
    ${enc ? "" : linhaModelos()}
    <div class="editor ${o.assinatura_com_mensagem ? "curto" : ""}" id="nf-msg" contenteditable="true" spellcheck="true"
      data-dica="${o.assinatura_com_mensagem ? "Escreva aqui só se quiser acrescentar algo — a mensagem padrão já vem na assinatura abaixo." : ""}"></div>
    ${o.selos.length ? `<div class="selo-previa"><img id="nf-selo-img" alt="Selo"><div id="nf-selo-texto" hidden></div></div>
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
    envNF.selos = o.selos;
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
  $("nf-assunto").addEventListener("input", ev => { if (ev.isTrusted) envNF.assuntoManual = !!$("nf-assunto").value.trim(); validarEnvioNF(); });   // digitou: o Painel não troca mais
  $("nf-para").addEventListener("input", validarEnvioNF);
  $("nf-ir").onclick = () => enviarNF();
  $("nf-lig")?.addEventListener("click", () => alternarLigacao());
  if (o.sugestoes.length === 1 && !o.sugestoes[0].outra && !o.sugestoes[0].possivel) escolherSugestao(0);   // nota confirmada pelo conteúdo: já vem anexada ("outra nota" e "possível" nunca vêm marcadas)
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
  const s = (envNF.selos || []).find(x => x.id === id), img = $("nf-selo-img"), txt = $("nf-selo-texto");
  if (s && s.texto) {   // selo só de texto (sem imagem): as linhas que saem no e-mail, depois do "Atenciosamente,"
    img.hidden = true; img.removeAttribute("src"); txt.hidden = false; txt.innerHTML = s.texto.map(esc).join("<br>");
  } else { txt.hidden = true; img.hidden = false; img.src = `/assinaturas/${encodeURIComponent(id)}.png`; }
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
  assuntoComAnexos();
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
    "CPF/CNPJ inválido": "O CPF ou CNPJ informado não confere (algum número deve estar errado). Pode confirmar o correto?",
    "CEP": "CEP do endereço que deve constar na nota:",
    "CEP inválido": "O CEP informado está incompleto ou errado. Pode confirmar o correto?",
    "telefone": "Telefone para contato:",
    "número do endereço": "Número do endereço (casa ou apartamento):",
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
