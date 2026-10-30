// Regras do que é preciso para emitir a NF (João, 30/10/2026). Um lugar só: a etiqueta "Falta dado", a etapa "Dados completos"
// e a mensagem "Pedir o que falta" leem daqui.
//
// Principal (sempre): nome do tomador, CPF ou CNPJ de verdade (com os dígitos conferindo) e CEP (8 números).
// Sem um deles, o pedido fica "Falta dado". O emissor nacional acha o tomador pelo CPF; com 1 dígito errado não acha, então
// "CPF/CNPJ inválido" pede de novo em vez de passar como se estivesse certo.
// Extras (só entram na mensagem, não viram "Falta dado"): telefone e número do endereço, quando o formulário tem o campo.

function regrasSemAcento(x) { return String(x || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase(); }

function cpfValido(txt) {
  const d = String(txt || "").replace(/\D/g, "");
  if (d.length !== 11 || /^(\d)\1{10}$/.test(d)) return false;
  const dv = n => { let s = 0; for (let i = 0; i < n; i++) s += +d[i] * (n + 1 - i); const r = (s * 10) % 11; return r === 10 ? 0 : r; };
  return dv(9) === +d[9] && dv(10) === +d[10];
}

function cnpjValido(txt) {
  const d = String(txt || "").replace(/\D/g, "");
  if (d.length !== 14 || /^(\d)\1{13}$/.test(d)) return false;
  const dv = n => {
    const pesos = n === 12 ? [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2] : [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2];
    const r = pesos.reduce((s, p, i) => s + p * +d[i], 0) % 11;
    return r < 2 ? 0 : 11 - r;
  };
  return dv(12) === +d[12] && dv(13) === +d[13];
}

function cepValido(txt) { return String(txt || "").replace(/\D/g, "").length === 8; }

// Valor de um campo do formulário pelo nome do campo (sem acento, qualquer caixa): o 1º teste que casar.
function campoDoPedido(s, ...testes) {
  const c = (s.campos || []).find(([k]) => testes.some(r => r.test(regrasSemAcento(k))));
  return c ? String(c[1] || "").trim() : "";
}

const CAMPO_NOME = [/nome.*tomador/, /razao social/, /^nome( completo)?$/];
const CAMPO_DOC = [/documento.*tomador/, /cpf.*cnpj|cnpj.*cpf/, /^cnpj/, /^cpf(?!.*titular)/];

// O que impede de emitir: ["nome", "CPF/CNPJ" | "CPF/CNPJ inválido", "CEP" | "CEP inválido"]
function faltaDados(s) {
  if (s.situacao === "concluida") return [];
  const falta = [];
  if (!campoDoPedido(s, ...CAMPO_NOME)) falta.push("nome");
  const doc = campoDoPedido(s, ...CAMPO_DOC);
  if (!doc.replace(/\D/g, "")) falta.push("CPF/CNPJ");
  else if (!(cpfValido(doc) || cnpjValido(doc))) falta.push("CPF/CNPJ inválido");
  const cep = campoDoPedido(s, /^cep/, /\bcep\b/);
  if (!cep.replace(/\D/g, "")) falta.push("CEP");
  else if (!cepValido(cep)) falta.push("CEP inválido");
  return falta;
}

// Só para a mensagem: o resto que o robô reconhece que falta (campo existe no formulário e veio vazio)
function faltaExtras(s) {
  if (s.situacao === "concluida") return [];
  const extras = [];
  const tem = (...t) => (s.campos || []).some(([k]) => t.some(r => r.test(regrasSemAcento(k))));
  if (tem(/telefone|celular|whatsapp/) && !campoDoPedido(s, /telefone|celular|whatsapp/)) extras.push("telefone");
  if (tem(/^numero/, /numero (da )?(casa|residencia|endereco)/) && !campoDoPedido(s, /^numero/, /numero (da )?(casa|residencia|endereco)/)) extras.push("número do endereço");
  return extras;
}
