// Peças de texto que todas as telas usam: cabeçalho da tela, pergunta do bloco, "como ler", bolinha com ícone.
import Icone from "./Icone.jsx";
import "./Bloco.css";

export function CabecalhoTela({ icone, titulo, explica, children }) {
  return (
    <div className="tela-cab">
      <span className="bolinha-grande"><Icone nome={icone} tamanho={22} /></span>
      <div className="tela-cab-texto"><h2>{titulo}</h2>{explica && <p>{explica}</p>}</div>
      <span className="tela-cab-espaco" />
      {children}
    </div>
  );
}

export function Pergunta({ assunto, children }) {
  return <div className="pergunta"><small>{assunto}</small><h3>{children}</h3></div>;
}

export function ComoLer({ children }) {
  return <p className="como-ler"><Icone nome="livro" tamanho={15} /><span>{children}</span></p>;
}

// tipo = verde · vermelha · ambar · azul · cinza
export function Bolinha({ icone, tipo = "verde", tamanho = 38 }) {
  return <span className={`bolinha ${tipo}`} style={{ width: tamanho, height: tamanho }}><Icone nome={icone} tamanho={Math.round(tamanho * .45)} /></span>;
}

// Abas em pílula (Agora / Registro, Mês / Semana…). opcoes = [[valor, texto], …]
export function AbasPilula({ valor, opcoes, aoEscolher, rotulo }) {
  return (
    <div className="abas-pilula" role="group" aria-label={rotulo}>
      {opcoes.map(([v, t]) => <button key={v} type="button" aria-pressed={valor === v} onClick={() => aoEscolher(v)}>{t}</button>)}
    </div>
  );
}
