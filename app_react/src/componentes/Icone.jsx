// Os ícones de linha do Painel (nunca emoji). Um nome, um desenho: <Icone nome="enviar" />.
const DESENHOS = {
  casa: <><path d="M4 11l8-7 8 7v9H4z" /><path d="M10 20v-5h4v5" /></>,
  caixa: <><path d="M4 13l2.2-8h11.6L20 13v6H4z" /><path d="M4 13h5l1 2.5h4L15 13h5" /></>,
  alerta: <><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17v.5" /></>,
  nota: <><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5M10 13h6M10 17h6" /></>,
  robo: <><path d="M20 12a8 8 0 0 0-14-5.3L4 9" /><path d="M4 4v5h5" /><path d="M4 12a8 8 0 0 0 14 5.3L20 15" /><path d="M20 20v-5h-5" /></>,
  pc: <><rect x="3" y="4" width="18" height="12" rx="2" /><path d="M8 20h8M12 16v4" /></>,
  cadeado: <><rect x="5" y="11" width="14" height="9" rx="2" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></>,
  rede: <><circle cx="12" cy="5.5" r="2" /><circle cx="5.5" cy="18" r="2" /><circle cx="18.5" cy="18" r="2" /><path d="M12 7.5V12M12 12l-5 4.5M12 12l5 4.5" /></>,
  enviar: <><path d="M21 3L3 10.5l7 3 3 7z" /><path d="M10 13.5L21 3" /></>,
  seta: <path d="M6 9l6 6 6-6" />, esquerda: <path d="M15 6l-6 6 6 6" />, direita: <path d="M9 6l6 6-6 6" />,
  sino: <><path d="M6 16V11a6 6 0 0 1 12 0v5l1.5 2h-15z" /><path d="M10 20a2 2 0 0 0 4 0" /></>,
  tema: <><circle cx="12" cy="12" r="8" /><path d="M12 4a8 8 0 0 1 0 16z" fill="currentColor" /></>,
  ajuda: <><circle cx="12" cy="12" r="9" /><path d="M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17v.5" /></>,
  busca: <><circle cx="11" cy="11" r="6.5" /><path d="M16 16l4.5 4.5" /></>,
  novo: <path d="M4 20l1-4L16.5 4.5a2 2 0 0 1 3 3L8 19z" />,
  responder: <><path d="M9 7L4 12l5 5" /><path d="M4 12h9a7 7 0 0 1 7 7" /></>,
  responderTodos: <><path d="M8 7L3 12l5 5" /><path d="M13 7l-5 5 5 5" /><path d="M8 12h5a7 7 0 0 1 7 7" /></>,
  encaminhar: <><path d="M15 7l5 5-5 5" /><path d="M20 12h-9a7 7 0 0 0-7 7" /></>,
  lido: <><rect x="4" y="6" width="16" height="12" rx="2" /><path d="M4 8l8 5 8-5" /></>,
  bandeira: <path d="M6 21V4h11l-2 4 2 4H6" />,
  check: <path d="M5 12.5l4.5 4.5L19 7.5" />,
  relogio: <><circle cx="12" cy="12" r="8.5" /><path d="M12 7v5l3 2" /></>,
  nuvem: <path d="M7 18a4 4 0 0 1-.6-7.96A6 6 0 0 1 18 9.5 4.3 4.3 0 0 1 17.5 18z" />,
  livro: <><path d="M5 4h10a4 4 0 0 1 4 4v12H9a4 4 0 0 1-4-4z" /><path d="M9 4v12" /></>,
  envelope: <><rect x="3.5" y="6" width="17" height="12" rx="2" /><path d="M4 8l8 5.5L20 8" /></>,
  atualizar: <path d="M20 11a8 8 0 00-14-5L4 8M4 4v4h4M4 13a8 8 0 0014 5l2-2M20 20v-4h-4" />,
  voltar: <><path d="M9 14L4 9l5-5" /><path d="M4 9h10a6 6 0 0 1 0 12h-3" /></>,
};

export default function Icone({ nome, tamanho = 18, titulo }) {
  return (
    <svg className="ico" width={tamanho} height={tamanho} viewBox="0 0 24 24" aria-hidden={titulo ? undefined : true} role={titulo ? "img" : undefined} aria-label={titulo}>
      {DESENHOS[nome]}
    </svg>
  );
}
