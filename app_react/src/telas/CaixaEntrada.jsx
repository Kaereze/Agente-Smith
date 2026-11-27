// Caixa de entrada: o mesmo jeito da tela de hoje (faixa de comandos, pastas, lista, leitura), com as cores novas e o vidro.
// Por enquanto só lê; responder, enviar NF e mover continuam na tela de hoje (os botões levam até lá).
import { useMemo, useState } from "react";
import Icone from "../componentes/Icone.jsx";
import Botao from "../componentes/Botao.jsx";
import BotaoEnviarNF from "../componentes/BotaoEnviarNF.jsx";
import Etiqueta from "../componentes/Etiqueta.jsx";
import { abrirNaTelaDeHoje } from "../api.js";
import "./CaixaEntrada.css";

const dataCurta = (q) => (q ? `${q.slice(8, 10)}/${q.slice(5, 7)}` : "");
function grupo(dias) {
  if (dias < 1) return "Hoje";
  if (dias < 2) return "Ontem";
  if (dias < 7) return "Esta semana";
  return "Mais antigos";
}
const ORDEM_GRUPOS = ["Hoje", "Ontem", "Esta semana", "Mais antigos"];

function etiquetasDoEmail(e) {
  const lista = [];
  if (e.pasta === "enviado") {
    (e.anexos || []).slice(0, 2).forEach((a) => lista.push(<Etiqueta key={a} tipo="verde" icone="nota">{a}</Etiqueta>));
    if (e.ligacao) lista.push(<Etiqueta key="lig" tipo="azul">Ligação</Etiqueta>);
    return lista;
  }
  const notas = e.notas || [];
  if (notas.length) lista.push(<Etiqueta key="nf" tipo="verde" icone="check">NF enviada · {notas.join(", ")}</Etiqueta>);
  else if (e.solicitacao) lista.push(<Etiqueta key="sem" tipo="azul" icone="nota">Sem NF</Etiqueta>);
  if ((e.classes || []).includes("correcao") || (e.classes || []).includes("cancelamento")) lista.push(<Etiqueta key="c" tipo="ambar" icone="robo">Correção</Etiqueta>);
  if (e.urgente) lista.push(<Etiqueta key="u" tipo="vermelho" icone="bandeira" contorno>{e.motivo_urgencia || `Sem resposta há ${Math.floor(e.dias || 0)} dias`}</Etiqueta>);
  return lista;
}

