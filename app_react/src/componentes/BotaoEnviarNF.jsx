// O botão "Enviar NF" do Painel inteiro. Faixa de comandos, e-mail aberto, ficha do pedido, ficha do hóspede:
// todas as telas usam ESTA peça. Mudou aqui, muda em todas.
//   hospede: primeiro nome de quem recebe ("Enviar NF para Olívia") — evita enviar para a pessoa errada (Nielsen 5)
//   semEmail: nenhum e-mail aberto → o botão fica apagado e a dica diz por quê
//   aoClicar: abre a tela de escrever com a NF (a conferência de CPF/CNPJ e valor acontece antes de sair)
import Botao from "./Botao.jsx";

export default function BotaoEnviarNF({ hospede, semEmail, pequeno, aoClicar }) {
  const texto = hospede ? `Enviar NF para ${String(hospede).trim().split(" ")[0]}` : "Enviar NF";
  const dica = semEmail ? "Abra um e-mail para enviar a NF" : "Responde ao hóspede com o PDF da nota, pela caixa do hotel (Ctrl+Shift+R)";
  return <Botao tipo="verde" icone="nota" titulo={dica} desligado={semEmail || !aoClicar} pequeno={pequeno} onClick={aoClicar}>{texto}</Botao>;
}
