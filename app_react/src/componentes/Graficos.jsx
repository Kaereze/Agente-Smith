// Gráficos do Painel (linhas, rosca, barras, anel). Todos animam ao abrir a tela e têm o texto para leitor de tela.
import Conta from "./Conta.jsx";
import "./Graficos.css";

export function GraficoLinhas({ dias, series, ligado, maximo }) {
  const L = 640, A = 220, esq = 30, dir = 40, cima = 12, baixo = 28;
  const topo = Math.max(10, Math.ceil(((maximo ?? Math.max(...series.flatMap((s) => s.valores))) || 10) / 10) * 10);
  const x = (i) => esq + (i * (L - esq - dir)) / Math.max(1, dias.length - 1);
  const y = (v) => cima + (1 - v / topo) * (A - cima - baixo);
  const caminho = (vs) => vs.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const ultimo = dias.length - 1;
  const marcas = [0, topo / 2, topo];
  const descricao = series.map((s) => `${s.nome}: ${s.valores.join(", ")}`).join("; ");
  return (
    <svg className={`grafico-linhas${ligado ? " ligado" : ""}`} viewBox={`0 0 ${L} ${A}`} role="img" aria-label={descricao}>
      {marcas.map((v) => (
        <g key={v}><line x1={esq} x2={L - dir} y1={y(v)} y2={y(v)} className="grade" /><text x={esq - 8} y={y(v) + 4} textAnchor="end">{v}</text></g>
      ))}
      {series[0] && <path className="area" d={`${caminho(series[0].valores)} L${x(ultimo)} ${y(0)} L${x(0)} ${y(0)} Z`} style={{ fill: series[0].cor }} />}
      {series.map((s, k) => <path key={s.nome} className="serie" d={caminho(s.valores)} style={{ stroke: s.cor, transitionDelay: `${k * .2}s` }} />)}
      {dias.map((d, i) => <text key={d} x={x(i)} y={A - 6} textAnchor="middle" className={i === ultimo ? "hoje" : ""}>{i === ultimo ? "Hoje" : d.slice(8, 10) + "/" + d.slice(5, 7)}</text>)}
      {ligado && series.map((s) => (
        <g key={s.nome + "p"}><circle cx={x(ultimo)} cy={y(s.valores[ultimo])} r="5" style={{ fill: s.cor }} />
          <text x={x(ultimo) + 9} y={y(s.valores[ultimo]) + 4} className="valor">{s.valores[ultimo]}</text></g>
      ))}
    </svg>
  );
}

export function Rosca({ partes, ligado, rotulo }) {
  const total = partes.reduce((s, p) => s + p.total, 0);
  const r = 60, c = 2 * Math.PI * r;
  let acumulado = 0;
  return (
    <div className="rosca">
      <svg width="150" height="150" viewBox="0 0 150 150" role="img" aria-label={`${total} ${rotulo}, ${partes.map((p) => `${p.total} ${p.nome}`).join(", ")}`}>
        <circle cx="75" cy="75" r={r} className="trilha-rosca" />
        {partes.filter((p) => p.total).map((p) => {
          const tam = (p.total / total) * c - (partes.length > 1 ? 3 : 0);
          const el = <circle key={p.nome} cx="75" cy="75" r={r} className="fatia" style={{ stroke: p.cor, strokeDasharray: `${ligado ? tam : 0} ${c}`, strokeDashoffset: -acumulado }} />;
          acumulado += (p.total / total) * c;
          return el;
        })}
      </svg>
      <div className="rosca-meio"><b><Conta valor={total} /></b><small>{rotulo}</small></div>
    </div>
  );
}

export function Barra({ parte, todo, ligado }) {
  return <div className="barra"><span style={{ width: ligado && todo ? `${(parte / todo) * 100}%` : 0 }} /></div>;
}

export function Anel({ porcento, ligado, rotulo }) {
  const r = 56, c = 2 * Math.PI * r;
  return (
    <div className="anel">
      <svg width="140" height="140" viewBox="0 0 140 140" role="img" aria-label={`${porcento}% ${rotulo}`}>
        <circle cx="70" cy="70" r={r} className="trilha-anel" />
        <circle cx="70" cy="70" r={r} className="anel-cheio" style={{ strokeDasharray: c, strokeDashoffset: ligado ? c * (1 - porcento / 100) : c }} />
      </svg>
      <div className="rosca-meio"><b><Conta valor={porcento} sufixo="%" /></b><small>{rotulo}</small></div>
    </div>
  );
}
