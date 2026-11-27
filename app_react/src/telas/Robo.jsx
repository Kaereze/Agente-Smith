// Robô: o que ele está fazendo (Agora) e o que aconteceu (Registro). Só dados reais (/api/estado, /api/correio, /api/atividade).
import { useState } from "react";
import Icone from "../componentes/Icone.jsx";
import Botao from "../componentes/Botao.jsx";
import Conta from "../componentes/Conta.jsx";
import Etiqueta from "../componentes/Etiqueta.jsx";
import { CabecalhoTela, Pergunta, ComoLer, Bolinha, AbasPilula } from "../componentes/Bloco.jsx";
import useAtividade from "../dados/useAtividade.js";
import { enviarPendentes } from "../dados/acoes.js";
import "./Robo.css";

// "11/27/2026 01:15:13" (planilha do formulário) -> Date
export function quandoDoCarimbo(c) {
  const m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})\s+(\d{1,2}):(\d{2})/.exec(c || "");
  return m ? new Date(+m[3], +m[1] - 1, +m[2], +m[4], +m[5]) : null;
}
const horaCurta = (d) => (d ? d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "—");

function Etapas({ p }) {   // 4 etapas: recebido · enviado ao hotel · NF emitida · NF enviada ao hóspede
  const feitas = [true, !!p.enviado, (p.nfs || []).length > 0, p.situacao === "concluida" && !p.envio_pendente];
  const proxima = feitas.indexOf(false);
  return (
    <span className="etapas" role="img" aria-label={`${feitas.filter(Boolean).length} de 4 etapas feitas`}>
      {feitas.map((f, i) => <i key={i} className={f ? "feita" : i === proxima ? "agora" : ""} />)}
    </span>
  );
}

function Agora({ estado, r, soVer }) {
  const [enviando, setEnviando] = useState("");
  const status = estado.status || {};
  const agora = new Date();
  const fila = (estado.fila || []).filter((p) => !p.enviado).map((p) => ({ ...p, quando: quandoDoCarimbo(p.carimbo) }))
    .sort((a, b) => (a.quando || 0) - (b.quando || 0));
  const atrasados = fila.filter((p) => p.quando && agora - p.quando > 2 * 3600 * 1000);
  const porHotel = Object.entries(atrasados.reduce((m, p) => ({ ...m, [p.hotel]: (m[p.hotel] || 0) + 1 }), {}))
    .sort((a, b) => b[1] - a[1]).slice(0, 4).map(([h, n]) => `${h} (${n})`).join(", ");
  const enviarAgora = async () => {
    setEnviando("Pedindo ao robô…");
    setEnviando((await enviarPendentes()).texto);
  };
  return (
    <>
      {atrasados.length > 0 && (
        <section className="faixa-alerta vidro entra">
          <Bolinha icone="alerta" tipo="vermelha" />
          <div><b>{atrasados.length} pedidos estão sem envio ao hotel há mais de 2 h</b><small>{porHotel}{atrasados.length > 4 ? "…" : ""}. Confira se o robô está ligado.</small></div>
          <Botao tipo="principal" icone="enviar" desligado={soVer} titulo={soVer ? "Este PC só visualiza" : "Pede ao robô para enviar agora"} onClick={enviarAgora}>Enviar agora</Botao>
        </section>
      )}
      {enviando && <p className="robo-recado" role="status">{enviando}</p>}
      <div className="robo-grade">
        <section className="bloco vidro entra" style={{ "--i": 1 }}>
          <Pergunta assunto="Fila">O que está esperando para ir ao hotel?</Pergunta>
          <p className="resposta"><b>{fila.length} pedidos</b> ainda não foram para a caixa do hotel.</p>
          <ComoLer>Cada pedido tem 4 etapas: recebido, enviado ao hotel, NF emitida e NF enviada ao hóspede. Verde = feita · azul = a próxima · cinza = falta.</ComoLer>
          <div className="fila">
            {fila.slice(0, 9).map((p, i) => (
              <div className="fila-linha entra" style={{ "--i": i }} key={p.chave + p.linha}>
                <Bolinha icone="caixa" tamanho={34} />
                <span className="fila-texto"><b>{p.hotel}</b><small>{p.nome || p.email} · chegou às {horaCurta(p.quando)}</small></span>
                <Etapas p={p} />
              </div>
            ))}
            {fila.length === 0 && <p className="vazio-fila">Nada esperando: todos os pedidos já foram para os hotéis.</p>}
          </div>
          {fila.length > 9 && <span className="mais">E mais {fila.length - 9} pedidos.</span>}
        </section>
        <div className="robo-lado">
          <section className="bloco vidro entra" style={{ "--i": 2 }}>
            <Pergunta assunto="Hoje">Quanto saiu hoje?</Pergunta>
            <div className="dois-numeros">
              <div><small>Pedidos de hoje já no hotel</small><b><Conta valor={(estado.fila || []).filter((p) => p.enviado && p.data === r.hoje).length} /></b></div>
              <div><small>NF enviadas aos hóspedes</small><b className="verde"><Conta valor={r.nfHoje} /></b></div>
            </div>
          </section>
          <section className="bloco vidro entra" style={{ "--i": 3 }}>
            <Pergunta assunto="Rodadas">Quando o robô rodou?</Pergunta>
            <div className="fato-linha"><Bolinha icone="relogio" tipo="azul" tamanho={34} /><span><b>Última rodada</b><small>{status.ultima_execucao || "ainda não registrada"}</small></span></div>
            {status.resumo && <div className="fato-linha"><Bolinha icone="check" tamanho={34} /><span><b>O que fez</b><small>{status.resumo}</small></span></div>}
            {status.resposta && <div className="fato-linha"><Bolinha icone="robo" tipo="cinza" tamanho={34} /><span><b>Último recado do robô</b><small>{status.resposta}</small></span></div>}
          </section>
        </div>
      </div>
    </>
  );
}

