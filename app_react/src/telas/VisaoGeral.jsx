// Visão geral: o resumo do dia em perguntas, com a resposta escrita antes de cada gráfico e um "como ler".
// Todos os números vêm do Painel (resumo.js); nada é inventado.
import Icone from "../componentes/Icone.jsx";
import { Pergunta, ComoLer } from "../componentes/Bloco.jsx";
import Botao from "../componentes/Botao.jsx";
import Conta, { useLigado } from "../componentes/Conta.jsx";
import { GraficoLinhas, Rosca, Barra, Anel } from "../componentes/Graficos.jsx";
import { comparaOntem, porcento } from "../dados/resumo.js";
import { abrirNaTelaDeHoje } from "../api.js";
import "./VisaoGeral.css";

function Numero({ rotulo, valor, comparacao, explica, ruim }) {
  return (
    <div className="numero">
      <span className="numero-rotulo">{rotulo}</span>
      <span className={`numero-valor${ruim ? " ruim" : ""}`}><Conta valor={valor} /></span>
      {comparacao && <span className={`variacao ${comparacao.bom ? "bom" : "ruim"}`}>{comparacao.texto}</span>}
      <span className="numero-explica">{explica}</span>
    </div>
  );
}

function saudacao(agora) {
  const h = agora.getHours();
  return h < 12 ? "Bom dia" : h < 18 ? "Boa tarde" : "Boa noite";
}

