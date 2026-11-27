// As ações num e-mail. Todas rodam no Outlook do PC dono da caixa, sem abrir janela, e valem para a equipe toda.
// A tela muda NA HORA (o "ajuste" local) e a próxima leitura do servidor confirma. Excluir, tirar da entrada e concluir
// têm 10 s de "Desfazer": só depois disso o pedido sai daqui. Nada é apagado de verdade (vai para Itens Excluídos ou "NF enviada").
import { useCallback, useState } from "react";
import { api } from "../../api.js";
import { useAvisos } from "../../componentes/Avisos.jsx";

const VALE_MS = 45000;   // o ajuste local vale até o servidor contar a mesma coisa

export default function useAcoesCorreio(reler) {
  const { recado, desfazer } = useAvisos();
  const [ajustes, setAjustes] = useState({});       // id -> { lido, urgente, motivo_urgencia, ligacao, em }
  const [escondidos, setEscondidos] = useState({}); // id -> true (excluído / movido, esperando o Desfazer)
  const [respondidos, setRespondidos] = useState({}); // id -> true: a resposta saiu, a linha fica cinza até sumir

  const ajustar = (id, campos) => setAjustes((a) => ({ ...a, [id]: { ...a[id], ...campos, em: Date.now() } }));
  const esconder = (ids, sim) => setEscondidos((x) => { const n = { ...x }; ids.forEach((i) => (sim ? (n[i] = true) : delete n[i])); return n; });

  // a lista com o que mudou aqui e ainda não voltou do servidor
  const aplicar = useCallback((lista) => {
    const agora = Date.now();
    return (lista || []).filter((e) => !escondidos[e.id]).map((e) => {
      const a = ajustes[e.id];
      return a && agora - a.em < VALE_MS ? { ...e, ...a, respondido: e.respondido || !!respondidos[e.id] } : respondidos[e.id] ? { ...e, respondido: true } : e;
    });
  }, [ajustes, escondidos, respondidos]);

  const lido = useCallback((e, sim, avisar = true) => {
    if (!e || e.pasta === "enviado") return;
    api("/api/correio/evento", { ids: [e.id], acao: sim ? "LIDO" : "NAO_LIDO" });
    ajustar(e.id, { lido: sim });
    if (avisar) recado(sim ? "Marcado como lido para a equipe" : "Marcado como não lido para a equipe");
  }, [recado]);

  const urgencia = useCallback(async (e, sim) => {
    const antes = { urgente: e.urgente, motivo_urgencia: e.motivo_urgencia };
    ajustar(e.id, { urgente: sim, motivo_urgencia: sim ? "Marcado como urgente" : "" });
    const r = await api("/api/correio/urgencia", { id: e.id, marcar: sim ? "urgente" : "normal" });
    if (r.ok === false) { ajustar(e.id, antes); return recado(r.motivo || r.erro || "Não deu para marcar agora", true); }
    recado(sim ? "Marcado como urgente para a equipe (fica no Outlook do PC dono)" : "Urgência tirada para a equipe");
  }, [recado]);

  const ligacao = useCallback(async (e, sim) => {
    ajustar(e.id, { ligacao: sim });
    const r = await api("/api/ligacao", { id: e.id, marcar: sim });
    if (r.ok === false) { ajustar(e.id, { ligacao: !sim }); return recado(r.motivo || r.erro || "Não deu para marcar agora", true); }
    recado(sim ? "Marcado como ligação: já conta na Visão geral" : "Marca de ligação tirada");
  }, [recado]);

  // some na hora; 10 s para desfazer; depois o pedido vai ao PC dono
  const comDesfazer = useCallback((ids, msg, caminho, corpo, desfeito) => {
    esconder(ids, true);
    desfazer(msg, () => esconder(ids, false), async () => {
      const r = await api(caminho, corpo);
      if (r.ok === false) { esconder(ids, false); recado(r.motivo || r.erro || "Não deu certo agora", true); }
      else if (r.aviso) recado(r.aviso);
      reler?.();
    }, desfeito);
  }, [desfazer, recado, reler]);

  const excluir = useCallback((e) => comDesfazer([e.id], "E-mail excluído", "/api/correio/excluir",
    { id: e.id, entry: e.entry || "", caixa: e.caixa || "", de: e.de || "", nome: e.nome || "", hotel: e.hotel || "", assunto: e.assunto || "" }, "Exclusão desfeita"), [comDesfazer]);
  const tirarDaEntrada = useCallback((e) => comDesfazer([e.id], "E-mail movido para “NF enviada”", "/api/correio/mover_nf", { id: e.id }, "Movimento desfeito"), [comDesfazer]);
  const respondeu = useCallback((e, todos) => setRespondidos((x) => { const n = { ...x }; (todos?.length ? todos : [e]).forEach((m) => (n[m.id] = true)); return n; }), []);

  return { aplicar, lido, urgencia, ligacao, excluir, tirarDaEntrada, respondeu, respondidos };
}
