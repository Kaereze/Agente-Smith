// Catálogo de peças do Painel (22/10/2026): abre o Painel no MODO DEMONSTRAÇÃO (dados inventados) num Edge escondido,
// passa por cada tela e copia o HTML real de cada peça para catalogo_pecas.json. Só lê e abre telas; o "envio" do modo
// demonstração não manda nada. NUNCA rode contra o Painel de verdade (porta 8765 num PC do trabalho sem --demo).
// Uso: node copiar_pecas.js <pasta de saída> [porta do modo demonstração, padrão 8765]
// Depois: python gerar_catalogo.py <pasta do projeto> <pasta de saída>
const { spawn } = require("child_process"); const path = require("path"); const fs = require("fs");
const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"; const OUT = process.argv[2]; const PORTA = process.argv[3] || "8765";
const edge = spawn(EDGE, ["--headless=new", "--disable-gpu", "--remote-debugging-port=9476", "--user-data-dir=" + path.join(OUT, "edge-catalogo-pecas"), "about:blank"], { stdio: "ignore" });
const espera = ms => new Promise(r => setTimeout(r, ms));

// roda na página: copia um elemento (ou um clone aparado) com a cadeia de pais
function pegarNaPagina(sel, opts) {
  opts = opts || {};
  let el = null;
  for (const s of String(sel).split(" || ")) { try { el = document.querySelector(s); } catch (e) { el = null; } if (el) break; }
  if (!el) return { erro: "não achei " + sel };
  const r = el.getBoundingClientRect();
  const pais = [];
  for (let p = el.parentElement; p && p !== document.body; p = p.parentElement)
    pais.unshift({ tag: p.tagName.toLowerCase(), id: p.id || "", cls: typeof p.className === "string" ? p.className : "" });
  const c = el.cloneNode(true);
  if (opts.manter) { const [s, n] = opts.manter; [...c.querySelectorAll(s)].slice(n).forEach(x => x.remove()); }
  if (opts.tirar) c.querySelectorAll(opts.tirar).forEach(x => x.remove());
  return { html: c.outerHTML, largura: Math.round(r.width), altura: Math.round(r.height), pais,
           corpo: document.body.className, raiz: document.documentElement.className };
}

