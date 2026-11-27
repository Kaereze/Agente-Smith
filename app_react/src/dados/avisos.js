// Os avisos do sistema (estado.saude: [{ texto, nivel, tipo, pc }]) ditos do jeito que a equipe fala, e o que fazer.
// Um lugar só: o sino do topo, o Robô e o Monitoramento leem daqui (vieram de robo.js e telas.js da tela de antes).

// -> [título, linha de apoio]
export function fraseDoAviso(t) {
  const texto = String(t || "");
  let q;
  if ((q = texto.match(/^Caixa de Sa[ií]da do Outlook de (.+?) travada: (\d+) e-mail\(s\) parado\(s\) há mais de (\d+) min/)))
    return [`O Outlook de ${q[1]} não está enviando`, `${q[2]} ${+q[2] === 1 ? "e-mail preso" : "e-mails presos"} na Caixa de Saída há mais de ${q[3]} min`];
  if ((q = texto.match(/^PC de (.+?) rodando outra vers[ãa]o \(/)))
    return [`O PC de ${q[1]} está com uma versão diferente do Painel`, "Em Monitoramento, use “Atualizar todos os PCs”"];
  const m = texto.match(/^(.*?)(?:: |\. )(.*)$/);
  return m ? [m[1], m[2]] : [texto, ""];
}

// O que fazer, por tipo de aviso: { passos: [texto] } | { ver: "robo" } | {}
export function comoResolver(t) {
  const texto = String(t || "");
  if (/Caixa de Sa[ií]da/i.test(texto)) return { passos: ["No PC dessa pessoa, abra o Outlook e vá em Caixa de Saída.", "Apague ou reenvie o e-mail que está parado.", "O Painel confere sozinho em até 1 minuto e este aviso some."] };
  if (/Outlook (fechado|aberto sem janela)/i.test(texto)) return { passos: ["No PC dessa pessoa, abra o Outlook (com a janela).", "O robô volta a ler os e-mails sozinho em instantes."] };
  if (/sem envio ao hotel/i.test(texto)) return { ver: "robo" };
  return {};
}

// Os avisos do sino: saúde do sistema primeiro (o grave antes), depois PCs desligados e hóspedes esperando
export function avisosDoPainel(estado, r, erro) {
  const lista = [];
  if (erro) lista.push({ icone: "alerta", grave: true, texto: erro, detalhe: "o Painel tenta de novo sozinho" });
  [...(estado?.saude || [])].sort((a, b) => (a.nivel === "warn") - (b.nivel === "warn")).forEach((a) => {
    const [t, d] = fraseDoAviso(a.texto);
    lista.push({ icone: a.tipo === "caixa" ? "caixa" : "alerta", grave: a.nivel !== "warn", texto: t, detalhe: d, ajuda: comoResolver(a.texto), monitor: true });
  });
  if (r) {
    const visto = (pc) => { const v = String((estado?.pcs || []).find((x) => x.pc === pc)?.visto || "").replace("T", " "); return v ? `visto pela última vez em ${v.slice(8, 10)}/${v.slice(5, 7)} às ${v.slice(11, 16)}` : "sem notícia dele ainda"; };
    r.pcs.filter((p) => !p.online).forEach((p) => lista.push({ icone: "pc", texto: `O PC de ${p.agente} está desligado`, detalhe: visto(p.pc), monitor: true }));
    if (r.semResposta) lista.push({ icone: "envelope", texto: `${r.semResposta} hóspedes sem resposta há mais de 2 dias`, detalhe: "veja na Caixa de entrada", ir: "correio" });
  }
  return lista;
}
