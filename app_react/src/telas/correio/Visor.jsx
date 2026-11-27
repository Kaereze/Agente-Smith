// O anexo aberto aqui mesmo no Painel (foto ou PDF do hóspede), pedido ao vivo ao Outlook do PC dono.
// Setas ← → trocam de anexo; clicar na foto amplia; "Baixar" abre no programa do PC.
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import Icone from "../../componentes/Icone.jsx";
import { pegarAnexo, useTextos } from "./textos.js";
import "../../componentes/Janela.css";

export default function Visor({ email, nomes, inicio = 0, aoFechar }) {
  const [i, setI] = useState(inicio);
  const [grande, setGrande] = useState(false);
  const { anexo } = useTextos();
  const nome = nomes[i], n = nomes.length;
  const u = anexo(email.id, nome);
  useEffect(() => { pegarAnexo(email, nome); setGrande(false); }, [email, nome]);
  useEffect(() => {
    const tecla = (ev) => {
      ev.stopPropagation();   // com o visor aberto, as teclas são dele (Delete não exclui o e-mail de trás)
      if (ev.key === "Escape") { ev.preventDefault(); aoFechar(); }
      if (n > 1 && (ev.key === "ArrowRight" || ev.key === "ArrowLeft")) { ev.preventDefault(); setI((x) => (x + (ev.key === "ArrowRight" ? 1 : -1) + n) % n); }
    };
    window.addEventListener("keydown", tecla, true);
    return () => window.removeEventListener("keydown", tecla, true);
  }, [n, aoFechar]);

  let corpo;
  if (!u || u.carregando) corpo = <div className="visor-msg">Pedindo o anexo ao Outlook do PC dono…</div>;
  else if (u.erro) corpo = <div className="visor-msg">Não deu para abrir: {u.erro}</div>;
  else if (u.tipo.startsWith("image/")) corpo = <img src={u.url} alt={nome} className={`visor-img${grande ? " grande" : ""}`} onClick={() => setGrande(!grande)} />;
  else if (u.tipo === "application/pdf" || u.tipo.startsWith("text/")) corpo = <iframe src={u.url} title={nome} className="visor-pdf" />;
  else corpo = <div className="visor-msg">Esse tipo de arquivo não dá para mostrar aqui.<br />Use “Baixar” para abrir no programa do PC.</div>;

  return createPortal(
    <div className="janela-fundo" onMouseDown={(ev) => ev.target === ev.currentTarget && aoFechar()}>
      <div className="visor vidro" role="dialog" aria-modal="true" aria-label={`Anexo ${nome}`}>
        <div className="visor-cab">
          <Icone nome="clipe" tamanho={16} /><b title={nome}>{nome}</b>
          {n > 1 && <>
            <span className="visor-n">{i + 1} de {n}</span>
            <button type="button" onClick={() => setI((i - 1 + n) % n)} aria-label="Anexo anterior"><Icone nome="esquerda" tamanho={16} /></button>
            <button type="button" onClick={() => setI((i + 1) % n)} aria-label="Próximo anexo"><Icone nome="direita" tamanho={16} /></button>
          </>}
          {u?.url && <a className="visor-baixar" href={u.url} download={nome}><Icone nome="baixar" tamanho={15} />Baixar</a>}
          <button type="button" onClick={aoFechar} aria-label="Fechar" title="Fechar (Esc)"><Icone nome="fechar" tamanho={16} /></button>
        </div>
        <div className="visor-corpo">{corpo}</div>
      </div>
    </div>,
    document.body,
  );
}
