// Ficha do hóspede (João, 09/11/2026): quando chega um FORMULÁRIO, abre esta página no lugar da leitura. Os campos que o
// hóspede preencheu, cada um com Copiar; a situação do pedido; o que o Painel conferiu; os e-mails e os outros pedidos dele(a).
// "Copiar tudo para a emissão" abre uma janelinha EDITÁVEL com o texto que vai para o emissor. Nada é inventado.
import { useEffect, useRef, useState } from "react";
import Icone from "../../componentes/Icone.jsx";
import Botao from "../../componentes/Botao.jsx";
import BotaoEnviarNF from "../../componentes/BotaoEnviarNF.jsx";
import Etiqueta from "../../componentes/Etiqueta.jsx";
import Janela from "../../componentes/Janela.jsx";
import { useAvisos } from "../../componentes/Avisos.jsx";
import { copiarTexto } from "./Formulario.jsx";
import { aj } from "../../ajustes.js";
import {
  campoDoPedido, CAMPO_DOC, CAMPO_NOME, cepValido, cnpjValido, contarDiarias, cpfValido, dataBr, etapasDoPedido, faltaDados, faltaExtras,
  hpData, nomeDoHospede, nomeSituacao, OCULTOS_FORM, prazoInfo, semAcento, seloDoDocumento, situacaoDoPedido, SITUACOES, textoEmissao, valorDoForm,
} from "../../dados/formulario.js";

function conferencia(d, ci, co) {
  const itens = [], c = (...t) => campoDoPedido(d, ...t);
  const doc = c(...CAMPO_DOC);
  itens.push(!doc.replace(/\D/g, "") ? [false, "Documento do tomador não informado"] : cpfValido(doc) || cnpjValido(doc) ? [true, "CPF/CNPJ do tomador confere"] : [false, "CPF/CNPJ do tomador com dígito errado"]);
  itens.push(c(...CAMPO_NOME) ? [true, "Nome do tomador preenchido"] : [false, "Nome do tomador não informado"]);
  const cep = c(/^cep/, /\bcep\b/);
  itens.push(!cep.replace(/\D/g, "") ? [false, "CEP não informado"] : cepValido(cep) ? [true, "CEP preenchido"] : [false, "CEP incompleto"]);
  const n = contarDiarias(ci, co);
  if (!ci.txt || !co.txt) itens.push([false, "Datas da hospedagem não informadas"]);
  else if (!Number.isFinite(ci.ms) || !Number.isFinite(co.ms)) itens.push([false, "Não consegui ler as datas da hospedagem"]);
  else itens.push(n ? [true, `Datas coerentes (${n} diária${n > 1 ? "s" : ""})`] : [false, "Check-out não vem depois do check-in"]);
  for (const x of faltaExtras(d)) itens.push([false, `${x[0].toUpperCase() + x.slice(1)} não informado`]);
  return itens;
}
function fraseDaSituacao(sit, falta, pz, d) {
  if (sit === "enviada") return "Concluído" + (d.nfs?.length ? `. NF ${d.nfs.join(", ")} enviada.` : ".");
  if (sit === "pronta") return "A nota existe, mas falta enviar ao hóspede.";
  if (sit === "falta") return "Falta dado para emitir: " + falta.join(", ") + ".";
  return "Falta emitir a nota." + (pz ? " Prazo " + pz.texto + "." : "");
}

function Campo({ rot, valor, mono, selo, inteiro, longo }) {
  const { recado } = useAvisos();
  const vazio = !String(valor || "").trim();
  const copiar = async () => { const ok = await copiarTexto(valor); recado(ok ? `Copiado: ${valor.length > 40 ? valor.slice(0, 40) + "…" : valor}` : "Não deu para copiar agora", !ok); };
  return (
    <div className={inteiro ? "hp-inteiro" : ""}>
      <span className="hp-rot">{rot}</span>
      <div className={`hp-campo${vazio ? " vazio" : ""}${longo ? " longo" : ""}`}>
        <span className={`hp-v${mono ? " mono" : ""}`}>{vazio ? "Não informado" : valor}</span>
        {selo && !vazio && <Etiqueta tipo={selo[1] ? "verde" : "vermelho"}>{selo[0]}</Etiqueta>}
        {!vazio && <button type="button" className="hp-cp" onClick={copiar} aria-label={`Copiar ${rot}`}><Icone nome="copiar" tamanho={14} />Copiar</button>}
      </div>
    </div>
  );
}

