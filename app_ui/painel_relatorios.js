// painel_relatorios.js: parte de painel.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// ---------- Relatório do dia e da semana (Gerência) — dados do Mail Analytics, só leitura (usuário, 11/10/2026) ----------
const REL = { tipo: "mes", desl: 0, html: "", chave: "", em: 0, texto: "" };   // repaginação v2: mês × mês anterior; dia -1 = último dia com dados
const COLS_REL = [["pedidos", "Pedidos (formulário)"], ["recebidos", "E-mails recebidos"], ["enviados", "E-mails enviados"],
                  ["nfs", "NFs emitidas"], ["subst_canc", "Subst./canc."], ["ligacoes", "Ligações"]];
async function carregarRelatorio(forcar = false) {
  const chave = REL.tipo + ":" + REL.desl;
  if (!forcar && REL.chave === chave && Date.now() - REL.em < 5 * 60 * 1000) return;
  REL.chave = chave; REL.em = Date.now();
  const r = await api(`/api/relatorio_semana?tipo=${REL.tipo}&deslocamento=${REL.desl}`);
  if (!r.erro && REL.desl < 0) { REL.desl = r.deslocamento; REL.chave = REL.tipo + ":" + REL.desl; }
  REL.html = r.erro ? `<div class="vazio">${esc(r.erro)}</div>` : htmlRelatorio(r);
  REL.texto = r.texto || "";
  if ($("ger-relatorio")) $("ger-relatorio").innerHTML = REL.html;
}
// Gerência v2 (usuário, 14/10/2026): relatório que o gerente lê em 1 minuto — volume e variação, canceladas/refeitas,
// onde as solicitações se perdem e "O que melhorar". Mail Analytics (só leitura) + o que o Painel/Outlook sabem.
function numerosPainel(ini, fim) {
  const agenteDe = s => AG[String(s.hotel || "").split(" / ")[0]] || s.dono || "Sem agente";
  const chegada = s => new Date(`${s.data}T${horaDoCarimbo(s.carimbo) || "12:00"}`);
  const isoEnvio = q => { const m = String(q || "").match(/(\d{2})\/(\d{2})\/(\d{4}) (\d{2}):(\d{2})/); return m ? `${m[3]}-${m[2]}-${m[1]}T${m[4]}:${m[5]}` : ""; };
  const pedidos = st.fila.filter(s => s.data >= ini && s.data <= fim);
  const envios = [];
  st.fila.forEach(s => (s.envios || []).forEach(v => { const iso = isoEnvio(v.quando); if (iso.slice(0, 10) >= ini && iso.slice(0, 10) <= fim)
    envios.push({ s, h: (new Date(iso) - chegada(s)) / 36e5, ag: agenteDe(s) }); }));
  const validos = envios.filter(e => e.h >= 0);
  const pct = l => l.length ? Math.round(100 * l.filter(e => e.h <= 48).length / l.length) : null;
  const porAg = {};
  validos.forEach(e => (porAg[e.ag] ||= []).push(e));
  const abertos = pedidos.filter(s => s.situacao !== "concluida");
  const vencidos = abertos.filter(s => (prazoInfo(s.prazo)?.resta ?? 1) <= 0);
  const comNf = pedidos.filter(s => s.situacao === "concluida" || s.nfs?.length).length;
  const enviados = pedidos.filter(s => s.envios?.length).length;
  const fds = s => { const d = chegada(s); return d.getDay() === 0 || d.getDay() === 6 || (d.getDay() === 5 && d.getHours() >= 18); };
  return { pedidos, noPrazo: pct(validos), porAgPrazo: Object.fromEntries(Object.entries(porAg).map(([a, l]) => [a, pct(l)])),
    perdidas: vencidos.length, vencidos, comNf, enviados,
    faltaDado: abertos.filter(s => faltaDados(s).length).length, esperando: vencidos.filter(s => s.situacao === "tratativa").length,
    fimDeSemana: vencidos.filter(fds).length, agenteDe };
}
function htmlRelatorio(r) {
  const n = v => (v ?? 0).toLocaleString("pt-BR");
  const dt = iso => iso.slice(8, 10) + "/" + iso.slice(5, 7);
  const MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"];
  const nomeMes = MESES[Number(r.ini.slice(5, 7)) - 1];
  const titulo = r.tipo === "mes" ? `Relatório de ${nomeMes}` : r.tipo === "dia" ? `Relatório do dia ${dt(r.ini)}` : `Relatório da semana`;
  const contra = r.tipo === "mes" ? "mês anterior" : r.tipo === "dia" ? "dia anterior" : "semana anterior";
  const pa = numerosPainel(r.ini, r.ate), pb = numerosPainel(r.ini_anterior || r.ini, r.fim_anterior || r.ini);
  const BOM_SUBIR = { nfs: true, enviados: true, noprazo: true, subst_canc: false, perdidas: false };
  const varTxt = (x, y, k, pts) => { if (y == null || (!y && !pts)) return `<span class="var-n">sem comparação</span>`;
    const d = pts ? x - y : Math.round(100 * (x - y) / y); if (!d) return `<span class="var-n">igual · era ${y}${pts ? "%" : ""}</span>`;
    const cls = BOM_SUBIR[k] === undefined ? "neutro" : (d > 0) === BOM_SUBIR[k] ? "bom" : "ruim";
    return `<span class="var-n"><em class="${cls}">${d > 0 ? "▲" : "▼"} ${Math.abs(d)}${pts ? " pts" : "%"}</em> · era ${y}${pts ? "%" : ""}</span>`; };
  const kpi = (rot, v, sub) => `<div class="g-kpi"><small>${rot}</small><b>${v}</b>${sub}</div>`;
  const T = r.total, A = r.total_anterior;
  const hot = (r.hoteis_todos || []);
  const canc = hot.filter(h => h.subst_canc).sort((x, y) => y.subst_canc - x.subst_canc).slice(0, 6);
  const maxCanc = Math.max(1, ...canc.map(h => h.subst_canc));
  const mudaram = hot.filter(h => h.recebidos + h.recebidos_ant >= 5).map(h => ({ ...h, d: h.recebidos_ant ? (h.recebidos - h.recebidos_ant) / h.recebidos_ant : 1 }))
    .sort((x, y) => Math.abs(y.d) - Math.abs(x.d)).slice(0, 6);
  // O que melhorar: regras simples sobre os números acima (sem IA)
  const ideias = [];
  if (canc.length && T.subst_canc) ideias.push(["Notas refeitas concentradas", `<em>${esc(canc[0].hotel)}</em> teve ${canc[0].subst_canc} de ${T.subst_canc} substituições/cancelamentos do período. Conferir o tomador antes de emitir para esse hotel.`]);
  const piorAg = Object.entries(pa.porAgPrazo).filter(([a, v]) => v != null && a !== "Sem agente").sort((x, y) => x[1] - y[1])[0];
  if (piorAg && piorAg[1] < 90) ideias.push([`${esc(piorAg[0])} abaixo da meta de prazo`, `<em>${piorAg[1]}%</em> das notas enviadas em até 48 h (meta: 90%). Ver se a carteira de hotéis está pesada.`]);
  const venc = {}; pa.vencidos.forEach(s => venc[s.hotel] = (venc[s.hotel] || 0) + 1);
  const piorHotel = Object.entries(venc).sort((x, y) => y[1] - x[1])[0];
  if (piorHotel && piorHotel[1] >= 2) ideias.push([`${esc(piorHotel[0])} acumula pedidos vencidos`, `<em>${piorHotel[1]} pedidos</em> do período passaram do prazo sem NF.`]);
  if (pa.faltaDado) ideias.push(["Pedidos parados por falta de dado", `<em>${pa.faltaDado}</em> pedidos sem nome, CPF/CNPJ ou o que entra na nota. Usar "Pedir o que falta" logo que o pedido chega.`]);
  if (pa.fimDeSemana && pa.perdidas && pa.fimDeSemana / pa.perdidas >= 0.25) ideias.push(["Fim de semana acumula", `<em>${Math.round(100 * pa.fimDeSemana / pa.perdidas)}% dos vencidos</em> chegaram entre sexta 18 h e domingo. Vale um plantão no sábado de manhã.`]);
  if (A.ligacoes && T.ligacoes > A.ligacoes * 1.15) ideias.push(["Ligações subindo", `As ligações subiram <em>${Math.round(100 * (T.ligacoes - A.ligacoes) / A.ligacoes)}%</em>. Em geral é hóspede cobrando nota: responder primeiro quem cobrou de novo.`]);
  const agentes = Object.keys(r.por_agente).sort((a, b) => r.por_agente[b].nfs - r.por_agente[a].nfs);
  const atrasados = Object.entries(r.ultimo_dia || {}).filter(([, d]) => d && d < r.ate).map(([a, d]) => `${a} (até ${dt(d)})`);
  return `<div class="g-cab"><div><h3>${titulo}</h3><div class="sub">${dt(r.ini)} a ${dt(r.ate)} comparado com ${dt(r.ini_anterior || r.ini)} a ${dt(r.fim_anterior || r.ini)} · fontes: Mail Analytics (só leitura) e Painel</div></div>
      <div class="g-ferr"><div class="seg" role="group" aria-label="Comparação">
        <button data-rel-tipo="mes" aria-pressed="${r.tipo === "mes"}">Mês × mês anterior</button><button data-rel-tipo="semana" aria-pressed="${r.tipo === "semana"}">Semana</button><button data-rel-tipo="dia" aria-pressed="${r.tipo === "dia"}">Dia</button></div>
        <button class="btn-ic" data-rel-mover="1" title="Período anterior" aria-label="Período anterior">◀</button>
        <button class="btn-ic" data-rel-mover="-1" title="Próximo período" aria-label="Próximo período" ${REL.desl <= 0 ? "disabled" : ""}>▶</button>
        <button data-rel-copiar="1" title="Copia o resumo em texto pra colar no WhatsApp ou no e-mail"><svg class="ic"><use href="#i-copiar"/></svg>Copiar resumo</button></div></div>
    <div class="g-kpis">
      ${kpi("Solicitações", n(T.pedidos), varTxt(T.pedidos, A.pedidos, "pedidos"))}
      ${kpi("NFs emitidas", n(T.nfs), varTxt(T.nfs, A.nfs, "nfs"))}
      ${kpi("Enviadas no prazo", pa.noPrazo == null ? "—" : pa.noPrazo + "%", pa.noPrazo == null ? `<span class="var-n">até 48 h</span>` : varTxt(pa.noPrazo, pb.noPrazo, "noprazo", true))}
      ${kpi("Canceladas ou refeitas", n(T.subst_canc), varTxt(T.subst_canc, A.subst_canc, "subst_canc"))}
      ${kpi("Perdidas", n(pa.perdidas), varTxt(pa.perdidas, pb.perdidas, "perdidas"))}
      ${kpi("Ligações", n(T.ligacoes), varTxt(T.ligacoes, A.ligacoes, "ligacoes"))}
    </div>
    <div class="g-grade">
      <section class="g-painel"><div class="g-tit"><b>Canceladas ou refeitas · onde</b><small>${n(T.subst_canc)} no período</small></div>
        ${canc.length ? `<div class="g-barras">${canc.map(h => `<div class="g-br"><span>${esc(h.hotel)}</span><span class="g-trilho"><i style="width:${Math.round(100 * h.subst_canc / maxCanc)}%"></i></span><span class="g-n">${h.subst_canc}</span></div>`).join("")}</div>
          <p class="g-nota">O Mail Analytics conta as substituições e cancelamentos, mas não grava o motivo.</p>` : `<div class="vazio">Nenhuma nota cancelada ou refeita no período.</div>`}</section>
      <section class="g-painel"><div class="g-tit"><b>Solicitações perdidas · onde se perdem</b><small>pedidos do formulário no período</small></div>
        <div class="g-funil">${[["Recebidas", pa.pedidos.length], ["Com NF", pa.comNf], ["NF enviada", pa.enviados]].map(([rot, v]) =>
          `<div class="g-fl"><span>${rot}</span><span class="g-trilho"><i class="v" style="width:${pa.pedidos.length ? Math.round(100 * v / pa.pedidos.length) : 0}%"></i></span><span class="g-n">${n(v)}</span></div>`).join("")}</div>
        <div class="g-perdas"><div><b>${n(pa.perdidas - pa.esperando - Math.min(pa.faltaDado, pa.perdidas))}</b><span>sem NF e com o prazo vencido</span></div>
          <div><b>${n(pa.esperando)}</b><span>esperando o hóspede responder</span></div><div><b>${n(pa.faltaDado)}</b><span>com dado faltando para emitir</span></div></div></section>
    </div>
    <section class="g-painel"><div class="g-tit"><b>O que melhorar</b><small>gerado a partir dos números acima</small></div>
      ${ideias.length ? `<div class="g-ideias">${ideias.slice(0, 4).map(([t1, t2], i) => `<div class="g-ideia"><i>${i + 1}</i><div><b>${t1}</b><span>${t2}</span></div></div>`).join("")}</div>`
        : `<div class="vazio">Nada fora do normal no período. 👍</div>`}</section>
    <div class="g-grade">
      <section class="g-painel"><div class="g-tit"><b>Por agente</b><small>${contra}</small></div>
        <div class="tabela-wrap"><table class="ger-tab"><thead><tr><th>Agente</th><th class="num">Pedidos</th><th class="num">E-mails</th><th class="num">NFs</th><th class="num">No prazo</th><th class="num">Refeitas</th><th class="num">Variação NFs</th></tr></thead><tbody>
          ${agentes.map(a => { const d = r.por_agente[a], b = r.anterior[a] || {};
            return `<tr><td><b>${esc(a)}</b></td><td class="num">${d.dias || d.pedidos ? n(d.pedidos) : "—"}</td><td class="num">${d.dias ? n(d.recebidos) : `<span class="dica">sem dados</span>`}</td>
              <td class="num">${d.dias ? n(d.nfs) : "—"}</td><td class="num">${pa.porAgPrazo[a] == null ? "—" : pa.porAgPrazo[a] + "%"}</td><td class="num">${d.dias ? n(d.subst_canc) : "—"}</td>
              <td class="num">${d.dias && b.nfs ? varTxt(d.nfs, b.nfs, "nfs").replace(/ · era \d+/, "") : "—"}</td></tr>`; }).join("")}
        </tbody></table></div></section>
      <section class="g-painel"><div class="g-tit"><b>Hotéis que mais mudaram</b><small>e-mails recebidos · ${contra}</small></div>
        ${mudaram.length ? `<div class="tabela-wrap"><table class="ger-tab"><thead><tr><th>Hotel</th><th class="num">Agora</th><th class="num">Antes</th><th class="num">Variação</th><th class="num">NFs</th></tr></thead><tbody>
          ${mudaram.map(h => `<tr><td>${esc(h.hotel)}</td><td class="num">${n(h.recebidos)}</td><td class="num">${n(h.recebidos_ant)}</td>
            <td class="num"><em class="${h.d > 0 ? "neutro" : "neutro"}">${h.d > 0 ? "▲" : "▼"} ${Math.abs(Math.round(100 * h.d))}%</em></td><td class="num">${n(h.nfs)}</td></tr>`).join("")}
        </tbody></table></div>` : `<div class="vazio">Pouco movimento para comparar.</div>`}</section>
    </div>
    ${r.contado_painel?.length ? `<p class="dica">${esc(r.contado_painel.join(" e "))}: sexta a domingo contados pelo Painel (o Mail Analytics grava o fim de semana na segunda de manhã; nada é somado duas vezes).</p>` : ""}
    ${atrasados.length ? `<p class="dica">⚠ O Mail Analytics ainda não gravou todos os dias de: ${esc(atrasados.join(", "))}. Os números desses agentes podem estar incompletos.</p>` : ""}`;
}
document.addEventListener("click", async e => {
  const t = e.target.closest("[data-rel-tipo],[data-rel-mover],[data-rel-copiar]");
  if (!t) return;
  if (t.dataset.relTipo) { REL.tipo = t.dataset.relTipo; REL.desl = REL.tipo === "dia" ? -1 : 0; }
  if (t.dataset.relMover) REL.desl = Math.max(0, REL.desl + Number(t.dataset.relMover));
  if (t.dataset.relCopiar) {
    try { await navigator.clipboard.writeText(REL.texto); toast("Resumo copiado: é só colar no WhatsApp ou no e-mail"); }
    catch (er) { toast("Não consegui copiar", true); }
    return;
  }
  $("ger-relatorio").innerHTML = `<div class="vazio">Carregando o relatório…</div>`;
  carregarRelatorio(true);
});

