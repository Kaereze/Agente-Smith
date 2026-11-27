// Etiqueta de situação: sempre com texto (nunca só cor). tipo = verde · vermelho · ambar · azul · cinza
import Icone from "./Icone.jsx";

const CORES = {
  verde: ["var(--verde-suave)", "var(--verde-texto)"], vermelho: ["var(--vermelho-suave)", "var(--vermelho-texto)"],
  ambar: ["var(--ambar-suave)", "var(--ambar-texto)"], azul: ["var(--azul-suave)", "var(--azul-texto)"], cinza: ["var(--cinza)", "var(--texto2)"],
};

export default function Etiqueta({ children, tipo = "verde", icone, contorno, titulo }) {
  const [fundo, cor] = CORES[tipo] || CORES.cinza;
  return (
    <span title={titulo || undefined} style={{
      display: "inline-flex", alignItems: "center", gap: 5, minHeight: 22, padding: "2px 9px", borderRadius: 11, lineHeight: 1.3, maxWidth: "100%", overflowWrap: "anywhere",
      fontSize: 12, fontWeight: 600, color: cor, background: contorno ? "transparent" : fundo, border: contorno ? `1px solid ${cor}` : 0,
    }}>
      {icone && <Icone nome={icone} tamanho={12} />}{children}
    </span>
  );
}
