// A cápsula da barra lateral: um círculo por tela; a tela aberta fica no círculo claro.
// Telas já passadas para React abrem aqui; as outras abrem na tela de hoje (a reserva).
import Icone from "../componentes/Icone.jsx";
import { abrirNaTelaDeHoje } from "../api.js";
import "./Moldura.css";

export const TELAS = [
  { chave: "visao", nome: "Visão geral", icone: "casa", react: true },
  { chave: "correio", nome: "Caixa de entrada", icone: "caixa", react: true, numero: "entrada" },
  { chave: "urgencia", nome: "Urgência", icone: "alerta", numero: "urgencia", antiga: "correio" },
  { chave: "fila", nome: "Notas fiscais", icone: "nota" },
  { chave: "robo", nome: "Robô", icone: "robo", antiga: "" },
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
        const clicar = () => (t.react ? irPara(t.chave) : abrirNaTelaDeHoje(t.antiga ?? t.chave));
        return (
          <button key={t.chave} type="button" className="capsula-botao" title={t.react ? t.nome : `${t.nome} (abre na tela de hoje)`}
            aria-label={t.nome} aria-current={tela === t.chave ? "page" : undefined} onClick={clicar}>
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
