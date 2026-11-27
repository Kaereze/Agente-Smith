// O e-mail aberto, como no Outlook (opção C, 27/10/2026): a ficha do pedido no topo (etapas e o que o robô conferiu),
// o assunto e quem mandou, os anexos (abrem aqui mesmo), a verificação da NF e o texto inteiro, pedido ao PC dono.
import { useEffect, useState } from "react";
import Icone from "../../componentes/Icone.jsx";
import Botao from "../../componentes/Botao.jsx";
import BotaoEnviarNF from "../../componentes/BotaoEnviarNF.jsx";
import Etiqueta from "../../componentes/Etiqueta.jsx";
import Formulario from "./Formulario.jsx";
import Visor from "./Visor.jsx";
import { carregarTexto, useTextos } from "./textos.js";
import {
  campoDoPedido, CAMPO_DOC, CAMPO_NOME, etapasDoPedido, faltaDados, formDoTexto, itensConferidos, nomeSituacao, pedidoDoEmail,
  prazoInfo, valorDoForm, dataBr,
} from "../../dados/formulario.js";

export const dataLonga = (q) => {
  if (!q) return "";
  const d = new Date(q);
  return Number.isNaN(+d) ? q : d.toLocaleString("pt-BR", { weekday: "short", day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" });
};
const guardado = () => { try { return localStorage.getItem("painel.fichaAberta") === "1"; } catch { return false; } };

// Os dados do formulário deste e-mail: o pedido ligado a ele ou, no e-mail do Emissor, os campos do próprio texto
export function dadosDoEmail(e, fila, texto) {
  const ped = pedidoDoEmail(e, fila);
  const form = (e.classes || []).includes("formulario");
  return { ped, dados: ped || (form ? formDoTexto(texto) : null), form };
}

export default function Leitura({ e, fila, pcs, noEspelho, cinza, soVer, acoes, aoFechar, aoAbrirPedido }) {
  const { texto } = useTextos();
  const [visor, setVisor] = useState(null);
  const [aberta, setAberta] = useState(guardado);
  useEffect(() => { carregarTexto({ ...e, noEspelho }); }, [e, noEspelho]);
  const t = texto(e.id);
  const enviado = e.pasta === "enviado";
  const { ped, dados, form } = dadosDoEmail(e, fila, t?.texto);
  const pc = pcs.find((p) => p.pc === e.pc);
  const onde = [e.hotel, e.pc ? `PC de ${pc?.agente || e.pc}${pc && !pc.online ? " (desligado)" : ""}` : ""].filter(Boolean).join(" · ");
  const podeAgir = noEspelho && !cinza && !soVer && !enviado;
  const nome = enviado ? (e.caixa || "") : (e.nome || e.de || "");
  const ender = enviado ? e.caixa : e.de;
  const para = enviado ? e.para : (e.caixa || e.para || "");
  const abrirFicha = () => { const v = !aberta; setAberta(v); try { localStorage.setItem("painel.fichaAberta", v ? "1" : ""); } catch { /* só nesta janela */ } };

  return (
    <div className="leit-corpo" key={e.id}>
      {!enviado && <ResumoPedido e={e} ped={ped} dados={dados} form={form} onde={onde} podeAgir={podeAgir} acoes={acoes} aberta={aberta} abrirFicha={abrirFicha} />}
      {!enviado && ped && <AvisoRepetido ped={ped} fila={fila} aoAbrirPedido={aoAbrirPedido} />}

      <header className="c-msg">
        <h3>{e.assunto || "(sem assunto)"}</h3>
        <div className="c-de">
          <span>{nome}{ender && ender !== nome ? ` <${ender}>` : ""} · para {para} · {dataLonga(e.quando)}</span>
          <button type="button" className="c-fechar" onClick={aoFechar} title="Fechar (Esc)"><Icone nome="fechar" tamanho={13} />fechar</button>
        </div>
        {enviado && onde && <p className="c-onde"><Icone nome="pc" tamanho={14} />{onde}</p>}
        {podeAgir ? (
          <div className="c-acoes">
            <Botao icone="responder" pequeno onClick={() => acoes.escrever("resp")} titulo="Ctrl+R">Responder</Botao>
            <Botao icone="encaminhar" pequeno onClick={() => acoes.escrever("enc")} titulo="Ctrl+F">Encaminhar</Botao>
            <Botao icone="mais" tipo="fantasma" pequeno titulo="Mais ações: lido, urgência, tirar da caixa, excluir" onClick={(ev) => acoes.menu(ev)} />
          </div>
        ) : (
          <span className="c-sit">{cinza ? "Respondido · sai da caixa quando o Outlook do PC dono confirmar" : enviado ? "E-mail enviado · só leitura" : soVer ? "Este PC só visualiza" : "Fora da caixa de entrada · só leitura"}</span>
        )}
      </header>

      {(e.anexos || []).length > 0 && (
        <div className="c-anexos">{e.anexos.map((a, i) => (
          <button key={a + i} type="button" className="c-anexo" onClick={() => setVisor(i)} title="Ver aqui no Painel">
            <b>{String(a).split(".").pop().toUpperCase().slice(0, 4)}</b><span>{a}</span></button>
        ))}</div>
      )}
      {e.alerta_doc && <div className="c-verifica"><b>NF com CPF/CNPJ diferente do pedido</b><div>{e.alerta_doc}</div>
        <small>O robô abriu a nota deste hóspede e comparou com o formulário. Confira antes de responder.</small></div>}
      {!enviado && <Verificacao e={e} />}

      <div className="c-corpo">
        {form && dados ? <Formulario dados={dados} email={e} />
          : !t || t.carregando ? <p className="dica">Abrindo o e-mail no Outlook do PC dono…</p>
          : t.erro ? <p className="dica erro-txt">{t.erro}</p>
          : <>
              {formDoTexto(t.texto) ? <Formulario dados={formDoTexto(t.texto)} email={e} /> : <div className="c-texto">{t.texto || "(sem texto)"}</div>}
              {t.citado && <details className="c-citado"><summary>Mostrar mensagens anteriores</summary><div className="c-texto">{t.citado}</div></details>}
              {t.origem && !["ao vivo", "este PC"].includes(t.origem) && <p className="dica">{t.origem}</p>}
            </>}
      </div>
      {visor !== null && <Visor email={{ ...e, noEspelho }} nomes={e.anexos} inicio={visor} aoFechar={() => setVisor(null)} />}
    </div>
  );
}

// A ficha do pedido no topo: quem é, o prazo, as etapas, o que o robô conferiu e o botão que a situação pede
function ResumoPedido({ e, ped, dados, form, onde, podeAgir, acoes, aberta, abrirFicha }) {
  const c = (...r) => (dados ? campoDoPedido(dados, ...r) : "");
  const tom = c(...CAMPO_NOME), doc = c(...CAMPO_DOC), tit = c(/nome.*titular/, /nome do hospede/);
  const nome = tit || (doc.replace(/\D/g, "").length === 11 ? tom : "") || (form ? tom || "Hóspede do formulário" : e.nome || e.de || "");
  const falta = ped ? faltaDados(ped) : [];
  const m = etapasDoPedido({ hora: e.quando ? String(e.quando).slice(11, 16) : "", falta, semFormulario: !dados, temPedido: !!ped });
  const itens = dados ? itensConferidos(dados) : [];
  const prazo = prazoInfo(ped?.prazo || e.prazo);
  return (
    <>
      <section className="c-top" aria-label="Resumo do pedido">
        <div className="c-lin">
          <h2>{nome}</h2>
          {prazo && <Etiqueta tipo={prazo.nivel === "vencido" ? "vermelho" : prazo.nivel === "perto" ? "ambar" : "verde"} icone="relogio">{prazo.texto}</Etiqueta>}
          <span className="c-onde">{onde}</span>
          <span style={{ flex: 1 }} />
          {podeAgir && (m.principal.acao === "pedir"
            ? <Botao tipo="principal" pequeno icone="envelope" onClick={acoes.pedirFalta}>Pedir o que falta</Botao>
            : <BotaoEnviarNF pequeno hospede={nome} aoClicar={() => acoes.escrever("nf")} />)}
        </div>
        <ol className="c-etapas">
          {m.passos.map((p, i) => <li key={p.nome} className={p.feita ? "feita" : p.atual ? "atual" : ""} style={{ "--i": i }}><b>{p.nome}</b><span>{p.sub}</span></li>)}
        </ol>
      </section>
      <section className="c-lista" aria-label="O que o robô conferiu">
        {itens.length ? itens.map((it, i) => (
          <div key={i} className={`c-item ${it.tipo}`} style={{ "--i": i }}>
            <Icone nome={it.tipo === "ok" ? "check" : it.tipo === "at" ? "alerta" : "voltar"} tamanho={14} />
            <div><span>{it.rot}</span><span>{it.val}</span></div>
          </div>
        )) : <div className="c-sem">Sem formulário: os dados estão no texto do e-mail.</div>}
      </section>
      {dados && !form && (
        <>
          <button type="button" className="c-ficha" aria-expanded={aberta} onClick={abrirFicha}>
            {aberta ? "Fechar o formulário completo" : "Ver o formulário completo"}<Icone nome="seta" tamanho={14} /></button>
          {aberta && <div className="c-ficha-tab"><Formulario dados={dados} email={e} /></div>}
        </>
      )}
    </>
  );
}

// Pedido repetido: o robô já juntou os formulários iguais (mesmo hotel, CPF/CNPJ, datas); aqui só avisa e compara. Nada é gravado.
function AvisoRepetido({ ped, fila, aoAbrirPedido }) {
  const [comparar, setComparar] = useState(false);
  const acha = (k) => (fila || []).find((s) => s.chave === k);
  const outro = ped.repetido_de ? acha(ped.repetido_de) : ped.repetidos?.length ? acha(ped.repetidos[0].chave) || ped.repetidos[0] : null;
  if (!outro) return null;
  const vezes = (ped.repetido_de ? outro.repetidos?.length || 1 : ped.repetidos.length) + 1;
  const linhas = linhasComparacao(ped, outro);
  return (
    <section className="c-repetido" role="status" aria-label="Pedido repetido">
      <div className="rp1"><Icone nome="alerta" tamanho={20} />
        <div><b>Este hóspede já pediu nota desta estadia · {vezes}x</b>
          <p>Mesmo hotel, CPF/CNPJ e datas: {ped.repetido_de ? "o pedido principal" : "outro formulário"} de {dataBr(outro.data) || "outra data"} · {outro.hotel} · {nomeSituacao(outro)}. O robô conta como um pedido só: trate pelo principal.</p></div></div>
      <div className="rp-bts">
        {aoAbrirPedido && <Botao tipo="principal" pequeno onClick={() => aoAbrirPedido(outro.chave)}>Abrir o outro pedido</Botao>}
        <Botao pequeno onClick={() => setComparar(!comparar)}>{comparar ? "Fechar comparação" : "Comparar"}</Botao>
      </div>
      {comparar && <>
        <div className="rp-cmp" role="table"><span className="h" /><span className="h">Este pedido</span><span className="h">O outro</span>
          {linhas.map(([r, x, y, d]) => <span key={r} style={{ display: "contents" }}><span className="k">{r}</span><span className={d ? "dif" : ""}>{x || "—"}</span><span className={d ? "dif" : ""}>{y || "—"}</span></span>)}</div>
        <p className="rp-nota">O que é diferente fica em âmbar.</p>
      </>}
    </section>
  );
}
function linhasComparacao(a, b) {
  const c = (s, ...r) => campoDoPedido(s, ...r) || "";
  const doc = (s) => { const v = c(s, ...CAMPO_DOC); return v ? valorDoForm("CPF/CNPJ", v)[0] : ""; };
  const linhas = [["Quem", (s) => c(s, /nome.*titular/, /nome do hospede/) || s.nome || ""], ["CPF/CNPJ", doc], ["Nota em", (s) => c(s, /nome.*tomador/, /razao social/)],
    ["Hotel", (s) => s.hotel || ""], ["Datas", (s) => [c(s, /check.?in/), c(s, /check.?out/)].filter(Boolean).join(" → ")], ["O que pede", (s) => c(s, /informac/, /o que.*nota/)],
    ["Pedido em", (s) => dataBr(s.data)], ["Situação", nomeSituacao]];
  return linhas.map(([rot, f]) => { const x = f(a), y = f(b); return [rot, x, y, !["Pedido em", "Situação"].includes(rot) && x !== y]; });
}

// Verificação da NF: o robô abriu a nota (anexada ou no Dropbox) e cruzou com o que o cliente escreveu
function Verificacao({ e }) {
  const a = e.analise_d;
  if (!a && !e.analise) return null;
  return (
    <div className="c-verifica"><b>Verificação da NF</b>
      {a ? <>
        <div className="c-motivo">Motivo: {a.m}{a.d && <small> ({a.d})</small>}</div>
        {a.nf && <div>{a.nf}</div>}
        {(a.c || []).map((c) => <div key={c}>{c.startsWith("⚠") ? <b>{c}</b> : `· ${c}`}</div>)}
        {a.o?.length > 0 && <div className="c-tambem">também citou: {a.o.join(", ")}</div>}
      </> : <div>{e.analise}</div>}
      <small>O robô abriu a NF (anexada ou no Dropbox) e cruzou com o que o cliente escreveu. Confira antes de reenviar.</small>
    </div>
  );
}