const TIPOS_EVENTO = [["tudo", "Tudo"], ["entrada", "Entradas"], ["saida", "Saídas"], ["aviso", "Avisos e erros"]];
function tipoDoEvento(ev) {
  const t = `${ev.tipo || ""} ${ev.detalhe || ""}`.toLowerCase();
  if (/erro|falh|aviso|não /.test(t)) return "aviso";
  if (/enviad|envio|saiu|respond/.test(t)) return "saida";
  return "entrada";
}

function Registro() {
  const { atividade } = useAtividade();
  const [filtro, setFiltro] = useState("tudo");
  const [busca, setBusca] = useState("");
  const eventos = (atividade?.eventos || []).map((ev) => ({ ...ev, k: tipoDoEvento(ev) }));
  const vistos = eventos.filter((ev) => (filtro === "tudo" || ev.k === filtro) &&
    (!busca || JSON.stringify(ev).toLowerCase().includes(busca.toLowerCase())));
  const contar = (k) => (k === "tudo" ? eventos.length : eventos.filter((e) => e.k === k).length);
  const cor = { entrada: ["envelope", "azul"], saida: ["check", "verde"], aviso: ["alerta", "ambar"] };
  return (
    <section className="bloco vidro entra registro">
      <div className="registro-filtros">
        <AbasPilula rotulo="Mostrar" valor={filtro} aoEscolher={setFiltro} opcoes={TIPOS_EVENTO.map(([v, t]) => [v, `${t} ${contar(v)}`])} />
        <span style={{ flex: 1 }} />
        <label className="busca-pilula"><Icone nome="busca" tamanho={16} />
          <input type="search" value={busca} onChange={(e) => setBusca(e.target.value)} placeholder="Procurar hóspede ou hotel" aria-label="Procurar no registro" /></label>
      </div>
      <ComoLer>Tudo o que o robô e os PCs fizeram, do mais novo para o mais antigo. Azul = chegou · verde = saiu · âmbar = aviso ou erro.</ComoLer>
      <div className="registro-lista">
        {vistos.length === 0 && <p className="vazio-fila">{eventos.length ? "Nada com esse filtro." : "Ainda não há nada registrado hoje."}</p>}
        {vistos.slice(0, 60).map((ev, i) => (
          <div className="fila-linha" key={i}>
            <span className="registro-hora">{String(ev.quando || "").slice(11, 16)}</span>
            <Bolinha icone={cor[ev.k][0]} tipo={cor[ev.k][1]} tamanho={32} />
            <span className="fila-texto"><b>{[ev.tipo, ev.pedido].filter(Boolean).join(" · ")}</b><small>{[ev.hotel, ev.agente ? `PC de ${ev.agente}` : ev.pc, ev.detalhe].filter(Boolean).join(" · ")}</small></span>
          </div>
        ))}
      </div>
    </section>
  );
}

export default function Robo({ estado, r }) {
  const [aba, setAba] = useState("agora");
  if (!estado || !r) return <main className="principal vidro carregando">Lendo o robô…</main>;
  const ligado = estado.status?.ligado !== false;
  return (
    <main className="principal vidro">
      <CabecalhoTela icone="robo" titulo="Robô" explica="Copia os pedidos dos formulários e envia para a caixa de cada hotel.">
        <Etiqueta tipo={ligado ? "verde" : "ambar"} icone={ligado ? "check" : "alerta"}>{ligado ? "Ligado" : "Pausado"}</Etiqueta>
        <AbasPilula rotulo="Parte do robô" valor={aba} aoEscolher={setAba} opcoes={[["agora", "Agora"], ["registro", "Registro"]]} />
      </CabecalhoTela>
      {aba === "agora" ? <Agora estado={estado} r={r} soVer={!!estado.so_ver} /> : <Registro />}
    </main>
  );
}
