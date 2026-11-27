// Agentes do Smith: o mapa do sistema (o mesmo de sempre, servido em /agentes/mapa), dentro da moldura nova.
// Só o administrador vê; o servidor recusa os outros.
import { CabecalhoTela } from "../componentes/Bloco.jsx";

export default function Agentes() {
  return (
    <main className="principal vidro" style={{ display: "flex", flexDirection: "column" }}>
      <CabecalhoTela icone="rede" titulo="Agentes do Smith" explica="O mapa do sistema: cada parte do Painel e o que ela está fazendo agora · só o administrador vê" />
      <iframe title="Agentes do Smith: mapa do sistema" src="/agentes/mapa" referrerPolicy="no-referrer"
        style={{ flex: 1, minHeight: 480, width: "100%", border: 0, borderRadius: 18, background: "var(--vidro-forte)" }} />
    </main>
  );
}
