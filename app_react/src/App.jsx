// O Painel Fiscal em React: a moldura (cápsula, topo, rodapé) e a tela escolhida no meio.
// Os avisos (recado e Desfazer) e o acompanhamento dos envios valem para o Painel inteiro, em qualquer tela.
import { useEffect, useMemo, useState } from "react";
import Capsula from "./moldura/Capsula.jsx";
import Topo from "./moldura/Topo.jsx";
import Rodape from "./moldura/Rodape.jsx";
import VisaoGeral from "./telas/VisaoGeral.jsx";
import CaixaEntrada from "./telas/CaixaEntrada.jsx";
import Robo from "./telas/Robo.jsx";
import Monitoramento from "./telas/Monitoramento.jsx";
import Notas from "./telas/Notas.jsx";
import Agentes from "./telas/Agentes.jsx";
import Gerencia from "./telas/Gerencia.jsx";
import { TELAS } from "./moldura/Capsula.jsx";
import { AvisosProvider } from "./componentes/Avisos.jsx";
import { EnviosProvider } from "./telas/correio/Envios.jsx";
import usePainel from "./dados/usePainel.js";
import { resumoDoDia } from "./dados/resumo.js";
import "./moldura/Moldura.css";

const guardado = (chave, padrao) => { try { return localStorage.getItem(chave) || padrao; } catch { return padrao; } };
const guardar = (chave, valor) => { try { localStorage.setItem(chave, valor); } catch { /* sem armazenamento: só não lembra */ } };
const CHAVES = TELAS.filter((t) => t !== "separador").map((t) => t.chave);
const telaDoEndereco = () => { const h = window.location.hash.replace("#", ""); return CHAVES.includes(h) ? h : "visao"; };
const DE_EMAIL = ["correio", "urgencia", "enviados"];

// arquivo solto fora da área de anexo não pode abrir no lugar do Painel
const naoAbrirArquivo = (ev) => { if (!ev.target.closest?.(".esc-soltar")) ev.preventDefault(); };

export default function App() {
  const { estado, correio, erro, lidoEm, reler } = usePainel();
  const [tela, setTela] = useState(telaDoEndereco);
  const [tema, setTema] = useState(() => guardado("painel-tema", window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "escuro" : "claro"));
  const [busca, setBusca] = useState("");
  const [aba, setAba] = useState("inicio");
  const r = useMemo(() => (estado && correio ? resumoDoDia(estado, correio) : null), [estado, correio]);

  useEffect(() => { document.documentElement.dataset.tema = tema; guardar("painel-tema", tema); }, [tema]);
  useEffect(() => {
    const aoMudar = () => setTela(telaDoEndereco());
    window.addEventListener("hashchange", aoMudar);
    ["dragover", "drop"].forEach((t) => window.addEventListener(t, naoAbrirArquivo));
    return () => { window.removeEventListener("hashchange", aoMudar); ["dragover", "drop"].forEach((t) => window.removeEventListener(t, naoAbrirArquivo)); };
  }, []);
  const irPara = (t) => { window.location.hash = t; setTela(t); };
  const pesquisar = (t) => { setBusca(t); if (t.trim() && !DE_EMAIL.includes(tela)) irPara("correio"); };
  const trocarTema = () => setTema(tema === "escuro" ? "claro" : "escuro");

  const avisos = [];
  if (erro) avisos.push({ icone: "alerta", texto: erro, detalhe: "o Painel tenta de novo sozinho" });
  if (r) {
    r.pcs.filter((p) => !p.online).forEach((p) => avisos.push({ icone: "pc", texto: `O PC de ${p.agente} está desligado`, detalhe: `visto pela última vez ${p.visto || "—"}` }));
    if (r.semResposta) avisos.push({ icone: "alerta", texto: `${r.semResposta} hóspedes sem resposta há mais de 2 dias`, detalhe: "veja na Caixa de entrada" });
  }

  return (
    <AvisosProvider>
      <EnviosProvider irPara={irPara}>
        <div className="fundo-bolhas" aria-hidden="true"><i /><i /><i /></div>
        <div className="casco">
          <Capsula tela={tela} irPara={irPara} admin={!!estado?.admin} agente={estado?.agente}
            contagem={{ entrada: correio?.contagem?.entrada_nao_lidos, urgencia: correio?.contagem?.urgencia }} />
          <Topo modo={DE_EMAIL.includes(tela) ? "emails" : "inicio"} agente={estado?.agente} tema={tema} trocarTema={trocarTema} avisos={avisos}
            busca={busca} setBusca={pesquisar} aba={aba} setAba={setAba} />
          {DE_EMAIL.includes(tela) && <CaixaEntrada key={tela} pastaInicial={tela === "correio" ? "entrada" : tela} correio={correio} estado={estado}
            busca={busca} setBusca={setBusca} aba={aba} reler={reler} trocarTema={trocarTema} />}
          {tela === "visao" && <VisaoGeral r={r} agente={estado?.agente} irPara={irPara} soVer={!!estado?.so_ver} />}
          {tela === "robo" && <Robo estado={estado} r={r} />}
          {tela === "maquinas" && <Monitoramento estado={estado} />}
          {tela === "fila" && <Notas irPara={irPara} />}
          {tela === "agentes" && <Agentes />}
          {tela === "gerencia" && <Gerencia />}
          <Rodape resumo={r} demo={!!estado?.demo} lidoEm={lidoEm} />
        </div>
      </EnviosProvider>
    </AvisosProvider>
  );
}
