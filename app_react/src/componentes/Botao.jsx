// O botão do Painel. Um só desenho para todos: muda o "tipo".
//   principal = a ação da tela (escuro no claro, creme no escuro)  ·  verde = enviar/concluir
//   vidro = ação secundária  ·  perigo = excluir  ·  fantasma = "depois", "cancelar" discreto
import Icone from "./Icone.jsx";
import "./Botao.css";

export default function Botao({ children, tipo = "vidro", icone, titulo, desligado, onClick, pequeno }) {
  return (
    <button type="button" className={`botao botao-${tipo}${pequeno ? " botao-pequeno" : ""}`} title={titulo} aria-label={children ? undefined : titulo}
      disabled={desligado} onClick={onClick}>
      {icone && <Icone nome={icone} tamanho={pequeno ? 15 : 16} />}
      {children}
    </button>
  );
}

// Botão redondo só com ícone (tema, sino, fechar…). Sempre com o nome escrito para o leitor de tela e na dica.
export function BotaoRedondo({ icone, titulo, branco, ponto, onClick, tamanho = 40 }) {
  return (
    <button type="button" className={`botao-redondo${branco ? " branco" : ""}`} style={{ width: tamanho, height: tamanho }} title={titulo} aria-label={titulo} onClick={onClick}>
      <Icone nome={icone} tamanho={Math.round(tamanho * .44)} />
      {ponto && <span className="ponto" aria-hidden="true" />}
    </button>
  );
}
