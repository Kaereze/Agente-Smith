// O topo em pílula. Na Visão geral: saudação + pesquisa + tema + avisos.
// Nos e-mails: as abas do Outlook (Página Inicial · Enviar/Receber · Exibir) + pesquisa + tema + avisos.
// A pesquisa procura nos e-mails dos 4 PCs (a partir de 3 letras); digitar em outra tela leva para os e-mails. Ctrl+K ou Ctrl+E chegam nela.
import { useState } from "react";
import Icone from "../componentes/Icone.jsx";
import { BotaoRedondo } from "../componentes/Botao.jsx";
import "./Moldura.css";

const ABAS = [["inicio", "Página Inicial"], ["enviar", "Enviar/Receber"], ["exibir", "Exibir"]];

export default function Topo({ modo, agente, tema, trocarTema, avisos, busca, setBusca, aba, setAba }) {
  const [abertos, setAbertos] = useState(false);
  return (
    <header className="topo vidro">
      {modo === "emails" ? (
        <div className="topo-abas" role="tablist" aria-label="Faixa de comandos">
          {ABAS.map(([k, t]) => <button key={k} type="button" role="tab" aria-selected={aba === k} aria-pressed={aba === k} onClick={() => setAba(k)}>{t}</button>)}
        </div>
      ) : (
        <div className="topo-quem">
          <span className="capsula-avatar grande" aria-hidden="true">{(agente || "?").slice(0, 1)}</span>
          <b>Bem-vindo, {agente || "…"}</b>
        </div>
      )}
      <label className="topo-busca">
        <span className="orbe" aria-hidden="true" />
        <input id="busca-topo" type="search" value={busca} onChange={(ev) => setBusca(ev.target.value)} autoComplete="off" spellCheck={false}
          onKeyDown={(ev) => { if (ev.key === "Escape" && busca) { ev.stopPropagation(); setBusca(""); } }}
          placeholder={window.innerWidth < 760 ? "Pesquisar…" : "Pesquisar hóspede, CPF/CNPJ, nº da NF ou frase"} aria-label="Pesquisar nos e-mails dos 4 PCs" />
        {busca ? <button type="button" className="topo-limpar" onClick={() => setBusca("")} aria-label="Limpar a pesquisa"><Icone nome="fechar" tamanho={14} /></button> : <kbd>Ctrl K</kbd>}
      </label>
      <BotaoRedondo icone="tema" titulo={tema === "escuro" ? "Usar o tema claro" : "Usar o tema escuro"} onClick={trocarTema} />
      <BotaoRedondo icone="sino" titulo={`Avisos: ${avisos.length}`} branco ponto={avisos.length > 0} onClick={() => setAbertos(!abertos)} />
      {abertos && (
        <div className="avisos vidro" role="dialog" aria-label="Avisos">
          <b>Avisos</b>
          {avisos.length === 0 && <p>Nenhum aviso agora. Tudo funcionando.</p>}
          {avisos.map((a) => (
            <div className="aviso" key={a.texto}><Icone nome={a.icone} /><div>{a.texto}<small>{a.detalhe}</small></div></div>
          ))}
        </div>
      )}
    </header>
  );
}
