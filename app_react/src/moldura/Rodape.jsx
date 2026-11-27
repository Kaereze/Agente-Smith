// O rodapé em pílula, em linha própria (nunca por cima da lista). Sempre com texto, nunca só cor:
// a situação geral · o robô (abre o Robô) · os PCs (Outlook fechado ou conferência parada; abre o Monitoramento) · a Central ·
// modo casa / demonstração · Recarregar (relê a planilha e pede o Enviar/Receber aos PCs) · tema · ajuda.
import { useEffect, useState } from "react";
import Icone from "../componentes/Icone.jsx";
import { MiniK } from "../componentes/Carregando.jsx";
import { TEMAS } from "./MenuOperador.jsx";
import "./Moldura.css";

function textoDosPcs(pcs) {
  const on = pcs.filter((p) => p.online), nome = (p) => p.agente || p.pc;
  const fechados = on.filter((p) => p.outlook === "fechado"), parados = on.filter((p) => p.conferencia_atrasada);
  if (fechados.length) return ["Outlook fechado: " + fechados.map(nome).join(", "), "ruim"];
  if (parados.length) return ["Conferência parada: " + parados.map(nome).join(", "), "atencao"];
  return [`${on.length} de ${pcs.length} PCs no ar`, on.length < pcs.length ? "atencao" : "ok"];
}
function textoDoRobo(estado) {
  const s = estado?.status || {};
  if (s.ligado === false) return ["Robô pausado", "atencao"];
  const esperando = (estado?.fila || []).filter((x) => !x.enviado && !x.repetido_de && x.situacao === "aguardando_envio").length;
  return [esperando ? `Robô · ${esperando} esperando` : "Robô · tudo certo", "ok"];
}

export default function Rodape({ estado, erro, demo, lidoEm, irPara, admin, tema, trocarTema, abrirAjuda, recarregar, recarregando }) {
  const [espera, setEspera] = useState(0);
  useEffect(() => { const f = (e) => setEspera(e.detail.n); window.addEventListener("painel:espera", f); return () => window.removeEventListener("painel:espera", f); }, []);
  const pcs = estado?.pcs || [];
  const [txtPcs, nivelPcs] = textoDosPcs(pcs);
  const [txtRobo, nivelRobo] = textoDoRobo(estado);
  const semCentral = !!(erro || estado?.erro);
  const hora = estado?.atualizado_em ? String(estado.atualizado_em).replace("T", " ").slice(11, 16) : lidoEm ? lidoEm.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "";
  const tudoBem = nivelPcs === "ok" && nivelRobo === "ok" && !semCentral && !(estado?.saude || []).some((a) => a.nivel !== "warn");
  const nomeTema = (TEMAS.find(([v]) => v === tema) || TEMAS[0])[1];
  return (
    <footer className="rodape vidro" aria-label="Situação do sistema">
      <span className={`rodape-estado${tudoBem ? "" : " atencao"}`}><Icone nome={tudoBem ? "check" : "alerta"} tamanho={15} />{tudoBem ? "Tudo funcionando" : "Precisa de atenção"}</span>
      <button type="button" className={`rodape-item ${nivelRobo}`} onClick={() => irPara("robo")} title={`${txtRobo}${estado?.status?.resumo ? "\n" + estado.status.resumo : ""}\nClique para ver o que o robô está fazendo`}>
        <Icone nome="robo" tamanho={15} />{txtRobo}</button>
      <button type="button" className={`rodape-item ${nivelPcs}`} disabled={!admin} onClick={() => irPara("maquinas")}
        title={pcs.map((p) => `${p.agente || p.pc} (${p.pc}): ${p.online ? "ligado" : "desligado"} · Outlook ${p.outlook || "?"}`).join("\n")}>
        <Icone nome="pc" tamanho={15} />{txtPcs}</button>
      <span className={`rodape-item fraco ${semCentral ? "ruim" : ""}`} title="A planilha central, de onde vêm os pedidos e os e-mails"><Icone nome="nuvem" tamanho={15} />{semCentral ? "sem conexão com a planilha" : hora ? `Central às ${hora}` : "lendo a planilha…"}</span>
      {estado?.so_ver && <span className="rodape-demo" title="Este PC só vê os dados reais: responder, enviar NF e marcar lido ficam nos PCs do trabalho">Modo casa · só visualização</span>}
      {demo && <span className="rodape-demo">Demonstração · dados fictícios</span>}
      <span className="rodape-bts">
        <button type="button" className="rodape-ic" onClick={recarregar} disabled={!!recarregando} aria-busy={!!recarregando || espera > 0}
          title="Recarregar: reler a planilha e pedir o Enviar/Receber aos PCs" aria-label="Recarregar">
          {recarregando || espera > 0 ? <MiniK /> : <Icone nome="atualizar" tamanho={16} />}</button>
        <button type="button" className="rodape-ic" onClick={trocarTema} title={`Tema: ${nomeTema}. Clique para trocar`} aria-label={`Tema: ${nomeTema}. Clique para trocar`}><Icone nome="tema" tamanho={16} /></button>
        <button type="button" className="rodape-ic" onClick={abrirAjuda} title="Ajuda: o que cada nome significa e os atalhos (tecla ?)" aria-label="Ajuda"><Icone nome="ajuda" tamanho={16} /></button>
      </span>
    </footer>
  );
}
