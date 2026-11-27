// O topo em pílula. Na Visão geral: saudação + pesquisa + tema + avisos.
// Nos e-mails: as abas do Outlook + "Caixa de" + pesquisa + tema + avisos (igual à tela de hoje, com o vidro novo).
import { useState } from "react";
import Icone from "../componentes/Icone.jsx";
import { BotaoRedondo } from "../componentes/Botao.jsx";
import "./Moldura.css";

export default function Topo({ modo, agente, tema, trocarTema, avisos }) {
  const [abertos, setAbertos] = useState(false);
  return (
    <header className="topo vidro">
      {modo === "emails" ? (
        <>
          <div className="topo-abas" role="group" aria-label="Faixa de comandos">
            <button type="button" aria-pressed="true">Página Inicial</button>
            <button type="button" aria-pressed="false">Enviar/Receber</button>
            <button type="button" aria-pressed="false">Exibir</button>
          </div>
          <button type="button" className="topo-caixa" title="De quem é a caixa que você está vendo">
            Caixa de <b>{agente ? `${agente} (minha)` : "…"}</b><Icone nome="seta" tamanho={13} />
          </button>
        </>
      ) : (
        <div className="topo-quem">
          <span className="capsula-avatar grande" aria-hidden="true">{(agente || "?").slice(0, 1)}</span>
          <b>Bem-vindo, {agente || "…"}</b>
        </div>
      )}
      <label className="topo-busca">
        <span className="orbe" aria-hidden="true" />
        <input type="search" placeholder={window.innerWidth < 760 ? "Pesquisar…" : "Pesquisar hóspede, CPF/CNPJ, nº da NF ou frase"} aria-label="Pesquisar nos e-mails dos 4 PCs" />
        <kbd>Ctrl K</kbd>
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
