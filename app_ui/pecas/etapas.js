// Peça única: etapas do pedido (27/10/2026, opção C aprovada pelo João no desenho animado "Tela do e-mail 2.0").
// Em vez de várias caixas coloridas empilhadas antes da mensagem, uma ficha só no topo do e-mail:
//   cabeçalho (nome, prazo, hotel e PC, 2 botões) · 4 etapas (Recebido, Dados completos, NF pronta, NF enviada) ·
//   lista de conferência (✓ certo, ! falta, – ainda não existe).
// O botão azul principal muda com a situação: pedir o que falta, enviar a NF ou concluir.
// As regras (qual etapa, qual botão) ficam em etapasModelo(), sem tocar na tela, pra poderem ser testadas.
//   situação: falta · completo (dados ok, nota ainda não existe) · pronta (NF na pasta, falta enviar) · enviada
// Decisões do João: o Painel nunca tira nem apaga e-mail sozinho (Concluir é um clique); a tag "NF enviada" não é prova
// (quem decide "enviada" é o que o servidor conferiu: pedido concluído ou NF achada nos Itens Enviados).

function etapasSituacao({ falta = [], notas = [], nfsEnviadas = [], situacaoPedido = "" }) {
  if (nfsEnviadas.length || situacaoPedido === "enviada") return "enviada";
  if (notas.length || situacaoPedido === "pronta") return "pronta";
  return falta.length ? "falta" : "completo";
}

function etapasModelo(x) {
  // x: { hora, falta:[], semFormulario, tom, doc, docRot, datas, diarias, valor, pede, divisao, reserva, titular,
  //      notas:[{nf}], nfsEnviadas:[{nf, quando}], situacaoPedido, cobre:{cobre, pede_nova, motivos, avisos_envio, sugere_concluir}|null,
  //      temPedido }
  const falta = x.falta || [], notas = x.notas || [], enviadas = x.nfsEnviadas || [], c = x.cobre || null;
  const estado = etapasSituacao(x);
  const nfNum = (enviadas[0]?.nf) || (notas[0]?.nf) || "";
  const dadosOk = !falta.length && !x.semFormulario;
  const passos = [
    { nome: "Recebido", sub: x.hora || "", cls: "feita" },
    { nome: "Dados completos", sub: x.semFormulario ? "no texto do e-mail" : falta.length ? `falta ${falta.length} dado${falta.length > 1 ? "s" : ""}` : "tudo certo",
      cls: x.semFormulario ? "" : falta.length ? (estado === "falta" ? "atual" : "") : "feita" },
    { nome: "NF pronta", sub: estado === "enviada" ? (nfNum ? "NF " + nfNum : "") : estado === "pronta" ? (nfNum ? "NF " + nfNum + " na pasta" : "na pasta") : dadosOk ? "esperando a nota" : "ainda não",
      cls: estado === "enviada" ? "feita" : estado === "pronta" || (estado === "completo") ? "atual azul" : "" },
    { nome: "NF enviada", sub: estado === "enviada" ? (enviadas[0]?.quando || "") : estado === "pronta" ? "falta enviar" : "", cls: estado === "enviada" ? "feita" : "" },
  ];
  if (estado === "enviada" && c && (c.pede_nova || c.cobre === null || (c.avisos_envio || []).length)) passos[3].cls = "feita atencao";

  const na = (rot, val) => ({ tipo: "na", rot, val });
  const ok = (rot, val) => ({ tipo: "ok", rot, val });
  const at = (rot, val) => ({ tipo: "at", rot, val });
  const itens = x.semFormulario ? [] : [
    x.tom ? ok("Nota no nome de", x.tom) : at("Falta", "Nome para a nota"),
    x.doc ? ok(x.docRot || "CPF / CNPJ", x.doc) : at("Falta", "CPF ou CNPJ"),
    x.datas ? ok("Check-in → check-out", x.datas) : na("Check-in → check-out", "Não informado"),
    x.diarias || x.valor ? ok("Diárias e valor", [x.diarias, x.valor].filter(Boolean).join(" · ")) : na("Diárias e valor", "Não informado"),
    x.pede ? ok("O que entra", x.pede) : at("Falta", "O que deve entrar na nota"),
    c?.pede_nova ? at("Atenção", "Pede nova nota" + ((c.motivos || [])[0] ? ": " + c.motivos[0] : "")) : x.divisao ? ok("Divisão", x.divisao) : ok("Divisão", "1 nota só"),
    x.reserva ? ok("Reserva", x.reserva) : x.titular ? ok("Titular da reserva", x.titular) : na("Reserva", "Não informada"),
  ];
  if (!x.semFormulario) {
    if (estado === "enviada") {
      itens.push(c && (c.avisos_envio || []).length ? at("NF enviada", `Marcada como enviada, mas não achei o envio da NF ${c.avisos_envio.join(", ")} nos Itens Enviados`)
        : c && c.cobre === null ? at("NF enviada", "Não consegui ler a nota enviada: confira antes de concluir")
        : ok("NF enviada", nfNum ? `NF ${nfNum} · conferida no Outlook e no PDF` : "Conferida no Outlook"));
    } else itens.push(estado === "pronta" ? ok(`NF ${nfNum} na pasta`.trim(), "Confere com o pedido") : na("NF nas pastas", "Ainda não emitida"));
  }

  const principal = estado === "enviada" ? { texto: "Concluir", acao: "concluir", cls: "p" }
    : estado === "falta" && x.temPedido ? { texto: "Pedir o que falta", acao: "pedir", cls: "p" }
    : estado === "completo" ? { texto: "Enviar NF", acao: "nf", cls: "" }
    : { texto: "Enviar NF", acao: "nf", cls: "p" };
  const secundario = estado === "enviada" ? { texto: "Enviar outra NF", acao: "nf" }
    : x.temPedido ? { texto: "Marcar tratativa", acao: "tratativa" } : null;
  if (estado === "falta" && !x.temPedido) { principal.texto = "Enviar NF"; principal.acao = "nf"; principal.cls = ""; }
  return { estado, passos, itens, principal, secundario };
}

