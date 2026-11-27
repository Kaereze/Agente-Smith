// Monitoramento: os PCs da equipe em cartões. Sem commit nem número de versão: diz em palavras se está no ar,
// o que está fazendo, se está na mesma versão e o que fez por último. Só o administrador vê.
import { useEffect, useState } from "react";
import { useAvisos } from "../componentes/Avisos.jsx";
import { aj } from "../ajustes.js";
import Icone from "../componentes/Icone.jsx";
import Botao from "../componentes/Botao.jsx";
import Etiqueta from "../componentes/Etiqueta.jsx";
import { Barra } from "../componentes/Graficos.jsx";
import { useLigado } from "../componentes/Conta.jsx";
import { CabecalhoTela, Bolinha, Pergunta } from "../componentes/Bloco.jsx";
import useAtividade from "../dados/useAtividade.js";
import { api } from "../api.js";
import "./Monitoramento.css";

const hora = (t) => String(t || "").replace("T", " ").slice(11, 16);
function usoEmPalavras(uso, online) {
  if (!online) return { texto: "PC desligado", tipo: "cinza" };
  const [estado, tela] = String(uso || "").split("|");
  if (estado === "aberto") return { texto: `Painel aberto agora${tela ? ` · em ${tela}` : ""}`, tipo: "verde" };
  return { texto: "Painel fechado · o robô segue trabalhando", tipo: "cinza" };
}

// "Atualizar PC" (29/10/2026): o botão mostra "Pedido enviado…"; quando a versão do PC muda (ou aparece ATUALIZADO na atividade)
// vira "Atualizado". Passou de 1 minuto sem mudar: "Sem mudança". O resultado fica 3,5 s e o botão volta ao normal.
const ATZ_LIMITE_MS = aj("tela.atualizar_pc_limite_segundos", 60) * 1000, ATZ_FIM_MS = aj("tela.atualizar_pc_resultado_segundos", 3.5) * 1000;
function situacaoAtz(a, atividade, agora) {
  const eventos = atividade?.eventos || [], pcsAgora = atividade?.pcs || [];
  const mudou = (x) => {
    const p = pcsAgora.find((q) => q.pc === x.pc);
    if (p?.versao && p.versao !== x.antes) return true;
    return eventos.some((e) => e.pc === x.pc && e.tipo === "ATUALIZADO" && Date.parse(String(e.quando).replace(" ", "T")) >= a.desde - 1000);
  };
  const total = a.pcs.length, feitos = a.pcs.filter(mudou).length, faltam = a.pcs.filter((x) => !mudou(x)).map((x) => x.agente);
  const todos = a.para === "TODOS";
  if (feitos >= total) return { estado: "ok", botao: "Atualizado", linha: todos ? `${feitos} de ${total} atualizados` : "Está na versão nova" };
  if (agora - a.desde >= ATZ_LIMITE_MS) return { estado: "sem", botao: "Sem mudança", linha: todos ? `${feitos} de ${total} atualizados · sem mudança: ${faltam.join(", ")}` : "Sem mudança em 1 min · veja o Registro do Robô" };
  return { estado: "andando", botao: "Pedido enviado…", linha: todos ? `${feitos} de ${total} atualizados · aguardando` : "Aguardando o PC reiniciar (até 1 min)" };
}

