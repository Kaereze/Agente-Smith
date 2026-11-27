// Conversa com o servidor do Painel (o mesmo da tela de hoje). A senha da sessão vem no <meta name="painel-token">.
const TOKEN = document.querySelector('meta[name="painel-token"]')?.content || "";

export async function api(caminho, corpo) {
  const r = await fetch(caminho, {
    method: corpo ? "POST" : "GET",
    headers: { "X-Token": TOKEN, "Content-Type": "application/json" },
    body: corpo ? JSON.stringify(corpo) : undefined,
  });
  const texto = await r.text();
  let j;
  try { j = JSON.parse(texto); } catch { j = { ok: false, motivo: "resposta inválida" }; }
  if (!r.ok && j.ok !== false) j = { ...j, ok: false };
  return j;
}
