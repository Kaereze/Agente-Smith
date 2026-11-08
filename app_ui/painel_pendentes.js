// painel_pendentes.js: parte de painel.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// ---------- Enviar pendentes: o caminho que o robô faz, com as linhas reais do log ----------
// Cada etapa acende quando aparece no log uma linha dela (main.py); a linha vira o detalhe da etapa.
const ETAPAS_ENVIO = [
  ["Pedido ao robô", "o PC principal recebe o pedido", /Pedido entregue|início|DESLIGADO/i],
  ["Planilha Central", "abas de respostas de cada hotel", /aba\(s\) de respostas/i],
  ["Solicitações pendentes", "o que ainda não foi pra caixa do hotel", /pendente\(s\) lida|já tratada|esperando a vez/i],
  ["Montando os e-mails", "um e-mail por operador, com as solicitações", /montado/i],
  ["Enviando às caixas dos hotéis", "pelo Outlook do PC principal", /Enviando|SAIU/i],
  ["Marcando a planilha", "Enviado = TRUE e aviso ao conferente de NF", /marcada|anotado/i],
  ["Concluído", "", null],
];
let envioTimer = null;
async function abrirEnvio() {
  if (document.querySelector(".modal-fundo")) return;
  const fundo = document.createElement("div");
  fundo.className = "modal-fundo";
  fundo.innerHTML = `<div class="modal proc" role="dialog" aria-modal="true" aria-labelledby="env-titulo">
    <div class="proc-cab"><div class="anel" id="env-anel"></div>
      <div><h3 id="env-titulo">Enviar solicitações pendentes</h3><div class="sub" id="env-sub">Confirme para o robô começar</div></div></div>
    <div class="proc-barra" id="env-barra"><i></i></div>
    <div class="proc-corpo">
      <ol class="etapas" id="env-etapas">${ETAPAS_ENVIO.map(([t, s], k) =>
        `<li class="etapa" id="env-et-${k}"><span class="marco">${k + 1}</span><span><b>${esc(t)}</b><small>${esc(s)}</small></span></li>`).join("")}</ol>
      <div class="trilha" id="env-trilha"><div class="vazio" style="padding:30px;font-family:var(--f-texto)">O robô lê as pendentes da Planilha Central,
        monta um e-mail por operador e envia pra caixa de cada hotel. Nada é enviado ao hóspede.</div></div>
    </div>
    <div class="modal-rodape"><span class="res" id="env-res"></span>
      <span style="display:flex;gap:8px"><button id="env-fechar">Cancelar</button><button class="creme" id="env-ir">Enviar agora</button></span></div></div>`;
  document.body.appendChild(fundo);
  $("env-anel").style.animationPlayState = "paused";
  $("env-fechar").onclick = () => { clearTimeout(envioTimer); fundo.remove(); };
  $("env-ir").onclick = async () => {
    $("env-ir").disabled = true;
    const r = await api("/api/enviar", {});
    if (!r.ok) { $("env-ir").disabled = false; return toast(r.motivo || "Não deu certo", true); }
    $("env-ir").style.display = "none";
    $("env-fechar").textContent = "Fechar (continua em segundo plano)";
    $("env-anel").style.animationPlayState = "running";
    $("env-titulo").textContent = "O robô está enviando as pendentes";
    $("env-sub").textContent = r.modo === "local" ? "Rodando neste PC" : "Pedido entregue ao PC principal";
    $("env-trilha").innerHTML = "";
    acompanharEnvio(r.modo === "local" ? 700 : 2500);
  };
}

function marcarEtapas(linhas, rodando, ok) {
  let atual = 0;
  const detalhe = {};
  linhas.forEach(l => ETAPAS_ENVIO.forEach(([, , re], k) => { if (re && re.test(l.texto)) { atual = Math.max(atual, k); detalhe[k] = l.texto; } }));
  if (!rodando) atual = ETAPAS_ENVIO.length - 1;
  ETAPAS_ENVIO.forEach((et, k) => {
    const li = $("env-et-" + k);
    if (!li) return;
    li.classList.toggle("feita", k < atual || (!rodando && ok));
    li.classList.toggle("agora", rodando && k === atual);
    if (detalhe[k]) li.querySelector("small").textContent = detalhe[k].replace(/^\W+\s*/u, "");
  });
  $("env-barra").querySelector("i").style.width = Math.round(100 * (rodando ? atual + .5 : ETAPAS_ENVIO.length) / ETAPAS_ENVIO.length) + "%";
}

async function acompanharEnvio(ms) {
  const e = await api("/api/envio").catch(() => null);
  if (!$("env-trilha")) return;   // janela fechada: o envio segue sozinho
  if (e) {
    const trilha = $("env-trilha"), noFim = trilha.scrollTop + trilha.clientHeight >= trilha.scrollHeight - 30;
    const existentes = trilha.children.length;
    e.linhas.slice(existentes).forEach(l => {
      const div = document.createElement("div");
      div.className = "passo" + (l.nivel === "WARNING" ? " aviso" : l.nivel === "ERROR" ? " erro" : "");
      div.innerHTML = `<span class="m"></span><span class="h">${esc(l.hora)}</span><span class="t">${esc(l.texto)}</span>`;
      trilha.appendChild(div);
    });
    [...trilha.children].forEach((d, i) => {
      const atual = e.rodando && i === trilha.children.length - 1;
      d.classList.toggle("atual", atual);
      d.querySelector(".m").textContent = atual ? "" : "✓";
    });
    if (noFim) trilha.scrollTop = trilha.scrollHeight;
    const terminou = !e.rodando && e.modo, ok = e.codigo === 0;
    marcarEtapas(e.linhas, !terminou, ok);
    if (terminou) {
      $("env-anel").className = "anel " + (ok ? "ok" : "ruim");
      $("env-anel").textContent = ok ? "✓" : "!";
      $("env-barra").classList.add("fim");
      $("env-titulo").textContent = ok ? "Envio concluído" : "Envio terminou com aviso";
      $("env-sub").textContent = e.resumo || "";
      $("env-et-" + (ETAPAS_ENVIO.length - 1)).querySelector("small").textContent = e.resumo || "";
      $("env-res").textContent = e.resumo || "";
      $("env-fechar").textContent = "Fechar";
      carregar();
      return;
    }
  }
  envioTimer = setTimeout(() => acompanharEnvio(ms), ms);
}