// Cadastro de hotéis: caixas e planilhas de hotel que faltam no Cadastro_Hoteis (sem cadastro, a planilha não é copiada)
function Cadastro({ soVer }) {
  const { recado: aviso } = useAvisos();
  const [dados, setDados] = useState(null);
  const [linhas, setLinhas] = useState([]);
  const ler = () => api("/api/cadastro/faltando").then((r) => { setDados(r); setLinhas((r.faltando || []).map((x) => ({ ...x }))); }).catch(() => {});
  useEffect(() => { ler(); }, []);
  if (!dados) return null;
  const salvar = async (i) => {
    const x = linhas[i];
    if (!x.agente) return aviso("Escolha o agente", true);
    const r = await api("/api/cadastro/adicionar", { hotel: x.hotel, email: x.email, agente: x.agente });
    if (r.ok === false) return aviso(r.motivo || r.erro || "Não deu certo", true);
    aviso(`${x.hotel} cadastrado (a cópia dos hotéis pega na próxima volta)`);
    ler();
  };
  const mudar = (i, campo, v) => setLinhas((l) => l.map((x, k) => (k === i ? { ...x, [campo]: v } : x)));
  return (
    <section className="bloco vidro entra mon-cadastro" style={{ "--i": 6 }}>
      <Pergunta assunto="Cadastro">Todo hotel está no cadastro?</Pergunta>
      {!linhas.length ? <p className="resposta"><b>Sim.</b> Toda caixa de hotel do Outlook e toda planilha de formulário estão no Cadastro_Hoteis.</p> : <>
        <p className="resposta"><b>{linhas.length} faltando.</b> Sem cadastro, a planilha do hotel não é copiada e a caixa fica sem agente. Confira o nome (igual ao da planilha) e cadastre.</p>
        {linhas.map((x, i) => (
          <div key={i} className="cad-linha">
            <input className="campo" value={x.hotel} onChange={(e) => mudar(i, "hotel", e.target.value)} aria-label="Nome do hotel" title="Nome do hotel (igual ao da planilha do formulário)" />
            <input className="campo" value={x.email} onChange={(e) => mudar(i, "email", e.target.value)} placeholder="caixa notafiscal@… (se tiver)" aria-label="E-mail da caixa" />
            <select className="campo" value={x.agente} onChange={(e) => mudar(i, "agente", e.target.value)} aria-label="Agente">
              {!x.agente && <option value="">Agente…</option>}{(dados.agentes || []).map((a) => <option key={a}>{a}</option>)}
            </select>
            <Botao tipo="principal" pequeno desligado={soVer} onClick={() => salvar(i)}>Cadastrar</Botao>
            <small>{x.motivo}</small>
          </div>
        ))}
      </>}
    </section>
  );
}