export default function CaixaEntrada({ correio, estado, pastaInicial = "entrada" }) {
  const [pasta, setPasta] = useState(pastaInicial);
  const [soNaoLidos, setSoNaoLidos] = useState(false);
  const [aberto, setAberto] = useState(null);
  const emails = correio?.emails || [];
  const contagem = correio?.contagem || {};
  const caixaPcs = estado?.caixa_pcs || {};

  const lista = useMemo(() => {
    let l = pasta === "enviados" ? (correio?.enviados || []) : emails.filter((e) => e.pasta === "entrada");
    if (pasta === "urgencia") l = l.filter((e) => e.urgente);
    if (soNaoLidos && pasta !== "enviados") l = l.filter((e) => !e.lido);
    return [...l].sort((a, b) => (a.quando < b.quando ? 1 : -1));
  }, [emails, correio, pasta, soNaoLidos]);
  const idade = (m) => m.dias ?? (Date.now() - new Date(m.quando || 0)) / 864e5;
  const grupos = ORDEM_GRUPOS.map((g) => [g, lista.filter((m) => grupo(idade(m)) === g)]).filter(([, l]) => l.length);
  const e = lista.find((x) => x.id === aberto);

  if (!correio) return <main className="ol-vazio vidro">Lendo as caixas de entrada dos 4 PCs…</main>;
  return (
    <div className="ol">
      <div className="faixa vidro" role="toolbar" aria-label="Comandos do e-mail">
        {[["responder", "Responder"], ["responderTodos", "Responder a todos"], ["encaminhar", "Encaminhar"]].map(([ic, t]) => (
          <button key={ic} type="button" className="cmd" title={e ? `${t} (abre na tela de hoje)` : "Abra um e-mail primeiro"} disabled={!e} onClick={() => abrirNaTelaDeHoje("correio")}>
            <Icone nome={ic} tamanho={17} /><span className="cmd-texto">{t}</span></button>
        ))}
        <span className="sep" />
        {[["lido", "Não lido/Lido"], ["bandeira", "Sinalizar"]].map(([ic, t]) => (
          <button key={ic} type="button" className="cmd" disabled={!e} title={e ? t : "Abra um e-mail primeiro"} onClick={() => abrirNaTelaDeHoje("correio")}>
            <Icone nome={ic} tamanho={17} /><span className="cmd-texto">{t}</span></button>
        ))}
        <span style={{ flex: 1 }} />
        <Botao tipo="contorno" icone="novo" pequeno onClick={() => abrirNaTelaDeHoje("correio")}>Novo e-mail</Botao>
        <BotaoEnviarNF pequeno semEmail={!e} hospede={e?.nome} />
      </div>
      <div className="ol-mesa">
        <aside className="pn vidro pastas entra" aria-label="Pastas">
          <div className="pn-cab">Favoritos</div>
          <button type="button" className={`pasta${pasta === "entrada" ? " sel" : ""}`} onClick={() => setPasta("entrada")}>
            <Icone nome="caixa" tamanho={17} /><span>Caixa de Entrada (todas)</span><span className="qt">{contagem.entrada ?? lista.length}</span></button>
          <button type="button" className={`pasta${pasta === "urgencia" ? " sel" : ""}`} onClick={() => setPasta("urgencia")}>
            <Icone nome="alerta" tamanho={17} /><span>Urgência</span><span className="qt urg">{contagem.urgencia ?? 0}</span></button>
          <button type="button" className={`pasta${pasta === "enviados" ? " sel" : ""}`} onClick={() => setPasta("enviados")}><Icone nome="enviar" tamanho={17} /><span>Itens Enviados (72 h)</span><span className="qt">{(correio?.enviados || []).length}</span></button>
          <div className="pn-cab">Agentes e PCs</div>
          {Object.entries(caixaPcs).map(([pc, c]) => (
            <div key={pc} className="pasta agente">
              <span className="capsula-avatar" style={{ width: 30, height: 30, fontSize: 12 }}>{(c.agente || "?").slice(0, 1)}</span>
              <span className="agente-texto"><b>{c.agente}</b><small className={c.online ? "pc-ok" : "pc-fora"}>{c.online ? "PC ligado" : "PC desligado"}</small></span>
              <span className="qt">{c.emails}</span>
            </div>
          ))}
        </aside>
        <section className="pn vidro entra" style={{ "--i": 1 }} aria-label="Lista de e-mails">
          <div className="cab-lista">
            <div className="abas-lista" role="group" aria-label="Mostrar">
              <button type="button" aria-pressed={!soNaoLidos} onClick={() => setSoNaoLidos(false)}>Todas</button>
              <button type="button" aria-pressed={soNaoLidos} onClick={() => setSoNaoLidos(true)}>Não lidos</button>
            </div>
            <span className="info"><b>{{ urgencia: "Urgência", enviados: "Itens Enviados" }[pasta] || "Caixa de Entrada"}</b> · {lista.length} e-mails · {lista.filter((x) => !x.lido).length} não lidos</span>
          </div>
          <div className="linhas" role="listbox" aria-label="E-mails">
            {grupos.length === 0 && <p className="lista-vazia">Nenhum e-mail aqui.</p>}
            {grupos.map(([g, l]) => (
              <div key={g}>
                <div className="grp">{g}</div>
                {l.map((m, i) => (
                  <button key={m.id} type="button" role="option" aria-selected={m.id === aberto}
                    className={`em${m.urgente ? " urg" : ""}${m.lido ? "" : " nao-lido"}`} style={{ "--i": Math.min(i, 8) }} onClick={() => setAberto(m.id)}>
                    <span className="l1"><span className="de">{pasta === "enviados" ? `Para: ${m.para}` : (m.nome || m.de)}</span>{m.urgente && <Icone nome="bandeira" tamanho={14} />}</span>
                    <span className="l1"><span className="as">{m.assunto}</span><span className="d">{dataCurta(m.quando)}</span></span>
                    <span className="pv">{m.hotel} · {m.previa}</span>
                    <span className="tags">{etiquetasDoEmail(m)}</span>
                  </button>
                ))}
              </div>
            ))}
          </div>
        </section>
        <article className="pn vidro leit entra" style={{ "--i": 2 }} aria-label="Leitura">
          {e ? (
            <div className="leit-corpo" key={e.id}>
              <h3>{e.assunto}</h3>
              <div className="meta-l">{e.nome || e.de} · caixa {e.hotel} · {dataCurta(e.quando)} às {(e.quando || "").slice(11, 16)} · {e.agente ? `PC de ${e.agente}` : e.pc}</div>
              <p>{e.previa}…</p>
              <div className="ficha-p">
                <div><small>Hotel</small>{e.hotel}</div>
                <div><small>Quem cuida</small>{e.agente || "—"}</div>
                <div><small>Situação</small><span className="tags">{etiquetasDoEmail(e)}</span></div>
              </div>
              <div className="acoes-leitura">
                <Botao icone="responder" onClick={() => abrirNaTelaDeHoje("correio")}>Responder</Botao>
                <BotaoEnviarNF hospede={e.nome} />
              </div>
              <p className="dica">O texto completo, os anexos e as ações abrem na tela de hoje por enquanto.</p>
            </div>
          ) : (
            <div className="vazio"><Icone nome="envelope" tamanho={44} /><b>Selecione um e-mail para ler</b><span>Clique numa linha da lista</span></div>
          )}
        </article>
      </div>
    </div>
  );
}