export default function VisaoGeral({ r, agente, irPara }) {
  const ligado = useLigado();
  if (!r) return <main className="principal vidro carregando">Lendo os dados dos 4 PCs…</main>;
  const agora = new Date();
  const hora = agora.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  const tudoBem = r.robo.ligado !== false && r.pcsLigados === r.pcs.length;
  const maiorMotivo = [...r.porMotivo].sort((a, b) => b.total - a.total)[0];
  const doisPrimeiros = r.agentes.slice(0, 2);
  const pctDois = porcento(doisPrimeiros.reduce((s, a) => s + a.emails, 0), r.totalAgentes);
  const chegaram8 = r.porDia.reduce((s, d) => s + d.pedidos, 0);
  const pctPcs = porcento(r.pcsLigados, r.pcs.length);
  const desligados = r.pcs.filter((p) => !p.online).map((p) => p.agente);

  return (
    <main className="principal vidro">
      <div className="titulo">
        <h2>{saudacao(agora)}, {agente || "equipe"}</h2>
        <p>Este é o resumo do setor fiscal hoje, até as {hora}. Cada bloco responde a uma pergunta. Os números juntam os e-mails dos 4 PCs.</p>
      </div>
      <div className="painel-grade">
        <section className="resumo vidro entra" aria-label="Hoje em uma frase">
          <span className={`estado-geral${tudoBem ? "" : " atencao"}`}>
            <Icone nome={tudoBem ? "check" : "alerta"} tamanho={15} />
            {tudoBem ? "Tudo funcionando: robô ligado e todos os PCs conectados" : `Atenção: ${desligados.length ? `PC de ${desligados.join(", ")} desligado` : "o robô está pausado"}`}
          </span>
          <p className="frase">
            Hoje chegaram <b>{r.pedidosHoje} pedidos de NF</b> e a equipe já enviou <b>{r.nfHoje} notas</b>. Ainda há <b>{r.abertos} pedidos esperando</b>
            {r.semResposta > 0 ? <>, e <b>{r.semResposta} hóspedes estão sem resposta há mais de 2 dias</b>: comece por eles.</> : ". Nenhum hóspede está sem resposta há mais de 2 dias."}
          </p>
          <div className="numeros">
            <Numero rotulo="Pedidos que chegaram hoje" valor={r.pedidosHoje} comparacao={comparaOntem(r.pedidosHoje, r.pedidosOntem, false)} explica="pelos formulários dos hotéis" />
            <Numero rotulo="NF enviadas hoje" valor={r.nfHoje} comparacao={comparaOntem(r.nfHoje, r.nfOntem, true)} explica="e-mails com o PDF da nota" />
            <Numero rotulo="Pedidos esperando" valor={r.abertos} explica="ainda sem a NF enviada" />
            <Numero rotulo="Sem resposta há mais de 2 dias" valor={r.semResposta} ruim={r.semResposta > 0} explica="o hóspede está esperando" />
          </div>
        </section>

        <section className="bloco b-largo vidro entra" style={{ "--i": 1 }}>
          <Pergunta assunto="Ritmo da semana">O que chegou nos últimos 8 dias úteis?</Pergunta>
          <p className="resposta">Chegaram <b>{chegaram8} pedidos</b> pelos formulários. Hoje: <b>{r.pedidosHoje}</b>.</p>
          <div className="legenda"><span><i style={{ background: "var(--verde)" }} />Pedidos dos formulários</span><span><i style={{ background: "var(--linha-grafico)" }} />E-mails recebidos</span></div>
          <GraficoLinhas ligado={ligado} dias={r.porDia.map((d) => d.dia)}
            series={[{ nome: "Pedidos dos formulários", cor: "var(--verde)", valores: r.porDia.map((d) => d.pedidos) },
                     { nome: "E-mails recebidos", cor: "var(--linha-grafico)", valores: r.porDia.map((d) => d.emails) }]} />
          <ComoLer>Cada ponto é um dia. A linha verde são os pedidos que chegaram pelos formulários; a outra, os e-mails que chegaram às caixas dos hotéis.</ComoLer>
        </section>

        <section className="bloco b-estreito vidro entra" style={{ "--i": 2 }}>
          <Pergunta assunto="Pedidos esperando">Por que os {r.abertos} pedidos ainda estão em aberto?</Pergunta>
          <p className="resposta">{r.abertos ? <>A maioria (<b>{porcento(maiorMotivo.total, r.abertos)}%</b>) está em “{maiorMotivo.nome}”.</> : "Nenhum pedido em aberto."}</p>
          <div className="rosca-e-lista">
            <Rosca partes={r.porMotivo} ligado={ligado} rotulo="em aberto" />
            <ul className="partes">
              {r.porMotivo.map((m) => (
                <li key={m.chave}><i style={{ background: m.cor }} /><span><b>{m.nome}</b><small>{m.explica}</small></span><span className="partes-n">{m.total} · {porcento(m.total, r.abertos)}%</span></li>
              ))}
            </ul>
          </div>
          <ComoLer>O círculo inteiro são os pedidos em aberto. Cada cor é um motivo; quanto maior a fatia, mais pedidos param ali.</ComoLer>
        </section>

        <section className="bloco b-meio vidro entra" style={{ "--i": 3 }}>
          <Pergunta assunto="Equipe">Com quem estão os e-mails da caixa de entrada?</Pergunta>
          <p className="resposta">{doisPrimeiros.map((a) => a.nome).join(" e ")} cuidam de <b>{pctDois}%</b> dos e-mails agora.</p>
          <div className="barras">
            {r.agentes.map((a) => (
              <div className="barra-linha" key={a.nome}>
                <div className="barra-texto"><b>{a.nome}</b><span>{a.emails} e-mails · {porcento(a.emails, r.totalAgentes)}% do total · <span className={a.ligado ? "pc-ok" : "pc-fora"}>{a.ligado ? "PC ligado" : "PC desligado"}</span></span></div>
                <Barra parte={a.emails} todo={r.agentes[0]?.emails || 1} ligado={ligado} />
              </div>
            ))}
          </div>
          <ComoLer>Cada barra é a caixa de entrada de uma pessoa. A barra cheia é quem tem mais e-mails.</ComoLer>
        </section>

        <section className="bloco b-meio vidro entra" style={{ "--i": 4 }}>
          <Pergunta assunto="Robô e PCs">O sistema está funcionando?</Pergunta>
          <div className="anel-e-fatos">
            <Anel porcento={pctPcs} ligado={ligado} rotulo="PCs ligados" />
            <ul className="fatos">
              <li><Icone nome="pc" tamanho={16} /><span><b>{r.pcsLigados} de {r.pcs.length} PCs</b> ligados e conectados{desligados.length ? ` (desligado: ${desligados.join(", ")})` : ""}.</span></li>
              <li><Icone nome="robo" tamanho={16} /><span>Robô <b>{r.robo.ligado === false ? "pausado" : "ligado"}</b>{r.robo.ultima_execucao ? `, última rodada ${r.robo.ultima_execucao}` : ""}.</span></li>
              <li><Icone nome="enviar" tamanho={16} /><span><b>{r.paraHotel} pedidos</b> esperando para ir ao hotel.</span></li>
            </ul>
          </div>
          <ComoLer>O anel mostra quantos dos PCs da equipe estão ligados agora. Cheio quer dizer todos.</ComoLer>
        </section>

        <section className="bloco vidro entra" style={{ "--i": 5 }}>
          <Pergunta assunto="Agora">O que precisa de atenção agora?</Pergunta>
          <div className="lista-atencao">
            <div className="atencao-item"><span className="bolinha vermelha"><Icone nome="alerta" /></span>
              <div><b>{r.semResposta} hóspedes sem resposta há mais de 2 dias</b><small>{r.maisAntigo ? `O mais antigo: ${r.maisAntigo.nome || r.maisAntigo.de}, há ${Math.floor(r.maisAntigo.dias)} dias (${r.maisAntigo.hotel}).` : "Ninguém esperando."}</small></div>
              <Botao tipo="principal" onClick={() => irPara("correio")}>Ver os e-mails</Botao></div>
            <div className="atencao-item"><span className="bolinha ambar"><Icone nome="nota" /></span>
              <div><b>{r.prontas} NF prontas, falta só enviar</b><small>A nota existe; é só mandar o e-mail com o PDF ao hóspede.</small></div>
              <Botao onClick={() => irPara("correio")}>Ver na caixa</Botao></div>
            <div className="atencao-item"><span className="bolinha azul"><Icone nome="robo" /></span>
              <div><b>{r.paraHotel} pedidos ainda não foram para o hotel</b><small>O robô manda aos hotéis a cada rodada. Dá para mandar agora.</small></div>
              <Botao icone="enviar" onClick={() => abrirNaTelaDeHoje("")}>Enviar pendentes</Botao></div>
          </div>
        </section>
      </div>
    </main>
  );
}
