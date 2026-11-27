// Notas fiscais: a página está reservada para a emissão automática de NF (em construção desde 07/11/2026).
// As solicitações dos hóspedes continuam na Caixa de entrada.
import Botao from "../componentes/Botao.jsx";
import { CabecalhoTela, Bolinha } from "../componentes/Bloco.jsx";

export default function Notas({ irPara }) {
  return (
    <main className="principal vidro">
      <CabecalhoTela icone="nota" titulo="Notas fiscais" explica="Emissão automática de NF" />
      <section className="bloco vidro entra" style={{ justifyItems: "center", textAlign: "center", padding: "48px 24px" }}>
        <Bolinha icone="nota" tamanho={64} />
        <h3 style={{ margin: 0, fontSize: 20 }}>Esta página vai emitir as notas fiscais sozinha</h3>
        <p className="resposta" style={{ maxWidth: "56ch" }}>A emissão automática de NF está em construção. Enquanto isso, as solicitações dos hóspedes continuam na Caixa de entrada.</p>
        <Botao tipo="principal" icone="caixa" onClick={() => irPara("correio")}>Ir para a Caixa de entrada</Botao>
      </section>
    </main>
  );
}
