// Peça única: etiquetas (usuário, 21/10/2026: "etiquetas e situações únicas"). Cor + ícone + palavra, iguais em todas
// as telas. Aqui ficam também as REGRAS (qual situação e quais alertas cada pedido/e-mail recebe), pra todas as telas
// decidirem do mesmo jeito.
//   Situação do pedido (uma por vez): sem_nf · falta · pronta · enviada · correcao
//   Alertas (somam): urgente · repetido · dividida · doc · nao_recebeu
// Decisões do João (21/10/2026): responder NÃO vira "NF enviada"; "diz que falta nota" é o alerta "Diz que não recebeu".
const ETQ_IC = {
  doc: '<path d="M7 3h7l5 5v13H7z"/>',
  relogio: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  aviao: '<path d="M4 12l16-8-6 16-2-7z"/>',
  check: '<path d="M5 12l5 5L20 7"/>',
  volta: '<path d="M4 12a8 8 0 1 0 3-6.2"/><path d="M4 4v4h4"/>',
  bandeira: '<path d="M5 21V4h11l-2 4 2 4H5"/>',
  copia: '<rect x="8" y="8" width="12" height="12" rx="2"/><path d="M4 16V5a1 1 0 0 1 1-1h11"/>',
  carta: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="M3 7l9 6 9-6"/>',
  tel: '<path d="M22 16.9v3a2 2 0 0 1-2.2 2 19.8 19.8 0 0 1-8.6-3.1 19.5 19.5 0 0 1-6-6A19.8 19.8 0 0 1 2.1 4.2 2 2 0 0 1 4.1 2h3a2 2 0 0 1 2 1.7c.1 1 .4 1.9.7 2.8a2 2 0 0 1-.5 2.1L8.1 9.9a16 16 0 0 0 6 6l1.3-1.3a2 2 0 0 1 2.1-.4c.9.3 1.8.6 2.8.7a2 2 0 0 1 1.7 2z"/>',
};
const SITUACOES_ETQ = {
  sem_nf: ["Sem NF", "s-semnf", "doc"],
  falta: ["Falta dado", "s-falta", "relogio"],
  pronta: ["NF pronta, falta enviar", "s-pronta", "aviao"],
  enviada: ["NF enviada", "s-enviada", "check"],
  correcao: ["Correção", "s-corr", "volta"],
};
const ALERTAS_ETQ = {
  urgente: ["Urgente", "a-urg", "bandeira"],
  repetido: ["Possível repetido", "a-dup", "copia"],
  dividida: ["÷ Nota dividida", "a-div", ""],
  doc: ["≠ CPF/CNPJ diferente", "a-doc", ""],
  nao_recebeu: ["Diz que não recebeu", "a-nrec", "carta"],
};
const etqEsc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const ETQ_CURTO = { "o que quer na nota": "o que pede" };   // cabe na linha da lista
const etqIcone = k => k ? `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ETQ_IC[k]}</svg>` : "";

// Pedido que veio por ligação (usuário, 22/10/2026): marca do agente, não é situação nem alerta; verde-água, só dela
function pecaLigacao({ id = "", oculta = false } = {}) {
  return `<span class="peca-etq s-lig${oculta ? " oculta" : ""}"${id ? ` id="${etqEsc(id)}"` : ""} title="O hóspede pediu por telefone (marcado por quem enviou)">${etqIcone("tel")}Ligação</span>`;
}
function pecaSituacao(chave, { texto = "", titulo = "" } = {}) {
  const [nome, cls, ic] = SITUACOES_ETQ[chave] || SITUACOES_ETQ.sem_nf;
  return `<span class="peca-etq sit ${cls}"${titulo ? ` title="${etqEsc(titulo)}"` : ""}>${etqIcone(ic)}${etqEsc(texto || nome)}</span>`;
}
function pecaAlerta(chave, { texto = "", titulo = "" } = {}) {
  const [nome, cls, ic] = ALERTAS_ETQ[chave] || ALERTAS_ETQ.urgente;
  return `<span class="peca-etq al ${cls}"${titulo ? ` title="${etqEsc(titulo)}"` : ""}>${etqIcone(ic)}${etqEsc(texto || nome)}</span>`;
}

