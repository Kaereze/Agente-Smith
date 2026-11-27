// A pílula da situação do sistema, em linha própria (nunca por cima da lista). Sempre com texto, nunca só cor.
import Icone from "../componentes/Icone.jsx";
import { abrirNaTelaDeHoje } from "../api.js";
import "./Moldura.css";

export default function Rodape({ resumo, demo, lidoEm }) {
  const pcs = resumo?.pcs || [];
  const ligados = resumo?.pcsLigados ?? 0;
  const robo = resumo?.robo || {};
  const tudoBem = robo.ligado !== false && ligados === pcs.length && pcs.length > 0;
  const hora = lidoEm ? lidoEm.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) : "…";
  return (
    <footer className="rodape vidro" aria-label="Situação do sistema">
      <span className={`rodape-estado${tudoBem ? "" : " atencao"}`}>
        <Icone nome={tudoBem ? "check" : "alerta"} tamanho={15} />{tudoBem ? "Tudo funcionando" : "Precisa de atenção"}
      </span>
      <span className="rodape-item" title="O robô que envia os pedidos aos hotéis"><Icone nome="robo" tamanho={15} />Robô: {robo.ligado === false ? "pausado" : "ligado"}</span>
      <span className="rodape-item"><Icone nome="pc" tamanho={15} />{ligados} de {pcs.length} PCs ligados</span>
      <span className="rodape-item fraco"><Icone nome="relogio" tamanho={15} />lido às {hora}</span>
      {demo && <span className="rodape-demo">Demonstração · dados fictícios</span>}
      <button type="button" className="rodape-reserva" onClick={() => abrirNaTelaDeHoje("")} title="Volta para a tela de hoje, a reserva">
        <Icone nome="voltar" tamanho={14} />Tela de hoje
      </button>
    </footer>
  );
}
