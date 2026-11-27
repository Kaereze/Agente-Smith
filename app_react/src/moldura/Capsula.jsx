// A cápsula da barra lateral: um círculo por tela; a tela aberta fica no círculo claro. Embaixo, o avatar de quem está neste PC
// (abre "Quem está neste PC"). Urgência e Itens enviados não são telas próprias: viram o classificador dentro da Caixa de entrada
// (João, 27/11/2026); os endereços #urgencia e #enviados continuam abrindo a caixa já filtrada.
import { useRef, useState } from "react";
import Icone from "../componentes/Icone.jsx";
import MenuOperador, { iniciais } from "./MenuOperador.jsx";
import "./Moldura.css";

export const TELAS = [
  { chave: "visao", nome: "Visão geral", icone: "casa" },
  { chave: "correio", nome: "Caixa de entrada", icone: "caixa", numero: "entrada", tambem: ["urgencia", "enviados"] },
  { chave: "fila", nome: "Notas fiscais", icone: "nota" },
  { chave: "robo", nome: "Robô", icone: "robo" },
  "separador",
  { chave: "maquinas", nome: "Monitoramento", icone: "pc", admin: true },
  { chave: "agentes", nome: "Agentes do Smith", icone: "rede", admin: true },
  { chave: "gerencia", nome: "Gerência", icone: "cadeado" },
];
export const CHAVES = [...TELAS.filter((t) => t !== "separador").map((t) => t.chave), "urgencia", "enviados"];

export default function Capsula({ tela, irPara, contagem, admin, estado, tema, escolherTema, abrirAjuda, reler }) {
  const [menu, setMenu] = useState(false);
  const avatar = useRef(null);
  const agente = estado?.agente;
  return (
    <nav className="capsula vidro" aria-label="Navegação">
      <div className="capsula-selo" aria-hidden="true">NF</div>
      {TELAS.map((t, i) => {
        if (t === "separador") return <hr key={"s" + i} />;
        if (t.admin && !admin) return null;
        const n = t.numero ? contagem?.[t.numero] : 0;
        const atual = tela === t.chave || (t.tambem || []).includes(tela);
        return (
          <button key={t.chave} type="button" className="capsula-botao" title={t.nome}
            aria-label={t.nome} aria-current={atual ? "page" : undefined} onClick={() => irPara(t.chave)}>
            <Icone nome={t.icone} tamanho={19} />
            {n > 0 && <span className="capsula-numero">{n > 99 ? "99+" : n}</span>}
          </button>
        );
      })}
      <span className="capsula-mola" />
      <button ref={avatar} type="button" className="capsula-avatar" aria-haspopup="dialog" aria-expanded={menu}
        title={`Quem está neste PC: ${agente || "…"} (operador, tema, tamanho da tela)`} aria-label={`Quem está neste PC: ${agente || "…"}`} onClick={() => setMenu(!menu)}>
        {iniciais(agente, estado?.operadores || [])}
      </button>
      {menu && <MenuOperador estado={estado} tema={tema} escolherTema={escolherTema} aoFechar={() => setMenu(false)} abrirAjuda={abrirAjuda} ancora={avatar.current} reler={reler} />}
    </nav>
  );
}
