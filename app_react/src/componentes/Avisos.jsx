// Os avisos do Painel inteiro, numa peça só:
//   recado("Marcado como lido")            → aviso curto embaixo, some sozinho (erro fica vermelho e dura mais)
//   desfazer("E-mail excluído", volta, vai) → barra com contagem de 10 s e o botão Desfazer; só depois dela o pedido sai daqui
// Qualquer tela usa: const { recado, desfazer } = useAvisos();
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import Icone from "./Icone.jsx";
import "./Avisos.css";

const Contexto = createContext({ recado: () => {}, desfazer: () => {} });
export const useAvisos = () => useContext(Contexto);

const SEGUNDOS_DESFAZER = 10;

export function AvisosProvider({ children }) {
  const [recados, setRecados] = useState([]);
  const [barra, setBarra] = useState(null);   // { msg, s, desfeito }
  const pendente = useRef(null);               // { volta, vai, desfeito, timer, tique }
  const seq = useRef(0);

  const recado = useCallback((texto, erro = false) => {
    if (!texto) return;
    const id = ++seq.current;
    setRecados((l) => [...l.slice(-2), { id, texto, erro }]);
    setTimeout(() => setRecados((l) => l.filter((r) => r.id !== id)), erro ? 7000 : 3500);
  }, []);

  const confirmarPendente = useCallback(() => {
    const p = pendente.current;
    if (!p) return;
    clearTimeout(p.timer); clearInterval(p.tique);
    pendente.current = null;
    setBarra(null);
    p.vai();
  }, []);

  const desfazer = useCallback((msg, volta, vai, desfeito = "Desfeito") => {
    confirmarPendente();   // só uma de cada vez: a anterior segue o caminho dela
    let s = SEGUNDOS_DESFAZER;
    setBarra({ msg, s });
    const tique = setInterval(() => { s -= 1; if (s > 0) setBarra({ msg, s }); }, 1000);
    const timer = setTimeout(confirmarPendente, SEGUNDOS_DESFAZER * 1000);
    pendente.current = { volta, vai, desfeito, timer, tique };
  }, [confirmarPendente]);

  const voltar = () => {
    const p = pendente.current;
    if (!p) return;
    clearTimeout(p.timer); clearInterval(p.tique);
    pendente.current = null;
    setBarra(null);
    p.volta();
    recado(p.desfeito);
  };
  useEffect(() => () => confirmarPendente(), [confirmarPendente]);   // a tela fechou: o que estava esperando segue

  return (
    <Contexto.Provider value={{ recado, desfazer }}>
      {children}
      <div className="avisos-canto" aria-live="polite">
        {barra && (
          <div className="aviso-desfazer" role="status">
            <span>{barra.msg} · {barra.s}s</span>
            <button type="button" onClick={voltar}><Icone nome="voltar" tamanho={15} />Desfazer</button>
          </div>
        )}
        {recados.map((r) => (
          <div key={r.id} className={`aviso-curto${r.erro ? " erro" : ""}`} role={r.erro ? "alert" : "status"}>
            <Icone nome={r.erro ? "alerta" : "check"} tamanho={16} /><span>{r.texto}</span>
          </div>
        ))}
      </div>
    </Contexto.Provider>
  );
}
