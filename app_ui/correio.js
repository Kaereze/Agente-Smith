// E-mails: espelho do Outlook dos 4 PCs, no formato do Outlook (usuário, 08/10/2026): lista compacta, 1 linha por
// e-mail separada por Hoje / Ontem / Esta semana; ao clicar, o e-mail aberto à direita (De, Para, Data, texto) e o
// histórico do hóspede puxado ao vivo do Outlook. Tudo que se faz aqui (responder, encaminhar, excluir) roda no
// Outlook do PC dono por trás, sem abrir janela. A busca vai direto ao Outlook dos 4 PCs. Usa api/$/esc/toast/st.
let cx = { caixa: "entrada", dados: null, sel: null, hist: {}, textos: {}, hotel: "", live: null, buscando: "",
           resolvendo: {}, escondidos: {}, desfazer: null, manterNaoLido: {}, timerBusca: null, conv: {},
           soNaoLidos: false, fechados: {}, caixaSel: "", soForm: false, pcsAbertos: {}, pcsTodas: {}, aba: "inicio",
           semPastas: false, menu: false };   // igual ao Outlook (15/10/2026): pasta escolhida, faixa e menus
const CAIXAS = { entrada: "Caixa de entrada", urgencia: "Urgência", enviados: "Itens enviados" };
// O Painel só mostra a nota como emitida/enviada (e oferece "Concluir") quando houver uma regra concreta, que o João ainda vai definir
// (29/10/2026). Até lá: sem "NF na pasta", sem "NF enviada", sem Concluir e sem o histórico x notas prontas.
const RECONHECE_NF = false;
const CLASSES = { corrigir: ["Corrigir / cancelar NF", "erro"], complementar: ["Nota complementar", "atencao"],
  cobranca: ["Cobrança", "atencao"], dados_tomador: ["Dados do tomador", "info"], pedido_nf: ["Pedido de NF", "ok"] };
const PASTAS = { entrada: "Recebido", enviado: "Enviado", excluido: "Excluído" };
const RESOLVENDO_MS = (globalThis.aj?.("tela.linha_resolvendo_minutos") ?? 4) * 60 * 1000;   // cinza até o espelho do PC dono confirmar (até ~2 min) e a linha sumir

async function carregarCorreio(soSeMudou = false) {   // soSeMudou: volta automática, igual = não redesenha (velocidade 3)
  try {
    const j = await api("/api/correio");
    if (!j.emails) return;
    if (soSeMudou && j.__igual) return;
    cx.dados = j;
    const agora = Date.now();
    for (const [k, t] of Object.entries(cx.resolvendo)) if (agora - t > RESOLVENDO_MS) delete cx.resolvendo[k];
    desenharLateralCorreio();
    if (typeof desenharSeletorCaixa === "function") desenharSeletorCaixa();
    if (pn.vista === "correio") desenharCorreio();
    else if (pn.vista === "fila") desenharAbasNotas();   // e-mails chegaram: atualiza os números das abas
    else if (pn.vista === "visao" && typeof desenharVisao === "function") desenharVisao();   // 23/10/2026: abria com "E-mails na caixa: 0"
  } catch (e) { /* a próxima volta tenta de novo */ }
}

const doEscopo = (e, alvo) => doAgente([nomeAgente(e.pc)], alvo);   // a caixa é do PC de quem (filtro dos 4 agentes)
const emailsDa = (caixa, alvo) => (cx.dados?.emails || []).filter(e => !cx.escondidos[e.id] && doEscopo(e, alvo) && (caixa === "urgencia" ? e.urgente : true));   // Entrada = a caixa inteira, igual ao Outlook (14/10/2026)
function desenharLateralCorreio() {
  const c = cx.dados?.contagem || {};
  const n = (id, v, alerta) => { const el = $(id); if (!el) return; el.textContent = v ? v.toLocaleString("pt-BR") : "";
    el.classList.toggle("alerta-n", !!(alerta && v)); };
  n("nav-entrada-n", emailsDa("entrada").filter(e => e.lido === false).length);   // não lidos do Outlook, do agente escolhido
  n("nav-urgencia-n", emailsDa("urgencia").length, true);
}

const nomeAgente = pc => (cx.dados?.pcs || []).find(p => p.pc === pc)?.agente || cx.live?.agentes?.[pc] || pc;
const pcOnline = pc => !!(cx.dados?.pcs || []).find(p => p.pc === pc)?.online;
function horaCurta(iso) {
  if (!iso) return "";
  const d = iso.slice(0, 10);
  return d === hojeIsoF() ? iso.slice(11, 16) : d === ontemIso() ? "Ontem " + iso.slice(11, 16) : d.slice(8, 10) + "/" + d.slice(5, 7);
}
const dataLonga = iso => { const d = new Date(iso); return isNaN(d) ? iso : d.toLocaleString("pt-BR", { weekday: "short", day: "2-digit",
  month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" }); };
function grupoData(iso) {   // Hoje / Ontem / Esta semana / Mais antigos (como o Outlook)
  const dias = diasDesde(iso);
  return dias === 0 ? "Hoje" : dias === 1 ? "Ontem" : dias < 7 ? "Esta semana" : dias < 14 ? "Semana passada" : "Mais antigos";
}
const etiqueta = c => CLASSES[c] ? `<span class="et et-${CLASSES[c][1]}">${esc(CLASSES[c][0])}</span>` : "";
function textoBusca(e) {
  return semAcento([e.nome, e.de, e.assunto, e.previa, e.hotel, e.para, e.caixa,
    (e.classes || []).map(k => CLASSES[k]?.[0]).join(" "), e.agente].join(" \n "));
}
function passaBusca(e, busca) {
  if (!busca) return true;
  const t = textoBusca(e);
  return semAcento(busca).split(/\s+/).filter(Boolean).every(p => t.includes(p) || soDigitos(t).includes(soDigitos(p)));
}
