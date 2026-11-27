// Escrever, igual ao Outlook: uma peça para Responder, Responder com a NF, Encaminhar, Novo e-mail e Enviar NF de um pedido.
//   modo: "resp" | "nf" | "enc" | "novo" | "pedido"
// Sai sempre pela caixa do hotel, pelo Outlook do PC dono. Antes de enviar com PDF anexado, o Painel abre a nota e confere com o
// pedido (CPF/CNPJ, valor, nome): se algo não bate, avisa e a pessoa decide ("Conferi, pode enviar" ou "Voltar e corrigir").
import { useEffect, useRef, useState } from "react";
import { api } from "../../api.js";
import Icone from "../../componentes/Icone.jsx";
import Botao from "../../componentes/Botao.jsx";
import Etiqueta from "../../componentes/Etiqueta.jsx";
import { useAvisos } from "../../componentes/Avisos.jsx";
import { assuntoDoArquivo, dadosDoModelo, modeloPedirFalta, modeloSolicitacaoDados, MODELOS_RESPOSTA, semAcento } from "../../dados/formulario.js";

const TITULOS = { resp: "Responder", nf: "Responder com a NF", enc: "Encaminhar", novo: "Novo e-mail", pedido: "Enviar NF" };
const tamanho = (b) => (b > 1048576 ? (b / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(b / 1024)) + " KB");
const lerBase64 = (f) => new Promise((ok, erro) => { const r = new FileReader(); r.onload = () => ok(String(r.result).split(",")[1]); r.onerror = erro; r.readAsDataURL(f); });
const semSaudacao = (t) => String(t || "").trim().replace(/^(Bom dia|Boa tarde|Boa noite)!/, "");
const guardado = (k) => { try { return localStorage.getItem(k); } catch { return null; } };
const guardar = (k, v) => { try { localStorage.setItem(k, v); } catch { /* sem armazenamento */ } };

