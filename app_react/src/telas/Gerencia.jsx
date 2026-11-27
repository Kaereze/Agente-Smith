// Gerência: o relatório do mês (ou da semana) que o gerente lê em 1 minuto. Números do Mail Analytics (só leitura)
// e do Painel; cada número diz contra o quê compara. Mesmo endpoint da tela de hoje: /api/relatorio_semana.
import { useEffect, useState } from "react";
import Icone from "../componentes/Icone.jsx";
import Botao from "../componentes/Botao.jsx";
import Conta, { useLigado } from "../componentes/Conta.jsx";
import { Barra } from "../componentes/Graficos.jsx";
import { CabecalhoTela, Pergunta, ComoLer, AbasPilula } from "../componentes/Bloco.jsx";
import { api } from "../api.js";
import "./Gerencia.css";

const METRICAS = [["pedidos", "Pedidos pelo formulário"], ["recebidos", "E-mails recebidos"], ["enviados", "E-mails enviados"],
                  ["nfs", "NF emitidas"], ["subst_canc", "Substituídas ou canceladas"], ["ligacoes", "Ligações"]];
const dataBR = (d) => (d ? `${d.slice(8, 10)}/${d.slice(5, 7)}` : "");

function variacao(agora, antes) {
  if (!antes) return null;
  const d = agora - antes;
  return { texto: d === 0 ? "igual" : `${d > 0 ? "+" : "−"}${Math.abs(d)} (${Math.round((Math.abs(d) / antes) * 100)}%)`, sobe: d > 0 };
}

export default function Gerencia() {
  const [tipo, setTipo] = useState("mes");
  const [desl, setDesl] = useState(0);
  const [rel, setRel] = useState(null);
  const [copiado, setCopiado] = useState(false);
  const ligado = useLigado();
  useEffect(() => {
    let vivo = true;
    setRel(null);
    api(`/api/relatorio_semana?tipo=${tipo}&deslocamento=${desl}`).then((j) => { if (vivo) setRel(j); });
    return () => { vivo = false; };
  }, [tipo, desl]);

  const copiar = async () => {
    try { await navigator.clipboard.writeText(rel?.texto || ""); setCopiado(true); setTimeout(() => setCopiado(false), 2000); } catch { setCopiado(false); }
  };
  const total = rel?.total || {}, antes = rel?.total_anterior || {};
  const agentes = Object.entries(rel?.por_agente || {}).map(([nome, v]) => ({ nome, ...v })).sort((a, b) => (b.pedidos || 0) - (a.pedidos || 0));
  const hoteis = (rel?.hoteis || []).slice(0, 8);
  const maxHotel = Math.max(1, ...hoteis.map((h) => h.recebidos || 0));
  const nomePeriodo = tipo === "mes" ? "mês" : "semana";

  return (
    <main className="principal vidro">
      <CabecalhoTela icone="cadeado" titulo="Gerência" explica="O relatório para o gerente: números do Mail Analytics (só leitura) e do Painel">
        <AbasPilula rotulo="Período" valor={tipo} aoEscolher={(v) => { setTipo(v); setDesl(0); }} opcoes={[["mes", "Mês"], ["semana", "Semana"]]} />
        <button type="button" className="botao-redondo" style={{ width: 40, height: 40 }} aria-label={`${nomePeriodo} anterior`} title={`${nomePeriodo} anterior`} onClick={() => setDesl(desl - 1)}><Icone nome="esquerda" /></button>
        <button type="button" className="botao-redondo" style={{ width: 40, height: 40 }} aria-label={`Próximo ${nomePeriodo}`} title={`Próximo ${nomePeriodo}`} disabled={desl >= 0} onClick={() => setDesl(desl + 1)}><Icone nome="direita" /></button>
        <Botao icone="livro" onClick={copiar} desligado={!rel?.texto}>{copiado ? "Copiado" : "Copiar o texto"}</Botao>
      </CabecalhoTela>

      {!rel && <section className="bloco vidro">Lendo o relatório…</section>}
      {rel?.erro && <section className="bloco vidro"><p className="resposta">{rel.erro}</p></section>}
      {rel && !rel.erro && (
        <div className="ger-grade">
          <section className="bloco vidro entra ger-numeros-bloco">
            <Pergunta assunto={`${dataBR(rel.ini)} a ${dataBR(rel.ate || rel.fim)}`}>Como foi o {nomePeriodo}, comparado com o anterior?</Pergunta>
            <div className="ger-numeros">
              {METRICAS.map(([k, nome]) => {
                const v = variacao(total[k] || 0, antes[k] || 0);
                return (
                  <div key={k} className="ger-numero">
                    <small>{nome}</small><b><Conta valor={total[k] || 0} /></b>
                    <span className="ger-var">{v ? `${v.texto} contra ${dataBR(rel.ini_anterior)} a ${dataBR(rel.fim_anterior)}` : "sem período anterior para comparar"}</span>
                  </div>
                );
              })}
            </div>
            <ComoLer>O período anterior é cortado no mesmo dia (ex.: 1 a 27 deste mês contra 1 a 27 do mês passado), para a comparação ser justa.</ComoLer>
          </section>

          <section className="bloco vidro entra" style={{ "--i": 1 }}>
            <Pergunta assunto="Equipe">Quanto cada agente fez?</Pergunta>
            {agentes.length === 0 && <p className="resposta">Ainda não há números por agente neste período.</p>}
            <div className="ger-agentes">
              {agentes.map((a) => (
                <div key={a.nome} className="ger-agente">
                  <span className="capsula-avatar">{a.nome.slice(0, 1)}</span>
                  <b>{a.nome}</b>
                  <span>{a.pedidos || 0} pedidos · {a.nfs || 0} NF · {a.enviados || 0} e-mails enviados</span>
                </div>
              ))}
            </div>
          </section>

          <section className="bloco vidro entra" style={{ "--i": 2 }}>
            <Pergunta assunto="Hotéis">Quais hotéis mais receberam e-mails de NF?</Pergunta>
            {hoteis.length === 0 && <p className="resposta">Ainda não há números por hotel neste período.</p>}
            {hoteis.length > 0 && <ComoLer>Cada barra são os e-mails que chegaram ao hotel no período (Mail Analytics). Passe o mouse no número para ver as NF emitidas.</ComoLer>}
            {hoteis.map((h, i) => {
              return <div key={h.hotel + i} className="ger-hotel"><span>{h.hotel}</span><Barra parte={h.recebidos || 0} todo={maxHotel} ligado={ligado} /><b title={`${h.nfs || 0} NF emitidas`}>{h.recebidos || 0}</b></div>;
            })}
          </section>
        </div>
      )}
    </main>
  );
}