// ---------- tela ----------
const ETP_IC = {
  ok: '<path d="M5 12l5 5 9-10"/>',
  at: '<path d="M12 7v6M12 17v.5"/>',
  na: '<path d="M7 12h10"/>',
};
const etpEsc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function etapasBotao(b, e, chave) {
  if (!b) return "";
  const dado = b.acao === "pedir" ? `data-pedir-dados="${etpEsc(chave)}"` : b.acao === "tratativa" ? `data-abrir-ficha="${etpEsc(chave)}"`
    : b.acao === "concluir" ? `data-nf-concluir="${etpEsc(e.id)}"` : `data-cx-faixa="nf"`;
  return `<button type="button" class="c-bt ${b.cls}" ${dado}>${etpEsc(b.texto)}</button>`;
}

// m: o que sai de etapasModelo; o: { nome, prazo:{texto,nivel}|null, onde, chave, entra, podeAbrir, aberta, fichaHtml }
function etapasTelaHtml(m, e, o) {
  const prazo = m.estado !== "enviada" && o.prazo ? `<span class="c-prazo ${etpEsc(o.prazo.nivel)}">${etpEsc(o.prazo.texto)}</span>` : "";
  const passos = m.passos.map((p, i) => `<div class="c-et ${p.cls}" style="--i:${i}"><b>${etpEsc(p.nome)}</b><span>${etpEsc(p.sub)}</span></div>`).join("");
  const itens = m.itens.map((it, i) => `<div class="c-item ${it.tipo}" style="--i:${i}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ETP_IC[it.tipo]}</svg>`
    + `<div><span>${etpEsc(it.rot)}</span><span>${etpEsc(it.val)}</span></div></div>`).join("");
  const sem = !m.itens.length ? `<div class="c-sem">Sem formulário: os dados estão no texto do e-mail.</div>` : "";
  const ficha = o.podeAbrir ? `<button type="button" class="c-ficha" data-resumo-ficha aria-expanded="${!!o.aberta}">${o.aberta ? "Fechar o formulário completo ▴" : "Ver o formulário completo ▾"}</button>` : "";
  return `<section class="c-top${o.entra ? " c-anim" : ""}" aria-label="Resumo do pedido" data-estado="${m.estado}">
    <div class="c-lin"><h2>${etpEsc(o.nome)}</h2>${prazo}<span class="c-onde">${etpEsc(o.onde || "")}</span><span class="c-esp"></span>
      ${etapasBotao(m.secundario, e, o.chave)}${etapasBotao(m.principal, e, o.chave)}</div>
    <div class="c-etapas">${passos}</div></section>
    <section class="c-lista${o.entra ? " c-anim" : ""}" aria-label="O que o robô conferiu">${itens}${sem}</section>
    ${ficha ? `<div class="c-fichalin">${ficha}</div>` : ""}${o.aberta && o.fichaHtml ? `<div class="c-ficha-tab">${o.fichaHtml}</div>` : ""}`;
}
