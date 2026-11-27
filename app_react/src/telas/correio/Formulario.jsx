// O formulário do Emissor Automático como chega no Outlook: "Enviado por", a tabela Campo / Valor em grupos
// (Tomador da nota · Estadia · Como quer a nota) e "Enviado em". CPF/CNPJ, CEP e telefone formatados; Copiar leva o valor
// como o hóspede escreveu (para colar na emissão).
import Icone from "../../componentes/Icone.jsx";
import { useAvisos } from "../../componentes/Avisos.jsx";
import { gruposDoFormulario, valorDoForm, SEM_COPIAR_FORM } from "../../dados/formulario.js";

export async function copiarTexto(txt) {
  try { await navigator.clipboard.writeText(txt); return true; } catch { return false; }
}

export default function Formulario({ dados, email }) {
  const { recado } = useAvisos();
  const f = gruposDoFormulario(dados, email);
  const copiar = async (v) => {
    const ok = await copiarTexto(v);
    recado(ok ? `Copiado: ${v.length > 40 ? v.slice(0, 40) + "…" : v}` : "Não deu para copiar agora", !ok);
  };
  return (
    <div className="fg">
      {f.email && <div className="fg-por">Enviado por: <span>{f.email}</span></div>}
      <h4>Dados para emissão de Nota Fiscal</h4>
      <div className="fg-tab" role="table" aria-label="Dados para emissão de Nota Fiscal">
        <div className="fg-cab" role="row"><span role="columnheader">Campo</span><span role="columnheader">Valor</span><span role="columnheader" aria-label="Copiar" /></div>
        {f.grupos.map((g) => (
          <div key={g.titulo} role="rowgroup">
            <div className="fg-grp" role="row"><span role="rowheader">{g.titulo}</span></div>
            {g.linhas.map(({ rot, valor }) => {
              const [mostra, obs] = valorDoForm(rot, valor);
              return (
                <div className="fg-l" role="row" key={rot + valor}>
                  <span className="k" role="cell">{rot}</span>
                  <span className="v" role="cell">{mostra}{obs && <small>{obs}</small>}</span>
                  {SEM_COPIAR_FORM.has(rot) ? <span /> : (
                    <button type="button" className="fg-cp" onClick={() => copiar(String(valor))} aria-label={`Copiar ${rot}`} title="Copiar"><Icone nome="copiar" tamanho={15} /></button>
                  )}
                </div>
              );
            })}
          </div>
        ))}
      </div>
      <div className="fg-pe">
        {f.termos && (f.aceitou ? <span className="ok"><Icone nome="check" tamanho={14} />Aceitou os termos</span> : <span><b>Termos de aceite:</b> {f.termos}</span>)}
        {f.enviadoEm && <span><b>Enviado em:</b> {f.enviadoEm}</span>}
      </div>
    </div>
  );
}