export default function Ficha({ d, emailId, emails, fila, hotel, soVer, voltar, abrirEmail, enviarNF, pedirFalta, pesquisar, abrirPedido }) {
  const [emissao, setEmissao] = useState(false);
  if (!d) return null;
  const c = (...t) => campoDoPedido(d, ...t);
  const usados = new Set();
  const pega = (...t) => { const k = (d.campos || []).find(([r]) => t.some((x) => x.test(semAcento(r)))); if (k) usados.add(k); return k ? String(k[1] || "").trim() : ""; };
  const f = { doc: pega(...CAMPO_DOC), tom: pega(...CAMPO_NOME), cep: pega(/^cep/, /\bcep\b/), tel: pega(/telefone|celular|whatsapp/), cpfT: pega(/cpf.*titular/),
    nomeT: pega(/nome.*titular/, /nome do hospede/), ci: pega(/check.?in/), co: pega(/check.?out/), info: pega(/informac/, /o que.*nota/, /itens/),
    div: pega(/^nota dividida/), divEm: pega(/dividida em|quantas vezes/), valor: pega(/valor.*nota/) };
  const ci = hpData(f.ci), co = hpData(f.co), n = contarDiarias(ci, co);
  const resto = (d.campos || []).filter((k) => !usados.has(k) && String(k[1] || "").trim() && !OCULTOS_FORM.test(semAcento(k[0])) && !/^termos/.test(semAcento(k[0])));
  const termos = (d.campos || []).find(([k]) => /^termos/.test(semAcento(k)));
  const dividida = f.div ? (f.divEm && /^sim/i.test(f.div) ? `${f.div}, em ${f.divEm}` : f.div) : "";
  const ehPedido = !!d.chave, falta = faltaDados(d), sit = situacaoDoPedido(d), pz = prazoInfo(d.prazo);
  const m = etapasDoPedido({ hora: String(d.carimbo || d.data || "").slice(0, 16), falta, temPedido: ehPedido });
  const mail = String(d.email || "").trim().toLowerCase(), docNum = c(...CAMPO_DOC).replace(/\D/g, "");
  // E-mails dele(a) só desta hospedagem: desde N dias antes do check-in (ajustes: tela.dias_antes_checkin). Sem check-in: todos.
  const desde = Number.isFinite(ci.ms) ? new Date(ci.ms - aj("tela.dias_antes_checkin", 30) * 864e5).toISOString().slice(0, 10) : "";
  const mails = emails.filter((e) => e.id === emailId || (d.chave && e.solicitacao?.chave === d.chave) || (mail && String(e.de || "").toLowerCase() === mail && String(e.quando || "") >= desde))
    .sort((a, b) => String(b.quando).localeCompare(String(a.quando))).slice(0, 6);
  const outros = ehPedido ? (fila || []).filter((o) => o.chave !== d.chave && ((mail && String(o.email || "").toLowerCase() === mail) || (docNum.length >= 11 && campoDoPedido(o, ...CAMPO_DOC).replace(/\D/g, "") === docNum)))
    .sort((a, b) => String(b.data).localeCompare(String(a.data))).slice(0, 5) : [];
  const [sitNome, sitTipo, sitIcone] = SITUACOES[sit];

  return (
    <main className="hp vidro entra" aria-label="Ficha do hóspede">
      <div className="hp-faixa">
        <Botao tipo="fantasma" pequeno icone="esquerda" onClick={voltar}>Voltar</Botao>
        <span style={{ flex: 1 }} />
        <Botao pequeno icone="busca" onClick={() => pesquisar(d.email || nomeDoHospede(d))}>E-mails dele(a)</Botao>
      </div>
      <div className="hp-cab">
        <div>
          <h2>{nomeDoHospede(d)}</h2>
          <div className="hp-sub">
            {(d.hotel || hotel) && <Etiqueta tipo="cinza">{d.hotel || hotel}</Etiqueta>}
            <Etiqueta tipo={sitTipo} icone={sitIcone}>{sit === "falta" ? `Falta dado: ${falta.join(", ")}` : sitNome}</Etiqueta>
            {pz && <Etiqueta tipo={pz.nivel === "vencido" ? "vermelho" : pz.nivel === "perto" ? "ambar" : "verde"} icone="relogio">Prazo {pz.texto}</Etiqueta>}
            {(d.carimbo || d.data) && <span>Pedido de {String(d.carimbo || "").trim() || dataBr(d.data)}</span>}
          </div>
        </div>
        <div className="hp-acoes">
          <Botao icone="copiar" onClick={() => setEmissao(true)}>Copiar tudo para a emissão</Botao>
          {emailId && <Botao icone="envelope" onClick={() => abrirEmail(emailId)}>Abrir e-mail do pedido</Botao>}
          {!soVer && (m.principal.acao === "pedir" && d.email ? <Botao tipo="principal" icone="envelope" onClick={() => pedirFalta(d)}>Pedir o que falta</Botao>
            : m.principal.acao === "nf" && emailId ? <BotaoEnviarNF hospede={nomeDoHospede(d)} aoClicar={() => enviarNF(emailId)} /> : null)}
        </div>
      </div>
      <div className="hp-miolo">
        <div className="hp-form">
          <section className="hp-sec"><div className="hp-sec-t"><h3>Quem vai receber a nota</h3><small>Documento Tomador · Nome Tomador</small></div><div className="hp-campos">
            <Campo rot="Documento do tomador (CPF/CNPJ)" valor={f.doc ? valorDoForm("CPF/CNPJ", f.doc)[0] : ""} mono selo={seloDoDocumento(f.doc)} />
            <Campo rot="Nome do tomador" valor={f.tom} />
            <Campo rot="E-mail" valor={d.email || ""} />
            <Campo rot="Telefone para contato" valor={valorDoForm("Telefone", f.tel)[0]} mono />
            <Campo rot="CEP" valor={valorDoForm("CEP", f.cep)[0]} mono />
          </div></section>
          <section className="hp-sec"><div className="hp-sec-t"><h3>Titular da reserva</h3></div><div className="hp-campos">
            <Campo rot="CPF do titular da reserva" valor={f.cpfT ? valorDoForm("CPF", f.cpfT)[0] : ""} mono selo={seloDoDocumento(f.cpfT)} />
            <Campo rot="Nome do titular da reserva" valor={f.nomeT} />
            <Campo rot="Check-in da hospedagem" valor={ci.txt} mono />
            <Campo rot="Check-out da hospedagem" valor={co.txt ? co.txt + (n ? ` · ${n} diária${n > 1 ? "s" : ""}` : "") : ""} mono />
          </div></section>
          <section className="hp-sec"><div className="hp-sec-t"><h3>O que o hóspede pediu</h3></div><div className="hp-campos">
            <Campo rot="Informações necessárias na nota fiscal" valor={f.info} inteiro longo />
            <Campo rot="Nota dividida" valor={dividida} />
            {f.valor && <Campo rot="Valor da nota" valor={f.valor} mono />}
            <Campo rot="Enviado pelo formulário em" valor={String(d.carimbo || "").trim() || dataBr(d.data)} mono />
          </div></section>
          {(resto.length > 0 || termos) && (
            <section className="hp-sec"><div className="hp-sec-t"><h3>Outros campos</h3></div><div className="hp-campos">
              {resto.map(([k, v]) => <Campo key={k} rot={k} valor={String(v)} inteiro={String(v).length > 60} longo />)}
              {termos && <Campo rot="Termos de aceite" valor={termos[1]} inteiro />}
            </div></section>
          )}
        </div>
        <div className="hp-lado">
          <section className="hp-card"><h3>Situação</h3><p className="hp-situ">{fraseDaSituacao(sit, falta, pz, d)}</p>
            <ol className="hp-et">{m.passos.map((p) => <li key={p.nome} className={p.feita ? "feito" : p.atual ? "agora" : "falta"}>{p.nome}{p.sub && <small>{p.sub}</small>}</li>)}</ol></section>
          <section className="hp-card"><h3>O Painel conferiu</h3>
            <ul className="hp-conf">{conferencia(d, ci, co).map(([ok, x]) => <li key={x}><span className={`m ${ok ? "ok" : "mau"}`}><Icone nome={ok ? "check" : "alerta"} tamanho={12} /></span><span>{x}</span></li>)}</ul></section>
          <section className="hp-card"><h3>E-mails dele(a)</h3>
            <ul className="hp-lst">{mails.length ? mails.map((e) => (
              <li key={e.id}><time>{String(e.quando || "").slice(11, 16)}</time>
                <button type="button" className="hp-link" title={e.assunto || ""} onClick={() => abrirEmail(e.id)}>{e.assunto || "(sem assunto)"}</button>
                <Etiqueta tipo={(e.classes || []).includes("formulario") ? "azul" : e.respondido ? "verde" : "cinza"}>{(e.classes || []).includes("formulario") ? "Formulário" : e.respondido ? "Respondido" : "Recebido"}</Etiqueta></li>
            )) : <li className="vazio">Nenhum e-mail ligado.</li>}</ul></section>
          {ehPedido && (
            <section className="hp-card"><h3>Outros pedidos</h3>
              <ul className="hp-lst">{outros.length ? outros.map((o) => (
                <li key={o.chave}><time>{dataBr(o.data).slice(0, 5)}</time>
                  <button type="button" className="hp-link" onClick={() => abrirPedido(o.chave)}>{o.hotel}</button><Etiqueta tipo="cinza">{nomeSituacao(o)}</Etiqueta></li>
              )) : <li className="vazio">Só este pedido.</li>}</ul></section>
          )}
        </div>
      </div>
      {emissao && <JanelaEmissao d={d} aoFechar={() => setEmissao(false)} />}
    </main>
  );
}