// ---------- regras ----------
function situacaoDoPedido(s) {   // s: pedido do formulário (situacao do servidor + envio_pendente + o que falta)
  if (!s) return "sem_nf";
  if (s.situacao === "concluida") return s.envio_pendente ? "pronta" : "enviada";
  if (typeof faltaDados === "function" && faltaDados(s).length) return "falta";
  return "sem_nf";
}
function nomeSituacao(s) {   // texto curto, pra onde não cabe a etiqueta (histórico, resultado da pesquisa)
  const k = situacaoDoPedido(s), nfs = s?.nfs?.length ? ` · ${s.nfs.join(", ")}` : "";
  return SITUACOES_ETQ[k][0] + (k === "enviada" || k === "pronta" ? nfs : "");
}
function etiquetasDoPedido(s) {
  const k = situacaoDoPedido(s);
  const falta = k === "falta" ? faltaDados(s) : [];
  const nfs = s.nfs?.length ? s.nfs.join(", ") : "";
  let html = pecaSituacao(k, {
    texto: k === "falta" ? `Falta dado: ${ETQ_CURTO[falta[0]] || falta[0]}${falta.length > 1 ? ` +${falta.length - 1}` : ""}` : (k === "enviada" || k === "pronta") && nfs ? `${SITUACOES_ETQ[k][0]} · ${nfs}` : "",
    titulo: k === "falta" ? "Falta para emitir: " + falta.join(", ") : k === "pronta" ? "A NF existe, mas nenhum e-mail com ela saiu para o hóspede" : "" });
  const urg = typeof motivoUrgente === "function" ? motivoUrgente(s) : "";
  if (urg === "Cobrou de novo") html += pecaAlerta("repetido", { texto: "Pediu de novo", titulo: "O hóspede mandou outro pedido igual" });
  else if (urg) html += pecaAlerta("urgente", { texto: urg });
  if (s.situacao === "nf_parcial") html += pecaAlerta("dividida", { texto: `÷ Nota dividida · ${s.nfs.length} de ${s.partes || 2}` });
  else if (s.dividida) html += pecaAlerta("dividida");
  if (s.alerta_doc?.length) html += pecaAlerta("doc", { titulo: s.alerta_doc.map(a => a.texto || a).join(" · ") });
  if (s.falta_nota) html += pecaAlerta("nao_recebeu", { titulo: s.falta_nota });
  return html;
}
function etiquetasDoEmail(e) {   // e: e-mail da caixa de entrada (com o pedido ligado, se houver)
  const ped = typeof pedidoDoEmail === "function" ? pedidoDoEmail(e) : null;
  const correcao = (e.classes || []).includes("corrigir") || /corre/i.test(e.motivo_urgencia || "");
  let html;
  if (correcao) html = pecaSituacao("correcao");
  else if (ped) html = etiquetasDoPedido(ped).replace(/<span class="peca-etq al [^>]*>.*?<\/span>/g, "");   // a situação do pedido; os alertas vêm do e-mail
  else if (e.notas?.length) html = pecaSituacao("pronta", { texto: `NF pronta, falta enviar · ${e.notas.map(n => n.nf).join(", ")}`, titulo: e.notas.map(n => n.nome).join(" · ") });
  else html = pecaSituacao("sem_nf");
  if (e.urgente && !correcao) {
    const m = e.motivo_urgencia || "";
    html += pecaAlerta("urgente", { texto: /^(\d+) dias sem resposta$/.test(m) ? m.replace(/^(\d+) dias sem resposta$/, "Sem resposta há $1 dias") : /ouvidoria/i.test(m) ? "Ouvidoria" : "Urgente", titulo: m });
  }
  if ((e.quartos?.[0] || e.quartos || 0) >= 2) html += pecaAlerta("dividida");
  if (e.alerta_doc) html += pecaAlerta("doc", { titulo: e.alerta_doc });
  if (e.falta_nota) html += pecaAlerta("nao_recebeu", { titulo: e.falta_nota });
  return html;
}
