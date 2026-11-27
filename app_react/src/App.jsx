// O Painel Fiscal em React: a moldura (cápsula, topo, rodapé) e a tela escolhida no meio.
// Os avisos (recado e Desfazer), o acompanhamento dos envios e a tela de carregamento valem para o Painel inteiro.
import { useEffect, useMemo, useRef, useState } from "react";
import Capsula, { CHAVES } from "./moldura/Capsula.jsx";
import Topo from "./moldura/Topo.jsx";
import Rodape from "./moldura/Rodape.jsx";
import Ajuda from "./moldura/Ajuda.jsx";
import { aplicarEscala } from "./moldura/MenuOperador.jsx";
import VisaoGeral from "./telas/VisaoGeral.jsx";
import CaixaEntrada from "./telas/CaixaEntrada.jsx";
import Robo from "./telas/Robo.jsx";
import Monitoramento from "./telas/Monitoramento.jsx";
import Notas from "./telas/Notas.jsx";
import Agentes from "./telas/Agentes.jsx";
import Gerencia from "./telas/Gerencia.jsx";
import Carregando from "./componentes/Carregando.jsx";
import Icone from "./componentes/Icone.jsx";
import { AvisosProvider, useAvisos } from "./componentes/Avisos.jsx";
import { EnviosProvider } from "./telas/correio/Envios.jsx";
import usePainel, { escrevendo } from "./dados/usePainel.js";
import { useEnviarReceber } from "./dados/acoes.js";
import { avisosDoPainel } from "./dados/avisos.js";
import { resumoDoDia } from "./dados/resumo.js";
import { api } from "./api.js";
import "./moldura/Moldura.css";

const guardado = (chave, padrao) => { try { return localStorage.getItem(chave) ?? padrao; } catch { return padrao; } };
const guardar = (chave, valor) => { try { localStorage.setItem(chave, valor); } catch { /* sem armazenamento: só não lembra */ } };
const telaDoEndereco = () => { const h = window.location.hash.replace("#", ""); return CHAVES.includes(h) ? h : "visao"; };
const DE_EMAIL = ["correio", "urgencia", "enviados"];
// Tema por PC: "" (segue o Windows), "claro" ou "escuro". No servidor o nome é "", "light" ou "dark".
const DO_SERVIDOR = { "": "", light: "claro", dark: "escuro" }, PARA_SERVIDOR = { "": "", claro: "light", escuro: "dark" };
const escuroNoWindows = () => !!window.matchMedia?.("(prefers-color-scheme: dark)").matches;

// arquivo solto fora da área de anexo não pode abrir no lugar do Painel
const naoAbrirArquivo = (ev) => { if (!ev.target.closest?.(".esc-soltar")) ev.preventDefault(); };
const digitando = (t) => /INPUT|TEXTAREA|SELECT/.test(t?.tagName) || t?.isContentEditable;

export default function App() {
  const [tela, setTela] = useState(telaDoEndereco);
  const irPara = (t) => { window.location.hash = t; setTela(t); };
  useEffect(() => {
    const aoMudar = () => setTela(telaDoEndereco());
    window.addEventListener("hashchange", aoMudar);
    return () => window.removeEventListener("hashchange", aoMudar);
  }, []);
  return (
    <AvisosProvider>
      <EnviosProvider irPara={irPara}>
        <Painel tela={tela} irPara={irPara} />
        <Carregando />
      </EnviosProvider>
    </AvisosProvider>
  );
}