export default function Escrever({ modo, email, chave, extra = {}, paraDoFormulario = "", citacao, inline, aoFechar, aoEnviado, aoMinimizar }) {
  const { recado } = useAvisos();
  const enc = modo === "enc", novo = modo === "novo", resposta = modo !== "pedido";
  const [o, setO] = useState(null);
  const [erroO, setErroO] = useState("");
  const [para, setPara] = useState(""), [cc, setCc] = useState(""), [assunto, setAssunto] = useState(""), [msg, setMsg] = useState("");
  const [anexos, setAnexos] = useState([]);
  const [selo, setSelo] = useState(""), [ligacao, setLigacao] = useState(!!extra.rascunho?.ligacao);
  const [contaDe, setContaDe] = useState(""), [contaLocal, setContaLocal] = useState("");
  const [conferencia, setConferencia] = useState(null);   // [avisos]
  const [res, setRes] = useState(""), [falha, setFalha] = useState(null), [enviando, setEnviando] = useState(false);
  const [sobre, setSobre] = useState(false);
  const manual = useRef(false), antes = useRef(null), arquivo = useRef(null), campoPara = useRef(null), campoMsg = useRef(null);

  // as opções do envio: de qual caixa sai, para quem, a mensagem padrão, a assinatura e as notas achadas no Dropbox
  useEffect(() => {
    let vivo = true;
    const caminho = novo ? "/api/email/novo" + (extra.conta ? "?conta=" + encodeURIComponent(extra.conta) : "")
      : modo === "pedido" ? `/api/envio_nf/opcoes?chave=${encodeURIComponent(chave)}` : `/api/email/opcoes?id=${encodeURIComponent(email.id)}`;
    api(caminho).then((r) => {
      if (!vivo) return;
      if (r.erro || r.ok === false) { setErroO(r.erro || r.motivo || "Não deu para abrir agora."); return; }
      if (enc) { const orig = r.email?.assunto || ""; r.assunto = /^(enc|fw|fwd):/i.test(orig) ? orig : "ENC: " + orig; r.para = []; r.sugestoes = []; }
      setO(r);
      setContaDe(r.conta_de || "");
      setContaLocal((r.contas_locais || [])[0] || "");
      const rasc = extra.rascunho;
      setPara(rasc?.para || extra.para || paraDoFormulario || (r.para || [])[0] || "");
      setCc(rasc?.cc || "");
      let texto = resposta ? (r.corpo_nf || r.corpo || "") : (r.corpo || "");
      let titulo = novo ? `Nota Fiscal - ${r.hotel}` : resposta ? r.assunto || "" : "";
      if (novo && extra.solicitar) {
        texto = extra.faltas?.length ? modeloPedirFalta(extra.faltas) : modeloSolicitacaoDados();
        titulo = `Solicitação de dados - Nota Fiscal ${r.hotel}`;
      }
      setMsg(rasc?.msg ?? texto);
      setAssunto(rasc?.assunto || titulo);
      if (rasc?.assunto) manual.current = true;
      const salvo = guardado("selo_nf");
      setSelo((r.selos || []).some((s) => s.id === salvo) ? salvo : r.selo || r.selos?.[0]?.id || "");
      const sug = r.sugestoes || [];
      if (sug.length === 1 && !sug[0].outra && !sug[0].possivel) trocarAnexos([{ tipo: "dropbox", rel: sug[0].rel, nome: sug[0].nome }], r);   // nota confirmada pelo conteúdo
      setTimeout(() => ((enc || (novo && !extra.para)) ? campoPara : campoMsg).current?.focus(), 60);
    });
    return () => { vivo = false; };
  }, []);   // eslint-disable-line react-hooks/exhaustive-deps

  // Alt+L liga e desliga "Ligação"
  useEffect(() => {
    if (enc) return undefined;
    const tecla = (ev) => { if (ev.altKey && !ev.ctrlKey && (ev.key === "l" || ev.key === "L")) { ev.preventDefault(); setLigacao((x) => !x); } };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [enc]);

  // Ao anexar o PDF da nota, o assunto vira o nome do arquivo ("NF 1234 - NOME"); tirou o anexo, volta o de antes.
  // Se a pessoa escreveu o assunto à mão, o Painel não mexe mais.
  function trocarAnexos(novos, op = o) {
    setAnexos(novos);
    if (manual.current) return;
    const nf = novos.find((a) => /\.pdf$/i.test(a.nome)) || novos[0];
    setAssunto((atual) => {
      if (nf) { if (antes.current === null) antes.current = atual; return assuntoDoArquivo(nf.nome, op?.nome); }
      if (antes.current !== null) { const v = antes.current; antes.current = null; return v; }
      return atual;
    });
  }
  function adicionarArquivos(lista) {
    const novos = [...anexos];
    for (const f of lista) {
      if (!/\.(pdf|xml)$/i.test(f.name)) { recado(`${f.name}: só PDF ou XML`, true); continue; }
      if (!novos.some((a) => a.nome === f.name)) novos.push({ tipo: "arquivo", nome: f.name, file: f, bytes: f.size });
    }
    trocarAnexos(novos);
    // Novo e-mail: anexou a NF e o texto ainda é a solicitação de dados intacta -> vira a mensagem da NF
    if (novo && novos.length && o?.corpo_nf && semSaudacao(msg) === semSaudacao(modeloSolicitacaoDados())) {
      setMsg(o.corpo_nf);
      recado("NF anexada: a mensagem virou a de envio da NF (dá para editar)");
    }
  }
  const escolherSugestao = (a) => { if (!anexos.some((x) => x.rel === a.rel)) trocarAnexos([...anexos, { tipo: "dropbox", rel: a.rel, nome: a.nome }]); };

  async function escolherDe(conta) {   // Novo e-mail: trocou a caixa -> de qual PC sai e o hotel do assunto
    setContaDe(conta);
    const n = await api("/api/email/novo?conta=" + encodeURIComponent(conta));
    if (n.erro || n.ok === false) return;
    const prefixo = assunto.startsWith("Solicitação de dados") ? "Solicitação de dados - Nota Fiscal " : "Nota Fiscal - ";
    if (assunto === prefixo + o.hotel) setAssunto(prefixo + n.hotel);
    setO((x) => ({ ...x, conta_de: n.conta_de, destino: n.destino, motivo: n.motivo, hotel: n.hotel }));
  }

  function usarModelo(i) {
    const d = dadosDoModelo(o?.nome, o?.hotel, anexos);
    setMsg(MODELOS_RESPOSTA[i][1](d).replace("Olá, !", "Olá!"));
    if (novo && i === 0 && assunto === `Nota Fiscal - ${o.hotel}`) setAssunto(`Solicitação de dados - Nota Fiscal ${o.hotel}`);
    campoMsg.current?.focus();
  }

  const conteudo = anexos.length || enc || (resposta && msg.trim());
  const pronto = o && conteudo && assunto.trim() && para.includes("@") && (o.destino || contaLocal) && !enviando;
  const porQueNao = !o ? "Carregando…" : !para.includes("@") ? "Preencha o Para" : !assunto.trim() ? "Preencha o assunto"
    : !conteudo ? (resposta ? "Escreva a mensagem ou anexe a nota" : "Anexe a nota fiscal") : "";

  async function enviar(contaForcada, jaConferido = false) {
    setEnviando(true); setFalha(null);
    const anx = await Promise.all(anexos.map(async (a) => (a.tipo === "arquivo" ? { tipo: "arquivo", nome: a.nome, b64: await lerBase64(a.file) } : { tipo: "dropbox", rel: a.rel, nome: a.nome })));
    if (!jaConferido && !enc && !novo && anx.length) {
      setRes("Conferindo a NF com o pedido…");
      const c = await api("/api/envio_nf/conferir", { chave: chave || undefined, id: email?.id, anexos: anx });
      setRes(c.conferidas ? `NF conferida com o pedido${c.avisos?.length ? "" : " ✓"}` : "");
      if (c.avisos?.length) { setConferencia(c.avisos); setEnviando(false); return; }
    }
    const conta = contaForcada || (o.destino ? "" : contaLocal);
    const base = { para: para.trim(), cc: cc.trim(), assunto: assunto.trim(), corpo: msg, anexos: anx, selo: selo || undefined, ligacao: ligacao || undefined };
    const r = novo ? await api("/api/email/novo", { ...base, conta_de: contaDe })
      : enc ? await api("/api/correio/encaminhar", { id: email.id, para: para.trim(), corpo: msg, selo: selo || undefined })
      : await api(modo === "pedido" ? "/api/envio_nf" : "/api/email/responder", { ...base, chave: chave || undefined, id: email?.id, conta_de: conta || undefined });
    if (!r.ok) { setEnviando(false); setRes(""); setFalha({ motivo: r.motivo || r.erro || "", contas: r.contas_locais || [] }); return; }
    if (r.aviso_ligacao) recado(r.aviso_ligacao, true);
    aoEnviado(r, { modo, rascunho: { para, cc, assunto, msg, ligacao } });
  }

  const seloAtual = (o?.selos || []).find((s) => s.id === selo);
  const titulo = TITULOS[modo];
  return (
    <section className={`escrever${inline ? " inline" : ""}`} aria-label={titulo}>
      <div className="esc-topo">
        <Icone nome={enc ? "encaminhar" : novo ? "envelope" : modo === "pedido" ? "nota" : "responder"} tamanho={17} />
        <b>{titulo}</b>
        {ligacao && <Etiqueta tipo="azul" icone="telefone">Ligação</Etiqueta>}
        <span className="esc-quem">{!o ? "carregando…" : novo ? "sai da caixa do hotel, pelo Outlook do PC dono" : `${o.nome} · ${o.hotel}`}</span>
        {aoMinimizar && <button type="button" className="esc-min" onClick={() => aoMinimizar(assunto || para)} title="Minimizar: o e-mail fica guardado embaixo, à direita" aria-label="Minimizar"><Icone nome="seta" tamanho={16} /></button>}
        <Botao tipo="fantasma" pequeno onClick={aoFechar} titulo="Descartar e voltar">Descartar</Botao>
      </div>
      {erroO ? <p className="esc-erro">{erroO}</p> : !o ? <p className="esc-carregando">Carregando…</p> : (
        <div className="esc-corpo">
          <div className="esc-cab">
            <div className="esc-coluna">
              <button type="button" className="esc-enviar" disabled={!pronto} onClick={() => enviar()} title={porQueNao || "Enviar pela caixa do hotel"}>
                <Icone nome="enviar" tamanho={18} />{enviando ? "Enviando…" : "Enviar"}</button>
              {!enc && <button type="button" className="esc-lig" aria-pressed={ligacao} onClick={() => setLigacao(!ligacao)}
                title="O hóspede pediu por telefone? Marque aqui (Alt+L). Não vai no e-mail, só conta no Painel."><Icone nome={ligacao ? "check" : "telefone"} tamanho={15} />Ligação</button>}
            </div>
            <div className="esc-campos">
              <div className="esc-linha"><span className="rot">De</span>
                {novo ? <ComboDe o={o} conta={contaDe} escolher={escolherDe} />
                  : o.destino ? <span className="esc-de"><b>{o.conta_de}</b> <small>{o.destino === o.este_pc ? "· por este PC" : `· pelo PC ${o.destino}`}</small></span>
                  : <span className="esc-de alerta">{o.motivo} Enviar por: <select value={contaLocal} onChange={(ev) => setContaLocal(ev.target.value)}>{(o.contas_locais || []).map((c) => <option key={c}>{c}</option>)}</select></span>}
              </div>
              <label className="esc-linha"><span className="rot">Para</span>
                <input ref={campoPara} value={para} onChange={(ev) => setPara(ev.target.value)} list="esc-paras" autoComplete="off" spellCheck={false} />
                <datalist id="esc-paras">{(o.para || []).map((p) => <option key={p} value={p} />)}</datalist></label>
              {!enc && <label className="esc-linha"><span className="rot">Cc</span><input value={cc} onChange={(ev) => setCc(ev.target.value)} placeholder="opcional" autoComplete="off" spellCheck={false} /></label>}
              <label className="esc-linha"><span className="rot">Assunto</span>
                <input value={assunto} readOnly={enc} placeholder="NF 1212 - NOME DO HÓSPEDE" onChange={(ev) => { manual.current = !!ev.target.value.trim(); setAssunto(ev.target.value); }} /></label>
            </div>
          </div>

          {!enc && (
            <div className={`esc-soltar${sobre ? " sobre" : ""}${anexos.length ? " tem" : ""}`} role="button" tabIndex={0}
              onClick={(ev) => { if (!ev.target.closest("[data-tirar]")) arquivo.current?.click(); }}
              onKeyDown={(ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); arquivo.current?.click(); } }}
              onDragEnter={(ev) => { ev.preventDefault(); setSobre(true); }} onDragOver={(ev) => { ev.preventDefault(); setSobre(true); }}
              onDragLeave={() => setSobre(false)} onDrop={(ev) => { ev.preventDefault(); setSobre(false); adicionarArquivos(ev.dataTransfer.files); }}>
              <input ref={arquivo} type="file" accept=".pdf,.xml" multiple hidden onChange={(ev) => { adicionarArquivos(ev.target.files); ev.target.value = ""; }} />
              <span className="esc-soltar-txt"><Icone nome="clipe" tamanho={16} />
                {novo ? <span>Anexar arquivo <b>(opcional)</b> · arraste aqui ou <u>clique para escolher</u></span>
                  : <span><b>Arraste a nota fiscal aqui</b> ou <u>clique para escolher</u> · PDF ou XML · pode mais de um (nota dividida){resposta ? " · opcional numa resposta" : ""}</span>}</span>
              {anexos.length > 0 && <span className="esc-chips">{anexos.map((a, i) => (
                <span key={a.nome + i} className="esc-chip"><Icone nome="nota" tamanho={14} />{a.nome}<small>{a.bytes ? tamanho(a.bytes) : "Dropbox"}</small>
                  <button type="button" data-tirar aria-label={`Tirar ${a.nome}`} onClick={() => trocarAnexos(anexos.filter((_, k) => k !== i))}><Icone nome="fechar" tamanho={12} /></button></span>
              ))}</span>}
            </div>
          )}
          {(o.avisos_nf || []).map((t) => <p key={t} className="esc-aviso" role="note">{t}</p>)}
          {(o.sugestoes || []).length > 0 && (
            <div className="esc-sug"><span className="rot">Do Dropbox:</span>
              {o.sugestoes.map((a) => (
                <button key={a.rel} type="button" className={`esc-sug-b${a.outra || a.possivel ? "" : " forte"}`} title={a.prova || ""} onClick={() => escolherSugestao(a)}>
                  <Icone nome="nota" tamanho={14} />{a.nome}{a.outra ? <em className="am">outra nota</em> : a.possivel ? <em className="am">possível</em> : a.mais_nova ? <em>mais nova</em> : null}</button>
              ))}
              {o.sugestoes.some((a) => a.outra || a.possivel) && <p className="esc-sug-aviso">{o.sugestoes.filter((a) => a.outra || a.possivel).map((a) => `${a.outra ? "Outra nota" : "Possível"} · ${a.nome}: ${a.prova || ""}`).join(" | ")}. Clique para anexar; nada vem marcado.</p>}
            </div>
          )}
          {conferencia && (
            <div className="esc-conferir" role="alert">
              <b>{conferencia.length} ponto{conferencia.length > 1 ? "s" : ""} para conferir antes de enviar</b>
              {conferencia.map((a) => <div key={a}>{a}</div>)}
              <div className="esc-conferir-bts">
                <Botao tipo="principal" pequeno onClick={() => { setConferencia(null); enviar(undefined, true); }}>Conferi, pode enviar</Botao>
                <Botao pequeno onClick={() => setConferencia(null)}>Voltar e corrigir</Botao>
              </div>
            </div>
          )}
          {!enc && (
            <div className="esc-sug modelos"><span className="rot">Respostas prontas:</span>
              {MODELOS_RESPOSTA.map(([rot], i) => <button key={rot} type="button" className="esc-sug-b" title="Preenche a mensagem (dá para editar depois)" onClick={() => usarModelo(i)}>{rot}</button>)}
            </div>
          )}
          <textarea ref={campoMsg} className={`esc-msg${o.assinatura_com_mensagem ? " curto" : ""}`} value={msg} onChange={(ev) => setMsg(ev.target.value)} spellCheck
            aria-label="Mensagem" placeholder={enc ? "Mensagem (dá para editar) — o e-mail original vai junto, embaixo." : o.assinatura_com_mensagem ? "Escreva aqui só se quiser acrescentar algo — a mensagem padrão já vem na assinatura abaixo." : ""} />
          {(o.selos || []).length > 0 ? (
            <div className="esc-assinatura">
              <div className="esc-selo">{seloAtual?.texto ? <div className="esc-selo-txt">{seloAtual.texto.map((l) => <div key={l}>{l}</div>)}</div>
                : selo && <img src={`/assinaturas/${encodeURIComponent(selo)}.png`} alt={`Assinatura de ${seloAtual?.nome || ""}`} />}</div>
              <div className="esc-sug"><span className="rot">Assinatura:</span>
                {o.selos.map((s) => <button key={s.id} type="button" className={`esc-sug-b${s.id === selo ? " sel" : ""}`} aria-pressed={s.id === selo} onClick={() => { setSelo(s.id); guardar("selo_nf", s.id); }}>{s.nome}</button>)}</div>
            </div>
          ) : o.assinatura ? (
            <div className="esc-assinatura"><iframe className="esc-ass-html" sandbox="allow-same-origin" title="Assinatura" srcDoc={`<html><body style="margin:0;background:#fff">${o.assinatura}</body></html>`}
              onLoad={(ev) => { try { ev.target.style.height = ev.target.contentDocument.body.scrollHeight + 8 + "px"; } catch { ev.target.style.height = "230px"; } }} />
              <p className="esc-dica">Mensagem padrão e selo da caixa {o.conta_de}, como no Outlook (prévia deste PC; sai a do PC que enviar)</p></div>
          ) : !enc && <p className="esc-dica">Sem assinatura do Outlook para {o.conta_de} neste PC.</p>}
          {citacao && <div className="esc-citacao" aria-label="Mensagem original">{citacao}</div>}
        </div>
      )}
      {(res || falha) && (
        <div className="esc-rodape" role="status">
          {falha ? <span className="esc-falha"><b>Não deu para enviar pela caixa do hotel.</b> {falha.motivo}
            {falha.contas.length > 0 && <span className="esc-alt"> Enviar por: <select value={contaLocal || falha.contas[0]} onChange={(ev) => setContaLocal(ev.target.value)}>{falha.contas.map((c) => <option key={c}>{c}</option>)}</select>
              <Botao pequeno onClick={() => enviar(contaLocal || falha.contas[0], true)}>Enviar por esta</Botao></span>}</span>
            : <span>{res}</span>}
        </div>
      )}
    </section>
  );
}