// ---------- Cadastro completo (Máquinas): caixas e planilhas de hotel que faltam no Cadastro_Hoteis ----------
const CAD = { html: "", em: 0, dados: null };
async function carregarCadastro(forcar = false) {
  if (!forcar && Date.now() - CAD.em < 60 * 1000) return;
  CAD.em = Date.now();
  const r = await api("/api/cadastro/faltando");
  CAD.dados = r;
  CAD.html = htmlCadastro(r);
  if ($("cad-faltando")) $("cad-faltando").innerHTML = CAD.html;
}
function htmlCadastro(r) {
  const lista = r.faltando || [];
  if (!lista.length) return `<div class="cartao-topo"><div><h3>Cadastro de hotéis</h3><div class="sub">Toda caixa de hotel do Outlook e toda planilha de formulário estão no Cadastro_Hoteis ✓</div></div></div>`;
  const ops = a => (r.agentes || []).map(x => `<option ${x === a ? "selected" : ""}>${esc(x)}</option>`).join("");
  return `<div class="cartao-topo"><div><h3>Cadastro de hotéis · ${lista.length} faltando</h3>
      <div class="sub">Sem cadastro, a planilha do hotel não é copiada e a caixa fica sem agente. Confira o nome (igual ao da planilha) e cadastre.</div></div></div>
    <div class="cad-lista">${lista.map((x, i) => `<div class="cad-linha" data-cad="${i}">
      <input class="cad-hotel" value="${esc(x.hotel)}" aria-label="Nome do hotel" title="Nome do hotel (igual ao da planilha do formulário)">
      <input class="cad-email" value="${esc(x.email)}" placeholder="caixa notafiscal@… (se tiver)" aria-label="E-mail da caixa">
      <select class="cad-agente" aria-label="Agente">${x.agente ? "" : "<option value=''>Agente…</option>"}${ops(x.agente)}</select>
      <button class="prim" data-cad-salvar="${i}">Cadastrar</button>
      <span class="dica">${esc(x.motivo)}</span></div>`).join("")}</div>`;
}
document.addEventListener("click", async e => {
  const b = e.target.closest("[data-cad-salvar]");
  if (!b) return;
  const l = b.closest(".cad-linha");
  const corpo = { hotel: l.querySelector(".cad-hotel").value, email: l.querySelector(".cad-email").value, agente: l.querySelector(".cad-agente").value };
  if (!corpo.agente) return toast("Escolha o agente", true);
  b.disabled = true;
  const r = await api("/api/cadastro/adicionar", corpo);
  if (r.ok) { toast(`${corpo.hotel} cadastrado ✓ (a cópia dos hotéis pega na próxima volta)`); carregarCadastro(true); }
  else { b.disabled = false; toast(r.motivo || r.erro || "Não deu certo", true); }
});
