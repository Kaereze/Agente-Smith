// O texto inteiro e os anexos de um e-mail, pedidos ao vivo ao PC dono da caixa (nada fica guardado no servidor).
// Guardados aqui enquanto a tela está aberta, para abrir na hora: os primeiros da lista e os vizinhos do aberto já vêm antes do clique.
import { useEffect, useState } from "react";
import { api } from "../../api.js";

const textos = new Map();     // id -> { carregando } | { erro } | { texto, citado, origem, pc }
const anexos = new Map();     // id|nome -> { url, tipo, tamanho } | { erro } | { carregando }
const ouvintes = new Set();
const avisar = () => ouvintes.forEach((f) => f());

// e.noEspelho: o e-mail está na lista da equipe (o servidor acha pelo id); resultado de pesquisa vai pelo pc + entry
const consulta = (e, extra = {}) => new URLSearchParams({ id: e.noEspelho !== false ? e.id : "", pc: e.pc || "", entry: e.entry || "", ...extra });

export function carregarTexto(e) {
  if (!e || textos.has(e.id)) return Promise.resolve();
  textos.set(e.id, { carregando: true });
  avisar();
  return api("/api/correio/texto?" + consulta(e))
    .then((r) => textos.set(e.id, r.erro || r.ok === false ? { erro: r.erro || r.motivo || "Não deu para abrir o e-mail agora." } : r))
    .catch(() => textos.set(e.id, { erro: "O PC dono da caixa não respondeu agora." }))
    .finally(avisar);
}

let fila = [], ativos = 0;
function puxar() {
  while (ativos < 2 && fila.length) {
    const e = fila.shift();
    if (textos.has(e.id)) continue;
    ativos++;
    carregarTexto(e).finally(() => { ativos--; puxar(); });
  }
}
// Os 15 primeiros da lista e os vizinhos do e-mail aberto, 2 de cada vez
export function preCarregar(lista, aberto) {
  const i = lista.findIndex((e) => e.id === aberto);
  const alvos = [...(i >= 0 ? [lista[i + 1], lista[i - 1], lista[i + 2]] : []), ...lista.slice(0, 15)].filter((e) => e && !textos.has(e.id));
  fila = [...new Map(alvos.map((e) => [e.id, e])).values()];
  puxar();
}

export async function pegarAnexo(e, nome) {
  const k = e.id + "|" + nome;
  const ja = anexos.get(k);
  if (ja && !ja.carregando) return ja;
  anexos.set(k, { carregando: true });
  let r;
  try { r = await api("/api/correio/anexo?" + consulta(e, { nome })); } catch { r = { erro: "o PC dono não respondeu" }; }
  if (r.erro || !r.b64) anexos.set(k, { erro: r.erro || r.motivo || "não veio o arquivo" });
  else {
    const bin = atob(r.b64), bytes = new Uint8Array(bin.length);
    for (let j = 0; j < bin.length; j++) bytes[j] = bin.charCodeAt(j);
    anexos.set(k, { url: URL.createObjectURL(new Blob([bytes], { type: r.tipo })), tipo: r.tipo || "", tamanho: r.tamanho });
  }
  avisar();
  return anexos.get(k);
}

// Relê a tela quando chega um texto ou anexo
export function useTextos() {
  const [, setN] = useState(0);
  useEffect(() => { const f = () => setN((n) => n + 1); ouvintes.add(f); return () => ouvintes.delete(f); }, []);
  return { texto: (id) => textos.get(id), anexo: (id, nome) => anexos.get(id + "|" + nome) };
}
