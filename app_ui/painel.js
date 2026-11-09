// Visão geral, Log, Máquinas e as janelas de envio. Usa api/$/esc/toast/st/desenhar e o estado da tela de notas
// (mesmo escopo global).
let pn = { vista: "visao", janela: 30, rz: null, tabela: {}, resumo: "ontem" };   // resumo: a Visão geral abre no dia anterior   // tabela: gráfico mostrado como tabela
const hojeIso = () => new Date().toLocaleDateString("sv-SE");

const TITULOS = { visao: "Visão geral", fila: "Notas fiscais", maquinas: "Monitoramento / Máquinas", correio: "E-mails",
                  gerencia: "Gerência (em teste)", agentes: "Agentes do Smith", hospede: "Ficha do hóspede" };
// Aba Agentes do Smith (28/10/2026): o mapa do sistema roda num quadro à parte (/agentes/mapa, só o administrador no PC dele).
// Só carrega quando a aba abre e descarrega ao sair: assim as animações não pesam quando ninguém está olhando.
function agentesQuadro(aberto) {
  const q = $("agentes-quadro");
  if (!q) return;
  const aqui = q.getAttribute("src") === "/agentes/mapa";
  if (aberto && !aqui) q.setAttribute("src", "/agentes/mapa");
  if (!aberto && aqui) q.setAttribute("src", "about:blank");
}
function trocarVista(v) {
  // o log do robô agora é a janela grande do robô (robo.js, 22/10/2026): quem pedia a tela de Log abre ela
  if (v === "log") { if (typeof rbAbrir === "function") rbAbrir("reg"); return; }
  if (!TITULOS[v]) v = "visao";   // "Notas fiscais" está reservada para a emissão automática: nada cai mais nela por engano
  pn.vista = v;
  for (const id of Object.keys(TITULOS)) $("v-" + id).classList.toggle("oculta", id !== v);
  // E-mails igual ao Outlook (usuário, 15/10/2026): só ícones na esquerda e as cores da prévia aprovada
  // ... e em todas as páginas (usuário, 15/10/2026 à noite: "o mesmo layout da caixa de entrada para todas")
  const app = document.querySelector(".app");
  app.classList.add("modo-ol");   // só ícones ou com os nomes: o botão do pé da barra decide (aplicarMenu, 22/10/2026)
  app.classList.toggle("vista-correio", v === "correio");
  if (typeof desenharFaixaGlobal === "function") desenharFaixaGlobal();
  $("trilha").textContent = v === "correio" ? "E-mails / " + CAIXAS[cx.caixa] : TITULOS[v];
  document.querySelectorAll(".abas-monit").forEach(n => { n.innerHTML = [["maquinas", "", "Máquinas"], ["log", "tudo", "Registro do robô"]].map(([vv, lg, nome]) =>
      `<button type="button" data-vista="${vv}" ${lg ? `data-log="${lg}"` : ""} aria-current="${vv === v && (vv !== "log" || lg === at.aba)}">${nome}</button>`).join("") +
      `<span class="adm">Só o administrador vê</span>`; });
  const vNav = v === "hospede" ? "correio" : v, caixaNav = v === "hospede" ? "entrada" : cx.caixa;   // a ficha do hóspede acende "Caixa de entrada"
  document.querySelectorAll(".ln[data-vista]").forEach(b =>
    b.setAttribute("aria-current", String(b.dataset.vista === vNav && (vNav !== "log" || b.dataset.log === at.aba)
                                          && (vNav !== "correio" || b.dataset.caixa === caixaNav))));
  if (v === "log") $("nav-maquinas")?.setAttribute("aria-current", "true");   // Log e Máquinas = uma entrada no menu
  $("seletor-caixa")?.classList.toggle("oculta", !["fila", "correio"].includes(v));   // "Caixa de" só onde filtra (usuário, 14/10/2026)
  $("busca").placeholder = "Pesquisar no Outlook dos 4 PCs: hóspede, CPF/CNPJ, nº da NF, frase…";
  if (v !== "correio") $("topo-filtro").innerHTML = "";   // o filtro do topo é dos e-mails
  agentesQuadro(v === "agentes");
  if (v === "hospede") { desenharHospede(); return; }
  if (v === "correio") { desenharCorreio(); return; }
  desenhar();
  if (v === "visao") { pn.animar = true; desenharVisao(); }
  if (v === "gerencia") desenharGerencia();
  clearTimeout(at.timer);
  if (v === "log" || v === "maquinas") carregarAtividade();
}
