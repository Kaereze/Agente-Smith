// painel_eventos.js: parte de painel.js dividida por assunto em 08/11/2026 (mesma ordem de carga; nada de lógica mudou)
// ---------- Eventos ----------
document.addEventListener("click", e => {
  const t = e.target.closest("[data-vista],[data-vj],[data-ir],[data-vt]");
  if (!t) return;
  const ds = t.dataset;
  if (ds.vista) { if (ds.log) at.aba = ds.log; return trocarVista(ds.vista); }
  if (ds.vj) { pn.janela = Number(ds.vj); return desenharVisao(); }
  if (ds.vt) { pn.tabela[ds.vt] = !pn.tabela[ds.vt]; return desenharVisao(); }
  if (ds.ir) return abrirNotas({ filtro: ds.ir });
});
window.addEventListener("resize", () => { clearTimeout(pn.rz); pn.rz = setTimeout(() => pn.vista === "visao" && desenharVisao(), 200); });
trocarVista(location.hash.slice(1) || "visao");

// Arrastar o PDF da NF em cima de uma solicitação da lista (usuário, 11/10/2026): seleciona, abre o envio ali mesmo e
// já anexa a nota (o envio confere a NF com o pedido antes de sair, como sempre)
document.addEventListener("dragover", e => {
  const l = e.target.closest?.("#lista .nf-l");
  if (!l || !Array.from(e.dataTransfer?.types || []).includes("Files")) return;
  e.preventDefault();
  document.querySelectorAll("#lista .soltar-aqui").forEach(x => x !== l && x.classList.remove("soltar-aqui"));
  l.classList.add("soltar-aqui");
});
document.addEventListener("dragleave", e => { const l = e.target.closest?.("#lista .nf-l"); if (l && !l.contains(e.relatedTarget)) l.classList.remove("soltar-aqui"); });
document.addEventListener("drop", async e => {
  const l = e.target.closest?.("#lista .nf-l");
  if (!l || !e.dataTransfer?.files?.length) return;
  e.preventDefault();
  l.classList.remove("soltar-aqui");
  const arquivos = Array.from(e.dataTransfer.files);   // o navegador esvazia a lista depois do evento
  if (envNF && envNF.alvo) { toast("Termine ou descarte a mensagem que está escrevendo", true); return; }
  sel = l.dataset.k; emailSel = null; desenhar();
  await abrirEnvioNF(sel, null, $("detalhe"));
  if (envNF && $("nf-soltar")) adicionarArquivos(arquivos);
});
