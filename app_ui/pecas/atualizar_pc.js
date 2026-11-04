// Animação simples do "Atualizar este PC" / "Atualizar todos os PCs" (29/10/2026, pedido do João: algo bem simples e bem informativo).
// Depois do clique o botão mostra "Pedido enviado…" com o ícone girando e, embaixo, uma barrinha que corre e o que se espera. O Painel já
// recebe a versão de cada PC a cada poucos segundos: quando a versão muda (ou aparece o aviso ATUALIZADO na atividade), vira "✓ Atualizado".
// Passou de 1 minuto sem mudar: âmbar, "Sem mudança em 1 min · veja o Log", e o botão volta a ficar livre.
// As regras ficam aqui, sem tocar na tela, para poderem ser testadas. Quem desenha é painel.js (desenharMaquinas).
const ATZ_LIMITE_MS = (globalThis.aj?.("tela.atualizar_pc_limite_segundos") ?? 60) * 1000;   // sem mudança por tanto tempo: avisa
const ATZ_FIM_MS = (globalThis.aj?.("tela.atualizar_pc_resultado_segundos") ?? 3.5) * 1000;       // o resultado fica à vista por tanto tempo e o botão volta ao normal

// pcs: os PCs que vão atualizar ({pc, agente, versao}). Guarda a versão de antes de cada um.
function atzNovo(para, pcs, agora = Date.now()) {
  return { para, desde: agora, fim: 0, pcs: pcs.map(p => ({ pc: p.pc, agente: p.agente || p.pc, antes: p.versao || "" })) };
}

// d: o que a página Atividade recebeu ({pcs:[{pc, versao}], eventos:[{pc, tipo, quando}]}).
// -> { estado: "andando" | "ok" | "sem", feitos, total, faltam:[nome], botao, linha }
function atzSituacao(a, d, agora = Date.now()) {
  const eventos = d?.eventos || [], pcsAgora = d?.pcs || [];
  const mudou = x => {
    const p = pcsAgora.find(q => q.pc === x.pc);
    if (p && p.versao && p.versao !== x.antes) return true;   // o PC já publica a versão nova
    return eventos.some(e => e.pc === x.pc && e.tipo === "ATUALIZADO" && Date.parse(String(e.quando).replace(" ", "T")) >= a.desde - 1000);
  };
  const total = a.pcs.length, feitos = a.pcs.filter(mudou).length, faltam = a.pcs.filter(x => !mudou(x)).map(x => x.agente);
  const todos = a.para === "TODOS", decorrido = agora - a.desde;
  if (feitos >= total) {
    return { estado: "ok", feitos, total, faltam, botao: "✓ Atualizado", linha: todos ? `${feitos} de ${total} atualizados` : "Está na versão nova" };
  }
  if (decorrido >= ATZ_LIMITE_MS) {
    return { estado: "sem", feitos, total, faltam, botao: "Sem mudança",
      linha: todos ? `${feitos} de ${total} atualizados · sem mudança: ${faltam.join(", ")}` : "Sem mudança em 1 min · veja o Log" };
  }
  return { estado: "andando", feitos, total, faltam, botao: "Pedido enviado…",
    linha: todos ? `${feitos} de ${total} atualizados · aguardando` : "Aguardando o PC reiniciar (até 1 min)" };
}

// Fim de um acompanhamento: ok ou sem mudança ficam à vista por ATZ_FIM_MS e depois o botão volta ao normal.
function atzTerminou(a, sit, agora = Date.now()) {
  if (sit.estado === "andando") return false;
  if (!a.fim) a.fim = agora;
  return agora - a.fim >= ATZ_FIM_MS;
}
