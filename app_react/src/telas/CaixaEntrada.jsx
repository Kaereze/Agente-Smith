// Caixa de entrada: o mesmo jeito do Outlook (faixa de comandos, pastas, lista, leitura), com as cores novas e o vidro.
// Tudo acontece aqui: ler o e-mail inteiro e os anexos, responder, encaminhar, enviar a NF (com a conferência), novo e-mail,
// lido/não lido, urgência, excluir e tirar da entrada (com Desfazer), a ficha do hóspede e a pesquisa nos 4 PCs.
// Atalhos iguais aos do Outlook: Ctrl+R responder · Ctrl+Shift+R com a NF · Ctrl+F encaminhar · Delete excluir · Ctrl+U não lido · Ctrl+Q lido · ↑ ↓ andam.
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import Icone from "../componentes/Icone.jsx";
import Botao from "../componentes/Botao.jsx";
import BotaoEnviarNF from "../componentes/BotaoEnviarNF.jsx";
import Etiqueta from "../componentes/Etiqueta.jsx";
import Janela from "../componentes/Janela.jsx";
import { useAvisos } from "../componentes/Avisos.jsx";
import { api } from "../api.js";
import { enviarPendentes, useEnviarReceber } from "../dados/acoes.js";
import { ehFormulario, etiquetasDoEmail, faltaDados, faltaExtras, formDoTexto, nomeDoHospede, pedidoDoEmail, pedidoDoFormulario } from "../dados/formulario.js";
import Pastas, { nomeDaCaixa } from "./correio/Pastas.jsx";
import Leitura, { dadosDoEmail, dataLonga } from "./correio/Leitura.jsx";
import Escrever from "./correio/Escrever.jsx";
import Ficha from "./correio/Ficha.jsx";
import Formulario from "./correio/Formulario.jsx";
import MenuEmail from "./correio/MenuEmail.jsx";
import useAcoesCorreio from "./correio/useAcoesCorreio.js";
import { useEnvios } from "./correio/Envios.jsx";
import { carregarTexto, preCarregar, useTextos } from "./correio/textos.js";
import "./CaixaEntrada.css";
import "./correio/Correio.css";

const horaCurta = (q) => {
  if (!q) return "";
  const d = new Date(q), hoje = new Date();
  if (Number.isNaN(+d)) return "";
  return d.toDateString() === hoje.toDateString() ? d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : `${String(d.getDate()).padStart(2, "0")}/${String(d.getMonth() + 1).padStart(2, "0")}`;
};
const grupo = (dias) => (dias < 1 ? "Hoje" : dias < 2 ? "Ontem" : dias < 7 ? "Esta semana" : "Mais antigos");
const ORDEM_GRUPOS = ["Hoje", "Ontem", "Esta semana", "Mais antigos"];
const NOMES_PASTA = { entrada: "Caixa de Entrada", urgencia: "Urgência", form: "Formulários do robô", enviados: "Itens Enviados" };
const OQUE = { novo: "o e-mail", enc: "a mensagem", nf: "a resposta com a NF", pedido: "a NF", resp: "a resposta" };
const digitando = (t) => /INPUT|TEXTAREA|SELECT/.test(t?.tagName) || t?.isContentEditable;
const temJanela = () => !!document.querySelector(".janela-fundo, .menu-email");

function etiquetasDaLinha(e, fila, cinza) {
  if (e.pasta === "enviado") return e.ligacao ? [<Etiqueta key="lig" tipo="azul" icone="telefone">Ligação</Etiqueta>] : [];
  if ((e.pasta && e.pasta !== "entrada") || cinza) return [];
  const l = etiquetasDoEmail(e, fila).map((t, i) => <Etiqueta key={i} tipo={t.tipo} icone={t.icone} contorno={t.contorno} titulo={t.titulo}>{t.texto}</Etiqueta>);
  if ((e.classes || []).includes("formulario")) l.push(<Etiqueta key="form" tipo="cinza" icone="formulario">Formulário</Etiqueta>);
  return l;
}