// "De" do Novo e-mail com busca: digita parte do hotel, da caixa ou do agente (sem acento); setas e Enter escolhem
function ComboDe({ o, conta, escolher }) {
  const rot = (c) => `${c.hotel} · ${c.conta} · ${c.pc === o.este_pc ? "este PC" : "PC de " + c.agente}${c.online ? "" : " (desligado: sai quando ligar)"}`;
  const atual = o.contas.find((c) => c.conta === conta) || o.contas[0];
  const [texto, setTexto] = useState(null);   // null = mostrando a escolhida
  const [ativo, setAtivo] = useState(0);
  const termos = semAcento(texto || "").split(/\s+/).filter(Boolean);
  const achados = texto === null ? [] : o.contas.filter((c) => termos.every((q) => semAcento(rot(c)).includes(q)));
  const pegar = (c) => { setTexto(null); if (c) escolher(c.conta); };
  return (
    <span className="combo-de">
      <input value={texto ?? rot(atual)} aria-label="Caixa do hotel de onde o e-mail sai (digite para filtrar)" placeholder="Digite o nome do hotel…" autoComplete="off" spellCheck={false}
        onFocus={() => { setTexto(""); setAtivo(0); }} onChange={(ev) => { setTexto(ev.target.value); setAtivo(0); }}
        onBlur={() => setTimeout(() => setTexto(null), 120)}
        onKeyDown={(ev) => {
          if (ev.key === "ArrowDown" || ev.key === "ArrowUp") { ev.preventDefault(); setAtivo((a) => Math.max(0, Math.min(achados.length - 1, a + (ev.key === "ArrowDown" ? 1 : -1)))); }
          else if (ev.key === "Enter") { ev.preventDefault(); pegar(achados[ativo]); ev.currentTarget.blur(); }
          else if (ev.key === "Escape") { ev.preventDefault(); ev.stopPropagation(); setTexto(null); ev.currentTarget.blur(); }
        }} />
      <small className="esc-de-pc">{o.destino === o.este_pc ? "· por este PC" : o.destino ? `· pelo PC ${o.destino}` : ""}</small>
      {texto !== null && (
        <span className="combo-lista" role="listbox">
          {achados.length ? achados.map((c, i) => (
            <button key={c.conta} type="button" role="option" aria-selected={i === ativo} className={i === ativo ? "ativo" : ""} onMouseDown={(ev) => { ev.preventDefault(); pegar(c); ev.currentTarget.closest(".combo-de").querySelector("input").blur(); }}>{rot(c)}</button>
          )) : <span className="combo-vazio">Nenhuma caixa com “{texto}”</span>}
        </span>
      )}
    </span>
  );
}
