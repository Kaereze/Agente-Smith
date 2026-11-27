// O Painel Fiscal em React: a moldura (cápsula, topo, rodapé) e a tela escolhida no meio.
// Telas já em React: Visão geral e Caixa de entrada. As outras abrem na tela de hoje (a reserva) até serem passadas.
import { useEffect, useMemo, useState } from "react";
import Capsula from "./moldura/Capsula.jsx";
import Topo from "./moldura/Topo.jsx";
import Rodape from "./moldura/Rodape.jsx";
import VisaoGeral from "./telas/VisaoGeral.jsx";
import CaixaEntrada from "./telas/CaixaEntrada.jsx";
import usePainel from "./dados/usePainel.js";
import { resumoDoDia } from "./dados/resumo.js";
import "./moldura/Moldura.css";

const guardado = (chave, padrao) => { try { return localStorage.getItem(chave) || padrao; } catch { return padrao; } };
const guardar = (chave, valor) => { try { localStorage.setItem(chave, valor); } catch { /* sem armazenamento: só não lembra */ } };
const telaDoEndereco = () => (window.location.hash.replace("#", "") === "correio" ? "correio" : "visao");

export default function App() {
  const { estado, correio, erro, lidoEm } = usePainel();
  const [tela, setTela] = useState(telaDoEndereco);
  const [tema, setTema] = useState(() => guardado("painel-tema", window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "escuro" : "claro"));
  const r = useMemo(() => (estado && correio ? resumoDoDia(estado, correio) : null), [estado, correio]);

  useEffect(() => { document.documentElement.dataset.tema = tema; guardar("painel-tema", tema); }, [tema]);
  useEffect(() => {
    const aoMudar = () => setTela(telaDoEndereco());
    window.addEventListener("hashchange", aoMudar);
    return () => window.removeEventListener("hashchange", aoMudar);
  }, []);
  const irPara = (t) => { window.location.hash = t; setTela(t); };

  const avisos = [];
  if (erro) avisos.push({ icone: "alerta", texto: erro, detalhe: "o Painel tenta de novo sozinho" });
  if (r) {
    r.pcs.filter((p) => !p.online).forEach((p) => avisos.push({ icone: "pc", texto: `O PC de ${p.agente} está desligado`, detalhe: `visto pela última vez ${p.visto || "—"}` }));
    if (r.semResposta) avisos.push({ icone: "alerta", texto: `${r.semResposta} hóspedes sem resposta há mais de 2 dias`, detalhe: "veja na Caixa de entrada" });
  }

  return (
    <>
      <div className="fundo-bolhas" aria-hidden="true"><i /><i /><i /></div>
      <div className="casco">
        <Capsula tela={tela} irPara={irPara} admin={!!estado?.admin} agente={estado?.agente}
          contagem={{ entrada: correio?.contagem?.entrada_nao_lidos, urgencia: correio?.contagem?.urgencia }} />
        <Topo modo={tela === "correio" ? "emails" : "inicio"} agente={estado?.agente} tema={tema}
          trocarTema={() => setTema(tema === "escuro" ? "claro" : "escuro")} avisos={avisos} />
        {tela === "correio"
          ? <CaixaEntrada key="correio" correio={correio} estado={estado} />
          : <VisaoGeral key="visao" r={r} agente={estado?.agente} irPara={irPara} />}
        <Rodape resumo={r} demo={!!estado?.demo} lidoEm={lidoEm} />
      </div>
    </>
  );
}