export default function CaixaEntrada({ correio, estado, pastaInicial = "entrada", busca = "", setBusca, aba = "inicio", reler, trocarTema }) {
  const { recado } = useAvisos();
  const envios = useEnvios();
  const acoes = useAcoesCorreio(reler);
  const { texto } = useTextos();
  const [vista, setVista] = useState({ pasta: pastaInicial, caixa: "" });
  const [soNaoLidos, setSoNaoLidos] = useState(false);
  const [aberto, setAberto] = useState(null);
  const [escrevendo, setEscrevendo] = useState(null);   // { modo, id, extra } — dentro da leitura
  const [novo, setNovo] = useState(null);               // { modo, extra, minimizado, rotulo } — janela por cima
  const [ficha, setFicha] = useState(null);             // { emailId } | { chave }
  const [menu, setMenu] = useState(null);               // { e, x, y }
  const [confirmar, setConfirmar] = useState(null);     // e-mail a excluir (quem não é administrador confirma)
  const [semPastas, setSemPastas] = useState(false);
  const [live, setLive] = useState(null), [buscando, setBuscando] = useState("");
  const listaRef = useRef(null);
  const er = useEnviarReceber(recado, reler);

  const fila = estado?.fila || [];
  const pcs = estado?.pcs || correio?.pcs || [];
  const soVer = !!estado?.so_ver, admin = !!estado?.admin;
  const aplicar = acoes.aplicar;
  const entrada = useMemo(() => aplicar((correio?.emails || []).filter((e) => e.pasta === "entrada")), [correio, aplicar]);
  const enviados = useMemo(() => aplicar((correio?.enviados || []).map((e) => ({ ...e, pasta: "enviado" }))), [correio, aplicar]);
  const noEspelho = useCallback((e) => !!e && (entrada.some((x) => x.id === e.id) || enviados.some((x) => x.id === e.id)), [entrada, enviados]);

  // ---------- a pesquisa: direto no índice do Outlook dos 4 PCs ----------
  const termo = busca.trim();
  const termoAtual = useRef(termo);
  termoAtual.current = termo;
  const primeira = useRef(true);
  useEffect(() => {
    if (primeira.current) primeira.current = false; else { setAberto(null); setFicha(null); }   // pesquisa nova: fecha o e-mail aberto
    if (termo.length < 3) { setLive(null); setBuscando(""); return undefined; }
    const t = setTimeout(() => pesquisar(termo), 250);   // índice local: responde na hora
    return () => clearTimeout(t);
  }, [termo]);   // eslint-disable-line react-hooks/exhaustive-deps
  async function pesquisar(q, vivo = false) {
    setBuscando(q);
    const r = await api("/api/correio/buscar?q=" + encodeURIComponent(q) + (vivo ? "&vivo=1" : ""));
    if (termoAtual.current !== q) return;   // já digitaram outra coisa
    setBuscando("");
    if (r.erro || r.ok === false) { recado(r.erro || r.motivo || "Não deu para pesquisar agora", true); setLive(null); } else setLive(r);
  }

  const lista = useMemo(() => {
    let l;
    if (live) l = aplicar(live.resultados || []);
    else if (vista.pasta === "enviados") l = enviados.filter((e) => !vista.caixa || String(e.caixa).toLowerCase() === vista.caixa);
    else {
      l = entrada.filter((e) => !vista.caixa || String(e.caixa).toLowerCase() === vista.caixa);
      if (vista.pasta === "urgencia") l = l.filter((e) => e.urgente);
      if (vista.pasta === "form") l = l.filter((e) => (e.classes || []).includes("formulario"));
    }
    if (soNaoLidos && vista.pasta !== "enviados") l = l.filter((e) => e.lido === false);
    return [...l].sort((a, b) => (a.quando < b.quando ? 1 : -1));
  }, [live, entrada, enviados, vista, soNaoLidos, aplicar]);
  const idade = (m) => m.dias ?? (Date.now() - new Date(m.quando || 0)) / 864e5;
  const grupos = ORDEM_GRUPOS.map((g) => [g, lista.filter((m) => grupo(idade(m)) === g)]).filter(([, l]) => l.length);
  const todos = useMemo(() => [...entrada, ...enviados, ...(live?.resultados || [])], [entrada, enviados, live]);
  const e = aberto ? todos.find((x) => x.id === aberto) : null;
  const cinza = !!(e && acoes.respondidos[e.id]);

  useEffect(() => { if (lista.length) preCarregar(lista.map((x) => ({ ...x, noEspelho: noEspelho(x) })), aberto); }, [lista, aberto]);   // eslint-disable-line react-hooks/exhaustive-deps

  // ---------- abrir ----------
  const ocupado = () => { if (escrevendo || novo) { recado("Envie ou descarte a mensagem que está escrevendo", true); return true; } return false; };
  function abrir(id, semFicha = false) {
    if (escrevendo && aberto !== id) { recado("Envie ou descarte a mensagem que está escrevendo", true); return; }
    const x = todos.find((m) => m.id === id);
    setAberto(id); setMenu(null);
    if (!x) return;
    carregarTexto({ ...x, noEspelho: noEspelho(x) });
    setFicha(!semFicha && ehFormulario(x) ? { emailId: id } : null);   // chegou um formulário: abre a ficha do hóspede
    if (x.lido === false && x.pasta === "entrada" && noEspelho(x) && !soVer) acoes.lido(x, true, false);   // abriu = lido, para a equipe toda
  }
  const fechar = () => { if (!escrevendo) { setAberto(null); setFicha(null); } };
  const abrirPedido = (chave) => { setFicha({ chave }); setAberto(null); };

  // ---------- escrever ----------
  function escrever(modo, alvo = e) {
    if (!alvo || soVer) return;
    if (novo) { recado("Você já tem um e-mail em andamento: continue por ele ou descarte antes de abrir outro", true); setNovo({ ...novo, minimizado: false }); return; }
    if (escrevendo && escrevendo.id !== alvo.id) return ocupado();
    setAberto(alvo.id); setFicha(null);
    setEscrevendo({ modo, id: alvo.id, extra: {} });
  }
  function abrirNovo(extra = {}) {
    if (soVer) return;
    if (novo) { setNovo({ ...novo, minimizado: false }); recado("Você já tem um e-mail em andamento: continue por ele ou descarte antes de abrir outro", true); return; }
    if (escrevendo) return ocupado();
    setNovo({ extra, minimizado: false });
  }
  const pedirFalta = (d) => abrirNovo({ para: d.email, conta: d.na_caixa?.caixa || (estado?.hoteis || []).find((h) => h.hotel === d.hotel)?.email || "", solicitar: true, faltas: [...faltaDados(d), ...faltaExtras(d)] });
  function aoEnviado(modo, alvo, extra) {
    return (r, ctx) => {
      recado(r.aviso ? `Pedido de envio entregue · ${r.aviso}` : "Pedido de envio entregue");
      if (modo === "novo") setNovo(null); else setEscrevendo(null);
      if (alvo && (modo === "resp" || modo === "nf")) acoes.respondeu(alvo, entrada.filter((x) => x.de === alvo.de));
      envios.seguir(r.id, { oque: OQUE[modo], modo, emailId: alvo?.id, extra: { ...extra, rascunho: ctx.rascunho }, aoEnviado: reler });
    };
  }
  // "Escrever de novo" de um envio que falhou: reabre a mensagem com o texto
  useEffect(() => {
    const r = envios.reabrir;
    if (!r) return;
    envios.limparReabrir();
    if (r.modo === "novo") setNovo({ extra: r.extra, minimizado: false });
    else if (r.emailId) { setAberto(r.emailId); setFicha(null); setEscrevendo({ modo: r.modo, id: r.emailId, extra: r.extra }); }
    recado("Mensagem reaberta com o texto. Se tinha anexo, anexe de novo.");
  }, [envios.reabrir]);   // eslint-disable-line react-hooks/exhaustive-deps

  // ---------- ações ----------
  const excluir = (x) => { if (!x) return; if (admin) { acoes.excluir(x); if (aberto === x.id) setAberto(null); } else setConfirmar(x); };
  function acaoMenu(x, acao) {
    if (acao === "tirar") { acoes.tirarDaEntrada(x); if (aberto === x.id) setAberto(null); return; }
    if (acao === "lig" || acao === "semlig") return acoes.ligacao(x, acao === "lig");
    if (acao === "lido") return acoes.lido(x, true);
    if (acao === "naolido") { acoes.lido(x, false); if (aberto === x.id) setAberto(null); return; }
    if (acao === "urgente" || acao === "normal") return acoes.urgencia(x, acao === "urgente");
    if (acao === "nf" || acao === "resp" || acao === "enc") return escrever(acao, x);
    if (acao === "excluir") return excluir(x);
  }
  const abrirMenu = (x, ev, doBotao) => {
    ev.preventDefault();
    const r = doBotao ? ev.currentTarget.getBoundingClientRect() : null;
    setMenu({ e: x, x: r ? r.left : ev.clientX, y: r ? r.bottom + 4 : ev.clientY });
  };
  const alternarLido = () => { if (!e || e.pasta !== "entrada" || !noEspelho(e)) return; acaoMenu(e, e.lido === false ? "lido" : "naolido"); };

  // ---------- atalhos do Outlook ----------
  useEffect(() => {
    const tecla = (ev) => {
      const k = (ev.key || "").toLowerCase();
      if ((ev.ctrlKey && (k === "e" || k === "k")) && !temJanela()) { ev.preventDefault(); const b = document.getElementById("busca-topo"); b?.focus(); b?.select(); return; }
      if (digitando(ev.target) || temJanela()) return;
      const daCaixa = e && e.pasta === "entrada" && noEspelho(e) && !cinza ? e : null;
      const precisa = () => recado("Abra um e-mail da caixa primeiro (clique ou use as setas)", true);
      if (ev.ctrlKey && k === "r") { ev.preventDefault(); return daCaixa ? escrever(ev.shiftKey ? "nf" : "resp", daCaixa) : precisa(); }
      if (ev.ctrlKey && k === "f") { ev.preventDefault(); return daCaixa ? escrever("enc", daCaixa) : precisa(); }
      if (ev.ctrlKey && k === "u") { ev.preventDefault(); return daCaixa ? acaoMenu(daCaixa, "naolido") : precisa(); }
      if (ev.ctrlKey && k === "q") { ev.preventDefault(); return daCaixa ? acaoMenu(daCaixa, "lido") : precisa(); }
      if (ev.key === "Delete" && !escrevendo) { ev.preventDefault(); return e && !cinza && !soVer ? excluir(e) : precisa(); }
      if (ev.key === "Escape" && !escrevendo && (aberto || ficha)) { fechar(); return; }
      const linha = ev.target.closest?.(".em");
      if (linha && (ev.key === "ArrowDown" || ev.key === "ArrowUp")) {
        ev.preventDefault();
        const bts = [...(listaRef.current?.querySelectorAll(".em") || [])], i = bts.indexOf(linha);
        const prox = bts[Math.max(0, Math.min(bts.length - 1, i + (ev.key === "ArrowDown" ? 1 : -1)))];
        prox?.focus(); if (prox?.dataset.id) abrir(prox.dataset.id, true);   // como no Outlook: a seta já abre (sem a ficha)
      }
      if (linha && (ev.key === "ContextMenu" || (ev.shiftKey && ev.key === "F10"))) {
        ev.preventDefault(); const x = todos.find((m) => m.id === linha.dataset.id); const r = linha.getBoundingClientRect();
        if (x) setMenu({ e: x, x: r.left + 40, y: r.top + r.height / 2 });
      }
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  });

  if (!correio) return <main className="ol-vazio vidro">Lendo as caixas de entrada dos 4 PCs…</main>;

  // ---------- a ficha do hóspede ----------
  let fichaDados = null, fichaEmail = "", fichaLendo = false;
  if (ficha) {
    if (ficha.chave) {
      fichaDados = fila.find((s) => s.chave === ficha.chave) || null;
      fichaEmail = entrada.find((x) => x.solicitacao?.chave === ficha.chave)?.id || "";
    } else {
      const x = todos.find((m) => m.id === ficha.emailId), t = texto(ficha.emailId), f = formDoTexto(t?.texto);
      fichaDados = (x && (pedidoDoEmail(x, fila) || pedidoDoFormulario(f, fila))) || (f ? { ...f, hotel: x?.hotel || "", nome: x?.nome || "" } : null);
      fichaEmail = ficha.emailId;
      fichaLendo = !fichaDados && (!t || t.carregando);
    }
  }

  const leituraFormulario = e && ehFormulario(e) ? dadosDoEmail(e, fila, texto(e.id)?.texto).dados : null;
  const citacao = e && (
    <>
      <div className="cit-cab"><b>De:</b> {e.nome || e.de} &lt;{e.de}&gt;<br /><b>Enviado:</b> {dataLonga(e.quando)}<br /><b>Para:</b> {e.caixa || e.para || ""}<br /><b>Assunto:</b> {e.assunto || ""}</div>
      {leituraFormulario ? <Formulario dados={leituraFormulario} email={e} /> : <div className="c-texto">{texto(e.id)?.texto || e.previa || ""}</div>}
    </>
  );
  const paraDoForm = leituraFormulario?.email && String(leituraFormulario.email).includes("@") ? String(leituraFormulario.email).trim().toLowerCase() : "";
  const podeEscrever = e && e.pasta === "entrada" && noEspelho(e) && !cinza && !soVer;
  const tituloLista = live ? "Resultado da pesquisa" : vista.caixa ? `${nomeDaCaixa(vista.caixa, estado?.hoteis)} · ${NOMES_PASTA[vista.pasta === "enviados" ? "enviados" : "entrada"]}` : NOMES_PASTA[vista.pasta];
  const cmd = (icone, t, aoClicar, { titulo, desligado } = {}) => (
    <button type="button" className="cmd" title={titulo || t} disabled={desligado} onClick={aoClicar}><Icone nome={icone} tamanho={17} /><span className="cmd-texto">{t}</span></button>
  );
  const semEmail = { desligado: !podeEscrever, titulo: !e ? "Abra um e-mail primeiro" : !podeEscrever ? "Este e-mail é só para leitura" : undefined };

  return (
    <div className="ol">
      <div className="faixa vidro" role="toolbar" aria-label="Comandos do e-mail">
        {aba === "enviar" ? <>
          {cmd("atualizar", er.andamento ? (er.andamento.fim ? (er.andamento.aviso ? "Atualizado, com aviso" : "Atualizado") : `Enviando/recebendo… ${er.andamento.feitos || 0} de ${er.andamento.total || "?"} PCs`) : "Enviar/Receber todas as pastas", er.rodar, { desligado: !!er.andamento })}
          {cmd("enviar", "Enviar solicitações pendentes", async () => { const r = await enviarPendentes(); recado(r.texto, r.erro); }, { desligado: soVer })}
        </> : aba === "exibir" ? <>
          {cmd("caixa", semPastas ? "Mostrar as pastas" : "Esconder as pastas", () => setSemPastas(!semPastas))}
          {cmd("tema", "Tema do Painel", trocarTema)}
        </> : <>
          {cmd("responder", "Responder", () => escrever("resp"), { ...semEmail, titulo: semEmail.titulo || "Responder (Ctrl+R)" })}
          {cmd("responderTodos", "Responder a todos", () => escrever("resp"), semEmail)}
          {cmd("encaminhar", "Encaminhar", () => escrever("enc"), { ...semEmail, titulo: semEmail.titulo || "Encaminhar (Ctrl+F)" })}
          <span className="sep" />
          {cmd("lido", "Não lido/Lido", alternarLido, { ...semEmail, titulo: semEmail.titulo || "Ctrl+U / Ctrl+Q" })}
          {cmd("bandeira", e?.urgente ? "Tirar sinal" : "Sinalizar", () => acoes.urgencia(e, !e.urgente), { ...semEmail, titulo: semEmail.titulo || "Marca como urgente para a equipe (fica no Outlook do PC dono)" })}
          {cmd("lixo", "Excluir", () => excluir(e), { desligado: !e || cinza || soVer, titulo: !e ? "Abra um e-mail primeiro" : "Excluir (Delete)" })}
          <span style={{ flex: 1 }} />
          <Botao tipo="contorno" icone="novo" pequeno desligado={soVer} titulo="Escrever um e-mail novo: você escolhe a caixa do hotel que envia" onClick={() => abrirNovo()}>Novo e-mail</Botao>
          <BotaoEnviarNF pequeno semEmail={!podeEscrever} hospede={!podeEscrever ? "" : leituraFormulario ? nomeDoHospede(leituraFormulario) : e?.nome} aoClicar={() => escrever("nf")} />
          {cmd("atualizar", er.andamento && !er.andamento.fim ? "Enviando/recebendo…" : "Enviar/Receber todas", er.rodar, { desligado: !!er.andamento, titulo: "Pede aos PCs que rodem o Enviar/Receber do Outlook e relê a planilha" })}
        </>}
      </div>

      {ficha ? (
        fichaDados ? (
          <Ficha d={fichaDados} emailId={fichaEmail} emails={entrada} fila={fila} hotel={todos.find((m) => m.id === fichaEmail)?.hotel} soVer={soVer}
            voltar={() => { setFicha(null); setAberto(null); }} abrirEmail={(id) => abrir(id, true)} enviarNF={(id) => escrever("nf", todos.find((m) => m.id === id))}
            pedirFalta={pedirFalta} pesquisar={(t) => { setFicha(null); setAberto(null); setBusca?.(t); }} abrirPedido={abrirPedido} />
        ) : (
          <main className="hp vidro"><div className="hp-faixa"><Botao tipo="fantasma" pequeno icone="esquerda" onClick={() => { setFicha(null); setAberto(null); }}>Voltar</Botao></div>
            <div className="hp-vazio">{fichaLendo ? <FichaEsperando /> : "Não consegui ler os dados do formulário agora."}
              {fichaEmail && <p><Botao icone="envelope" onClick={() => abrir(fichaEmail, true)}>Abrir o e-mail</Botao></p>}</div></main>
        )
      ) : (
        <div className={`ol-mesa${semPastas ? " sem-pastas" : ""}${aberto || escrevendo ? " lendo" : ""}`}>
          {!semPastas && <Pastas vista={live ? {} : vista} escolher={(v) => { if (ocupado()) return; setBusca?.(""); setVista(v); setAberto(null); }}
            entrada={entrada} contagem={correio.contagem || {}} enviados={enviados.length} pcs={pcs} hoteis={estado?.hoteis} estePc={correio.este_pc} />}
          <section className="pn vidro entra" style={{ "--i": 1 }} aria-label="Lista de e-mails">
            <div className="cab-lista">
              {live || buscando ? (
                <div className="busca-info">
                  <span><b>{buscando ? `Procurando “${buscando}” nos 4 PCs…` : `${(live?.resultados || []).length} e-mails com “${live?.termo}”`}</b></span>
                  {live && !buscando && <span className="busca-pcs">{Object.entries(live.pcs || {}).map(([pc, s]) => (
                    <Etiqueta key={pc} tipo={s.ok ? "verde" : "cinza"} titulo={s.erro || ""}>{live.agentes?.[pc] || pc}: {s.ok ? s.achados : s.erro === "desligado" ? "desligado" : "sem resposta"}</Etiqueta>))}</span>}
                  <span className="busca-bts">
                    {live && !live.vivo && <Botao pequeno icone="busca" onClick={() => pesquisar(termo, true)} titulo="Procura direto no Outlook de cada PC (mais lento)">Procurar também no Outlook</Botao>}
                    <Botao pequeno tipo="fantasma" icone="fechar" onClick={() => setBusca?.("")}>Limpar</Botao>
                  </span>
                </div>
              ) : (
                <>
                  <div className="abas-lista" role="group" aria-label="Mostrar">
                    <button type="button" aria-pressed={!soNaoLidos} onClick={() => setSoNaoLidos(false)}>Todas</button>
                    <button type="button" aria-pressed={soNaoLidos} onClick={() => setSoNaoLidos(true)} disabled={vista.pasta === "enviados"}>Não lidos</button>
                  </div>
                  <span className="info"><b>{tituloLista}</b> · {lista.length} e-mails{vista.pasta !== "enviados" ? ` · ${lista.filter((x) => x.lido === false).length} não lidos` : ""}</span>
                </>
              )}
            </div>
            <div className="linhas" role="listbox" aria-label="E-mails" ref={listaRef}>
              {grupos.length === 0 && !buscando && <p className="lista-vazia">{live ? "Nenhum e-mail achado. Tente outra palavra ou “Procurar também no Outlook”." : "Nenhum e-mail aqui."}</p>}
              {grupos.map(([g, l]) => (
                <div key={g}>
                  <div className="grp">{g}</div>
                  {l.map((m, i) => {
                    const cinzaL = !!acoes.respondidos[m.id], enviado = m.pasta === "enviado", naoLido = !enviado && m.lido === false && !cinzaL;
                    const situacao = cinzaL || m.respondido ? "respondido · " : m.pasta === "excluido" ? "excluído · " : "";
                    return (
                      <button key={m.id} type="button" role="option" aria-selected={m.id === aberto} data-id={m.id} title={m.urgente ? m.motivo_urgencia || "Urgente" : undefined}
                        className={`em${m.urgente && !cinzaL ? " urg" : ""}${naoLido ? " nao-lido" : ""}${cinzaL ? " cinza" : ""}`} style={{ "--i": Math.min(i, 8) }}
                        onClick={() => abrir(m.id)} onContextMenu={(ev) => abrirMenu(m, ev)}>
                        <span className="l1"><span className="de">{enviado ? `Para: ${m.para}` : m.nome || m.de || "(sem remetente)"}</span>
                          <span className="ics">{(m.anexos || []).length > 0 && <Icone nome="clipe" tamanho={14} titulo="tem anexo" />}{m.urgente && !cinzaL && <Icone nome="bandeira" tamanho={14} titulo="urgente" />}</span></span>
                        <span className="l1"><span className="as">{m.assunto || "(sem assunto)"}</span><span className="d">{horaCurta(m.quando)}</span></span>
                        <span className="pv">{situacao}{m.hotel ? m.hotel + " · " : ""}{m.previa}</span>
                        <span className="tags">{etiquetasDaLinha(m, fila, cinzaL)}</span>
                        {naoLido && <span className="so-leitor">não lido</span>}
                      </button>
                    );
                  })}
                </div>
              ))}
            </div>
          </section>
          <article className="pn vidro leit entra" style={{ "--i": 2 }} aria-label="Leitura">
            {escrevendo && e ? (
              <Escrever key={escrevendo.id + escrevendo.modo} inline modo={escrevendo.modo} email={e} extra={escrevendo.extra} paraDoFormulario={escrevendo.modo === "enc" ? "" : paraDoForm}
                citacao={escrevendo.modo === "enc" ? null : citacao} aoFechar={() => setEscrevendo(null)} aoEnviado={aoEnviado(escrevendo.modo, e, escrevendo.extra)} />
            ) : e ? (
              <Leitura e={e} fila={fila} pcs={pcs} noEspelho={noEspelho(e)} cinza={cinza} soVer={soVer} aoFechar={fechar} aoAbrirPedido={abrirPedido}
                acoes={{ escrever: (m) => escrever(m, e), pedirFalta: () => { const d = pedidoDoEmail(e, fila); if (d) pedirFalta(d); }, menu: (ev) => abrirMenu(e, ev, true) }} />
            ) : (
              <div className="vazio"><Icone nome="envelope" tamanho={44} /><b>Selecione um e-mail para ler</b><span>Clique numa linha da lista · as setas ↑ ↓ andam pelos e-mails</span></div>
            )}
          </article>
        </div>
      )}

      {novo && createPortal(
        <>
          <div className={`escrever-fundo${novo.minimizado ? " minimizado" : ""}`}>
            <div className="escrever-janela vidro">
              <Escrever modo="novo" extra={novo.extra} aoFechar={() => setNovo(null)} aoEnviado={aoEnviado("novo", null, novo.extra)}
                aoMinimizar={(rotulo) => setNovo({ ...novo, minimizado: true, rotulo })} />
            </div>
          </div>
          {novo.minimizado && <Minimizado rotulo={novo.rotulo} voltar={() => setNovo({ ...novo, minimizado: false })} descartar={() => setNovo(null)} />}
        </>,
        document.body,
      )}
      {menu && <MenuEmail e={menu.e} x={menu.x} y={menu.y} enviado={menu.e.pasta === "enviado"} cinza={!!acoes.respondidos[menu.e.id]}
        extra={menu.e.pasta === "entrada" && noEspelho(menu.e) && !soVer ? [["nf", "nota", "Responder com a NF"], ["excluir", "lixo", "Excluir", "perigo"]] : []}
        aoEscolher={(a) => acaoMenu(menu.e, a)} aoFechar={() => setMenu(null)} />}
      {confirmar && (
        <Janela titulo="Excluir este e-mail?" sub={`“${confirmar.assunto || "(sem assunto)"}” · ${confirmar.nome || confirmar.de}`} aoFechar={() => setConfirmar(null)} largura={500}
          rodape={<><Botao onClick={() => setConfirmar(null)}>Cancelar</Botao><Botao tipo="perigo" icone="lixo" onClick={() => { acoes.excluir(confirmar); if (aberto === confirmar.id) setAberto(null); setConfirmar(null); }}>Excluir</Botao></>}>
          Vai para os <b>Itens Excluídos do Outlook de {pcs.find((p) => p.pc === confirmar.pc)?.agente || confirmar.pc}</b> (dá para recuperar de lá) e sai do Painel de toda a equipe. Fica registrado que foi você.
        </Janela>
      )}
    </div>
  );
}

// O PC dono da caixa ainda está mandando o texto: em 5 s vira aviso (com o botão "Abrir o e-mail")
function FichaEsperando() {
  const [tempo, setTempo] = useState(false);
  useEffect(() => { const t = setTimeout(() => setTempo(true), 5000); return () => clearTimeout(t); }, []);
  return tempo ? "Não consegui ler os dados do formulário agora." : "Lendo o formulário no PC dono da caixa…";
}

// Novo e-mail minimizado: a barrinha embaixo à direita; descartar daqui precisa de 2 cliques (não perde o rascunho por engano)
function Minimizado({ rotulo, voltar, descartar }) {
  const [certo, setCerto] = useState(false);
  useEffect(() => { if (!certo) return undefined; const t = setTimeout(() => setCerto(false), 3000); return () => clearTimeout(t); }, [certo]);
  return (
    <div className="escrever-barra vidro">
      <button type="button" className="eb-abrir" onClick={voltar} title="Voltar ao e-mail"><b>Novo e-mail</b><span>{(rotulo || "sem assunto").trim()}</span></button>
      <button type="button" className="eb-x" onClick={() => (certo ? descartar() : setCerto(true))} aria-label="Descartar este e-mail">{certo ? "Descartar?" : <Icone nome="fechar" tamanho={14} />}</button>
    </div>
  );
}