function Painel({ tela, irPara }) {
  const { estado, correio, erro, lidoEm, parado, reler } = usePainel();
  const { recado } = useAvisos();
  const [tema, setTema] = useState(() => guardado("painel-tema", ""));
  const [escuroSistema, setEscuroSistema] = useState(escuroNoWindows);
  const [busca, setBusca] = useState("");
  const [aba, setAba] = useState("inicio");
  const [ajuda, setAjuda] = useState(false);
  const temaServidor = useRef(null), f5 = useRef(0);
  const er = useEnviarReceber(recado, reler);
  const r = useMemo(() => (estado && correio ? resumoDoDia(estado, correio) : null), [estado, correio]);
  const admin = !!estado?.admin;

  // tema: o escolhido neste PC; "Sistema" acompanha o Windows na hora
  useEffect(() => {
    document.documentElement.dataset.tema = tema || (escuroSistema ? "escuro" : "claro");
    guardar("painel-tema", tema);
  }, [tema, escuroSistema]);
  useEffect(() => {
    const m = window.matchMedia?.("(prefers-color-scheme: dark)");
    const f = () => setEscuroSistema(!!m?.matches);
    m?.addEventListener?.("change", f);
    return () => m?.removeEventListener?.("change", f);
  }, []);
  useEffect(() => {   // o tema guardado neste PC (estado/app.json) vale mais que o do navegador
    if (estado?.tema === undefined || estado.tema === temaServidor.current) return;
    temaServidor.current = estado.tema;
    setTema(DO_SERVIDOR[estado.tema] ?? "");
  }, [estado?.tema]);
  const escolherTema = (t) => {
    setTema(t);
    temaServidor.current = PARA_SERVIDOR[t];
    api("/api/tema", { tema: PARA_SERVIDOR[t] });
    recado("Tema: " + ({ "": "Sistema", claro: "Claro", escuro: "Escuro" }[t]));
  };
  const trocarTema = () => escolherTema({ "": "claro", claro: "escuro", escuro: "" }[tema]);

  // a janela do app: tamanho da tela automático assim que ela fica pronta
  useEffect(() => {
    const f = () => aplicarEscala();
    window.addEventListener("pywebviewready", f);
    let t;
    const mudou = () => { clearTimeout(t); t = setTimeout(() => aplicarEscala(), 700); };
    window.addEventListener("resize", mudou);
    return () => { window.removeEventListener("pywebviewready", f); window.removeEventListener("resize", mudou); };
  }, []);

  // teclas do Painel inteiro: ? abre a ajuda · F5 recarrega (com mensagem sendo escrita pede o 2º aperto)
  useEffect(() => {
    const tecla = (e) => {
      if (e.key === "F5" && !e.ctrlKey && !e.altKey && !e.shiftKey) {
        e.preventDefault();
        if (escrevendo() && Date.now() - f5.current > 3000) { f5.current = Date.now(); recado("Tem mensagem sendo escrita. Aperte F5 de novo para recarregar mesmo assim.", true); return; }
        window.location.reload();
      }
      if (e.key === "?" && !digitando(e.target) && !document.querySelector(".janela-fundo")) { e.preventDefault(); setAjuda(true); }
    };
    window.addEventListener("keydown", tecla);
    ["dragover", "drop"].forEach((t) => window.addEventListener(t, naoAbrirArquivo));
    return () => { window.removeEventListener("keydown", tecla); ["dragover", "drop"].forEach((t) => window.removeEventListener(t, naoAbrirArquivo)); };
  }, [recado]);

  // quem não é administrador não fica numa tela de admin (ex.: endereço guardado)
  useEffect(() => { if (estado && !admin && (tela === "maquinas" || tela === "agentes")) irPara("visao"); }, [estado, admin, tela]);   // eslint-disable-line react-hooks/exhaustive-deps

  const pesquisar = (t) => { setBusca(t); if (t.trim() && !DE_EMAIL.includes(tela)) irPara("correio"); };
  const avisos = avisosDoPainel(estado, r, erro);

  return (
    <>
      <div className="fundo-bolhas" aria-hidden="true"><i /><i /><i /></div>
      <div className="casco">
        <Capsula tela={tela} irPara={irPara} admin={admin} estado={estado} tema={tema} escolherTema={escolherTema} abrirAjuda={() => setAjuda(true)} reler={reler}
          contagem={{ entrada: correio?.contagem?.entrada_nao_lidos }} />
        <Topo modo={DE_EMAIL.includes(tela) ? "emails" : "inicio"} agente={estado?.agente} avisos={avisos} estado={estado} irPara={irPara} admin={admin}
          busca={busca} setBusca={pesquisar} aba={aba} setAba={setAba} />
        {DE_EMAIL.includes(tela) && <CaixaEntrada key={tela} classeInicial={tela === "correio" ? "todas" : tela} correio={correio} estado={estado}
          busca={busca} setBusca={setBusca} aba={aba} reler={reler} trocarTema={trocarTema} er={er} />}
        {tela === "visao" && <VisaoGeral r={r} agente={estado?.agente} irPara={irPara} soVer={!!estado?.so_ver} />}
        {tela === "robo" && <Robo estado={estado} r={r} reler={reler} admin={admin} irPara={irPara} />}
        {tela === "maquinas" && admin && <Monitoramento estado={estado} />}
        {tela === "fila" && <Notas irPara={irPara} />}
        {tela === "agentes" && admin && <Agentes />}
        {tela === "gerencia" && <Gerencia />}
        <Rodape estado={estado} erro={erro} demo={!!estado?.demo} lidoEm={lidoEm} irPara={irPara} admin={admin} tema={tema} trocarTema={trocarTema}
          abrirAjuda={() => setAjuda(true)} recarregar={er.rodar} recarregando={er.andamento && !er.andamento.fim} />
      </div>
      {parado > 0 && (
        <div className="aviso-parado vidro" role="alert">
          <Icone nome="alerta" tamanho={18} /><span><b>Sem dados do servidor há {parado} min.</b> Tentando de novo a cada 15 s.</span>
          <button type="button" onClick={() => window.location.reload()}>Recarregar agora</button>
        </div>
      )}
      {ajuda && <Ajuda aoFechar={() => setAjuda(false)} />}
    </>
  );
}