(async () => {
  let alvo; for (let i = 0; i < 50 && !alvo; i++) { await espera(300); try { alvo = (await (await fetch("http://127.0.0.1:9476/json")).json()).find(t => t.type === "page"); } catch (e) {} }
  const ws = new WebSocket(alvo.webSocketDebuggerUrl); await new Promise(r => ws.onopen = r);
  let id = 0; const pend = {}; const erros = [];
  ws.onmessage = m => { const j = JSON.parse(m.data); if (j.method === "Runtime.exceptionThrown") erros.push((j.params.exceptionDetails.exception?.description || j.params.exceptionDetails.text).split("\n")[0]); if (pend[j.id]) { pend[j.id](j.result); delete pend[j.id]; } };
  const cdp = (method, params = {}) => new Promise(r => { const i = ++id; pend[i] = r; ws.send(JSON.stringify({ id: i, method, params })); });
  const js = async e => { const r = await cdp("Runtime.evaluate", { expression: e, awaitPromise: true, returnByValue: true }); if (r.exceptionDetails) console.log("   erro JS:", e.slice(0, 70).replace(/\s+/g, " "), "→", (r.exceptionDetails.exception?.description || "").split("\n")[0]); return r.result?.value; };
  await cdp("Runtime.enable");
  await cdp("Emulation.setDeviceMetricsOverride", { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
  await cdp("Page.navigate", { url: `http://127.0.0.1:${PORTA}/` }); await espera(9000);
  if (!(await js("st.demo"))) { console.log("PAREI: este Painel não está no modo demonstração. Abra o PAINEL_DEMO_EM_CASA.bat."); edge.kill(); process.exit(1); }
  await js("window.__pegar = " + pegarNaPagina.toString() + "; 1");
  const pecas = [];
  const pegar = async (grupo, chave, sel, opts = {}) => {
    const r = await js(`__pegar(${JSON.stringify(sel)}, ${JSON.stringify(opts)})`);
    if (!r || r.erro) { console.log("FALTOU  " + chave + " — " + (r?.erro || "?")); return; }
    pecas.push({ grupo, chave, modo: opts.modo || "fluxo", estados: !!opts.estados, ...r });
    console.log("ok      " + chave + " (" + r.html.length + " bytes, " + r.largura + "×" + r.altura + ")");
  };
  const fazer = async (e, ms = 600) => { await js("(() => { " + e + " })(); 1"); await espera(ms); };

  // ---------- estrutura ----------
  await fazer(`escopo = "todos"; trocarVista("visao")`, 2500);
  await pegar("estrutura", "lateral-icones", ".lateral");
  await fazer(`$("btn-recolher").click()`, 700);
  await pegar("estrutura", "lateral-nomes", ".lateral");
  await fazer(`$("btn-recolher").click()`, 700);
  await fazer(`$("op-btn").click()`, 500);
  await pegar("estrutura", "quem-esta", "#op-menu", { modo: "flutua" });
  await fazer(`document.body.click()`, 300);
  await pegar("estrutura", "rodape", "footer.rodape-status");
  await fazer(`document.querySelector("#saude .s-bolha")?.click()`, 500);
  await pegar("estrutura", "saude", "#saude", { modo: "flutua" });
  await fazer(`document.body.click()`, 300);

  // ---------- visão geral ----------
  await pegar("visao", "resumo-dia", "section.resumo-dia");
  await pegar("visao", "cab-operador", "#visao > .cab-pagina");
  await pegar("visao", "dica-prof", "#visao > p.dica-prof");
  await pegar("visao", "faixa-resumo", ".faixa-resumo");
  await pegar("visao", "tabela-operador", "#visao .grade2 > .cartao:nth-child(1)");
  await pegar("visao", "grafico-idade", "#visao .grade2 > .cartao:nth-child(2)");
  await pegar("visao", "cartao-ligacoes", ".lig-cartao");
  await pegar("visao", "grafico-dias", "#visao > .cartao:last-child");
  await fazer(`document.querySelector('[data-vt="dias"]')?.click()`, 700);
  await pegar("visao", "grafico-dias-tabela", "#visao > .cartao:last-child");
  await fazer(`document.querySelector('[data-vt="dias"]')?.click()`, 500);

  // ---------- notas fiscais ----------
  await fazer(`trocarVista("fila")`, 2000);
  await pegar("notas", "lista-vazia", "#mesa section.quadro");
  // o modo demonstração não tem pedidos na Caixa de Entrada: marca 8 pedidos inventados como "na caixa", só nesta tela
  await fazer(`st.fila.slice(0, 8).forEach((s, i) => { s.na_caixa = { pc: ["DEMO-CLARA","DEMO-JOAO","DEMO-BERNARDO"][i % 3], caixa: "nf@hotelexemplo.com.br", recebido: s.data + "T1" + i + ":05:00", lido: i % 3 === 0, emails: 1 + (i % 2) }; }); montarTodos(); desenhar()`, 1200);
  await pegar("notas", "notas-cab", "#notas-cab");
  await pegar("notas", "lista-pedidos", "#mesa section.quadro", { manter: ["#lista > *", 6] });
  await fazer(`document.querySelector('#lista .nf-l')?.click()`, 1500);
  await pegar("notas", "linha-pedido-sel", "#lista .nf-l.sel || #lista .nf-l");
  await pegar("notas", "detalhe-pedido", "#detalhe", { tirar: "iframe" });
  await fazer(`document.querySelector('#status-cards .ol-filtro-bt')?.click()`, 500);
  await pegar("notas", "filtro-aberto", "#status-cards .peca-filtro", { modo: "flutua" });
  await fazer(`document.body.click()`, 300);

  // ---------- e-mails ----------
  await fazer(`trocarVista("correio"); cx.caixa = "entrada"; desenharLateralCorreio(); desenharCorreio()`, 2000);
  await pegar("emails", "faixa-outlook", "#cx-faixa");
  await pegar("estrutura", "topo", "header.topo");
  await pegar("emails", "cx-cab", ".cx-cab");
  await fazer(`document.querySelector('#cx-pastas .ol-pc2')?.click()`, 700);
  await pegar("emails", "pastas", "#cx-pastas");
  await pegar("emails", "lista-cab", "#cx-lcab");
  await pegar("emails", "linha-nao-lida", "#cx-lista .cx-l.nao-lido");
  await pegar("emails", "linha-urgente", "#cx-lista .cx-l.urgente");
  await fazer(`const e = cx.dados.emails[2]; e.classes = [...(e.classes || []), "formulario"]; cx.dados.emails[3].lido = true; desenharCorreio()`, 1000);
  await pegar("emails", "linha-form", "#cx-lista .cx-l:has(.pin)");
  await pegar("emails", "linha-lida", "#cx-lista .cx-l:not(.nao-lido):not(.urgente)");
  await pegar("emails", "lista-emails", "#cx-lista", { manter: ["#cx-lista > *", 7] });
  await fazer(`document.querySelector('#cx-lista .cx-l.nao-lido')?.click()`, 1500);
  await pegar("emails", "linha-selecionada", "#cx-lista .cx-l.sel");
  await pegar("emails", "leitura", "#cx-leitura", { tirar: "iframe" });
  await fazer(`document.querySelector('[data-pf-abrir="cx-filtro"]')?.click()`, 500);
  await pegar("emails", "filtro-lista", '[data-pf="cx-filtro"]', { modo: "flutua" });
  await fazer(`document.body.click()`, 300);
  await fazer(`const l = document.querySelector("#cx-lista .cx-l"); const r = l.getBoundingClientRect(); l.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, clientX: r.left + 60, clientY: r.top + 20 }))`, 500);
  await pegar("emails", "menu-direito", "#cx-ctx", { modo: "flutua" });
  await fazer(`fecharMenuEmail()`, 300);
  await fazer(`const b = $("busca"); b.focus(); b.value = "ana"; b.dispatchEvent(new Event("input", { bubbles: true }))`, 1800);
  await pegar("emails", "busca", "label.busca", { modo: "flutua" });
  await pegar("emails", "busca-sugestoes", ".sc-lista", { modo: "flutua" });
  await fazer(`const b = $("busca"); b.value = ""; b.dispatchEvent(new Event("input", { bubbles: true })); b.blur()`, 1200);
  await fazer(`cx.caixa = "enviados"; cx.filtroL = ""; desenharLateralCorreio(); desenharCorreio()`, 1000);
  await pegar("emails", "lista-enviados", "#cx-lista", { manter: ["#cx-lista > *", 5] });
  await fazer(`cx.caixa = "entrada"; desenharLateralCorreio(); desenharCorreio()`, 800);

  // ---------- escrever ----------
  await fazer(`document.querySelector('[data-ol-acao="novo"]')?.click()`, 2500);
  await pegar("escrever", "novo-email", ".modal.compor", { tirar: "iframe" });
  for (const [k, s] of [["bt-enviar", "#nf-ir"], ["bt-fechar", "#nf-fechar"], ["bt-modelo", "[data-modelo]"], ["bt-selo", ".selo-op"]]) await pegar("botoes", k, s, { estados: true });
  await pegar("botoes", "bt-ligacao", "#nf-lig", { estados: true });
  await fazer(`$("nf-lig").click()`, 300);
  await pegar("escrever", "escrever-topo-lig", ".modal.compor .compor-topo");
  await pegar("escrever", "escrever-cab-lig", ".modal.compor .compor-cab");
  await pegar("escrever", "zona-anexo", "#nf-soltar");
  await pegar("escrever", "respostas-prontas", ".modal.compor .linha-modelos || .modal.compor .modelos || .modal.compor [data-modelo]");
  await fazer(`const t = $("nf-de-txt"); t?.focus(); t && (t.value = "ara"); t?.dispatchEvent(new Event("input", { bubbles: true }))`, 700);
  await pegar("escrever", "combo-de", ".modal.compor .de-novo");
  await fazer(`$("nf-fechar").click()`, 800);
  await fazer(`document.querySelector('#cx-lista .cx-l.nao-lido')?.click()`, 1500);
  await fazer(`document.querySelector('[data-cx-faixa="nf"]')?.click()`, 2500);
  await pegar("escrever", "responder-nf", "#cx-leitura", { tirar: "iframe" });
  await fazer(`$("nf-fechar")?.click()`, 800);

  // ---------- envio e avisos ----------
  const env = (estado, aberto) => `if (!$("envios-andamento")) { const b = document.createElement("div"); b.id = "envios-andamento"; b.setAttribute("aria-live","polite"); document.body.appendChild(b); }
    $("envios-andamento").innerHTML = "";
    andamento.CAT = { ctx: { resp: { comNF: true, id: "x" }, pc: "DEMO-CLARA", chave: null, alvo: null, rascunho: {} }, estado: "${estado}", aberto: ${aberto}, fim: new Date() }; desenharEnvio("CAT")`;
  await fazer(env("entregue", false), 400);
  await pegar("envio", "pilula-enviando", "#envios-andamento", { modo: "flutua" });
  await fazer(env("enviado", false), 400);
  await pegar("envio", "pilula-enviado", "#envios-andamento", { modo: "flutua" });
  await fazer(env("falhou", false), 400);
  await pegar("envio", "pilula-erro", "#envios-andamento", { modo: "flutua" });
  await fazer(env("falhou", true), 400);
  await pegar("envio", "cartao-erro", "#envios-andamento", { modo: "flutua" });
  await fazer(`delete andamento.CAT; $("envios-andamento").innerHTML = ""`, 200);
  await fazer(`toast("Marcado como lido para a equipe")`, 300);
  await pegar("janelas", "toast", "body > .toast", { modo: "flutua" });
  await fazer(`toast("Não deu pra marcar agora", true)`, 300);
  await pegar("janelas", "toast-erro", "body > .toast", { modo: "flutua" });

  // ---------- robô ----------
  await fazer(`rbAbrir("agora")`, 2500);
  await pegar("robo", "robo-agora", ".modal.rb-sheet");
  await fazer(`document.querySelector('.rb-sheet [data-rb-ped]')?.click()`, 800);
  await pegar("robo", "robo-gaveta", ".rb-gaveta-ped");
  await fazer(`rbAbrir("reg")`, 2500);
  await pegar("robo", "robo-registro", ".modal.rb-sheet");
  await fazer(`rbFechar(true)`, 800);
  await pegar("robo", "robo-minimizado", "#rb-gaveta", { modo: "flutua" });
  await fazer(`rbz.gaveta = false; rbRenderGaveta(); rbMostrarFim()`, 500);
  await pegar("robo", "robo-fim", "#rb-fim", { modo: "flutua" });
  await fazer(`$("rb-fim")?.remove()`, 200);
  await pegar("botoes", "bt-robo", "#robo", { estados: true });

  // ---------- máquinas e ajuda ----------
  await fazer(`trocarVista("maquinas")`, 2500);
  await pegar("maquinas", "maquinas", "#v-maquinas");
  await fazer(`abrirAjuda()`, 1000);
  await pegar("janelas", "ajuda", ".modal-fundo .modal");
  await fazer(`document.querySelector(".modal-fundo")?.remove()`, 300);

  // ---------- peças únicas ----------
  await fazer(`const d = document.createElement("div"); d.id = "cat-etq"; d.style.cssText = "display:flex;flex-wrap:wrap;gap:8px;padding:12px";
    d.innerHTML = Object.keys(SITUACOES_ETQ).map(k => pecaSituacao(k)).join("") + Object.keys(ALERTAS_ETQ).map(k => pecaAlerta(k)).join("") + pecaLigacao();
    document.querySelector(".palco").appendChild(d)`, 200);
  await pegar("pecas", "etiquetas", "#cat-etq");
  await fazer(`$("cat-etq").remove()`, 100);

  // ---------- botões ----------
  await fazer(`trocarVista("correio")`, 1500);
  for (const [k, s] of [["bt-novo", "#cx-novo"], ["bt-faixa", "#cx-faixa > button:nth-of-type(2)"], ["bt-enviar-pend", "#btn-enviar"],
    ["bt-recolher", "#btn-recolher"], ["bt-filtro", "#cx-lcab .ol-filtro-bt || .ol-filtro-bt"], ["bt-aba", "#cx-lcab .ol-lcab button"],
    ["bt-op", "#op-cartoes-emails button"], ["bt-pasta", "#cx-pastas .ol-fav"], ["bt-rodape", "footer.rodape-status button"],
    ["bt-saude", "#saude .s-bolha"], ["bt-lateral", ".lateral .ln"]]) await pegar("botoes", k, s, { estados: true });
  await fazer(`trocarVista("visao")`, 2000);
  for (const [k, s] of [["bt-seg", ".seg-rd button"], ["bt-link", "[data-vt]"], ["bt-kpi", ".fr-item"]]) await pegar("botoes", k, s, { estados: true });

  // ---------- cores e ícones ----------
  const tokens = await js(`(() => { const cs = getComputedStyle(document.documentElement); const nomes = new Set();
    for (const sh of document.styleSheets) { try { for (const r of sh.cssRules) { (r.cssText.match(/--[a-z0-9-]+(?=\\s*:)/gi) || []).forEach(n => nomes.add(n)); } } catch (e) {} }
    return [...nomes].map(n => [n, cs.getPropertyValue(n).trim()]).filter(x => x[1]); })()`);
  const simbolos = await js(`[...document.querySelectorAll("symbol")].map(s => s.outerHTML)`);
  fs.writeFileSync(path.join(OUT, "catalogo_pecas.json"), JSON.stringify({ pecas, tokens, simbolos }));
  console.log("peças:", pecas.length, "· tokens:", tokens?.length, "· ícones:", simbolos?.length);
  console.log("erros JS:", erros.length ? [...new Set(erros)].join(" || ") : "nenhum");
  edge.kill(); process.exit(0);
})();
