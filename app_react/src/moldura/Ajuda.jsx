// Ajuda do Painel (botão "?" do rodapé, menu do operador ou a tecla ?): o que cada nome significa, onde fica cada coisa e os
// atalhos do teclado (iguais aos do Outlook). As cores das etiquetas são as mesmas da tela (Etiqueta.jsx).
import Janela from "../componentes/Janela.jsx";
import Etiqueta from "../componentes/Etiqueta.jsx";
import Botao from "../componentes/Botao.jsx";

const GLOSSARIO = [
  ["Sem NF", "azul", "nota", "Pedido que ainda não tem nota fiscal emitida."],
  ["Falta dado", "ambar", "relogio", "Falta nome, CPF/CNPJ (ou o número está errado) ou CEP para emitir. O botão “Pedir o que falta” escreve a mensagem."],
  ["NF pronta, falta enviar", "ambar", "enviar", "A nota existe nas pastas, mas o e-mail com ela ainda não saiu para o hóspede."],
  ["NF enviada", "verde", "check", "Nota pronta e enviada ao hóspede."],
  ["Correção", "ambar", "voltar", "O hóspede pediu correção ou cancelamento da nota."],
  ["Urgente", "vermelho", "bandeira", "Pede nova nota, ouvidoria, mais de 7 dias sem resposta ou alguém da equipe marcou."],
  ["÷ Nota dividida", "azul", null, "O pedido é de mais de uma nota (quartos ou partes)."],
  ["≠ CPF/CNPJ diferente", "vermelho", null, "A NF achada tem um CPF/CNPJ diferente do que o hóspede pediu. Confira antes de enviar."],
  ["Diz que não recebeu", "ambar", "envelope", "O hóspede escreveu que a nota não chegou."],
  ["Ligação", "azul", "telefone", "O pedido veio por telefone (marcado por quem enviou). Não vai no e-mail, só conta no Painel."],
  ["Formulário", "cinza", "formulario", "E-mail do Emissor Automático: os dados vêm na tabela. Clicar abre a ficha do hóspede."],
];
const ONDE = [
  ["Caixa de entrada", "Os e-mails das caixas dos hotéis dos 4 PCs. Em cima da lista: Todas, Não lidos, Urgência, Formulários e Enviados (72 h)."],
  ["Robô", "O que o robô está fazendo (Agora), o que já fez (Registro) e o botão de ligar ou pausar."],
  ["Visão geral", "O resumo do dia em perguntas, com os números reais."],
  ["Monitoramento", "Os PCs da equipe, atualizar os PCs e o cadastro de hotéis. Só o administrador vê."],
];
const ATALHOS = [["Ctrl+R", "Responder o e-mail aberto"], ["Ctrl+Shift+R", "Responder com a NF"], ["Ctrl+F", "Encaminhar"],
  ["Delete", "Excluir (com Desfazer de 10 s)"], ["Ctrl+Q", "Marcar como lido"], ["Ctrl+U", "Marcar como não lido"],
  ["Ctrl+K", "Ir para a pesquisa (Ctrl+E também)"], ["↑ ↓", "E-mail anterior / próximo (já abre)"], ["Alt+L", "Marcar “Ligação” ao escrever"],
  ["Esc", "Fechar o e-mail ou a janela"], ["F5", "Recarregar a tela"], ["?", "Abrir esta ajuda"]];

export default function Ajuda({ aoFechar }) {
  return (
    <Janela titulo="Ajuda do Painel" sub="O que cada nome significa, onde fica cada coisa e os atalhos do teclado (iguais aos do Outlook)"
      aoFechar={aoFechar} largura={860} classe="ajuda" rodape={<Botao tipo="principal" onClick={aoFechar}>Entendi</Botao>}>
      <div className="ajuda-corpo">
        <section><h4>O que significa</h4>
          <dl>{GLOSSARIO.map(([t, tipo, icone, d]) => <div key={t}><dt><Etiqueta tipo={tipo} icone={icone || undefined}>{t}</Etiqueta></dt><dd>{d}</dd></div>)}</dl>
        </section>
        <section><h4>Onde fica cada coisa</h4>
          <dl>{ONDE.map(([t, d]) => <div key={t}><dt><b>{t}</b></dt><dd>{d}</dd></div>)}</dl>
          <h4>Atalhos do teclado</h4>
          <dl className="ajuda-atalhos">{ATALHOS.map(([k, d]) => <div key={k}><dt>{k.split(" ").map((x) => <kbd key={x}>{x}</kbd>)}</dt><dd>{d}</dd></div>)}</dl>
          <p className="dica">Os atalhos de e-mail valem na Caixa de entrada, com um e-mail aberto.</p>
        </section>
      </div>
    </Janela>
  );
}
