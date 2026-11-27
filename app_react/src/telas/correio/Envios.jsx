// Envio sem espera (Prévia 5, 20/10/2026): a mensagem sai da tela na hora e o Painel confere em silêncio a cada 5 s.
// Entregue, saindo ou enviado não mostram nada (João, 16/11/2026: "se já foi enviada, precisa sumir da minha tela").
// Só a FALHA aparece: pílula vermelha "Não enviou · Ver", que abre o motivo e o "Escrever de novo" (volta o texto que estava escrito).
import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { api } from "../../api.js";
import Icone from "../../componentes/Icone.jsx";
import "./Envios.css";

const Contexto = createContext({ seguir: () => {}, reabrir: null, limparReabrir: () => {} });
export const useEnvios = () => useContext(Contexto);

export function EnviosProvider({ children, irPara }) {
  const [falhas, setFalhas] = useState([]);   // [{ id, ctx, detalhe, aberto }]
  const [reabrir, setReabrir] = useState(null);
  const timers = useRef({});

  const ver = useCallback(async (id, ctx) => {
    const s = await api(`/api/envio_nf/status?id=${encodeURIComponent(id)}`).catch(() => ({ estado: "aguardando" }));
    if (s.estado === "enviado") { delete timers.current[id]; ctx.aoEnviado?.(); return; }
    if (s.estado === "falhou" || s.estado === "sem_resposta") {
      delete timers.current[id];
      setFalhas((l) => [...l.filter((f) => f.id !== id), { id, ctx, detalhe: s.detalhe || "o PC dono não respondeu", aberto: false }]);
      return;
    }
    timers.current[id] = setTimeout(() => ver(id, ctx), 5000);
  }, []);
  const seguir = useCallback((id, ctx) => { if (id) ver(id, ctx); }, [ver]);
  useEffect(() => () => Object.values(timers.current).forEach(clearTimeout), []);

  const fechar = (id) => setFalhas((l) => l.filter((f) => f.id !== id));
  const escreverDeNovo = (f) => { fechar(f.id); setReabrir(f.ctx); irPara?.("correio"); };

  return (
    <Contexto.Provider value={{ seguir, reabrir, limparReabrir: () => setReabrir(null) }}>
      {children}
      <div className="envios-canto" aria-live="polite">
        {falhas.map((f) => f.aberto ? (
          <div key={f.id} className="envio-cartao vidro" role="alert">
            <b><i>!</i>Não deu para enviar {f.ctx.oque || "a mensagem"}</b>
            <p>{f.detalhe}</p>
            <div><button type="button" onClick={() => fechar(f.id)}>Fechar</button>
              <button type="button" className="forte" onClick={() => escreverDeNovo(f)}><Icone nome="novo" tamanho={14} />Escrever de novo</button></div>
          </div>
        ) : (
          <button key={f.id} type="button" className="envio-pilula" onClick={() => setFalhas((l) => l.map((x) => (x.id === f.id ? { ...x, aberto: true } : x)))}
            aria-label={`Não enviou ${f.ctx.oque || "a mensagem"}. Ver o motivo`}><i>!</i>Não enviou <u>Ver</u></button>
        ))}
      </div>
    </Contexto.Provider>
  );
}
