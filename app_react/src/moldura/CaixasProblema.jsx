// Caixas com problema (27/10/2026, desenho aprovado pelo João): só existe enquanto algum PC está com o Outlook sem enviar/receber.
// O clique abre o quadro com o que o Painel sabe (e-mails presos por caixa, o motivo) e "Reiniciar o Outlook de X" (fecha à força e
// abre de novo, o que o João fazia à mão), sempre com confirmação. Fechar o quadro não some com o botão.
import { useEffect, useState } from "react";
import Icone from "../componentes/Icone.jsx";
import Botao from "../componentes/Botao.jsx";
import Janela from "../componentes/Janela.jsx";
import { api, acaoLonga } from "../api.js";
import { aj } from "../ajustes.js";

export default function CaixasProblema({ saude, soVer }) {
  const pcsComProblema = [...new Set((saude || []).filter((a) => a.tipo === "caixa" && a.pc).map((a) => a.pc))];
  const [aberto, setAberto] = useState(false);
  const [dados, setDados] = useState(null);
  const [st, setSt] = useState({});   // pc -> { fase: "conf" | "andando" | "res", ok, texto }

  const buscar = () => api("/api/caixas").then((d) => setDados(d)).catch(() => {});
  useEffect(() => {   // aberto: pergunta aos PCs e repete de tempos em tempos
    if (!aberto) return undefined;
    buscar();
    const t = setInterval(buscar, aj("tela.caixas_atualiza_segundos", 15) * 1000);
    return () => clearInterval(t);
  }, [aberto]);
  useEffect(() => { if (!pcsComProblema.length) { setAberto(false); setSt({}); } }, [pcsComProblema.length]);
  if (!pcsComProblema.length) return null;

  const reiniciar = async (p) => {
    setSt((s) => ({ ...s, [p.pc]: { fase: "andando" } }));
    const longa = acaoLonga(`Reiniciando o Outlook de ${p.agente}`, { limiteMs: 0 });
    let r;
    try { r = await api("/api/outlook/reiniciar", { pc: p.pc }); } catch { r = { erro: "o Painel deste PC não respondeu" }; }
    const ok = !!r.ok && !r.erro;
    longa.fim(ok, r.erro || "");
    setSt((s) => ({ ...s, [p.pc]: { fase: "res", ok, aviso: ok && (r.presos || r.aviso),
      texto: ok ? (r.presos ? `Abriu, mas ainda há ${r.presos} e-mail(s) preso(s) em ${p.agente}. Veja se alguma janela do Outlook pede senha.`
        : `Voltou: o Outlook de ${p.agente} abriu${r.saiu ? ` e ${r.saiu} e-mail(s) saíram` : ""}. O botão some quando o Painel confirmar.`)
        : `${r.erro || "Não deu certo"}. Pode precisar de alguém no PC de ${p.agente}.` } }));
    buscar();
  };
  const pcs = (dados?.pcs || []).filter((p) => pcsComProblema.includes(p.pc) || st[p.pc]);

  return (
    <>
      <button type="button" className="botao-redondo caixas-bt" title="Caixas que não enviam ou não recebem" aria-label={`Caixas com problema: ${pcsComProblema.length}`} onClick={() => setAberto(true)}>
        <Icone nome="caixa" tamanho={18} /><span className="caixas-n">{pcsComProblema.length}</span>
      </button>
      {aberto && (
        <Janela titulo="Caixas com problema" sub="Fechar só guarda este quadro: o botão fica na tela enquanto houver caixa com problema." aoFechar={() => setAberto(false)} largura={520}>
          {!dados ? <p>Perguntando aos PCs…</p> : !pcs.length ? <p>Nenhuma caixa com problema agora.</p> : pcs.map((p) => {
            const s = st[p.pc] || {};
            return (
              <section key={p.pc} className="cp-pc">
                <h4>{p.agente}</h4>
                {(p.caixas || []).map((c) => <div key={c.caixa} className="cp-lin"><Icone nome="alerta" tamanho={15} /><div><b>{c.caixa}</b><small>{c.presos} e-mail{c.presos > 1 ? "s" : ""} preso{c.presos > 1 ? "s" : ""} na Caixa de Saída</small></div></div>)}
                {(p.textos || []).map((t) => <div key={t} className="cp-lin ambar"><Icone nome="alerta" tamanho={15} /><small>{t}</small></div>)}
                {p.erro && <div className="cp-lin ambar"><Icone nome="alerta" tamanho={15} /><small>Não consegui ler as caixas deste PC: {p.erro}</small></div>}
                {s.fase === "andando" && <p className="cp-res">Reiniciando o Outlook de {p.agente}…</p>}
                {s.fase === "res" && <p className={`cp-res ${s.ok ? (s.aviso ? "ambar" : "ok") : "erro"}`}>{s.texto}</p>}
                {s.fase === "conf" ? (
                  <div className="cp-conf">Isso <b>fecha o Outlook de {p.agente} de vez</b> e abre de novo (uns 30 s). Rascunhos abertos lá o Outlook costuma guardar sozinho. Continuar?
                    <div className="cp-acao"><Botao tipo="perigo" pequeno onClick={() => reiniciar(p)}>Sim, reiniciar</Botao><Botao pequeno onClick={() => setSt((x) => ({ ...x, [p.pc]: {} }))}>Cancelar</Botao></div></div>
                ) : s.fase !== "andando" && (
                  <div className="cp-acao"><Botao pequeno icone="atualizar" desligado={soVer} titulo={soVer ? "Este PC só visualiza" : undefined} onClick={() => setSt((x) => ({ ...x, [p.pc]: { fase: "conf" } }))}>Reiniciar o Outlook de {p.agente}</Botao></div>
                )}
              </section>
            );
          })}
        </Janela>
      )}
    </>
  );
}
