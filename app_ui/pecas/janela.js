// Peça única: janela que abre por cima (usuário, 21/10/2026, desenho Pr7). Entrar é só CSS (pecas/janela.css); aqui
// toda janela (.modal-fundo no body) ganha a SAÍDA animada sem mexer em cada uma: o .remove() dela vira fecharJanela.
// Ao fechar, ela troca .modal-fundo por .janela-saindo (as telas param de vê-la como aberta na hora) e só sai do body
// depois da animação.
const JANELA_SAIDA_MS = 150;
function fecharJanela(fundo, remover) {
  if (!fundo?.classList.contains("modal-fundo")) return;
  const semMovimento = matchMedia("(prefers-reduced-motion: reduce)").matches;
  fundo.classList.replace("modal-fundo", "janela-saindo");
  setTimeout(remover, semMovimento ? 0 : JANELA_SAIDA_MS);
}
new MutationObserver(ms => ms.forEach(m => m.addedNodes.forEach(n => {
  if (!n.classList?.contains("modal-fundo") || n.dataset.saidaAnimada) return;
  n.dataset.saidaAnimada = "1";
  const remover = Element.prototype.remove.bind(n);
  n.remove = () => fecharJanela(n, remover);
}))).observe(document.body, { childList: true });
