// As regras do pedido de NF, num lugar só (sem tela): ler os campos do formulário, conferir CPF/CNPJ e CEP, o que falta,
// as etapas do pedido, as mensagens prontas e o texto da emissão. Vieram da tela de hoje (regras_nf.js, etapas.js,
// hospede.js, painel_enviar_nf.js) sem mudar a regra. Nada aqui inventa dado: só lê o que o hóspede escreveu.

export const semAcento = (x) => String(x || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();

export function cpfValido(txt) {
  const d = String(txt || "").replace(/\D/g, "");
  if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
  const dv = (n) => { let s = 0; for (let i = 0; i < n; i++) s += +d[i] * (n + 1 - i); const r = (s * 10) % 11; return r === 10 ? 0 : r; };
  return dv(9) === +d[9] && dv(10) === +d[10];
}
export function cnpjValido(txt) {
  const d = String(txt || "").replace(/\D/g, "");
  if (d.length !== 14 || /^(\d)\1{13}$/.test(d)) return false;
  const dv = (n) => {
    const pesos = n === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const r = pesos.reduce((s, p, i) => s + p * +d[i], 0) % 11;
    return r < 2 ? 0 : 11 - r;
  };
  return dv(12) === +d[12] && dv(13) === +d[13];
}
export const cepValido = (txt) => String(txt || "").replace(/\D/g, "").length === 8;

// Valor de um campo pelo nome (sem acento, qualquer caixa): o 1º teste que casar.
export function campoDoPedido(s, ...testes) {
  const c = (s?.campos || []).find(([k]) => testes.some((r) => r.test(semAcento(k))));
  return c ? String(c[1] || "").trim() : "";
}
export const CAMPO_NOME = [/nome.*tomador/, /razao social/, /^nome( completo)?$/];
export const CAMPO_DOC = [/documento.*tomador/, /cpf.*cnpj|cnpj.*cpf/, /^cnpj/, /^cpf(?!.*titular)/];

// O que impede de emitir: "nome", "CPF/CNPJ" | "CPF/CNPJ inválido", "CEP" | "CEP inválido"
export function faltaDados(s) {
  if (!s || s.situacao === "concluida") return [];
  const falta = [];
  if (!campoDoPedido(s, ...CAMPO_NOME)) falta.push("nome");
  const doc = campoDoPedido(s, ...CAMPO_DOC);
  if (!doc.replace(/\D/g, "")) falta.push("CPF/CNPJ");
  else if (!(cpfValido(doc) || cnpjValido(doc))) falta.push("CPF/CNPJ inválido");
  const cep = campoDoPedido(s, /^cep/, /\bcep\b/);
  if (!cep.replace(/\D/g, "")) falta.push("CEP");
  else if (!cepValido(cep)) falta.push("CEP inválido");
  return falta;
}
// Só para a mensagem: o campo existe no formulário e veio vazio
export function faltaExtras(s) {
  if (!s || s.situacao === "concluida") return [];
  const extras = [];
  const tem = (...t) => (s.campos || []).some(([k]) => t.some((r) => r.test(semAcento(k))));
  if (tem(/telefone|celular|whatsapp/) && !campoDoPedido(s, /telefone|celular|whatsapp/)) extras.push("telefone");
  if (tem(/^numero/, /numero (da )?(casa|residencia|endereco)/) && !campoDoPedido(s, /^numero/, /numero (da )?(casa|residencia|endereco)/)) extras.push("número do endereço");
  return extras;
}

// Como mostrar um valor: [texto, observação]. CPF/CNPJ, CEP e telefone com pontuação; datas com a conta de diárias.
export function valorDoForm(rot, v) {
  const d = String(v || "").replace(/\D/g, "");
  if (/CPF|CNPJ/.test(rot) && d.length === 11) return [`${d.slice(0, 3)}.${d.slice(3, 6)}.${d.slice(6, 9)}-${d.slice(9)}`, "CPF"];
  if (/CPF|CNPJ/.test(rot) && d.length === 14) return [`${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`, "CNPJ"];
  if (rot === "CEP" && d.length === 8) return [`${d.slice(0, 5)}-${d.slice(5)}`, ""];
  if (rot === "Telefone" && (d.length === 10 || d.length === 11)) return [`(${d.slice(0, 2)}) ${d.slice(2, -4)}-${d.slice(-4)}`, ""];
  if (rot === "Datas") {
    const [a, b] = String(v).split(" → ").map((x) => x.trim().split("/").map(Number));
    const n = a?.length === 3 && b?.length === 3 ? Math.round((new Date(b[2], b[1] - 1, b[0]) - new Date(a[2], a[1] - 1, a[0])) / 864e5) : 0;
    return [String(v), n > 0 ? `${n} diária${n > 1 ? "s" : ""}` : ""];
  }
  return [String(v), ""];
}

// ---------- o formulário do Emissor Automático ----------
export const OCULTOS_FORM = /^(enviado|carimbo|importante|avalia|preenchimento|ritmo|sugest|sincroniz|endereco de e-?mail|e-?mail$)/i;
export const GRUPOS_FORM = [
  ["Tomador da nota", [[/nome.*tomador/, "Nome"], [/documento.*tomador/, "CPF/CNPJ"], [/^cep/, "CEP"], [/telefone/, "Telefone"]]],
  ["Estadia", [[/^hotel$/, "Hotel"], [/nome.*titular/, "Titular da reserva"], [/cpf.*titular/, "CPF do titular"], [/^datas$/, "Datas"], [/check.?in/, "Check-in"], [/check.?out/, "Check-out"]]],
  ["Como quer a nota", [[/informac/, "O que pede"], [/^nota dividida/, "Nota dividida"], [/dividida em|quantas vezes/, "Dividir em"], [/valor.*nota/, "Valor"], [/^enviar para$/, "Enviar para"]]],
];
export const SEM_COPIAR_FORM = new Set(["Hotel", "Datas", "Check-in", "Check-out", "O que pede", "Nota dividida", "Dividir em"]);

// O formulário em grupos: [{titulo, linhas:[{rot, valor}]}], os termos e o "Enviado em"
export function gruposDoFormulario(s, e = {}) {
  const campos = (s.campos || []).filter(([k, val]) => String(val || "").trim() && !OCULTOS_FORM.test(semAcento(k)));
  const extras = [["Hotel", s.hotel || e.hotel || ""], ["Enviar para", s.email || ""]].filter(([, v]) => v);
  const usados = new Set();
  const termos = campos.find(([k]) => /^termos/.test(semAcento(k)));
  if (termos) usados.add(termos);
  const ci = campos.find(([k]) => /check.?in/.test(semAcento(k))), co = campos.find(([k]) => /check.?out/.test(semAcento(k)));
  if (ci && co) { extras.push(["Datas", `${ci[1]} → ${co[1]}`]); usados.add(ci); usados.add(co); }
  const grupos = GRUPOS_FORM.map(([titulo, regras]) => ({
    titulo,
    linhas: regras.map(([re, rot]) => {
      const c = [...campos, ...extras].find((x) => !usados.has(x) && re.test(semAcento(x[0])));
      if (!c) return null;
      usados.add(c);
      return { rot, valor: c[1] };
    }).filter(Boolean),
  })).filter((g) => g.linhas.length);
  const resto = campos.filter((c) => !usados.has(c)).map(([rot, valor]) => ({ rot, valor }));
  if (resto.length) grupos.push({ titulo: "Outros campos", linhas: resto });
  return { grupos, termos: termos ? termos[1] : "", aceitou: !!termos && /acordo|aceit/i.test(termos[1]), enviadoEm: s.carimbo || dataBr(s.data) || "", email: s.email || "" };
}

// E-mail do Emissor sem o pedido na lista: os campos saem do próprio texto ("Campo<tab>Valor")
const ROTULOS_FORM = ["Termos de aceite", "Documento Tomador", "Nome Tomador", "CEP", "Telefone para contato", "CPF do Titular da Reserva",
  "Nome do Titular da Reserva", "Check-in da Hospedagem", "Check-out da Hospedagem", "Informações necessárias na Nota Fiscal",
  "Nota Dividida", "Dividida em quantas vezes", "Valor da Nota"];
export function formDoTexto(texto) {
  const t = String(texto || "").replace(/\r/g, "");
  if (!/dados para emiss[aã]o de nota fiscal/i.test(t) || !/^\s*campo\s+valor\s*$/im.test(t)) return null;
  const linhas = t.split("\n"), ini = linhas.findIndex((l) => /^\s*campo\s+valor\s*$/i.test(l));
  const campos = [];
  for (const l of linhas.slice(ini + 1)) {
    if (/^\s*enviado em\s*:/i.test(l)) break;
    if (!l.trim()) continue;
    let partes = l.split(/\t+| {2,}/).map((x) => x.trim()).filter(Boolean);
    if (partes.length < 2) {
      const r = ROTULOS_FORM.find((x) => l.trim().toLowerCase().startsWith(x.toLowerCase() + " "));
      partes = r ? [r, l.trim().slice(r.length).trim()] : partes;
    }
    if (partes.length >= 2) campos.push([partes[0], partes.slice(1).join(" ")]);
  }
  if (!campos.length) return null;
  const por = t.match(/enviado por\s*:\s*([^\s<]+@[^\s<>]+)/i), em = t.match(/enviado em\s*:\s*(.+)/i);
  return { campos, email: por ? por[1] : "", carimbo: em ? em[1].replace(/\s*GMT.*$/, "").trim() : "" };
}

export const ehFormulario = (e) => !!e && e.pasta !== "enviado" && (e.classes || []).includes("formulario");
export const pedidoDoEmail = (e, fila) => (e?.solicitacao?.chave ? (fila || []).find((s) => s.chave === e.solicitacao.chave) || null : null);
// O e-mail do Emissor vem do remetente do Emissor: acha o pedido pelo e-mail de quem preencheu e pelo carimbo do formulário
export function pedidoDoFormulario(f, fila) {
  const mail = String(f?.email || "").trim().toLowerCase(), carimbo = String(f?.carimbo || "").trim();
  return !mail || !carimbo ? null : (fila || []).find((s) => String(s.email || "").trim().toLowerCase() === mail && String(s.carimbo || "").trim() === carimbo) || null;
}

// ---------- situação do pedido (uma por vez) e alertas (somam) ----------
// Decisões do João (21/10/2026): responder NÃO vira "NF enviada"; "diz que falta nota" é o alerta "Diz que não recebeu".
export const SITUACOES = {
  sem_nf: ["Sem NF", "azul", "nota"], falta: ["Falta dado", "ambar", "relogio"], pronta: ["NF pronta, falta enviar", "ambar", "enviar"],
  enviada: ["NF enviada", "verde", "check"], correcao: ["Correção", "ambar", "voltar"],
};
const ETQ_CURTO = { "o que quer na nota": "o que pede" };
export function situacaoDoPedido(s) {
  if (!s) return "sem_nf";
  if (s.situacao === "concluida") return s.envio_pendente ? "pronta" : "enviada";
  return faltaDados(s).length ? "falta" : "sem_nf";
}
export function nomeSituacao(s) {
  const k = situacaoDoPedido(s), nfs = s?.nfs?.length ? ` · ${s.nfs.join(", ")}` : "";
  return SITUACOES[k][0] + (k === "enviada" || k === "pronta" ? nfs : "");
}
// As etiquetas de um e-mail da caixa de entrada: [{ texto, tipo, icone, titulo, contorno }]
export function etiquetasDoEmail(e, fila) {
  const lista = [];
  const ped = pedidoDoEmail(e, fila);
  const correcao = (e.classes || []).includes("corrigir") || /corre/i.test(e.motivo_urgencia || "");
  const sit = (k, texto, titulo) => { const [nome, tipo, icone] = SITUACOES[k]; lista.push({ texto: texto || nome, tipo, icone, titulo }); };
  if (correcao) sit("correcao");
  else if (ped) {
    const k = situacaoDoPedido(ped), falta = k === "falta" ? faltaDados(ped) : [], nfs = ped.nfs?.length ? ped.nfs.join(", ") : "";
    sit(k, k === "falta" ? `Falta dado: ${ETQ_CURTO[falta[0]] || falta[0]}${falta.length > 1 ? ` +${falta.length - 1}` : ""}` : (k === "enviada" || k === "pronta") && nfs ? `${SITUACOES[k][0]} · ${nfs}` : "",
      k === "falta" ? "Falta para emitir: " + falta.join(", ") : k === "pronta" ? "A NF existe, mas nenhum e-mail com ela saiu para o hóspede" : "");
  } else if (e.notas?.length) sit("pronta", `NF pronta, falta enviar · ${e.notas.map((n) => n.nf || n).join(", ")}`, e.notas.map((n) => n.nome || n).join(" · "));
  else sit("sem_nf");
  if (e.urgente && !correcao) {
    const m = e.motivo_urgencia || "";
    lista.push({ tipo: "vermelho", icone: "bandeira", contorno: true, titulo: m,
      texto: /^Pede nova nota/i.test(m) ? "Pede nova nota" : /^(\d+) dias sem resposta$/.test(m) ? m.replace(/^(\d+) dias sem resposta$/, "Sem resposta há $1 dias") : /ouvidoria/i.test(m) ? "Ouvidoria" : "Urgente" });
  }
  if ((e.quartos?.[0] || e.quartos || 0) >= 2) lista.push({ tipo: "azul", texto: "÷ Nota dividida" });
  if (e.alerta_doc) lista.push({ tipo: "vermelho", texto: "≠ CPF/CNPJ diferente", titulo: e.alerta_doc });
  if (e.falta_nota) lista.push({ tipo: "ambar", icone: "envelope", texto: "Diz que não recebeu", titulo: e.falta_nota });
  return lista;
}

// ---------- datas ----------
export const dataBr = (iso) => (iso ? String(iso).slice(0, 10).split("-").reverse().join("/") : "");
export function hpData(v) {   // "28/10/2026", "28/10/26", "2026-10-28" -> { txt, ms }; outra coisa fica como o hóspede escreveu
  const t = String(v || "").trim();
  let m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (!m && (m = t.match(/^(\d{4})-(\d{2})-(\d{2})/))) m = [t, m[3], m[2], m[1]];
  if (!m && (m = t.match(/^(\d{1,2})\/(\d{1,2})\/(\d{2})$/))) m = [t, m[1], m[2], "20" + m[3]];
  if (!m) return { txt: t, ms: NaN };
  const [, d, mes, a] = m;
  return { txt: `${d.padStart(2, "0")}/${mes.padStart(2, "0")}/${a}`, ms: Date.UTC(+a, +mes - 1, +d) };
}
export const contarDiarias = (ci, co) => { const n = Math.round((co.ms - ci.ms) / 864e5); return Number.isFinite(n) && n > 0 ? n : 0; };

// Prazo do pedido (correção e cobrança 24 h, pedido 48 h, dias corridos): { texto, nivel: "ok" | "perto" | "vencido" }.
// O servidor manda quando vence; o que falta é contado aqui, então anda sozinho entre as atualizações.
export function prazoInfo(p) {
  if (!p?.vence) return null;
  const resta = (new Date(p.vence) - Date.now()) / 36e5, h = Math.abs(resta);
  if (!Number.isFinite(resta)) return null;
  const nivel = resta <= 0 ? "vencido" : resta <= (p.horas || 48) / 2 ? "perto" : "ok";
  const tempo = h < 1 ? Math.max(1, Math.round(h * 60)) + " min" : h < 48 ? Math.round(h) + " h" : Math.round(h / 24) + " dias";
  return { nivel, texto: resta <= 0 ? "venceu há " + tempo : "vence em " + tempo };
}

// ---------- a ficha do pedido (etapas) ----------
// O Painel ainda NÃO decide sozinho se a nota foi emitida ou enviada (João, 29/10/2026): ficam só "Recebido" e
// "Dados completos"; o botão principal é "Pedir o que falta" (com pedido) ou "Enviar NF".
export function etapasDoPedido({ hora = "", falta = [], semFormulario = false, temPedido = false }) {
  const passos = [
    { nome: "Recebido", sub: hora, feita: true },
    { nome: "Dados completos", sub: semFormulario ? "no texto do e-mail" : falta.length ? `falta ${falta.length} dado${falta.length > 1 ? "s" : ""}` : "tudo certo",
      feita: !semFormulario && !falta.length, atual: !semFormulario && !!falta.length },
  ];
  const principal = falta.length && temPedido ? { texto: "Pedir o que falta", acao: "pedir" } : { texto: "Enviar NF", acao: "nf" };
  return { passos, principal };
}
// O que o robô conferiu, linha a linha: tipo ok | at (falta) | na (não informado)
export function itensConferidos(d) {
  const c = (...t) => campoDoPedido(d, ...t);
  const tom = c(...CAMPO_NOME), doc = c(...CAMPO_DOC), pede = c(/informac/, /o que.*nota/, /itens/);
  const ci = c(/check.?in/), co = c(/check.?out/);
  const [docF, docT] = doc ? valorDoForm("CPF/CNPJ", doc) : ["", ""];
  const [datas, diarias] = ci && co ? valorDoForm("Datas", `${ci} → ${co}`) : ["", ""];
  const valor = c(/valor.*nota/), reserva = c(/estada|reserva/), titular = c(/nome.*titular/, /nome do hospede/);
  const dividida = (d.dividida || d.partes > 1) ? `Dividir em ${(d.partes > 1 ? d.partes : c(/dividida em|quantas vezes/)) || 2} notas` : "";
  return [
    tom ? { tipo: "ok", rot: "Nota no nome de", val: tom } : { tipo: "at", rot: "Falta", val: "Nome para a nota" },
    doc ? { tipo: "ok", rot: docT || "CPF / CNPJ", val: docF } : { tipo: "at", rot: "Falta", val: "CPF ou CNPJ" },
    datas ? { tipo: "ok", rot: "Check-in → check-out", val: datas } : { tipo: "na", rot: "Check-in → check-out", val: "Não informado" },
    diarias || valor ? { tipo: "ok", rot: "Diárias e valor", val: [diarias, valor].filter(Boolean).join(" · ") } : { tipo: "na", rot: "Diárias e valor", val: "Não informado" },
    pede ? { tipo: "ok", rot: "O que entra", val: pede } : { tipo: "at", rot: "Falta", val: "O que deve entrar na nota" },
    { tipo: "ok", rot: "Divisão", val: dividida || "1 nota só" },
    reserva ? { tipo: "ok", rot: "Reserva", val: reserva } : titular ? { tipo: "ok", rot: "Titular da reserva", val: titular } : { tipo: "na", rot: "Reserva", val: "Não informada" },
  ];
}

// ---------- mensagens prontas ----------
const saudacao = () => { const h = new Date().getHours(); return h < 12 ? "Bom dia!" : h < 18 ? "Boa tarde!" : "Boa noite!"; };
export function modeloSolicitacaoDados() {
  return `${saudacao()}

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
const PERGUNTA_FALTA = {
  "nome": "Nome completo (ou razão social) que deve constar na nota:",
  "CPF/CNPJ": "CPF ou CNPJ que deve constar na nota:",
  "CPF/CNPJ inválido": "O CPF ou CNPJ informado não confere (algum número deve estar errado). Pode confirmar o correto?",
  "CEP": "CEP do endereço que deve constar na nota:",
  "CEP inválido": "O CEP informado está incompleto ou errado. Pode confirmar o correto?",
  "telefone": "Telefone para contato:",
  "número do endereço": "Número do endereço (casa ou apartamento):",
  "o que quer na nota": "A nota deve incluir apenas as diárias ou também consumos e estacionamento (se houver)?",
};
export function modeloPedirFalta(faltas) {
  return `${saudacao()}

Prezado(a),

Recebemos o seu pedido de nota fiscal. Para emitir, só precisamos de:

${faltas.map((f) => PERGUNTA_FALTA[f] || f).join("\n\n")}

Assim que responder, emitimos e enviamos a nota para este e-mail.`;
}
export const MODELOS_RESPOSTA = [
  ["Solicitação de dados", () => modeloSolicitacaoDados()],
  ["Segue a NF", (d) => `Olá, ${d.nome}! Segue em anexo a nota fiscal${d.nf ? " " + d.nf : ""} da sua hospedagem no ${d.hotel}. Qualquer dúvida, estamos à disposição.`],
  ["NF corrigida", (d) => `Olá, ${d.nome}! Segue em anexo a nota fiscal${d.nf ? " " + d.nf : ""} corrigida, conforme solicitado. Pedimos desculpas pelo transtorno.`],
  ["Pedir CPF/CNPJ", (d) => `Olá, ${d.nome}! Para emitir a nota fiscal da sua hospedagem no ${d.hotel}, precisamos do CPF ou CNPJ correto do tomador (e a razão social, se for empresa). Pode nos enviar?`],
  ["Pedir dados da reserva", (d) => `Olá, ${d.nome}! Para localizar sua hospedagem no ${d.hotel}, pode nos informar as datas de check-in e check-out e o nome do titular da reserva?`],
  ["NF sai até amanhã", (d) => `Olá, ${d.nome}! Recebemos seu pedido. A nota fiscal da sua hospedagem no ${d.hotel} será emitida e enviada até amanhã.`],
];
export function dadosDoModelo(nomeHospede, hotel, anexos) {
  const nome = String(nomeHospede || "").trim().split(/\s+/)[0] || "";
  const nf = (anexos || []).map((a) => (String(a.nome).match(/NF\s*(\d+)/i) || [])[1]).filter(Boolean);
  return { nome: nome ? nome.charAt(0).toUpperCase() + nome.slice(1).toLowerCase() : "", hotel: hotel || "o hotel",
    nf: nf.length ? (nf.length > 1 ? "s " : "") + nf.join(", ") : "" };
}
// Assunto pelo arquivo da NF: "NF 1234 - NOME" (o nome do arquivo, quando já vem assim)
export function assuntoDoArquivo(nomeArquivo, nome) {
  const base = (nomeArquivo || "").replace(/\.[^.]+$/, "").replace(/\s+/g, " ").trim();
  if (/^\s*nf-?e?\s*[-:nº°#]*\s*\d+\s*-\s*\S/i.test(base)) return base;
  const num = (base.match(/\d{2,}/) || [""])[0];
  return (num ? `NF ${num} - ` : "NF - ") + String(nome || "").toUpperCase();
}

// ---------- o texto da emissão (o que o João cola no emissor) ----------
// Nada inventado: diária e valor total só se o hóspede informou; diárias é só a conta das datas; a estada só se ele escreveu.
function estadaDoPedido(d) {
  const re = /estada\s*(?:n[º°o.]*\s*)?[:-]?\s*(\d{2,})/i;
  for (const [k, v] of d.campos || []) {
    const m = re.exec(String(v || ""));
    if (m) return m[1];
    if (/^((numero|n[º°o.]*)\s*(da\s+)?)?estada\b/.test(semAcento(k)) && /^\d{2,}$/.test(String(v || "").trim())) return String(v).trim();
  }
  return "";
}
export function nomeDoHospede(d) {
  return campoDoPedido(d, /nome.*titular/, /nome do hospede/) || campoDoPedido(d, ...CAMPO_NOME) || String(d?.nome || "").trim() || "Hóspede do formulário";
}
export function textoEmissao(d) {
  const c = (...t) => campoDoPedido(d, ...t);
  const ci = hpData(c(/check.?in/)), co = hpData(c(/check.?out/)), n = contarDiarias(ci, co);
  const valor = c(/valor.*nota/);
  const nome = c(/nome.*titular/, /nome do hospede/) || c(...CAMPO_NOME) || String(d.nome || "").trim();
  const estada = estadaDoPedido(d);
  return ["DATA DE CHECK-IN : " + ci.txt, "DATA DE CHECK-OUT : " + co.txt, "QUANTIDADE DE DIÁRIAS : " + (n || ""),
    "VALOR DA DIÁRIA :", "", "VALOR TOTAL :" + (valor ? " " + valor : ""), nome + (estada ? " - ESTADA " + estada : "")].join("\n");
}
export function seloDoDocumento(v) {   // [texto, válido?] ou null
  const dig = String(v || "").replace(/\D/g, "");
  if (!dig) return null;
  if (dig.length === 11) return cpfValido(v) ? ["CPF válido", true] : ["CPF com dígito errado", false];
  if (dig.length === 14) return cnpjValido(v) ? ["CNPJ válido", true] : ["CNPJ com dígito errado", false];
  return ["Documento incompleto", false];
}
