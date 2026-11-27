// O botão "Enviar NF" do Painel inteiro. Caixa de entrada, e-mail aberto, ficha do hóspede, novo e-mail:
// todas as telas usam ESTA peça. Mudou aqui, muda em todas.
//   hospede: primeiro nome de quem recebe ("Enviar NF para Olívia") — evita enviar para a pessoa errada (Nielsen 5)
//   semEmail: nenhum e-mail aberto → o botão fica apagado e a dica diz por quê
import Botao from "./Botao.jsx";
import { abrirNaTelaDeHoje } from "../api.js";

export default function BotaoEnviarNF({ hospede, semEmail, pequeno, aoClicar }) {
  const texto = hospede ? `Enviar NF para ${hospede.split(" ")[0]}` : "Enviar NF";
  const dica = semEmail ? "Abra um e-mail para enviar a NF" : "Responde ao hóspede com o PDF da nota, pela caixa do hotel";
  // Por enquanto o envio de verdade acontece na tela de hoje (com a conferência de CPF/CNPJ e valor); a tela nova leva até lá.
  const clicar = aoClicar || (() => abrirNaTelaDeHoje("correio"));
  return <Botao tipo="verde" icone="nota" titulo={dica} desligado={semEmail} pequeno={pequeno} onClick={clicar}>{texto}</Botao>;
}
