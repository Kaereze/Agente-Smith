// Monitoramento: os PCs da equipe em cartões. Sem commit nem número de versão: diz em palavras se está no ar,
// o que está fazendo, se está na mesma versão e o que fez por último. Só o administrador vê.
import { useState } from "react";
import Icone from "../componentes/Icone.jsx";
import Botao from "../componentes/Botao.jsx";
import Etiqueta from "../componentes/Etiqueta.jsx";
import { Barra } from "../componentes/Graficos.jsx";
import { useLigado } from "../componentes/Conta.jsx";
import { CabecalhoTela, Bolinha } from "../componentes/Bloco.jsx";
import useAtividade from "../dados/useAtividade.js";
import { api } from "../api.js";
import "./Monitoramento.css";

const hora = (t) => String(t || "").replace("T", " ").slice(11, 16);
function usoEmPalavras(uso, online) {
  if (!online) return { texto: "PC desligado", tipo: "cinza" };
  const [estado, tela] = String(uso || "").split("|");
  if (estado === "aberto") return { texto: `Painel aberto agora${tela ? ` · em ${tela}` : ""}`, tipo: "verde" };
  return { texto: "Painel fechado · o robô segue trabalhando", tipo: "cinza" };
}

export default function Monitoramento({ estado }) {
  const { atividade } = useAtividade();
  const ligado = useLigado();
  const [recado, setRecado] = useState("");
  const pcs = atividade?.pcs || estado?.pcs || [];
  const caixaPcs = estado?.caixa_pcs || {};
  const versaoAqui = atividade?.versao || "";
  const eventos = atividade?.eventos || [];
  const noAr = pcs.filter((p) => p.online);
  const desligados = pcs.filter((p) => !p.online).map((p) => p.agente || p.pc);
  const todosIguais = pcs.filter((p) => p.online).every((p) => !versaoAqui || p.versao === versaoAqui);
  const maxEmails = Math.max(1, ...Object.values(caixaPcs).map((c) => c.emails || 0));
  const soVer = !!estado?.so_ver;

  const atualizar = async (para, nome) => {
    setRecado(`Pedindo ${para === "TODOS" ? "a todos os PCs" : `ao PC de ${nome}`} para atualizar…`);
    const j = await api("/api/comando", { para, comando: "atualizar" });
    setRecado(j.ok === false ? (j.motivo || j.erro || "Não deu para pedir agora.") : "Pedido entregue. Cada PC puxa a versão nova e reinicia sozinho.");
  };

  return (
    <main className="principal vidro">
      <CabecalhoTela icone="pc" titulo="Monitoramento" explica="Os PCs da equipe · atualiza sozinho a cada 20 s · só o administrador vê">
        <Botao tipo="principal" icone="atualizar" desligado={soVer} titulo={soVer ? "Este PC só visualiza" : "Cada PC puxa a versão nova do GitHub e reinicia"}
          onClick={() => atualizar("TODOS")}>Atualizar todos os PCs</Botao>
      </CabecalhoTela>
      {recado && <p className="robo-recado" role="status">{recado}</p>}

      <section className="mon-resumo vidro entra">
        <Bolinha icone={desligados.length ? "alerta" : "check"} tipo={desligados.length ? "ambar" : "verde"} tamanho={44} />
        <div className="mon-resumo-texto">
          <b>{noAr.length} de {pcs.length} PCs no ar</b>
          <span>{desligados.length ? `Desligado: ${desligados.join(", ")}. ` : "Todos ligados. "}{todosIguais ? "Os PCs ligados estão na mesma versão." : "Há PC com versão diferente: use Atualizar."}</span>
        </div>
        <div className="mon-selos">
          <Etiqueta tipo={todosIguais ? "verde" : "ambar"} icone={todosIguais ? "check" : "alerta"}>{todosIguais ? "Mesma versão" : "Versões diferentes"}</Etiqueta>
          <Etiqueta tipo="azul" icone="nuvem">Central {estado?.erro ? "com aviso" : "conectada"}</Etiqueta>
        </div>
      </section>

      <div className="mon-cartoes">
        {pcs.map((p, i) => {
          const uso = usoEmPalavras(p.uso, p.online);
          const emails = caixaPcs[p.pc]?.emails ?? 0;
          const ultimos = eventos.filter((ev) => ev.pc === p.pc).slice(0, 3);
          const mesma = !versaoAqui || p.versao === versaoAqui;
          return (
            <article key={p.pc} className={`mon-cartao vidro entra${p.online ? "" : " fora"}`} style={{ "--i": i + 1 }}>
              <div className="mon-topo">
                <span className="capsula-avatar grande">{(p.agente || p.pc || "?").slice(0, 1)}</span>
                <div><b>{p.agente || p.pc}</b>
                  <span className="mon-selos-pc">
                    <Etiqueta tipo={p.online ? "verde" : "cinza"}>{p.online ? `No ar · visto ${hora(p.visto) || "agora"}` : `Desligado · visto ${hora(p.visto) || "—"}`}</Etiqueta>
                    <Etiqueta tipo="cinza">{p.papel === "principal" ? "PC principal: envia os pedidos" : "Confere as NF"}</Etiqueta>
                  </span></div>
              </div>
              <div className={`mon-uso ${uso.tipo}`}><Icone nome="pc" tamanho={16} />{uso.texto}</div>
              <div className="mon-numeros">
                <div><b>{p.caixas ?? "—"}</b><small>caixas de hotel</small></div>
                <div><b>{emails}</b><small>e-mails na caixa</small></div>
              </div>
              <div className="mon-parte"><small>Parte dos e-mails da equipe</small><Barra parte={emails} todo={maxEmails} ligado={ligado} /></div>
              {p.conferencia_resumo && <div className="mon-conf"><Icone nome="check" tamanho={15} /><span>Última conferência {hora(p.conferencia)}: {p.conferencia_resumo}</span></div>}
              <div className="mon-ultimos">
                <small>O QUE FEZ POR ÚLTIMO</small>
                {ultimos.length ? ultimos.map((ev, k) => <div key={k}><span>{hora(ev.quando)}</span><span>{[ev.tipo, ev.hotel].filter(Boolean).join(" · ")}</span></div>)
                  : <span className="mon-nada">Nada registrado hoje.</span>}
              </div>
              <span style={{ flex: 1 }} />
              <div className={`mon-versao${mesma ? "" : " diferente"}`}><Icone nome={mesma ? "check" : "alerta"} tamanho={14} />{mesma ? "Mesma versão deste PC" : "Versão diferente: precisa atualizar"}</div>
              {p.online
                ? <Botao icone="atualizar" desligado={soVer} onClick={() => atualizar(p.pc, p.agente)}>Atualizar este PC</Botao>
                : <Botao icone="voltar" desligado titulo="Quando o PC ligar, ele aparece aqui sozinho">Esperando ligar</Botao>}
            </article>
          );
        })}
      </div>
    </main>
  );
}