// Dados para a emissão: já copia ao abrir; dá para editar antes de copiar de novo (não muda a ficha)
function JanelaEmissao({ d, aoFechar }) {
  const [txt, setTxt] = useState(() => textoEmissao(d));
  const [editado, setEditado] = useState(false);
  const [rotulo, setRotulo] = useState("Copiar");
  const campo = useRef(null);
  const copiar = async () => {
    const ok = await copiarTexto(campo.current?.value ?? txt);
    setRotulo(ok ? "Copiado" : "Não copiou: selecione e copie");
    if (!ok) campo.current?.select();
    setTimeout(() => setRotulo("Copiar"), 1500);
  };
  useEffect(() => { copiar(); }, []);   // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Janela titulo="Dados para a emissão" sub={`${nomeDoHospede(d)}${d.hotel ? " · " + d.hotel : ""}`} aoFechar={aoFechar} fecharFora={!editado} largura={480}
      rodape={<><Botao onClick={aoFechar}>Fechar</Botao><Botao tipo="principal" icone="copiar" onClick={copiar}>{rotulo}</Botao></>}>
      <textarea ref={campo} className="campo mono" rows={8} spellCheck={false} value={txt} aria-label="Texto para a emissão (pode editar)"
        onChange={(ev) => { setTxt(ev.target.value); setEditado(true); }} />
      <p className={`hp-pop-dica${editado ? " editado" : ""}`}>{editado ? "Editado. Clique em Copiar para levar a sua versão." : "Pode editar antes de copiar. Isso não muda a ficha."}</p>
    </Janela>
  );
}
