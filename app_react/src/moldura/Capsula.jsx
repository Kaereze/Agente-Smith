// A cápsula da barra lateral: um círculo por tela; a tela aberta fica no círculo claro.
import Icone from "../componentes/Icone.jsx";
import "./Moldura.css";

export const TELAS = [
  { chave: "visao", nome: "Visão geral", icone: "casa" },
  { chave: "correio", nome: "Caixa de entrada", icone: "caixa", numero: "entrada" },
  { chave: "urgencia", nome: "Urgência", icone: "alerta", numero: "urgencia" },
  { chave: "enviados", nome: "Itens enviados", icone: "enviar" },
  { chave: "fila", nome: "Notas fiscais", icone: "nota" },
  { chave: "robo", nome: "Robô", icone: "robo" },
  "separador",
  { chave: "maquinas", nome: "Monitoramento", icone: "pc", admin: true },
  { chave: "agentes", nome: "Agentes do Smith", icone: "rede", admin: true },
  { chave: "gerencia", nome: "Gerência", icone: "cadeado" },
];

export default function Capsula({ tela, irPara, contagem, admin, agente }) {
  return (
    <nav className="capsula vidro" aria-label="Navegação">
      <div className="capsula-selo" aria-hidden="true">NF</div>
      {TELAS.map((t, i) => {
        if (t === "separador") return <hr key={"s" + i} />;
        if (t.admin && !admin) return null;
        const n = t.numero ? contagem?.[t.numero] : 0;
        return (
          <button key={t.chave} type="button" className="capsula-botao" title={t.nome}
            aria-label={t.nome} aria-current={tela === t.chave ? "page" : undefined} onClick={() => irPara(t.chave)}>
            <Icone nome={t.icone} tamanho={19} />
            {n > 0 && <span className="capsula-numero">{n > 99 ? "99+" : n}</span>}
          </button>
        );
      })}
      <span style={{ flex: 1 }} />
      <span className="capsula-avatar" title={`Operador deste PC: ${agente || "…"}`}>{(agente || "?").slice(0, 1)}</span>
    </nav>
  );
}