export default function Monitoramento({ estado }) {
  const { atividade } = useAtividade();
  const ligado = useLigado();
  const [recado, setRecado] = useState("");
  const [atz, setAtz] = useState({});   // "TODOS" ou o PC -> { para, desde, pcs, fim }
  const [agora, setAgora] = useState(Date.now());
  useEffect(() => { if (!Object.keys(atz).length) return undefined; const t = setInterval(() => setAgora(Date.now()), 1000); return () => clearInterval(t); }, [atz]);
  useEffect(() => {   // o resultado fica à vista por 3,5 s e o botão volta ao normal
    Object.entries(atz).forEach(([k, a]) => {
      const s = situacaoAtz(a, atividade, agora);
      if (s.estado !== "andando" && !a.fim) setAtz((x) => ({ ...x, [k]: { ...a, fim: agora } }));
      if (a.fim && agora - a.fim >= ATZ_FIM_MS) setAtz((x) => { const n = { ...x }; delete n[k]; return n; });
    });
  }, [agora, atividade]);   // eslint-disable-line react-hooks/exhaustive-deps
  const pcs = atividade?.pcs || estado?.pcs || [];
  const caixaPcs = estado?.caixa_pcs || {};
  const versaoAqui = atividade?.versao || "";
  const eventos = atividade?.eventos || [];
  const noAr = pcs.filter((p) => p.online);
  const desligados = pcs.filter((p) => !p.online).map((p) => p.agente || p.pc);
  const todosIguais = pcs.filter((p) => p.online).every((p) => !versaoAqui || p.versao === versaoAqui);
  const maxEmails = Math.max(1, ...Object.values(caixaPcs).map((c) => c.emails || 0));
  const soVer = !!estado?.so_ver;

  const atualizar = async (para, nome) => {
    if (atz[para]) return;   // um clique só enquanto anda
    setRecado(`Pedindo ${para === "TODOS" ? "a todos os PCs" : `ao PC de ${nome}`} para atualizar…`);
    const j = await api("/api/comando", { para, comando: "atualizar" });
    if (j.ok === false) { setRecado(j.motivo || j.erro || "Não deu para pedir agora."); return; }   // falhou: o botão continua livre
    setRecado("Pedido entregue. Cada PC puxa a versão nova e reinicia sozinho.");
    const alvos = pcs.filter((p) => p.online && (para === "TODOS" || p.pc === para));
    setAtz((x) => ({ ...x, [para]: { para, desde: Date.now(), pcs: alvos.map((p) => ({ pc: p.pc, agente: p.agente || p.pc, antes: p.versao || "" })) } }));
  };
  const sit = (para) => (atz[para] ? situacaoAtz(atz[para], atividade, agora) : null);
  const sitTodos = sit("TODOS");

  return (
    <main className="principal vidro">
      <CabecalhoTela icone="pc" titulo="Monitoramento" explica="Os PCs da equipe · atualiza sozinho a cada 20 s · só o administrador vê">
        <Botao tipo="principal" icone={sitTodos?.estado === "ok" ? "check" : "atualizar"} desligado={soVer || sitTodos?.estado === "andando"} titulo={soVer ? "Este PC só visualiza" : "Cada PC puxa a versão nova do GitHub e reinicia"}
          onClick={() => atualizar("TODOS")}>{sitTodos ? sitTodos.botao : "Atualizar todos os PCs"}</Botao>
      </CabecalhoTela>
      {sitTodos ? <p className={`robo-recado atz-${sitTodos.estado}`} role="status">{sitTodos.linha}</p> : recado && <p className="robo-recado" role="status">{recado}</p>}

      <section className="mon-resumo vidro entra">
        <Bolinha icone={desligados.length ? "alerta" : "check"} tipo={desligados.length ? "ambar" : "verde"} tamanho={44} />
        <div className="mon-resumo-texto">
          <b>{noAr.length} de {pcs.length} PCs no ar</b>
          <span>{desligados.length ? `Desligado: ${desligados.join(", ")}. ` : "Todos ligados. "}{todosIguais ? "Os PCs ligados estão na mesma versão." : "Há PC com versão diferente: use Atualizar."}</span>
        </div>
        <div className="mon-selos">
          <Etiqueta tipo={todosIguais ? "verde" : "ambar"} icone={todosIguais ? "check" : "alerta"}>{todosIguais ? "Mesma versão" : "Versões diferentes"}</Etiqueta>
          <Etiqueta tipo="azul" icone="nuvem">Central {estado?.erro ? "com aviso" : "conectada"}</Etiqueta>
        </div>
      </section>

      <div className="mon-cartoes">
        {pcs.map((p, i) => {
          const uso = usoEmPalavras(p.uso, p.online);
          const emails = caixaPcs[p.pc]?.emails ?? 0;
          const ultimos = eventos.filter((ev) => ev.pc === p.pc).slice(0, 3);
          const mesma = !versaoAqui || p.versao === versaoAqui;
          return (
            <article key={p.pc} className={`mon-cartao vidro entra${p.online ? "" : " fora"}`} style={{ "--i": i + 1 }}>
              <div className="mon-topo">
                <span className="capsula-avatar grande">{(p.agente || p.pc || "?").slice(0, 1)}</span>
                <div><b>{p.agente || p.pc}</b>
                  <span className="mon-selos-pc">
                    <Etiqueta tipo={p.online ? "verde" : "cinza"}>{p.online ? `No ar · visto ${hora(p.visto) || "agora"}` : `Desligado · visto ${hora(p.visto) || "—"}`}</Etiqueta>
                    <Etiqueta tipo="cinza">{p.papel === "principal" ? "PC principal: envia os pedidos" : "Confere as NF"}</Etiqueta>
                  </span></div>
              </div>
              <div className={`mon-uso ${uso.tipo}`}><Icone nome="pc" tamanho={16} />{uso.texto}</div>
              <div className="mon-numeros">
                <div><b>{p.caixas ?? "—"}</b><small>caixas de hotel</small></div>
                <div><b>{emails}</b><small>e-mails na caixa</small></div>
              </div>
              <div className="mon-parte"><small>Parte dos e-mails da equipe</small><Barra parte={emails} todo={maxEmails} ligado={ligado} /></div>
              {p.conferencia_resumo && <div className="mon-conf"><Icone nome="check" tamanho={15} /><span>Última conferência {hora(p.conferencia)}: {p.conferencia_resumo}</span></div>}
              <div className="mon-ultimos">
                <small>O QUE FEZ POR ÚLTIMO</small>
                {ultimos.length ? ultimos.map((ev, k) => <div key={k}><span>{hora(ev.quando)}</span><span>{[ev.tipo, ev.hotel].filter(Boolean).join(" · ")}</span></div>)
                  : <span className="mon-nada">Nada registrado hoje.</span>}
              </div>
              <span style={{ flex: 1 }} />
              <div className={`mon-versao${mesma ? "" : " diferente"}`}><Icone nome={mesma ? "check" : "alerta"} tamanho={14} />{mesma ? "Mesma versão deste PC" : "Versão diferente: precisa atualizar"}</div>
              {p.online ? (() => {
                const s = sit(p.pc);
                return <>
                  <Botao icone={s?.estado === "ok" ? "check" : "atualizar"} desligado={soVer || s?.estado === "andando"} onClick={() => atualizar(p.pc, p.agente)}>{s ? s.botao : "Atualizar este PC"}</Botao>
                  {s && <small className={`atz-linha atz-${s.estado}`} role="status">{s.linha}</small>}
                </>;
              })() : <Botao icone="voltar" desligado titulo="Quando o PC ligar, ele aparece aqui sozinho">Esperando ligar</Botao>}
            </article>
          );
        })}
      </div>
      <Cadastro soVer={soVer} />
    </main>
  );
}
