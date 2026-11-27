// Contas da Visão geral, feitas só com os dados que o Painel tem (regra P2: nunca inventar número;
// toda comparação diz contra o quê). Funções puras: recebem os dados, devolvem números e frases.

export const diaISO = (d) => {
  const x = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return x.toISOString().slice(0, 10);
};
const diaDe = (texto) => (texto || "").slice(0, 10);

export function ultimosDiasUteis(hoje, quantos = 8) {
  const dias = [];
  const d = new Date(hoje);
  while (dias.length < quantos) {
    if (d.getDay() !== 0 && d.getDay() !== 6) dias.unshift(diaISO(d));
    d.setDate(d.getDate() - 1);
  }
  return dias;
}

// Por que o pedido ainda está aberto — os mesmos grupos da tela de hoje, em palavras de quem usa.
export const MOTIVOS = [
  { chave: "hotel", nome: "Ainda não foi para o hotel", explica: "O robô ainda não mandou o pedido para a caixa do hotel.", cor: "var(--azul-texto)" },
  { chave: "nf", nome: "Esperando a NF ser emitida", explica: "O hotel recebeu, mas a nota ainda não apareceu.", cor: "var(--verde)" },
  { chave: "hospede", nome: "Esperando resposta do hóspede", explica: "Perguntamos um dado (CPF/CNPJ, endereço) e esperamos.", cor: "var(--ambar-texto)" },
  { chave: "pronta", nome: "NF pronta, falta enviar", explica: "A nota existe; só falta o e-mail com o PDF.", cor: "var(--vermelho-texto)" },
];

export function motivoDoPedido(p) {
  if (p.situacao === "concluida") return p.envio_pendente ? "pronta" : null;   // concluída e enviada: não está aberto
  if (p.situacao === "aguardando_envio" || !p.enviado) return "hotel";
  if (p.situacao === "tratativa" || (p.tratativas || []).length) return "hospede";
  return "nf";
}

export function resumoDoDia(estado, correio, agora = new Date()) {
  const hoje = diaISO(agora);
  const ontemD = new Date(agora); ontemD.setDate(ontemD.getDate() - 1);
  const ontem = diaISO(ontemD);
  const fila = estado?.fila || [];
  const emails = correio?.emails || [];
  const enviados = correio?.enviados || [];

  const pedidosHoje = fila.filter((p) => p.data === hoje).length;
  const pedidosOntem = fila.filter((p) => p.data === ontem).length;
  const ehNF = (e) => (e.anexos || []).some((a) => /\bNF\b|nota/i.test(a));
  const nfHoje = enviados.filter((e) => diaDe(e.quando) === hoje && ehNF(e)).length;
  const nfOntem = enviados.filter((e) => diaDe(e.quando) === ontem && ehNF(e)).length;

  const abertos = fila.map((p) => motivoDoPedido(p)).filter(Boolean);
  const porMotivo = MOTIVOS.map((m) => ({ ...m, total: abertos.filter((k) => k === m.chave).length }));
  const semResposta = emails.filter((e) => e.pasta === "entrada" && !e.respondido && (e.dias || 0) > 2);
  const maisAntigo = [...semResposta].sort((a, b) => (b.dias || 0) - (a.dias || 0))[0];

  const dias = ultimosDiasUteis(agora, 8);
  const porDia = dias.map((d) => ({
    dia: d,
    pedidos: fila.filter((p) => p.data === d).length,
    emails: emails.filter((e) => diaDe(e.recebido || e.quando) === d).length,
  }));

  const caixaPcs = estado?.caixa_pcs || {};
  const agentes = Object.values(caixaPcs).map((c) => ({ nome: c.agente, emails: c.emails || 0, ligado: !!c.online }))
    .sort((a, b) => b.emails - a.emails);
  const totalAgentes = agentes.reduce((s, a) => s + a.emails, 0);

  const pcs = estado?.pcs || [];
  const pcsLigados = pcs.filter((p) => p.online).length;
  const robo = estado?.status || {};

  return {
    hoje, pedidosHoje, pedidosOntem, nfHoje, nfOntem, abertos: abertos.length, porMotivo,
    semResposta: semResposta.length, maisAntigo, porDia, agentes, totalAgentes,
    pcs, pcsLigados, robo, urgencia: correio?.contagem?.urgencia || 0,
    prontas: porMotivo.find((m) => m.chave === "pronta").total,
    paraHotel: porMotivo.find((m) => m.chave === "hotel").total,
  };
}

// "3 a mais que ontem" / "igual a ontem": a comparação sempre diz contra o quê.
export function comparaOntem(hoje, ontem, maisEBom = true) {
  const d = hoje - ontem;
  if (d === 0) return { texto: "igual a ontem", bom: true };
  const texto = `${Math.abs(d)} a ${d > 0 ? "mais" : "menos"} que ontem`;
  return { texto, bom: maisEBom ? d > 0 : d < 0 };
}

export const porcento = (parte, todo) => (todo ? Math.round((parte / todo) * 100) : 0);
