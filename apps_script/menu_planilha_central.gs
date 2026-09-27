// SOLICITAÇÕES NF — menu da Planilha Central! (Krz)
// VERSÃO: 2026-09-26b
// Instalar: Extensões > Apps Script > arquivo "menu_nf" > colar tudo > Ctrl+S > F5 na planilha.
// Este script só LÊ e grava pedidos na aba Status — quem envia e-mail é o robô no computador.

var MARCADOR_RESPOSTAS = '(respostas)';
var ABA_CADASTRO = 'Cadastro_Hoteis';

// Mesmo apelido do config.json do robô: nome na aba -> nome no cadastro.
var APELIDOS_HOTEIS = {
  'governador valadares': 'gv'
};


// --- Menu — pra acrescentar um item no futuro, é só uma linha ---
function onOpen() {
  var ui;
  try {
    ui = SpreadsheetApp.getUi();
  } catch (e) {
    // Acontece quando alguém clica em "Executar" aqui no editor: o menu só
    Logger.log('Não precisa rodar pelo editor. Abra a Planilha Central e aperte F5: ' +
               'o menu "🧾 Solicitações NF" aparece sozinho no topo.');
    return;
  }
  ui.createMenu('🧾 Solicitações NF')
    .addItem('🔎 Buscar hotel', 'abrirBuscaHotel')
    .addSeparator()
    .addItem('📋 Verificar Pendências', 'verificarPendencias')
    .addItem('⚡ Ativar Claudio', 'ativarClaudio')
    .addItem('✉ Envio Separado', 'envioSeparado')
    .addSeparator()
    .addItem('📜 Log de Envios', 'abrirLogDeEnvios')
    .addItem('📊 Cota de Envio', 'abrirCotaEnvio')
    .addItem('🔍 Conferir Cópia dos Hotéis', 'abrirConferenciaCopia')
    .addToUi();
}


// --- 🔎 Buscar hotel ---
function abrirBuscaHotel() {
  var html = HtmlService.createHtmlOutput(_htmlBuscaHotel()).setWidth(1800).setHeight(900);
  SpreadsheetApp.getUi().showModelessDialog(html, 'Buscar hotel');
}

/** Chamado pela janela de busca: lista de todas as abas, com hotel e agente. */
function listarAbasParaBusca() {
  var planilha = SpreadsheetApp.getActiveSpreadsheet();
  var agentes = _agentesPorHotel(planilha);
  return planilha.getSheets().map(function (aba) {
    var nome = aba.getName();
    var ehHotel = nome.toLowerCase().indexOf(MARCADOR_RESPOSTAS) !== -1;
    var hotel = ehHotel ? _hotelDaAba(nome) : nome;
    var chave = _normalizar(hotel);
    chave = APELIDOS_HOTEIS[chave] || chave;
    return {
      aba: nome,
      hotel: hotel,
      ehHotel: ehHotel,
      agente: ehHotel ? (agentes[chave] || '') : ''
    };
  });
}

/** Chamado pela janela de busca: vai pra aba clicada. */
function irParaAba(nomeAba) {
  var aba = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(nomeAba);
  if (!aba) {
    throw new Error('A aba "' + nomeAba + '" não existe mais (foi renomeada ou apagada). Feche (Esc) e abra a busca de novo pra atualizar a lista.');
  }
  aba.activate();
  aba.getRange('A1').activate();
  return nomeAba;
}

/** {hotel normalizado: agente} lido do Cadastro_Hoteis (A = hotel, C = agente). */
function _agentesPorHotel(planilha) {
  var mapa = {};
  var cadastro = planilha.getSheetByName(ABA_CADASTRO);
  if (!cadastro || cadastro.getLastRow() === 0) return mapa;
  var valores = cadastro.getRange(1, 1, cadastro.getLastRow(), 3).getDisplayValues();
  valores.forEach(function (linha) {
    var hotel = _normalizar(linha[0]);
    if (hotel && !mapa[hotel]) mapa[hotel] = String(linha[2]).trim();
  });
  return mapa;
}

/** 'Solicitação Nota Fiscal (MERCADO) (respostas)' -> 'MERCADO' (mesma regra do robô). */
function _hotelDaAba(nomeAba) {
  var partes = [];
  var regex = /\(([^)]*)\)/g;
  var achado;
  while ((achado = regex.exec(nomeAba)) !== null) {
    if (_normalizar(achado[1]) !== 'respostas') partes.push(achado[1].trim());
  }
  return partes.length ? partes[0] : nomeAba;
}

function _normalizar(texto) {
  return String(texto || '').normalize('NFD').replace(/[\u0300-\u036f]/g, '')
    .toLowerCase().replace(/\s+/g, ' ').trim();
}

function _htmlBuscaHotel() {
  return '<!DOCTYPE html><html><head><base target="_top"><style>' +
    ':root{--principal:#d5bda1;--principal2:rgba(213,189,161,.6);--fundo:#173f39;--card:rgba(213,189,161,.05);--linha:rgba(213,189,161,.22);--texto:#d5bda1;--apagado:rgba(213,189,161,.68);}' +
    '*{box-sizing:border-box;}' +
    'html,body{margin:0;height:100%;background:var(--fundo);' +
    '  color:var(--texto);font-family:"Segoe UI",Arial,sans-serif;overflow:hidden;}' +
    '.caixa{padding:28px 24px;height:100%;display:flex;flex-direction:column;max-width:980px;margin:0 auto;}' +
    '.titulo{font-size:11px;letter-spacing:4px;text-transform:uppercase;color:var(--principal);margin-bottom:12px;}' +
    '.titulo b{color:var(--texto);letter-spacing:2px;}' +
    '.busca{position:relative;}' +
    '#busca{width:100%;padding:16px 18px 16px 46px;font-size:18px;color:var(--texto);background:var(--card);' +
    '  border:none;border-radius:14px;outline:none;transition:.2s;}' +
    '#busca:focus{border-color:var(--principal);box-shadow:0 0 0 3px rgba(213,189,161,.15),0 0 24px rgba(213,189,161,.18);}' +
    '#busca::placeholder{color:var(--apagado);}' +
    '.lupa{position:absolute;left:17px;top:50%;transform:translateY(-50%);color:var(--principal);font-size:18px;}' +
    '.info{display:flex;justify-content:space-between;color:var(--apagado);font-size:11px;margin:10px 2px 8px;}' +
    '.tecla{border:none;border-radius:4px;padding:0 5px;margin:0 2px;color:var(--texto);}' +
    '#lista{flex:1;overflow-y:auto;padding-right:4px;}' +
    '#lista::-webkit-scrollbar{width:6px;}#lista::-webkit-scrollbar-thumb{background:var(--linha);border-radius:3px;}' +
    '.item{display:flex;align-items:center;justify-content:space-between;padding:11px 14px;margin-bottom:6px;' +
    '  background:var(--card);border:none;border-radius:10px;cursor:pointer;transition:.12s;}' +
    '.item:hover{border-color:var(--linha);}' +
    '.item.sel{border-color:var(--principal);background:linear-gradient(90deg,rgba(213,189,161,.14),var(--card));' +
    '  box-shadow:0 0 18px rgba(213,189,161,.12);}' +
    '.nome{font-size:15px;font-weight:600;}' +
    '.aba{font-size:10.5px;color:var(--apagado);margin-top:2px;}' +
    '.chip{font-size:11px;padding:3px 10px;border-radius:20px;border:1px solid var(--principal2);color:var(--principal);white-space:nowrap;}' +
    '.chip.sem{border-color:#d5bda1;color:#d5bda1;}' +
    '.vazio{text-align:center;color:var(--apagado);padding:40px 0;}' +
    '#msg{color:#d5bda1;font-size:12px;min-height:16px;margin-top:6px;}' +
    '</style></head><body><div class="caixa">' +
    '<div class="titulo">Rede Andrade · <b>Solicitações NF</b></div>' +
    '<div class="busca"><span class="lupa">⌕</span>' +
    '<input id="busca" placeholder="Hotel ou agente..." autocomplete="off" autofocus></div>' +
    '<div class="info"><span id="contagem">Carregando...</span>' +
    '<span><span class="tecla">↑</span><span class="tecla">↓</span> escolher · <span class="tecla">Enter</span> abrir · ' +
    '<span class="tecla">Esc</span> fechar</span></div>' +
    '<div id="lista"></div><div id="msg"></div></div>' +
    '<script>' +
    'var ABAS=[],VISIVEIS=[],SEL=0;' +
    'function normalizar(t){return String(t||"").normalize("NFD").replace(/[\\u0300-\\u036f]/g,"").toLowerCase().replace(/\\s+/g," ").trim();}' +
    'function esc(t){return String(t).replace(/[&<>"\']/g,function(c){return {"&":"&amp;","<":"&lt;",">":"&gt;","\\"":"&quot;","\'":"&#39;"}[c];});}' +
    'function filtrar(){' +
    '  var termos=normalizar(document.getElementById("busca").value).split(" ").filter(Boolean);' +
    '  VISIVEIS=ABAS.filter(function(a){var alvo=normalizar(a.hotel+" "+a.agente+" "+a.aba);' +
    '    return termos.every(function(t){return alvo.indexOf(t)!==-1;});})' +
    '    .sort(function(x,y){if(x.ehHotel!==y.ehHotel)return x.ehHotel?-1:1;return normalizar(x.hotel)<normalizar(y.hotel)?-1:1;});' +
    '  SEL=0;desenhar();' +
    '}' +
    'function desenhar(){' +
    '  var total=ABAS.filter(function(a){return a.ehHotel;}).length;' +
    '  var achados=VISIVEIS.filter(function(a){return a.ehHotel;}).length;' +
    '  document.getElementById("contagem").textContent=achados+" de "+total+" hotéis";' +
    '  if(!VISIVEIS.length){document.getElementById("lista").innerHTML="<div class=vazio>Nenhum hotel encontrado</div>";return;}' +
    '  document.getElementById("lista").innerHTML=VISIVEIS.map(function(a,i){' +
    '    var chip=a.ehHotel?(a.agente?"<span class=chip>"+esc(a.agente)+"</span>":"<span class=\'chip sem\'>sem agente</span>"):"";' +
    '    return "<div class=\'item"+(i===SEL?" sel":"")+"\' data-i=\'"+i+"\'><div><div class=nome>"+esc(a.ehHotel?a.hotel:a.aba)+"</div>"+' +
    '      (a.ehHotel?"<div class=aba>"+esc(a.aba)+"</div>":"")+"</div>"+chip+"</div>";}).join("");' +
    '  document.querySelectorAll(".item").forEach(function(el){' +
    '    el.onclick=function(){SEL=+el.getAttribute("data-i");abrir();};' +
    '    el.onmouseenter=function(){SEL=+el.getAttribute("data-i");marcar();};});' +
    '}' +
    'function marcar(){' +
    '  document.querySelectorAll(".item").forEach(function(el,i){el.classList.toggle("sel",i===SEL);});' +
    '  var el=document.querySelector(".item.sel");if(el)el.scrollIntoView({block:"nearest"});' +
    '}' +
    'function abrir(){' +
    '  var a=VISIVEIS[SEL];if(!a)return;' +
    '  document.getElementById("msg").textContent="Abrindo "+(a.ehHotel?a.hotel:a.aba)+"...";' +
    '  google.script.run.withSuccessHandler(function(){google.script.host.close();})' +
    '    .withFailureHandler(function(e){document.getElementById("msg").textContent=e.message;}).irParaAba(a.aba);' +
    '}' +
    'document.getElementById("busca").addEventListener("input",filtrar);' +
    'document.addEventListener("keydown",function(ev){' +
    '  if(ev.key==="ArrowDown"){SEL=Math.min(SEL+1,VISIVEIS.length-1);marcar();ev.preventDefault();}' +
    '  else if(ev.key==="ArrowUp"){SEL=Math.max(SEL-1,0);marcar();ev.preventDefault();}' +
    '  else if(ev.key==="Enter"){abrir();}' +
    '  else if(ev.key==="Escape"){google.script.host.close();}' +
    '});' +
    'google.script.run.withSuccessHandler(function(abas){ABAS=abas;filtrar();})' +
    '  .withFailureHandler(function(e){document.getElementById("msg").textContent=e.message;}).listarAbasParaBusca();' +
    '</script></body></html>';
}


// --- 📋 VERIFICAR PENDÊNCIAS  +  ⚡ ATIVAR CLAUDIO ---

var ABA_STATUS = 'Status';
var LINHA_STATUS = { LIGADO: 1, COMANDO: 7, PEDIDO: 8, RESPOSTA: 9, VERIFICACAO: 10, CONFIG: 11, ONLINE: 12, SELECAO: 13, COTA: 14, ANDAMENTO: 15, CONFERENCIA: 16 };
var ROTULOS_STATUS = ['Robô ligado?', 'Última execução com sucesso', 'Resumo da última execução', 'Última tentativa',
  'Modo', 'Máquina', 'Comando', 'Pedido por', 'Resposta do robô', 'Última verificação de pendências',
  'Configuração do robô', 'Robô online (último sinal)', 'Seleção do envio separado', 'Cota de envio',
  'Andamento do envio (ao vivo)', 'Conferência da cópia (ao vivo)'];

// Quem pode usar o ⚡ Ativar Claudio. Vazio = qualquer pessoa com acesso de edição à planilha.
var EMAILS_AUTORIZADOS = [];

var MINUTOS_ROBO_ONLINE = 12;        // o robô dá sinal a cada 5 min; sem sinal há mais que isso = desligado
var PROPRIEDADE_VERIFICACAO = 'ultima_verificacao_pendencias';

// Mesmos nomes de coluna do config.json do robô
var COLUNAS = {
  enviado: ['Enviado'],
  carimbo: ['Carimbo de data/hora'],
  email: ['Endereço de e-mail', 'E-mail'],
  nome: ['Nome do Hóspede', 'Nome Tomador', 'Nome do Titular da Reserva'],
  reservaNoTomador: ['Reserva no Nome do Tomador'],
  nomePessoaFisica: ['Nome Pessoa Física'],
  notaDividida: ['Nota Dividida'],
  divididaQuantas: ['Dividida em quantas vezes', 'Dividida em quantas']
};


// --- Aba Status ---
function _abaStatus() {
  return SpreadsheetApp.getActiveSpreadsheet().getSheetByName(ABA_STATUS);
}

function _garantirRotulosStatus(aba) {
  var atuais = aba.getRange(1, 1, ROTULOS_STATUS.length, 1).getDisplayValues();
  for (var i = 0; i < ROTULOS_STATUS.length; i++) {
    if (atuais[i][0] !== ROTULOS_STATUS[i]) aba.getRange(i + 1, 1).setValue(ROTULOS_STATUS[i]);
  }
}

function _escreverStatus(linha, texto) {
  var aba = _abaStatus();
  _garantirRotulosStatus(aba);
  aba.getRange(linha, 2).setNumberFormat('@').setValue(texto);
}

/** Tudo que a tela precisa saber do robô, lido da aba Status. */
function _lerStatusRobo() {
  var aba = _abaStatus();
  if (!aba) {
    return { existe: false, ligado: false, online: false, config: _configPadrao(), comando: '', resposta: '' };
  }
  var v = aba.getRange(1, 2, ROTULOS_STATUS.length, 1).getDisplayValues().map(function (l) { return l[0]; });
  var config = _configPadrao();
  try {
    var publicada = JSON.parse(v[LINHA_STATUS.CONFIG - 1] || '{}');
    Object.keys(publicada).forEach(function (k) { config[k] = publicada[k]; });
  } catch (e) { /* robô ainda não publicou: fica o padrão */ }
  var sinal = v[LINHA_STATUS.ONLINE - 1] ? new Date(v[LINHA_STATUS.ONLINE - 1]) : null;
  var minutosSinal = (sinal && !isNaN(sinal)) ? Math.round((new Date() - sinal) / 60000) : null;
  return {
    existe: true,
    ligado: ['true', 'verdadeiro'].indexOf(_normalizar(v[LINHA_STATUS.LIGADO - 1])) !== -1,
    comando: String(v[LINHA_STATUS.COMANDO - 1] || '').toUpperCase(),
    pedido: v[LINHA_STATUS.PEDIDO - 1] || '',
    resposta: v[LINHA_STATUS.RESPOSTA - 1] || '',
    andamento: v[LINHA_STATUS.ANDAMENTO - 1] || '',
    ultimaExecucao: v[1] || '',
    resumoExecucao: v[2] || '',
    online: minutosSinal !== null && minutosSinal <= MINUTOS_ROBO_ONLINE,
    minutosSinal: minutosSinal,
    configPublicada: !!v[LINHA_STATUS.CONFIG - 1],
    config: config
  };
}

function _configPadrao() {
  return {
    modo: '?', agentes: {}, somente_hoteis: [], email_teste: '',
    abas_ignoradas: ['Solicitação Nota Fiscal (TesteEdu) (respostas)'],
    apelidos_hoteis: { 'Governador Valadares': 'GV' }, destino_envio: 'hotel'
  };
}


// --- Leitura das abas (mesmas regras do robô) ---
function _indiceColuna(cabecalhos, nomes) {
  var normalizados = cabecalhos.map(_normalizar);
  for (var i = 0; i < nomes.length; i++) {
    var pos = normalizados.indexOf(_normalizar(nomes[i]));
    if (pos !== -1) return pos;
  }
  return -1;
}

/** Descobre se a aba está em dia/mês (dados colados) ou mês/dia (Google Forms). */
function _formatoDatas(valores) {
  for (var i = 0; i < valores.length; i++) {
    var m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})/.exec(String(valores[i]).trim());
    if (!m) continue;
    if (+m[1] > 12) return 'brasileiro';
    if (+m[2] > 12) return 'americano';
  }
  return 'americano';
}

function _dataBrasileira(texto, formato) {
  var m = /^(\d{1,2})\/(\d{1,2})\/(\d{4})(.*)$/.exec(String(texto).trim());
  if (!m) return texto;
  var dia = formato === 'americano' ? m[2] : m[1];
  var mes = formato === 'americano' ? m[1] : m[2];
  return ('0' + dia).slice(-2) + '/' + ('0' + mes).slice(-2) + '/' + m[3] + m[4];
}

/**
 * Contexto que toda verificação precisa (config publicada pelo robô + Cadastro_Hoteis).
 * A tela ao vivo pega isto UMA vez e manda de volta a cada aba.
 */
function _contextoVerificacao() {
  var planilha = SpreadsheetApp.getActiveSpreadsheet();
  var robo = _lerStatusRobo();
  var cfg = robo.config;
  var normalizarMapa = function (obj) {
    var m = {};
    Object.keys(obj || {}).forEach(function (k) { if (k.charAt(0) !== '_') m[_normalizar(k)] = obj[k]; });
    return m;
  };
  var cadastro = {};
  var abaCadastro = planilha.getSheetByName(ABA_CADASTRO);
  if (abaCadastro && abaCadastro.getLastRow() > 0) {
    abaCadastro.getRange(1, 1, abaCadastro.getLastRow(), 3).getDisplayValues().forEach(function (l) {
      var chave = _normalizar(l[0]);
      if (chave && !cadastro[chave]) cadastro[chave] = { nome: String(l[0]).trim(), email: String(l[1]).trim().toLowerCase(),
                                                          agente: String(l[2]).trim() };
    });
  }
  var ignoradas = (cfg.abas_ignoradas || []).map(_normalizar);
  var abas = planilha.getSheets().map(function (a) { return a.getName(); }).filter(function (nome) {
    return nome.toLowerCase().indexOf(MARCADOR_RESPOSTAS) !== -1 && ignoradas.indexOf(_normalizar(nome)) === -1;
  });
  return {
    robo: robo, modo: cfg.modo, emailTeste: cfg.email_teste || '', destinoEnvio: cfg.destino_envio || 'agente',
    agentesEmail: normalizarMapa(cfg.agentes), apelidos: normalizarMapa(cfg.apelidos_hoteis),
    somente: (cfg.somente_hoteis || []).map(_normalizar), cadastro: cadastro, abas: abas
  };
}

/** Lê UMA aba de hotel e devolve o retrato dela (pendentes, problema, pra onde vai). Só lê. */
function _verificarAba(nomeAba, ctx) {
  var aba = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(nomeAba);
  var nomeNaAba = _hotelDaAba(nomeAba);
  var chave = _normalizar(nomeNaAba);
  chave = ctx.apelidos[chave] ? _normalizar(ctx.apelidos[chave]) : chave;
  var cad = ctx.cadastro[chave];
  var h = {
    aba: nomeAba, hotel: cad ? cad.nome : nomeNaAba, agente: cad ? cad.agente : '',
    destino: '', emailDestino: '', pendentes: [], totalLinhas: 0, jaEnviadas: 0, problema: ''
  };
  if (!cad) { h.destino = 'fora_cadastro'; }
  else if (ctx.somente.length && ctx.somente.indexOf(_normalizar(cad.nome)) === -1) { h.destino = 'fora_filtro'; }
  else if (ctx.modo === 'TESTE' && ctx.emailTeste) { h.destino = 'teste'; h.emailDestino = ctx.emailTeste; }
  else {
    // destino_envio = hotel: cada hotel recebe no próprio e-mail (coluna B do Cadastro_Hoteis)
    var email = ctx.destinoEnvio === 'hotel' ? cad.email : (ctx.agentesEmail[_normalizar(cad.agente)] || '');
    h.destino = email.indexOf('@') !== -1 ? 'ok' : (ctx.destinoEnvio === 'hotel' ? 'hotel_sem_email' : 'sem_email');
    h.emailDestino = email;
  }
  if (!aba) { h.problema = 'sumiu'; return h; }

  var valores = aba.getDataRange().getDisplayValues();
  if (!valores.length || (valores.length === 1 && !valores[0].join(''))) return h;
  var cab = valores[0].map(function (c) { return String(c).trim(); });
  var iEnv = _indiceColuna(cab, COLUNAS.enviado);
  var iCar = _indiceColuna(cab, COLUNAS.carimbo);
  h.totalLinhas = valores.length - 1;
  if (iEnv === -1 || iCar === -1) {
    h.problema = 'sem_cabecalho';
    h.totalLinhas = valores.length;
    h.primeiraLinha = cab.slice(0, 4).join(' · ');
    return h;
  }
  var iEmail = _indiceColuna(cab, COLUNAS.email), iNome = _indiceColuna(cab, COLUNAS.nome);
  var iTomador = _indiceColuna(cab, COLUNAS.reservaNoTomador), iPf = _indiceColuna(cab, COLUNAS.nomePessoaFisica);
  var iDiv = _indiceColuna(cab, COLUNAS.notaDividida), iQtd = _indiceColuna(cab, COLUNAS.divididaQuantas);
  var formato = _formatoDatas(valores.slice(1).map(function (l) { return l[iCar]; }));
  var celula = function (l, i) { return i === -1 ? '' : String(l[i] || '').trim(); };
  for (var r = 1; r < valores.length; r++) {
    var l = valores[r];
    if (!l.join('').trim()) continue;
    var enviado = _normalizar(celula(l, iEnv));
    if (['', 'false', 'falso'].indexOf(enviado) === -1) { h.jaEnviadas++; continue; }
    var carimbo = celula(l, iCar);
    if (!carimbo) continue;  // o robô também pula (não dá pra identificar)
    var nome = (_normalizar(celula(l, iTomador)) === 'sim' && celula(l, iPf)) ? celula(l, iPf) : celula(l, iNome);
    var dividida = _normalizar(celula(l, iDiv)) === 'sim' ? ('Sim' + (celula(l, iQtd) ? ' (' + celula(l, iQtd) + ')' : '')) : '';
    h.pendentes.push({
      linha: r + 1, data: _dataBrasileira(carimbo, formato), nome: nome || '—',
      email: celula(l, iEmail) || '—', dividida: dividida
    });
  }
  return h;
}

/** Junta os hotéis lidos: totais, resumo por agente; guarda pro ⚡ e escreve o resumo na aba Status. */
function _concluirVerificacao(hoteis, robo) {
  var planilha = SpreadsheetApp.getActiveSpreadsheet();
  var vaoSair = function (h) { return h.destino === 'ok' || h.destino === 'teste'; };
  var totais = { pendentes: 0, hoteisComPendencia: 0, hoteisEmDia: 0, problemas: 0, vaoSair: 0, naoVaoSair: 0 };
  var porAgente = {};
  hoteis.forEach(function (h) {
    var n = h.pendentes.length;
    if (h.problema) totais.problemas++;
    else if (n) totais.hoteisComPendencia++;
    else totais.hoteisEmDia++;
    totais.pendentes += n;
    if (!n) return;
    if (vaoSair(h)) totais.vaoSair += n; else totais.naoVaoSair += n;
    var ag = h.agente || '(sem agente)';
    porAgente[ag] = porAgente[ag] || { agente: ag, email: h.emailDestino, destino: h.destino, pendentes: 0, hoteis: [], emails: {} };
    porAgente[ag].pendentes += n;
    porAgente[ag].hoteis.push({ hotel: h.hotel, n: n, destino: h.destino });
    if (h.emailDestino) porAgente[ag].emails[h.emailDestino] = true;
    if (vaoSair(h) && !(porAgente[ag].destino === 'ok' || porAgente[ag].destino === 'teste')) porAgente[ag].destino = h.destino;
  });
  // Envio por hotel: cada hotel vai pro próprio e-mail — a tela mostra isso em vez de um e-mail só
  Object.keys(porAgente).forEach(function (k) {
    var a = porAgente[k], n = Object.keys(a.emails).length;
    if (n > 1) a.email = 'o e-mail de cada hotel (' + n + ' caixas)';
    delete a.emails;
  });
  var quem = Session.getActiveUser().getEmail() || 'menu';
  var agora = new Date();
  var resultado = {
    geradoEm: agora.toISOString(),
    geradoEmTxt: Utilities.formatDate(agora, planilha.getSpreadsheetTimeZone(), 'dd/MM/yyyy HH:mm'),
    por: quem, modo: robo.config.modo, totais: totais,
    porAgente: Object.keys(porAgente).map(function (k) { return porAgente[k]; })
      .sort(function (a, b) { return b.pendentes - a.pendentes; }),
    hoteis: hoteis.sort(function (a, b) {
      return (b.pendentes.length - a.pendentes.length) || (a.hotel < b.hotel ? -1 : 1);
    }),
    robo: robo
  };
  var resumo = { geradoEm: resultado.geradoEm, geradoEmTxt: resultado.geradoEmTxt, por: quem,
                 totais: totais, porAgente: resultado.porAgente };
  PropertiesService.getDocumentProperties().setProperty(PROPRIEDADE_VERIFICACAO, JSON.stringify(resumo));
  if (_abaStatus()) {
    _escreverStatus(LINHA_STATUS.VERIFICACAO, totais.pendentes + ' pendente(s) em ' + totais.hoteisComPendencia +
      ' hotel(éis) — ' + totais.vaoSair + ' prontas pra enviar · ' + resultado.geradoEmTxt + ' · ' + quem);
  }
  return resultado;
}

/**
 * Passa aba por aba e devolve o retrato das pendências (tudo de uma vez — usado pelo
 * ⚡ Ativar Claudio e pelo ✉ Envio Separado). A tela 📋 usa a versão ao vivo abaixo.
 */
function coletarPendencias() {
  var ctx = _contextoVerificacao();
  var hoteis = ctx.abas.map(function (nome) { return _verificarAba(nome, ctx); });
  return _concluirVerificacao(hoteis, ctx.robo);
}

// --- Versão AO VIVO (📋 Verificar Pendências): a tela chama uma aba de cada vez ---
function iniciarVerificacaoAoVivo() {
  return _contextoVerificacao();
}

function verificarAbaAoVivo(nomeAba, ctx) {
  return _verificarAba(nomeAba, ctx);
}

function concluirVerificacaoAoVivo(hoteis) {
  return _concluirVerificacao(hoteis, _lerStatusRobo());
}


// --- 📋 Verificar Pendências ---
function verificarPendencias() {
  var html = HtmlService.createHtmlOutput(_htmlPendencias()).setWidth(1800).setHeight(900);
  SpreadsheetApp.getUi().showModalDialog(html, 'Verificar Pendências');
}

/** Chamado pela tela de pendências: vai direto pra aba/linha do hotel. */
function irParaLinha(nomeAba, linha) {
  var aba = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(nomeAba);
  if (!aba) throw new Error('A aba "' + nomeAba + '" não existe mais.');
  aba.activate();
  aba.getRange(linha || 1, 1).activate();
}


// --- ⚡ Ativar Claudio ---
function ativarClaudio() {
  var html = HtmlService.createHtmlOutput(_htmlClaudio()).setWidth(1800).setHeight(900);
  SpreadsheetApp.getUi().showModalDialog(html, 'Ativar Claudio');
}

/** O que a tela do Claudio mostra ao abrir: última verificação + situação do robô. */
function obterPainelClaudio() {
  var bruto = PropertiesService.getDocumentProperties().getProperty(PROPRIEDADE_VERIFICACAO);
  var ultima = bruto ? JSON.parse(bruto) : null;
  if (ultima) ultima.minutosAtras = Math.round((new Date() - new Date(ultima.geradoEm)) / 60000);
  return { ultima: ultima, robo: _lerStatusRobo() };
}

function _autorizado() {
  if (!EMAILS_AUTORIZADOS.length) return true;
  var email = (Session.getActiveUser().getEmail() || '').toLowerCase();
  return EMAILS_AUTORIZADOS.map(function (e) { return e.toLowerCase(); }).indexOf(email) !== -1;
}

/** Grava o pedido de envio na aba Status. Quem envia é o robô no computador. */
function pedirEnvioClaudio() {
  if (!_autorizado()) throw new Error('Seu e-mail não está autorizado a ativar o Claudio (EMAILS_AUTORIZADOS no script).');
  var trava = LockService.getDocumentLock();
  if (!trava.tryLock(10000)) throw new Error('Outra pessoa está ativando agora. Tente de novo em alguns segundos.');
  try {
    var robo = _lerStatusRobo();
    if (!robo.existe) throw new Error('A aba Status ainda não existe — o robô cria ela na primeira execução.');
    if (!robo.ligado) throw new Error('O robô está DESLIGADO (aba Status, "Robô ligado?"). Marque a caixa e tente de novo.');
    if (robo.comando) throw new Error('Já existe um pedido em andamento ("' + robo.comando + '"). Aguarde terminar.');
    var quem = Session.getActiveUser().getEmail() || 'menu';
    _escreverStatus(LINHA_STATUS.PEDIDO, quem + ' | ' + new Date().toISOString());
    _escreverStatus(LINHA_STATUS.RESPOSTA, '⏳ Pedido registrado — aguardando o robô pegar (até 10 segundos)...');
    _escreverStatus(LINHA_STATUS.COMANDO, 'ENVIAR');
    return true;
  } finally {
    trava.releaseLock();
  }
}

/** A tela do Claudio pergunta isto a cada 3s enquanto o robô trabalha. */
function lerRespostaClaudio() {
  var robo = _lerStatusRobo();
  return { comando: robo.comando, resposta: robo.resposta, andamento: robo.andamento,
           online: robo.online, minutosSinal: robo.minutosSinal };
}

/** Botão ⚡ da tela de pendências: troca a janela pela do Claudio. */
function abrirClaudioDaVerificacao() {
  ativarClaudio();
}


// --- Telas (HTML). String.raw mantém as barras "\" do JavaScript da tela. ---
function _cssBase() {
  return String.raw`<style>
:root{--principal:#d5bda1;--principal2:rgba(213,189,161,.6);--fundo:#173f39;--card:rgba(213,189,161,.05);--card2:rgba(213,189,161,.1);--linha:rgba(213,189,161,.22);
  --texto:#d5bda1;--apagado:rgba(213,189,161,.68);--creme:#173f39;}
*{box-sizing:border-box;}
html,body{margin:0;height:100%;background:var(--fundo);
  color:var(--texto);font-family:"Segoe UI",Arial,sans-serif;font-size:13px;}
.rotulo{font-size:11px;letter-spacing:4px;text-transform:uppercase;color:var(--principal);}
h1{font-size:22px;margin:4px 0 2px;font-weight:600;}
.sub{color:var(--apagado);font-size:12px;}
.btn{border:1px solid var(--principal2);background:var(--card2);color:var(--texto);border-radius:10px;padding:10px 16px;
  font-size:13px;cursor:pointer;transition:.15s;font-family:inherit;}
.btn:hover{border-color:var(--principal);}
.btn.principal{background:linear-gradient(135deg,#d5bda1,#d5bda1);color:#173f39;border:none;font-weight:700;
  box-shadow:0 0 22px rgba(213,189,161,.25);}
.btn.perigo{background:linear-gradient(135deg,#d5bda1,#d5bda1);color:#173f39;border:none;font-weight:700;}
.btn:disabled{opacity:.35;cursor:not-allowed;box-shadow:none;}
.chip{display:inline-block;font-size:11px;padding:3px 10px;border-radius:20px;border:1px solid var(--principal2);
  color:var(--apagado);white-space:nowrap;margin:2px 4px 2px 0;}
.chip.ok{border-color:#d5bda1;color:#d5bda1;} .chip.mal{border-color:#d5bda1;color:#d5bda1;}
.chip.aviso{border-color:#d5bda1;color:#d5bda1;} .chip.principal{border-color:var(--principal2);color:var(--principal);}
.carregando{display:flex;flex-direction:column;align-items:center;justify-content:center;height:80vh;gap:18px;color:var(--apagado);}
.giro{width:46px;height:46px;border-radius:50%;border:3px solid var(--linha);border-top-color:var(--principal);animation:g 1s linear infinite;}
@keyframes g{to{transform:rotate(360deg)}}
table{border-collapse:collapse;width:100%;}
th{text-align:left;font-size:10.5px;letter-spacing:1px;text-transform:uppercase;color:var(--apagado);
  padding:8px 10px;border-bottom:none;font-weight:600;}
td{padding:8px 10px;border-bottom:none;vertical-align:top;}
tr:nth-child(even) td{background:rgba(213,189,161,.05);} tr:hover td{background:rgba(213,189,161,.1);}
.erro{color:#d5bda1;padding:10px 0;}
::-webkit-scrollbar{width:8px;height:8px;} ::-webkit-scrollbar-thumb{background:var(--linha);border-radius:4px;}
.chip.ok{background:#d5bda1;border-color:#d5bda1;color:#173f39;}
.chip.mal,.chip.aviso{border:1.5px dashed #d5bda1;color:#d5bda1;font-weight:600;background:transparent;}
.btn.principal{background:#d5bda1;color:#173f39;border:1px solid #d5bda1;box-shadow:none;}
.btn.perigo{background:#173f39;color:#d5bda1;border:2px solid #d5bda1;}
.btn{background:transparent;border-color:#d5bda1;color:#d5bda1;}
.btn:hover{background:rgba(213,189,161,.08);}
th{color:#d5bda1;}
.log{background:var(--card);border-radius:12px;padding:12px 16px;font-family:Consolas,"Courier New",monospace;font-size:12.5px;
  line-height:1.65;white-space:pre-wrap;overflow-y:auto;max-height:52vh;margin-top:12px;}
.log .l{padding:1px 0;} .log .l.mal{font-weight:700;} .log .l.ok{font-weight:700;}
.log .vazio{color:var(--apagado);}
.progresso{height:10px;border-radius:5px;background:rgba(213,189,161,.12);overflow:hidden;margin:12px 0 6px;}
.progresso div{height:100%;width:0;background:#d5bda1;transition:width .35s;}
</style>`;
}

function _htmlPendencias() {
  return String.raw`<!DOCTYPE html><html><head><base target="_top">` + _cssBase() + String.raw`<style>
body{overflow:hidden;}
.tela{height:100%;display:flex;flex-direction:column;padding:18px 24px 12px;}
.topo{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;}
.acoes{display:flex;gap:10px;}
.robo{margin:10px 0 12px;}
.cartoes{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:12px;}
.cartao{background:var(--card);border:none;border-radius:14px;padding:14px 16px;}
.cartao .n{font-size:30px;font-weight:700;line-height:1.1;}
.cartao .t{color:var(--apagado);font-size:11.5px;margin-top:2px;}
.cartao.destaque{border-color:var(--principal2);box-shadow:0 0 22px rgba(213,189,161,.12);}
.cartao.destaque .n{color:var(--principal);}
.barra{display:flex;gap:10px;align-items:center;margin-bottom:12px;}
#filtro{flex:1;padding:11px 14px;font-size:14px;color:var(--texto);background:var(--card);
  border:none;border-radius:10px;outline:none;font-family:inherit;}
#filtro:focus{border-color:var(--principal);}
.aba-btn{border:1px solid var(--principal2);background:transparent;color:var(--apagado);border-radius:20px;padding:7px 14px;cursor:pointer;font-family:inherit;}
.aba-btn.ativa{border-color:var(--principal);color:var(--principal);background:rgba(213,189,161,.08);}
#conteudo{flex:1;overflow-y:auto;padding-right:6px;}
.secao{font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--principal);margin:16px 0 8px;}
.hotel{background:var(--card);border:none;border-radius:14px;margin-bottom:10px;overflow:hidden;}
.hotel.problema{border-color:rgba(213,189,161,.6);}
.cab{display:flex;align-items:center;gap:14px;padding:12px 16px;cursor:pointer;}
.cab:hover{background:rgba(213,189,161,.05);}
.num{min-width:54px;height:54px;border-radius:12px;display:flex;flex-direction:column;align-items:center;justify-content:center;
  background:rgba(213,189,161,.1);border:1px solid var(--principal2);color:var(--principal);font-size:22px;font-weight:700;}
.num small{font-size:9px;font-weight:400;letter-spacing:1px;text-transform:uppercase;color:var(--apagado);}
.num.zero{background:rgba(213,189,161,.06);border-color:rgba(213,189,161,.5);color:#d5bda1;}
.num.mal{border-style:dashed !important;background:rgba(213,189,161,.06);border-color:rgba(213,189,161,.6);color:#d5bda1;}
.info{flex:1;}
.nome{font-size:16px;font-weight:600;}
.aba{color:var(--apagado);font-size:11px;margin-top:2px;}
.seta{color:var(--apagado);font-size:18px;transition:.2s;}
.hotel.aberto .seta{transform:rotate(90deg);}
.corpo{display:none;padding:0 16px 12px;}
.hotel.aberto .corpo{display:block;}
.abrir{color:var(--principal);cursor:pointer;font-size:12px;white-space:nowrap;}
.emdia{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:8px;}
.emdia div{background:var(--card);border:none;border-radius:10px;padding:9px 12px;cursor:pointer;}
.emdia div:hover{border-color:var(--principal2);}
.emdia b{display:block;font-size:13px;} .emdia span{color:var(--apagado);font-size:11px;}
.vazio{color:var(--apagado);text-align:center;padding:40px;}
.num{background:#d5bda1;border-color:#d5bda1;color:#173f39;}
.num small{color:#173f39;opacity:.8;}
.num.zero{background:transparent;border:1.5px solid #d5bda1;color:#d5bda1;}
.num.zero small{color:#d5bda1;}
.num.mal{border-style:dashed !important;background:transparent;border:2px dashed #d5bda1;color:#d5bda1;}
.num.mal small{color:#d5bda1;}
.hotel.problema{border:2px dashed #d5bda1;}
.cartao.destaque{background:#d5bda1;border-color:#d5bda1;}
.cartao.destaque .n,.cartao.destaque .t{color:#173f39;}
.emdia div{border-style:solid;}
.aovivo{height:100%;display:flex;flex-direction:column;}
.progresso{height:10px;border-radius:5px;background:rgba(213,189,161,.12);overflow:hidden;margin:12px 0 14px;}
#av-barra{height:100%;width:0;background:#d5bda1;transition:width .35s;}
.av-log{flex:1;overflow-y:auto;border:none;border-radius:14px;background:var(--card);}
.av-l{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:8px 14px;border-bottom:none;}
.av-l:nth-child(even){background:rgba(213,189,161,.05);} .av-l.lendo{opacity:.6;}
.av-l.pend{background:#d5bda1;color:#173f39;}
.av-l.pend .chip{border-color:#173f39;color:#173f39;}
.av-l.probl{border-left:4px dashed #d5bda1;font-weight:600;}
.av-nome{font-weight:600;} .av-res{font-size:12.5px;white-space:nowrap;}
.giro-mini{display:inline-block;width:11px;height:11px;border-radius:50%;border:2px solid rgba(213,189,161,.25);
  border-top-color:#d5bda1;animation:g 1s linear infinite;vertical-align:-1px;margin-right:4px;}
</style></head><body>
<div class="tela" id="tela"><div class="carregando"><div class="giro"></div>
  <div>Lendo todas as abas de hotel... (pode levar uns 20 segundos)</div></div></div>
<script>
var R = null, FILTRO = 'pendentes';
var DESTINO = {
  ok: function (h) { return '<span class="chip ok">→ ' + esc(h.emailDestino) + '</span>'; },
  teste: function (h) { return '<span class="chip aviso">→ TESTE: ' + esc(h.emailDestino) + '</span>'; },
  sem_email: function (h) { return '<span class="chip mal">⚠ agente sem e-mail no robô — não será enviado</span>'; },
  hotel_sem_email: function (h) { return '<span class="chip mal">⚠ hotel sem e-mail na coluna B do Cadastro_Hoteis — não será enviado</span>'; },
  fora_filtro: function (h) { return '<span class="chip">‖ fora do filtro de teste (somente_hoteis) — não será enviado</span>'; },
  fora_cadastro: function (h) { return '<span class="chip mal">⚠ hotel não está no Cadastro_Hoteis — não será enviado</span>'; }
};
function esc(t){return String(t==null?'':t).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function normalizar(t){return String(t||'').normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/\s+/g,' ').trim();}

var AO_VIVO = null, LINHAS_LOG = {}, PARALELO = 4;

function carregar(){
  LINHAS_LOG = {};
  document.getElementById('tela').innerHTML=
    '<div class="aovivo"><div class="rotulo">Rede Andrade · Solicitações NF</div>'+
    '<h1 id="av-titulo">Verificando pendências...</h1><div class="sub" id="av-sub">Buscando a lista de hotéis...</div>'+
    '<div class="progresso"><div id="av-barra"></div></div>'+
    '<div class="cartoes">'+
      '<div class="cartao destaque"><div class="n" id="av-feitos">0</div><div class="t">hotéis verificados</div></div>'+
      '<div class="cartao"><div class="n" id="av-pend">0</div><div class="t">solicitações pendentes</div></div>'+
      '<div class="cartao"><div class="n" id="av-compend">0</div><div class="t">hotéis com pendência</div></div>'+
      '<div class="cartao"><div class="n" id="av-emdia">0</div><div class="t">hotéis em dia</div></div>'+
      '<div class="cartao"><div class="n" id="av-probl">0</div><div class="t">abas com problema</div></div>'+
    '</div><div class="av-log" id="av-log"></div></div>';
  google.script.run.withSuccessHandler(function(ctx){
      AO_VIVO={ctx:ctx,total:ctx.abas.length,fila:ctx.abas.slice(),feitos:0,ativos:0,pend:0,compend:0,emdia:0,probl:0,hoteis:[],fim:false};
      atualizarContadores();
      for(var i=0;i<PARALELO;i++) proxima();
    }).withFailureHandler(falhaGeral).iniciarVerificacaoAoVivo();
}

function proxima(){
  var A=AO_VIVO;
  if(!A.fila.length){ if(A.ativos===0) concluir(); return; }
  var aba=A.fila.shift(); A.ativos++;
  linhaLog(aba,'lendo');
  google.script.run.withSuccessHandler(function(h){
      A.ativos--; A.feitos++; A.hoteis.push(h);
      if(h.problema) A.probl++; else if(h.pendentes.length){A.pend+=h.pendentes.length;A.compend++;} else A.emdia++;
      linhaLog(aba,'feito',h); atualizarContadores(); proxima();
    }).withFailureHandler(function(e){
      A.ativos--; A.feitos++; A.probl++;
      var h={aba:aba,hotel:aba,agente:'',destino:'',emailDestino:'',pendentes:[],totalLinhas:0,jaEnviadas:0,problema:'erro',primeiraLinha:e.message};
      A.hoteis.push(h); linhaLog(aba,'feito',h); atualizarContadores(); proxima();
    }).verificarAbaAoVivo(aba, A.ctx);
}

function concluir(){
  var A=AO_VIVO; if(A.fim) return; A.fim=true;
  document.getElementById('av-titulo').textContent='Verificação concluída';
  document.getElementById('av-sub').textContent='Juntando o resultado e abrindo o relatório...';
  google.script.run.withSuccessHandler(function(r){R=r;setTimeout(desenharTela,900);})
    .withFailureHandler(falhaGeral).concluirVerificacaoAoVivo(A.hoteis);
}

function hotelDaAba(aba){var m=aba.match(/\(([^)]*)\)/);return m&&normalizar(m[1])!=='respostas'?m[1]:aba;}

function linhaLog(aba,estado,h){
  var log=document.getElementById('av-log'); if(!log) return;
  var el=LINHAS_LOG[aba];
  if(!el){el=document.createElement('div');LINHAS_LOG[aba]=el;log.appendChild(el);}
  var nome=h?h.hotel:hotelDaAba(aba), agente=h&&h.agente?' <span class="chip principal">'+esc(h.agente)+'</span>':'';
  var cls='av-l', res;
  if(estado==='lendo'){cls+=' lendo';res='<span class="giro-mini"></span> lendo...';}
  else if(h.problema==='sem_cabecalho'){cls+=' probl';res='⚠ sem linha de cabeçalho — aba pulada';}
  else if(h.problema){cls+=' probl';res='⚠ não consegui ler: '+esc(h.primeiraLinha||h.problema);}
  else if(h.pendentes.length){cls+=' pend';res='<b>'+h.pendentes.length+' pendente(s)</b>'+(h.emailDestino?' → '+esc(h.emailDestino):' · agente sem e-mail no robô');}
  else if(!h.totalLinhas){res='— aba vazia';}
  else{res='✔ em dia · '+h.jaEnviadas+' com TRUE';}
  el.className=cls;
  el.innerHTML='<span class="av-nome">'+esc(nome)+agente+'</span><span class="av-res">'+res+'</span>';
  log.scrollTop=log.scrollHeight;
}

function atualizarContadores(){
  var A=AO_VIVO; if(!A) return;
  var pct=A.total?Math.round(100*A.feitos/A.total):100;
  document.getElementById('av-barra').style.width=pct+'%';
  document.getElementById('av-sub').textContent=A.feitos+' de '+A.total+' hotéis verificados ('+pct+'%)';
  document.getElementById('av-feitos').textContent=A.feitos+'/'+A.total;
  document.getElementById('av-pend').textContent=A.pend;
  document.getElementById('av-compend').textContent=A.compend;
  document.getElementById('av-emdia').textContent=A.emdia;
  document.getElementById('av-probl').textContent=A.probl;
}

function falhaGeral(e){document.getElementById('tela').innerHTML='<div class="carregando"><div class="erro">Erro: '+esc(e.message)+'</div><button class="btn" onclick="carregar()">Tentar de novo</button></div>';}

function chipsRobo(r){
  var h='';
  h+= r.online ? '<span class="chip ok">● Robô online'+(r.minutosSinal!=null?' (sinal há '+r.minutosSinal+' min)':'')+'</span>'
               : '<span class="chip mal">○ Robô sem sinal'+(r.minutosSinal!=null?' há '+r.minutosSinal+' min':'')+' — o conferente está ligado no PC?</span>';
  h+= r.ligado ? '<span class="chip ok">✔ Robô ligado (aba Status)</span>' : '<span class="chip mal">‖ Robô DESLIGADO na aba Status</span>';
  h+= '<span class="chip principal">Modo: '+esc(r.config.modo)+'</span>';
  if ((r.config.somente_hoteis||[]).length) h+='<span class="chip aviso">Filtro de teste ligado: só '+esc(r.config.somente_hoteis.join(', '))+'</span>';
  if (!r.configPublicada) h+='<span class="chip aviso">O robô ainda não publicou os e-mails dos agentes</span>';
  return h;
}

function desenharTela(){
  var t=R.totais;
  var h='<div class="topo"><div><div class="rotulo">Rede Andrade · Solicitações NF</div>'+
    '<h1>Pendências de Nota Fiscal</h1><div class="sub">Verificado em '+esc(R.geradoEmTxt)+' por '+esc(R.por)+
    ' · pendente = linha sem TRUE na coluna Enviado</div></div>'+
    '<div class="acoes"><button class="btn" onclick="carregar()">↻ Verificar de novo</button>'+
    '<button class="btn principal" '+(t.vaoSair?'':'disabled')+' onclick="claudio()">Ativar Claudio · '+t.vaoSair+' pronta(s)</button></div></div>'+
    '<div class="robo">'+chipsRobo(R.robo)+'</div>'+
    '<div class="cartoes">'+
      cartao(t.pendentes,'solicitações pendentes','destaque')+
      cartao(t.hoteisComPendencia,'hotéis com pendência')+
      cartao(t.vaoSair,'prontas pra enviar (agente com e-mail)')+
      cartao(t.hoteisEmDia,'hotéis em dia')+
      cartao(t.problemas,'abas com problema',t.problemas?'':'')+
    '</div>'+
    '<div class="barra"><input id="filtro" placeholder="Filtrar por hotel, agente, nome ou e-mail do hóspede..." oninput="desenharLista()">'+
      botaoFiltro('pendentes','Com pendência ('+t.hoteisComPendencia+')')+
      botaoFiltro('problemas','Problemas ('+t.problemas+')')+
      botaoFiltro('emdia','Em dia ('+t.hoteisEmDia+')')+
      botaoFiltro('todos','Todos')+
    '</div><div id="conteudo"></div>';
  document.getElementById('tela').innerHTML=h;
  desenharLista();
  document.getElementById('filtro').focus();
}
function cartao(n,t,cls){return '<div class="cartao '+(cls||'')+'"><div class="n">'+n+'</div><div class="t">'+t+'</div></div>';}
function botaoFiltro(id,txt){return '<button class="aba-btn'+(FILTRO===id?' ativa':'')+'" onclick="FILTRO=\''+id+'\';desenharTela()">'+txt+'</button>';}

function bate(h,termos){
  if(!termos.length) return true;
  var alvo=normalizar(h.hotel+' '+h.agente+' '+h.aba+' '+h.pendentes.map(function(p){return p.nome+' '+p.email;}).join(' '));
  return termos.every(function(x){return alvo.indexOf(x)!==-1;});
}

function desenharLista(){
  var termos=normalizar(document.getElementById('filtro').value).split(' ').filter(Boolean);
  var lista=R.hoteis.filter(function(h){return bate(h,termos);});
  var probl=lista.filter(function(h){return h.problema;});
  var pend=lista.filter(function(h){return !h.problema && h.pendentes.length;});
  var dia=lista.filter(function(h){return !h.problema && !h.pendentes.length;});
  var h='';
  if((FILTRO==='problemas'||FILTRO==='todos'||FILTRO==='pendentes') && probl.length){
    h+='<div class="secao">⚠ Abas com problema — o robô pula estas abas até corrigir</div>';
    probl.forEach(function(x){h+=cardProblema(x);});
  }
  if((FILTRO==='pendentes'||FILTRO==='todos') ){
    h+='<div class="secao">Hotéis com pendência · '+pend.reduce(function(s,x){return s+x.pendentes.length;},0)+' solicitação(ões)</div>';
    h+= pend.length ? pend.map(cardHotel).join('') : '<div class="vazio">Nenhum hotel com pendência'+(termos.length?' nesse filtro':'')+'</div>';
  }
  if((FILTRO==='emdia'||FILTRO==='todos') && dia.length){
    h+='<div class="secao">Hotéis em dia</div><div class="emdia">'+dia.map(function(x){
      return '<div onclick="ir(\''+esc(x.aba).replace(/'/g,"\\'")+'\',1)"><b>'+esc(x.hotel)+'</b><span>'+
        (x.totalLinhas?x.jaEnviadas+' enviada(s) · 0 pendente':'aba vazia')+(x.agente?' · '+esc(x.agente):'')+'</span></div>';}).join('')+'</div>';
  }
  if(FILTRO==='problemas' && !probl.length) h+='<div class="vazio">Nenhuma aba com problema ✔</div>';
  document.getElementById('conteudo').innerHTML=h;
}

function cardHotel(x){
  var linhas=x.pendentes.map(function(p){
    return '<tr><td>'+p.linha+'</td><td>'+esc(p.data)+'</td><td>'+esc(p.nome)+'</td><td>'+esc(p.email)+'</td><td>'+(p.dividida?esc(p.dividida):'—')+
      '</td><td><span class="abrir" onclick="ir(\''+esc(x.aba).replace(/'/g,"\\'")+'\','+p.linha+')">abrir ↗</span></td></tr>';}).join('');
  return '<div class="hotel aberto"><div class="cab" onclick="this.parentNode.classList.toggle(\'aberto\')">'+
    '<div class="num">'+x.pendentes.length+'<small>pend.</small></div>'+
    '<div class="info"><div class="nome">'+esc(x.hotel)+' '+(x.agente?'<span class="chip principal">'+esc(x.agente)+'</span>':'')+
      (DESTINO[x.destino]?DESTINO[x.destino](x):'')+'</div>'+
    '<div class="aba">'+esc(x.aba)+' · '+x.totalLinhas+' linha(s) · '+x.jaEnviadas+' já com TRUE</div></div>'+
    '<div class="seta">›</div></div>'+
    '<div class="corpo"><table><tr><th>Linha</th><th>Data do pedido</th><th>Nome / Tomador</th><th>E-mail do hóspede</th><th>Nota dividida</th><th></th></tr>'+linhas+'</table></div></div>';
}

function cardProblema(x){
  return '<div class="hotel problema"><div class="cab" onclick="ir(\''+esc(x.aba).replace(/'/g,"\\'")+'\',1)">'+
    '<div class="num mal">!<small>aba</small></div><div class="info"><div class="nome">'+esc(x.hotel)+
    (x.agente?' <span class="chip principal">'+esc(x.agente)+'</span>':'')+'</div>'+
    '<div class="aba">'+esc(x.aba)+' · '+x.totalLinhas+' linha(s)</div>'+
    '<div style="margin-top:6px;color:#d5bda1;">'+(x.problema==='sem_cabecalho'
      ? 'Sem a linha de cabeçalho (não achei a coluna "Enviado" / "Carimbo de data/hora"). A linha 1 hoje é: <i>'+esc(x.primeiraLinha||'')+'</i>'
      : 'Não consegui ler esta aba: '+esc(x.primeiraLinha||x.problema))+'</div></div><div class="abrir">abrir ↗</div></div></div>';
}

function ir(aba,linha){google.script.run.withSuccessHandler(function(){google.script.host.close();}).irParaLinha(aba,linha);}
function claudio(){google.script.run.abrirClaudioDaVerificacao();}
carregar();
</script></body></html>`;
}

function _htmlClaudio() {
  return String.raw`<!DOCTYPE html><html><head><base target="_top">` + _cssBase() + String.raw`<style>
.tela{padding:28px 26px;height:100%;overflow-y:auto;max-width:1200px;margin:0 auto;}
.grande{background:#d5bda1 !important;color:#173f39;display:flex;align-items:center;gap:22px;background:var(--card);border:1px solid var(--principal2);border-radius:16px;
  padding:18px 22px;margin:14px 0;box-shadow:0 0 28px rgba(213,189,161,.12);}
.grande .n{font-size:52px;font-weight:700;color:#173f39;line-height:1;}
.grande .t{font-size:15px;} .grande .s{color:#173f39;opacity:.85;font-size:12px;margin-top:4px;}
.bloco{background:var(--card);border:none;border-radius:14px;padding:14px 16px;margin-bottom:12px;}
.aviso{border-style:dashed !important;background:rgba(213,189,161,.06);border:1px solid rgba(213,189,161,.6);color:#d5bda1;border-radius:12px;padding:10px 14px;margin-bottom:10px;}
.mal{border-style:dashed !important;background:rgba(213,189,161,.06);border:1px solid rgba(213,189,161,.6);color:#d5bda1;border-radius:12px;padding:10px 14px;margin-bottom:10px;}
.acoes{display:flex;gap:10px;justify-content:flex-end;margin-top:14px;}
.etapas{display:flex;gap:10px;margin:10px 0;}
.etapa{flex:1;padding:10px;border-radius:10px;border:none;color:var(--apagado);text-align:center;font-size:12px;}
.etapa.feita{border-color:#d5bda1;color:#d5bda1;} .etapa.agora{border-color:var(--principal);color:var(--principal);}
.resposta{font-size:15px;padding:14px 16px;border-radius:12px;background:var(--card2);border:none;white-space:pre-wrap;}
</style></head><body><div class="tela" id="tela"><div class="carregando"><div class="giro"></div><div>Carregando...</div></div></div>
<script>
var P=null, CONFIRMANDO=false, RESPOSTA_INICIAL='', ANDAMENTO='';
function esc(t){return String(t==null?'':t).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function semEmoji(t){return String(t||'').replace(/✅/g,'✔').replace(/⚠️/g,'⚠').replace(/🚀/g,'➜').replace(/[⏳⌛]/g,'…');}
var MOTIVO={sem_email:'agente sem e-mail no robô',hotel_sem_email:'hotel sem e-mail no Cadastro_Hoteis',fora_filtro:'fora do filtro de teste',fora_cadastro:'fora do Cadastro_Hoteis'};

function carregar(){
  google.script.run.withSuccessHandler(function(p){P=p;
      // Sempre verifica de novo ao abrir (com o log ao vivo); só reaproveita se foi feita há menos de 2 min
      if(!p.ultima || (p.ultima.minutosAtras>=2 && !JA_VERIFICOU)){JA_VERIFICOU=true;verificar();return;}
      desenhar();})
    .withFailureHandler(erro).obterPainelClaudio();
}
var JA_VERIFICOU=false;
function limparEmoji(t){return String(t||'').replace(/✅/g,'✔').replace(/❌/g,'✖').replace(/⚠️?/g,'⚠').replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}]/gu,'').replace(/\s{2,}/g,'  ');}
function htmlLog(texto){
  var linhas=String(texto||'').split('\n').filter(function(l){return l.trim();});
  if(!linhas.length) return '<div class="log" id="log"><span class="vazio">Aguardando o robô começar...</span></div>';
  return '<div class="log" id="log">'+linhas.map(function(l){
    var cls=/[❌⚠]/.test(l)?' mal':(/✅/.test(l)?' ok':'');
    return '<div class="l'+cls+'">'+esc(limparEmoji(l))+'</div>';}).join('')+'</div>';
}
function rolarLog(){var el=document.getElementById('log');if(el)el.scrollTop=el.scrollHeight;}
var LOG_VERIF=[];
function verificar(){
  LOG_VERIF=[];
  var tela=document.getElementById('tela');
  tela.innerHTML='<div class="rotulo">Rede Andrade · Solicitações NF</div><h1>Claudio — verificando as pendências</h1>'+
    '<div class="sub" id="v-sub">Buscando a lista de hotéis...</div><div class="progresso"><div id="v-barra"></div></div>'+
    '<div class="log" id="log"></div>';
  var logV=function(txt){LOG_VERIF.push(txt);var el=document.getElementById('log');if(!el)return;
    var d=document.createElement('div');d.className='l';d.textContent=txt;el.appendChild(d);el.scrollTop=el.scrollHeight;};
  var agora=function(){var d=new Date();return ('0'+d.getHours()).slice(-2)+':'+('0'+d.getMinutes()).slice(-2)+':'+('0'+d.getSeconds()).slice(-2);};
  google.script.run.withSuccessHandler(function(ctx){
    var fila=ctx.abas.slice(), total=fila.length, feitos=0, ativos=0, hoteis=[], pend=0, fim=false;
    logV(agora()+'  Começando: '+total+' abas de hotel pra ler.');
    var proxima=function(){
      if(!fila.length){ if(ativos===0&&!fim){fim=true;
          logV(agora()+'  Leitura terminada: '+pend+' pendente(s). Montando o resumo por agente...');
          google.script.run.withSuccessHandler(function(){carregar();}).withFailureHandler(erro).concluirVerificacaoAoVivo(hoteis);}
        return; }
      var aba=fila.shift(); ativos++;
      google.script.run.withSuccessHandler(function(h){
          ativos--; feitos++; hoteis.push(h); pend+=h.pendentes.length;
          var res=h.problema?'⚠ não consegui ler ('+(h.primeiraLinha||h.problema)+')':
            (h.pendentes.length?h.pendentes.length+' pendente(s)'+(h.emailDestino?' → '+h.emailDestino:(h.destino==='fora_filtro'?' · fora do filtro de teste':' · agente sem e-mail')):'em dia');
          logV(agora()+'  '+h.hotel+(h.agente?' ('+h.agente+')':'')+': '+res);
          var pct=Math.round(100*feitos/total);
          document.getElementById('v-barra').style.width=pct+'%';
          document.getElementById('v-sub').textContent=feitos+' de '+total+' hotéis lidos ('+pct+'%) · '+pend+' pendente(s) até agora';
          proxima();
        }).withFailureHandler(function(e){
          ativos--; feitos++; hoteis.push({aba:aba,hotel:aba,agente:'',destino:'',emailDestino:'',pendentes:[],totalLinhas:0,jaEnviadas:0,problema:'erro',primeiraLinha:e.message});
          logV(agora()+'  ⚠ '+aba+': erro ao ler ('+e.message+')'); proxima();
        }).verificarAbaAoVivo(aba, ctx);
    };
    for(var i=0;i<4;i++) proxima();
  }).withFailureHandler(erro).iniciarVerificacaoAoVivo();
}
function erro(e){document.getElementById('tela').innerHTML='<div class="carregando"><div class="erro">Erro: '+esc(e.message)+'</div><button class="btn" onclick="carregar()">Tentar de novo</button></div>';}

function desenhar(){
  var u=P.ultima, r=P.robo, t=u.totais;
  var h='<div class="rotulo">Rede Andrade · Solicitações NF</div><h1>Claudio — envio das pendências</h1>'+
    '<div class="sub">Envia pelo Outlook do computador do robô — '+(r.config.destino_envio==='hotel'?'cada hotel pro próprio e-mail (Cadastro_Hoteis, coluna B)':'cada hotel pro agente do Cadastro_Hoteis')+' — e marca TRUE depois de confirmar.</div>';
  // avisos
  if(!r.existe) h+='<div class="mal">A aba Status ainda não existe — o robô cria ela na primeira execução.</div>';
  else if(!r.ligado) h+='<div class="mal">‖ O robô está DESLIGADO na aba Status ("Robô ligado?"). Marque a caixa pra poder enviar.</div>';
  if(r.existe && !r.online) h+='<div class="aviso">○ O robô não dá sinal'+(r.minutosSinal!=null?' há '+r.minutosSinal+' min':'')+
    '. O pedido fica guardado por 30 minutos — ligue o computador/conferente pra ele ser atendido.</div>';
  if(r.config.modo==='TESTE') h+='<div class="aviso">Modo TESTE: tudo vai só pro e-mail de teste ('+esc(r.config.email_teste)+') e nada vira TRUE.</div>';
  if(r.config.modo==='SIMULACAO') h+='<div class="aviso">Modo SIMULAÇÃO: o robô só gera arquivos no computador, não envia nada.</div>';
  if(u.minutosAtras>30) h+='<div class="aviso">A última verificação é de '+u.minutosAtras+' min atrás — vale verificar de novo antes de enviar.</div>';
  if(r.comando) h+='<div class="aviso">Já existe um pedido em andamento ('+esc(r.comando)+'): '+esc(r.resposta)+'</div>';

  h+='<div class="grande"><div class="n">'+t.vaoSair+'</div><div><div class="t">solicitação(ões) prontas pra enviar</div>'+
    '<div class="s">Verificação de '+esc(u.geradoEmTxt)+' ('+(u.minutosAtras<1?'agora':'há '+u.minutosAtras+' min')+') por '+esc(u.por)+
    ' · '+t.pendentes+' pendente(s) no total'+(t.naoVaoSair?' · <b style="color:#d5bda1">'+t.naoVaoSair+' não vão sair</b>':'')+'</div></div></div>';

  h+='<div class="bloco"><table><tr><th>Agente</th><th>Vai para</th><th>Hotéis</th><th style="text-align:right">Pendentes</th></tr>';
  if(!u.porAgente.length) h+='<tr><td colspan="4" style="text-align:center;color:rgba(213,189,161,.68);padding:18px;">Nada pendente</td></tr>';
  u.porAgente.forEach(function(a){
    var destino = (a.destino==='ok'||a.destino==='teste') ? '<span class="chip ok">'+esc(a.email)+'</span>'
                : '<span class="chip mal">não vai sair — '+esc(MOTIVO[a.destino]||a.destino)+'</span>';
    h+='<tr><td><b>'+esc(a.agente)+'</b></td><td>'+destino+'</td><td>'+a.hoteis.map(function(x){return esc(x.hotel)+' ('+x.n+')';}).join(', ')+
       '</td><td style="text-align:right;font-size:16px;font-weight:700;">'+a.pendentes+'</td></tr>';
  });
  h+='</table></div>';

  var pode = r.existe && r.ligado && !r.comando && t.vaoSair>0;
  h+='<div class="acoes"><button class="btn" onclick="verificar()">↻ Verificar agora</button>'+
     '<button class="btn" onclick="google.script.run.verificarPendencias()">☰ Ver detalhes</button>'+
     '<button id="enviar" class="btn '+(CONFIRMANDO?'perigo':'principal')+'" '+(pode?'':'disabled')+' onclick="enviar()">'+
     (CONFIRMANDO?'Confirmar: enviar '+t.vaoSair+' e marcar TRUE':'Enviar '+t.vaoSair+' agora')+'</button></div>';
  if(LOG_VERIF.length) h+='<details style="margin-top:14px;"><summary class="sub" style="cursor:pointer;">☰ Registro da verificação ('+LOG_VERIF.length+' linhas)</summary>'+
    '<div class="log">'+LOG_VERIF.map(function(l){return '<div class="l">'+esc(l)+'</div>';}).join('')+'</div></details>';
  document.getElementById('tela').innerHTML=h;
}

function enviar(){
  if(!CONFIRMANDO){CONFIRMANDO=true;desenhar();return;}
  CONFIRMANDO=false;
  document.getElementById('enviar').disabled=true;
  google.script.run.withSuccessHandler(acompanhar).withFailureHandler(function(e){alert(e.message);carregar();}).pedirEnvioClaudio();
}

function acompanhar(){
  var inicio=Date.now();
  var tela=function(etapa,texto){
    var nomes=['Pedido registrado','Robô enviando','Concluído'];
    var fim = etapa===2;
    document.getElementById('tela').innerHTML='<div class="rotulo">Rede Andrade · Solicitações NF</div><h1>'+(fim?'Claudio terminou':'Claudio trabalhando...')+'</h1>'+
      '<div class="etapas">'+nomes.map(function(n,i){var feita=i<etapa||fim;return '<div class="etapa '+(feita?'feita':(i===etapa?'agora':''))+'">'+(feita?'✔ ':'')+n+'</div>';}).join('')+'</div>'+
      '<div class="resposta">'+esc(semEmoji(texto))+'</div>'+
      '<div class="rotulo" style="margin-top:16px;">O que o robô está fazendo (ao vivo)</div>'+htmlLog(ANDAMENTO)+
      (etapa===2?'<div class="acoes"><button class="btn" onclick="google.script.run.verificarPendencias()">☰ Ver pendências de novo</button>'+
                  '<button class="btn principal" onclick="google.script.host.close()">Fechar</button></div>':
       '<div class="sub" style="margin-top:10px;">Pode fechar esta janela: o robô continua sozinho e a resposta fica na aba Status (linha "Resposta do robô").</div>');
    rolarLog();
  };
  tela(0,'Pedido gravado na aba Status. Aguardando o robô pegar (ele olha a cada 10 segundos)...');
  var perguntar=function(){
    google.script.run.withSuccessHandler(function(s){
      ANDAMENTO=s.andamento||'';
      if(s.comando==='ENVIAR'){ tela(0,s.resposta); }
      else if(s.comando==='EM ANDAMENTO'){ tela(1,s.resposta); }
      else { tela(2,s.resposta); return; }
      if(Date.now()-inicio>15*60*1000){ tela(1,'Está demorando mais que o normal. Confira a aba Status e o log do robô.'); return; }
      setTimeout(perguntar,3000);
    }).withFailureHandler(function(){setTimeout(perguntar,5000);}).lerRespostaClaudio();
  };
  setTimeout(perguntar,2500);
}
carregar();
</script></body></html>`;
}


// --- ✉ ENVIO SEPARADO — escolher o hotel e as linhas; vai SÓ isso. ---
function envioSeparado() {
  var html = HtmlService.createHtmlOutput(_htmlSeparado()).setWidth(1800).setHeight(900);
  SpreadsheetApp.getUi().showModalDialog(html, 'Envio Separado');
}

/** Todas as linhas de um hotel (pendentes e já enviadas) pra tela do Envio Separado. */
function linhasDoHotel(nomeAba) {
  var aba = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(nomeAba);
  if (!aba) throw new Error('A aba "' + nomeAba + '" não existe mais.');
  var valores = aba.getDataRange().getDisplayValues();
  if (!valores.length) return { linhas: [], problema: '' };
  var cab = valores[0].map(function (c) { return String(c).trim(); });
  var iEnv = _indiceColuna(cab, COLUNAS.enviado), iCar = _indiceColuna(cab, COLUNAS.carimbo);
  if (iEnv === -1 || iCar === -1) return { linhas: [], problema: 'sem_cabecalho' };
  var iEmail = _indiceColuna(cab, COLUNAS.email), iNome = _indiceColuna(cab, COLUNAS.nome);
  var iTomador = _indiceColuna(cab, COLUNAS.reservaNoTomador), iPf = _indiceColuna(cab, COLUNAS.nomePessoaFisica);
  var iDiv = _indiceColuna(cab, COLUNAS.notaDividida), iQtd = _indiceColuna(cab, COLUNAS.divididaQuantas);
  var formato = _formatoDatas(valores.slice(1).map(function (l) { return l[iCar]; }));
  var celula = function (l, i) { return i === -1 ? '' : String(l[i] || '').trim(); };
  var linhas = [];
  for (var r = 1; r < valores.length; r++) {
    var l = valores[r];
    if (!l.join('').trim() || !celula(l, iCar)) continue;
    var nome = (_normalizar(celula(l, iTomador)) === 'sim' && celula(l, iPf)) ? celula(l, iPf) : celula(l, iNome);
    linhas.push({
      linha: r + 1, data: _dataBrasileira(celula(l, iCar), formato), nome: nome || '—', email: celula(l, iEmail) || '—',
      dividida: _normalizar(celula(l, iDiv)) === 'sim' ? 'Sim' + (celula(l, iQtd) ? ' (' + celula(l, iQtd) + ')' : '') : '',
      enviado: ['', 'false', 'falso'].indexOf(_normalizar(celula(l, iEnv))) === -1
    });
  }
  return { linhas: linhas.reverse(), problema: '' };  // mais novas primeiro
}

/** Grava o pedido do Envio Separado. Quem envia é o robô no computador. */
function pedirEnvioSeparado(nomeAba, linhas, reenviar) {
  if (!_autorizado()) throw new Error('Seu e-mail não está autorizado a enviar (EMAILS_AUTORIZADOS no script).');
  if (!linhas || !linhas.length) throw new Error('Marque pelo menos uma solicitação.');
  var trava = LockService.getDocumentLock();
  if (!trava.tryLock(10000)) throw new Error('Outra pessoa está enviando agora. Tente de novo em alguns segundos.');
  try {
    var robo = _lerStatusRobo();
    if (!robo.existe) throw new Error('A aba Status ainda não existe — o robô cria ela na primeira execução.');
    if (!robo.ligado) throw new Error('O robô está DESLIGADO (aba Status, "Robô ligado?"). Marque a caixa e tente de novo.');
    if (robo.comando) throw new Error('Já existe um pedido em andamento ("' + robo.comando + '"). Aguarde terminar.');
    var quem = Session.getActiveUser().getEmail() || 'menu';
    _escreverStatus(LINHA_STATUS.SELECAO, nomeAba + ' | ' + linhas.join(', ') + (reenviar ? ' | reenviar' : ''));
    _escreverStatus(LINHA_STATUS.PEDIDO, quem + ' | ' + new Date().toISOString());
    _escreverStatus(LINHA_STATUS.RESPOSTA, '⏳ Pedido registrado — aguardando o robô pegar (até 10 segundos)...');
    _escreverStatus(LINHA_STATUS.COMANDO, 'ENVIAR_SEPARADO');
    return true;
  } finally {
    trava.releaseLock();
  }
}


// --- 📜 Log de Envios — página de log (lê a aba "Log de Envios", escrita pelo robô) ---
var ABA_LOG = 'Log de Envios';
var MAX_LINHAS_LOG = 3000;

function abrirLogDeEnvios() {
  var html = HtmlService.createHtmlOutput(_htmlLog()).setWidth(1800).setHeight(900);
  SpreadsheetApp.getUi().showModalDialog(html, 'Log de Envios');
}

/** Linhas da aba como objetos (mais recentes primeiro — o robô grava no topo). */
function lerLogDeEnvios() {
  var aba = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(ABA_LOG);
  if (!aba || aba.getLastRow() < 2) return { existe: !!aba, linhas: [] };
  var n = Math.min(aba.getLastRow() - 1, MAX_LINHAS_LOG);
  var cab = aba.getRange(1, 1, 1, aba.getLastColumn()).getDisplayValues()[0].map(function (c) { return _normalizar(c); });
  var col = function (inicio) {
    for (var i = 0; i < cab.length; i++) if (cab[i].indexOf(inicio) === 0) return i;
    return -1;
  };
  var I = {
    data: col('data e hora'), quem: col('quem pediu'), origem: col('como foi pedido'), modo: col('modo'),
    resultado: col('resultado'), explicacao: col('o que aconteceu'), para: col('enviado para'), agente: col('agente'),
    hotel: col('hotel'), qtd: col('qtd'), linhas: col('linhas da planilha'), hospedes: col('hospedes'),
    contagem: col('e-mails desta'), codigo: col('codigo')
  };
  var valores = aba.getRange(2, 1, n, aba.getLastColumn()).getDisplayValues();
  var linhas = valores.filter(function (l) { return l.join('').trim(); }).map(function (l) {
    var o = {};
    Object.keys(I).forEach(function (k) { o[k] = I[k] === -1 ? '' : String(l[I[k]] || '').trim(); });
    return o;
  });
  return { existe: true, linhas: linhas, total: aba.getLastRow() - 1 };
}

/** Botão "Abrir a aba" da página. */
function irParaAbaLog() {
  var aba = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(ABA_LOG);
  if (!aba) throw new Error('A aba "' + ABA_LOG + '" ainda não existe.');
  aba.activate();
  aba.getRange('A2').activate();
}

function _htmlLog() {
  return String.raw`<!DOCTYPE html><html><head><base target="_top">` + _cssBase() + String.raw`<style>
body{overflow:hidden;}
.tela{height:100%;display:flex;flex-direction:column;padding:18px 26px 12px;}
.topo{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;}
.cartoes{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:14px 0 12px;}
.cartao{background:var(--card);border-radius:14px;padding:12px 16px;}
.cartao .n{font-size:26px;font-weight:700;line-height:1.1;} .cartao .t{color:var(--apagado);font-size:11.5px;margin-top:2px;}
.cartao.destaque{background:#d5bda1;} .cartao.destaque .n,.cartao.destaque .t{color:#173f39;}
.barra{display:flex;gap:10px;align-items:center;margin-bottom:12px;}
#busca{flex:1;padding:11px 14px;font-size:14px;color:var(--texto);background:var(--card);border:none;border-radius:10px;outline:none;font-family:inherit;}
.filtro{border:1px solid rgba(213,189,161,.6);background:transparent;color:var(--apagado);border-radius:20px;padding:7px 14px;cursor:pointer;font-family:inherit;}
.filtro.ativo{background:#d5bda1;color:#173f39;border-color:#d5bda1;font-weight:700;}
#lista{flex:1;overflow-y:auto;padding-right:6px;}
.dia{font-size:11px;letter-spacing:3px;text-transform:uppercase;color:var(--principal);margin:16px 0 8px;}
.exec{background:var(--card);border-radius:14px;margin-bottom:10px;overflow:hidden;border-left:5px solid transparent;}
.exec.r-ok{border-left-color:#d5bda1;} .exec.r-at,.exec.r-er{border-left:5px dashed #d5bda1;}
.cab{display:flex;align-items:center;gap:16px;padding:12px 16px;cursor:pointer;}
.cab:hover{background:rgba(213,189,161,.05);}
.hora{font-size:20px;font-weight:700;min-width:74px;}
.hora small{display:block;font-size:10.5px;font-weight:400;color:var(--apagado);}
.info{flex:1;min-width:0;}
.titulo{font-size:14.5px;font-weight:600;}
.resumo{color:var(--apagado);font-size:12px;margin-top:3px;}
.selo{font-size:11.5px;font-weight:700;padding:5px 12px;border-radius:20px;white-space:nowrap;}
.selo.ok{background:#d5bda1;color:#173f39;} .selo.at,.selo.er{border:1.5px dashed #d5bda1;} .selo.nada{border:1px solid rgba(213,189,161,.5);color:var(--apagado);}
.seta{color:var(--apagado);font-size:18px;transition:.2s;} .exec.aberto .seta{transform:rotate(90deg);}
.corpo{display:none;padding:0 16px 14px;} .exec.aberto .corpo{display:block;}
.item{display:grid;grid-template-columns:190px 1fr;gap:6px 18px;padding:12px 14px;border-radius:10px;margin-top:8px;background:rgba(213,189,161,.05);}
.item .hotel{font-weight:700;font-size:14px;}
.item .hotel small{display:block;font-weight:400;color:var(--apagado);font-size:11.5px;margin-top:2px;}
.item .oque{font-size:13px;line-height:1.5;}
.det{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:6px;color:var(--apagado);font-size:12px;}
.det b{color:var(--texto);font-weight:600;}
.codigo{font-family:Consolas,monospace;cursor:pointer;border-bottom:1px dotted rgba(213,189,161,.6);}
.vazio{color:var(--apagado);text-align:center;padding:60px 20px;}
.abas{display:flex;gap:6px;margin-top:12px;}
.aba{border:none;background:transparent;color:var(--apagado);font-family:inherit;font-size:14px;font-weight:600;padding:9px 18px;border-radius:10px 10px 0 0;cursor:pointer;border-bottom:3px solid transparent;}
.aba.ativa{color:#d5bda1;border-bottom-color:#d5bda1;background:rgba(213,189,161,.06);}
.agentes{display:flex;gap:10px;flex-wrap:wrap;margin:12px 0;}
.ag{border:1px solid rgba(213,189,161,.6);border-radius:14px;padding:10px 16px;cursor:pointer;min-width:150px;}
.ag b{display:block;font-size:15px;} .ag span{font-size:11.5px;color:var(--apagado);}
.ag.ativo{background:#d5bda1;border-color:#d5bda1;} .ag.ativo b,.ag.ativo span{color:#173f39;}
.email{background:var(--card);border-radius:14px;margin-bottom:10px;overflow:hidden;}
.email .cab{gap:14px;}
.email table{margin:0 16px 14px;width:calc(100% - 32px);}
.email td,.email th{padding:7px 10px;}
.num-h{font-size:12px;color:var(--apagado);}
</style></head><body><div class="tela" id="tela"><div class="carregando"><div class="giro"></div><div>Lendo o log...</div></div></div>
<script>
var EXECS=[], FILTRO='todos', LINHAS=[], VISAO='envios', AGENTE='', MODO_AG='dia';
function esc(t){return String(t==null?'':t).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function normalizar(t){return String(t||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/\s+/g,' ').trim();}
function tipo(r){r=normalizar(r);return r.indexOf('sucesso')!==-1?'ok':r.indexOf('aten')!==-1?'at':r.indexOf('erro')!==-1?'er':'nada';}
var NOME_TIPO={ok:'✔ Tudo certo',at:'⚠ Atenção',er:'✖ Erro',nada:'— Nada a enviar'};

function carregar(){
  google.script.run.withSuccessHandler(function(r){
    if(!r.existe||!r.linhas.length){document.getElementById('tela').innerHTML='<div class="carregando"><h1>O log ainda está vazio</h1><div class="sub">O robô escreve aqui a cada envio (botão Ativar Claudio, Envio Separado ou automático).</div><button class="btn principal" onclick="google.script.host.close()">Fechar</button></div>';return;}
    LINHAS=r.linhas; agrupar(r.linhas); montar(r);
  }).withFailureHandler(function(e){document.getElementById('tela').innerHTML='<div class="carregando"><div class="erro">Erro: '+esc(e.message)+'</div><button class="btn" onclick="carregar()">Tentar de novo</button></div>';}).lerLogDeEnvios();
}

// Uma execução = mesmas data/hora + quem + como foi pedido (o robô grava tudo de uma vez)
function agrupar(linhas){
  var mapa={}; EXECS=[];
  linhas.forEach(function(l){
    var k=l.data+'|'+l.quem+'|'+l.origem;
    if(!mapa[k]){mapa[k]={data:l.data,quem:l.quem,origem:l.origem,modo:l.modo,itens:[],contagem:''};EXECS.push(mapa[k]);}
    mapa[k].itens.push(l); if(l.contagem) mapa[k].contagem=l.contagem;
  });
  EXECS.forEach(function(e){
    var t=e.itens.map(function(i){return tipo(i.resultado);});
    e.tipo=t.indexOf('er')!==-1?'er':t.indexOf('at')!==-1?'at':t.indexOf('ok')!==-1?'ok':'nada';
    e.hoteis=e.itens.filter(function(i){return i.hotel;}).length;
    e.solic=e.itens.reduce(function(s,i){return s+(parseInt(i.qtd,10)||0);},0);
    e.emails={}; e.itens.forEach(function(i){if(i.codigo&&tipo(i.resultado)==='ok')i.codigo.split(',').forEach(function(c){e.emails[c.trim()]=1;});});
    e.nEmails=Object.keys(e.emails).length;
    e.busca=normalizar(e.quem+' '+e.origem+' '+e.itens.map(function(i){return [i.hotel,i.agente,i.para,i.hospedes,i.codigo,i.explicacao].join(' ');}).join(' '));
  });
}

function montar(r){
  var tot={exec:EXECS.length,ok:0,solic:0,at:0,er:0};
  EXECS.forEach(function(e){tot.ok+=e.nEmails;if(e.tipo==='ok')tot.solic+=e.solic;if(e.tipo==='at')tot.at++;if(e.tipo==='er')tot.er++;});
  document.getElementById('tela').innerHTML=
    '<div class="topo"><div><div class="rotulo">Rede Andrade · Solicitações NF</div><h1>Log de Envios</h1>'+
    '<div class="sub">Tudo o que o robô enviou, do mais recente pro mais antigo · clique num envio pra ver os hotéis</div></div>'+
    '<div style="display:flex;gap:10px;"><button class="btn" onclick="carregar()">↻ Atualizar</button>'+
    '<button class="btn" onclick="google.script.run.withSuccessHandler(function(){google.script.host.close();}).irParaAbaLog()">☰ Abrir a aba (planilha)</button>'+
    '<button class="btn principal" onclick="google.script.host.close()">Fechar</button></div></div>'+
    '<div class="cartoes">'+cartao(tot.exec,'envios registrados','destaque')+cartao(tot.ok,'e-mails que saíram')+
      cartao(tot.solic,'solicitações enviadas')+cartao(tot.at,'envios com atenção')+cartao(tot.er,'envios com erro')+'</div>'+
    '<div class="abas"><button class="aba'+(VISAO==='envios'?' ativa':'')+'" onclick="VISAO=\'envios\';montar()">Envios</button>'+
      '<button class="aba'+(VISAO==='agentes'?' ativa':'')+'" onclick="VISAO=\'agentes\';montar()">Agentes</button></div>'+
    (VISAO==='envios'
      ?'<div class="barra" style="margin-top:12px;"><input id="busca" placeholder="Buscar hotel, hóspede, agente, e-mail ou código NF-..." oninput="lista()">'+
        ['todos','ok','at','er'].map(function(f){return '<button class="filtro'+(FILTRO===f?' ativo':'')+'" onclick="FILTRO=\''+f+'\';montar()">'+
          (f==='todos'?'Todos':NOME_TIPO[f])+'</button>';}).join('')+'</div>'
      :'<div id="agentes"></div><div class="barra"><input id="busca" placeholder="Buscar hóspede, hotel ou código NF-..." oninput="lista()">'+
        '<button class="filtro'+(MODO_AG==='dia'?' ativo':'')+'" onclick="MODO_AG=\'dia\';montar()">Por dia</button>'+
        '<button class="filtro'+(MODO_AG==='hospede'?' ativo':'')+'" onclick="MODO_AG=\'hospede\';montar()">Por hóspede</button></div>')+
    '<div id="lista"></div>';
  if(VISAO==='agentes') agentesTopo();
  lista();
}
function cartao(n,t,c){return '<div class="cartao '+(c||'')+'"><div class="n">'+n+'</div><div class="t">'+t+'</div></div>';}

function lista(){
  if(VISAO==='agentes') return listaAgente();
  var el=document.getElementById('busca'), termos=normalizar(el?el.value:'').split(' ').filter(Boolean);
  var vis=EXECS.filter(function(e){return (FILTRO==='todos'||e.tipo===FILTRO)&&termos.every(function(t){return e.busca.indexOf(t)!==-1;});});
  if(!vis.length){document.getElementById('lista').innerHTML='<div class="vazio">Nenhum envio encontrado'+(termos.length?' nessa busca':'')+'.</div>';return;}
  var h='', diaAtual='';
  vis.forEach(function(e,idx){
    var dia=e.data.split(' ')[0]||'', hora=(e.data.split(' ')[1]||'').slice(0,5);
    if(dia!==diaAtual){diaAtual=dia;h+='<div class="dia">'+esc(rotuloDia(dia))+'</div>';}
    var resumo=[];
    if(e.nEmails) resumo.push(e.nEmails+' e-mail(s)');
    if(e.hoteis) resumo.push(e.hoteis+' hotel(éis)');
    if(e.solic) resumo.push(e.solic+' solicitação(ões)');
    if(e.modo&&normalizar(e.modo)!=='valendo') resumo.push('modo '+e.modo);
    h+='<div class="exec r-'+e.tipo+(idx===0||termos.length?' aberto':'')+'"><div class="cab" onclick="this.parentNode.classList.toggle(\'aberto\')">'+
      '<div class="hora">'+esc(hora)+'<small>'+esc(dia)+'</small></div>'+
      '<div class="info"><div class="titulo">'+esc(e.origem)+' · '+esc(e.quem)+'</div><div class="resumo">'+esc(resumo.join(' · ')||'sem detalhes')+'</div></div>'+
      '<span class="selo '+e.tipo+'">'+NOME_TIPO[e.tipo]+'</span><div class="seta">›</div></div>'+
      '<div class="corpo">'+e.itens.map(item).join('')+'</div></div>';
  });
  document.getElementById('lista').innerHTML=h;
}

function item(i){
  var det=[];
  if(i.para) det.push('Para <b>'+esc(i.para)+'</b>');
  if(i.agente) det.push('Agente <b>'+esc(i.agente)+'</b>');
  if(i.qtd) det.push('<b>'+esc(i.qtd)+'</b> solicitação(ões)'+(i.linhas?' · linhas '+esc(i.linhas):''));
  if(i.codigo) det.push('Código <span class="codigo" title="Clique pra copiar e procurar no Outlook" onclick="copiar(this)">'+esc(i.codigo)+'</span>');
  return '<div class="item"><div class="hotel">'+esc(i.hotel||'Geral')+'<small>'+esc(NOME_TIPO[tipo(i.resultado)])+'</small></div>'+
    '<div><div class="oque">'+esc(i.explicacao||'')+'</div>'+
    (i.hospedes?'<div class="det">Hóspedes: <b>'+esc(i.hospedes)+'</b></div>':'')+
    (det.length?'<div class="det">'+det.join('<span>·</span>')+'</div>':'')+'</div></div>';
}

// ---- Aba Agentes: cada e-mail enviado pra cada agente (só os que saíram) ----
function hospedesDe(i){return String(i.hospedes||'').split(/\s*,\s*/).filter(Boolean);}
// E-mail que SAIU: resultado ✔, ou o código aparece depois numa linha "tinha saído ... marquei TRUE"
function codigosQueSairam(){
  var ok={};
  LINHAS.forEach(function(l){
    if(l.codigo&&tipo(l.resultado)==='ok') l.codigo.split(',').forEach(function(c){ok[c.trim()]=1;});
    if(/tinha sa[ií]do|j[aá] tinha enviado/i.test(l.explicacao||'')) (String(l.explicacao).match(/NF-[0-9A-F]{10}/g)||[]).forEach(function(c){ok[c]=1;});
  });
  return ok;
}
function emailsDoAgente(ag){
  var mapa={}, lista=[], sairam=codigosQueSairam();
  LINHAS.forEach(function(l){
    if(!l.agente||!l.codigo||!sairam[l.codigo.trim()]) return;
    if(ag&&l.agente!==ag) return;
    var k=l.codigo+'|'+l.hotel;
    if(!mapa[k]){mapa[k]={codigo:l.codigo,hotel:l.hotel,para:l.para,data:l.data,agente:l.agente,origem:l.origem,quem:l.quem,hospedes:[],linhas:l.linhas,qtd:0};lista.push(mapa[k]);}
    mapa[k].hospedes=mapa[k].hospedes.concat(hospedesDe(l)); mapa[k].qtd+=parseInt(l.qtd,10)||0;
  });
  return lista;
}
function agentesTopo(){
  var cont={};
  emailsDoAgente('').forEach(function(e){cont[e.agente]=cont[e.agente]||{emails:0,hosp:0};cont[e.agente].emails++;cont[e.agente].hosp+=e.hospedes.length;});
  var nomes=Object.keys(cont).sort();
  if(!AGENTE||!cont[AGENTE]) AGENTE=nomes[0]||'';
  document.getElementById('agentes').innerHTML=nomes.length?'<div class="agentes">'+nomes.map(function(n){
    return '<div class="ag'+(n===AGENTE?' ativo':'')+'" onclick="AGENTE=\''+esc(n).replace(/'/g,"\\'")+'\';montar()"><b>'+esc(n)+'</b><span>'+
      cont[n].emails+' e-mail(s) · '+cont[n].hosp+' hóspede(s)</span></div>';}).join('')+'</div>':'';
}
function listaAgente(){
  var el=document.getElementById('busca'), termos=normalizar(el?el.value:'').split(' ').filter(Boolean);
  var emails=emailsDoAgente(AGENTE);
  if(!emails.length){document.getElementById('lista').innerHTML='<div class="vazio">Nenhum e-mail enviado pra agentes ainda.</div>';return;}
  var h='';
  if(MODO_AG==='hospede'){
    var linhas=[];
    emails.forEach(function(e){e.hospedes.forEach(function(nome){linhas.push({nome:nome,e:e});});});
    linhas=linhas.filter(function(x){var alvo=normalizar(x.nome+' '+x.e.hotel+' '+x.e.codigo);return termos.every(function(t){return alvo.indexOf(t)!==-1;});});
    linhas.sort(function(a,b){return normalizar(a.nome)<normalizar(b.nome)?-1:1;});
    h='<div class="email"><table><tr><th>Hóspede</th><th>Hotel</th><th>Enviado em</th><th>Pra qual e-mail</th><th>Código</th></tr>'+
      (linhas.length?linhas.map(function(x){return '<tr><td><b>'+esc(x.nome)+'</b></td><td>'+esc(x.e.hotel)+'</td><td>'+esc(x.e.data)+'</td><td>'+esc(x.e.para)+
        '</td><td><span class="codigo" onclick="copiar(this)">'+esc(x.e.codigo)+'</span></td></tr>';}).join('')
        :'<tr><td colspan="5" class="vazio">Nenhum hóspede nessa busca.</td></tr>')+'</table></div>';
    document.getElementById('lista').innerHTML='<div class="num-h" style="margin-bottom:8px;">'+linhas.length+' hóspede(s) · '+esc(AGENTE)+'</div>'+h;
    return;
  }
  var diaAtual='';
  emails.filter(function(e){var alvo=normalizar(e.hotel+' '+e.codigo+' '+e.para+' '+e.hospedes.join(' '));return termos.every(function(t){return alvo.indexOf(t)!==-1;});})
    .forEach(function(e,idx){
      var dia=e.data.split(' ')[0]||'', hora=(e.data.split(' ')[1]||'').slice(0,5);
      if(dia!==diaAtual){diaAtual=dia;h+='<div class="dia">'+esc(rotuloDia(dia))+'</div>';}
      h+='<div class="email exec'+(idx<3||termos.length?' aberto':'')+'"><div class="cab" onclick="this.parentNode.classList.toggle(\'aberto\')">'+
        '<div class="hora">'+esc(hora)+'<small>'+esc(dia)+'</small></div>'+
        '<div class="info"><div class="titulo">'+esc(e.hotel)+'</div><div class="resumo">Para '+esc(e.para)+' · '+e.hospedes.length+' hóspede(s) · '+esc(e.origem)+'</div></div>'+
        '<span class="codigo" onclick="event.stopPropagation();copiar(this)">'+esc(e.codigo)+'</span><div class="seta">›</div></div>'+
        '<div class="corpo" style="padding:0;"><table><tr><th style="width:50px">#</th><th>Hóspede</th><th>Hotel</th><th>Linhas da planilha</th></tr>'+
        e.hospedes.map(function(n,i){return '<tr><td>'+(i+1)+'</td><td><b>'+esc(n)+'</b></td><td>'+esc(e.hotel)+'</td><td>'+(i===0?esc(e.linhas||''):'')+'</td></tr>';}).join('')+
        '</table></div></div>';
    });
  document.getElementById('lista').innerHTML=h||'<div class="vazio">Nenhum e-mail nessa busca.</div>';
}

function rotuloDia(dia){
  var m=/^(\d{2})\/(\d{2})\/(\d{4})$/.exec(dia); if(!m) return dia;
  var d=new Date(+m[3],+m[2]-1,+m[1]), hoje=new Date(); hoje.setHours(0,0,0,0);
  var dif=Math.round((hoje-d)/86400000);
  var semana=['domingo','segunda','terça','quarta','quinta','sexta','sábado'][d.getDay()];
  return (dif===0?'Hoje':dif===1?'Ontem':semana)+' · '+dia;
}
function copiar(el){var t=el.textContent;try{navigator.clipboard.writeText(t);el.textContent='copiado ✔';setTimeout(function(){el.textContent=t;},1200);}catch(e){}}
carregar();
</script></body></html>`;
}


function _htmlSeparado() {
  return String.raw`<!DOCTYPE html><html><head><base target="_top">` + _cssBase() + String.raw`<style>
body{overflow:hidden;}
.tela{height:100%;display:flex;flex-direction:column;padding:18px 24px 12px;}
.corpo{flex:1;display:grid;grid-template-columns:330px 1fr;gap:16px;min-height:0;margin-top:12px;}
.col{background:var(--card);border:none;border-radius:14px;display:flex;flex-direction:column;min-height:0;}
.col .topo{padding:12px;border-bottom:none;}
.lista{flex:1;overflow-y:auto;padding:8px;}
input[type=text]{width:100%;padding:10px 12px;font-size:14px;color:var(--texto);background:transparent;
  border:1px solid var(--principal);border-radius:10px;outline:none;font-family:inherit;}
.h{display:flex;justify-content:space-between;align-items:center;padding:9px 10px;border-radius:10px;cursor:pointer;
  border:none;margin-bottom:4px;}
.h:hover{border-color:var(--linha);}
.h.sel{background:#d5bda1;color:#173f39;}
.h .n{font-weight:700;font-size:12px;border:1px solid currentColor;border-radius:12px;padding:1px 8px;}
.h .nome{font-weight:600;} .h small{display:block;opacity:.75;font-size:11px;}
.tabela{flex:1;overflow-y:auto;padding:0 12px;}
tr.enviada td{opacity:.55;}
tr.marcada td{background:rgba(213,189,161,.1);}
input[type=checkbox]{width:17px;height:17px;accent-color:#d5bda1;cursor:pointer;}
.rodape{display:flex;justify-content:space-between;align-items:center;gap:12px;padding:12px;border-top:none;}
.vazio{color:var(--apagado);text-align:center;padding:50px 20px;}
.etapas{display:flex;gap:10px;margin:10px 0;}
.etapa{flex:1;padding:10px;border-radius:10px;border:none;color:var(--apagado);text-align:center;font-size:12px;}
.etapa.feita{background:#d5bda1;color:#173f39;border-color:#d5bda1;} .etapa.agora{border:2px solid #d5bda1;color:#d5bda1;}
.resposta{font-size:15px;padding:14px 16px;border-radius:12px;background:var(--card2);border:none;}
</style></head><body><div class="tela" id="tela">
<div class="carregando"><div class="giro"></div><div>Lendo os hotéis...</div></div></div>
<script>
var R=null, HOTEL=null, LINHAS=[], MARCADAS={}, VER_ENVIADAS=false, CONFIRMANDO=false, ANDAMENTO='';
function limparEmoji(t){return String(t||'').replace(/✅/g,'✔').replace(/❌/g,'✖').replace(/⚠️?/g,'⚠').replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{2B00}-\u{2BFF}\u{FE0F}]/gu,'').replace(/\s{2,}/g,'  ');}
function htmlLog(texto){
  var linhas=String(texto||'').split('\n').filter(function(l){return l.trim();});
  if(!linhas.length) return '<div class="log" id="log"><span class="vazio">Aguardando o robô começar...</span></div>';
  return '<div class="log" id="log">'+linhas.map(function(l){
    var cls=/[❌⚠]/.test(l)?' mal':(/✅/.test(l)?' ok':'');
    return '<div class="l'+cls+'">'+esc(limparEmoji(l))+'</div>';}).join('')+'</div>';
}
function rolarLog(){var el=document.getElementById('log');if(el)el.scrollTop=el.scrollHeight;}

function esc(t){return String(t==null?'':t).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function normalizar(t){return String(t||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/\s+/g,' ').trim();}
function semEmoji(t){return String(t||'').replace(/✅/g,'✔').replace(/⚠️/g,'⚠').replace(/🚀/g,'➜').replace(/[⏳⌛]/g,'…');}
var DESTINO={ok:function(h){return 'vai para '+h.emailDestino;},teste:function(h){return 'TESTE: vai para '+h.emailDestino;},
  sem_email:function(){return '⚠ agente sem e-mail no robô — não dá pra enviar';},
  hotel_sem_email:function(){return '⚠ hotel sem e-mail no Cadastro_Hoteis — não dá pra enviar';},
  fora_filtro:function(h){return 'vai para '+(h.emailDestino||'o agente');},
  fora_cadastro:function(){return '⚠ hotel fora do Cadastro_Hoteis — não dá pra enviar';}};

google.script.run.withSuccessHandler(function(r){R=r;montar();}).withFailureHandler(erro).coletarPendencias();
function erro(e){document.getElementById('tela').innerHTML='<div class="carregando"><div class="erro">Erro: '+esc(e.message)+'</div></div>';}

function montar(){
  document.getElementById('tela').innerHTML=
    '<div><div class="rotulo">Rede Andrade · Solicitações NF</div><h1>Envio Separado</h1>'+
    '<div class="sub">Escolha o hotel, marque as solicitações e envie só elas — pro agente do Cadastro_Hoteis. Depois de confirmado, vira TRUE.</div></div>'+
    '<div class="corpo"><div class="col"><div class="topo"><input type="text" id="busca" placeholder="Buscar hotel ou agente..." oninput="listaHoteis()"></div>'+
    '<div class="lista" id="hoteis"></div></div>'+
    '<div class="col" id="direita"><div class="vazio">← Escolha um hotel na lista</div></div></div>';
  listaHoteis();
  document.getElementById('busca').focus();
}

function listaHoteis(){
  var termos=normalizar(document.getElementById('busca').value).split(' ').filter(Boolean);
  var hs=R.hoteis.filter(function(h){var alvo=normalizar(h.hotel+' '+h.agente);return termos.every(function(t){return alvo.indexOf(t)!==-1;});});
  document.getElementById('hoteis').innerHTML=hs.map(function(h,i){
    return '<div class="h'+(HOTEL&&HOTEL.aba===h.aba?' sel':'')+'" onclick="escolher('+R.hoteis.indexOf(h)+')"><div><span class="nome">'+esc(h.hotel)+'</span>'+
      '<small>'+esc(h.agente||'sem agente')+(h.problema?' · ⚠ aba sem cabeçalho':'')+'</small></div>'+
      '<span class="n">'+(h.problema?'!':h.pendentes.length)+'</span></div>';}).join('') || '<div class="vazio">Nenhum hotel</div>';
}

function escolher(i){
  HOTEL=R.hoteis[i]; MARCADAS={}; VER_ENVIADAS=false; CONFIRMANDO=false; listaHoteis();
  document.getElementById('direita').innerHTML='<div class="carregando" style="height:100%"><div class="giro"></div><div>Lendo '+esc(HOTEL.hotel)+'...</div></div>';
  google.script.run.withSuccessHandler(function(r){
      LINHAS=r.linhas; LINHAS.forEach(function(l){if(!l.enviado)MARCADAS[l.linha]=true;}); tabela(r.problema);})
    .withFailureHandler(erro).linhasDoHotel(HOTEL.aba);
}

function tabela(problema){
  var h='<div class="topo"><div style="display:flex;justify-content:space-between;align-items:center;gap:10px;">'+
    '<div><div style="font-size:18px;font-weight:700">'+esc(HOTEL.hotel)+'</div><div class="sub">'+esc(DESTINO[HOTEL.destino]?DESTINO[HOTEL.destino](HOTEL):'')+
    ' · agente '+esc(HOTEL.agente||'—')+'</div></div>'+
    '<label style="cursor:pointer"><input type="checkbox" '+(VER_ENVIADAS?'checked':'')+' onchange="VER_ENVIADAS=this.checked;tabela()"> mostrar também as já enviadas (pra reenviar)</label></div></div>';
  if(problema){h+='<div class="vazio">⚠ Esta aba está sem a linha de cabeçalho. Corrija a aba antes de enviar.</div>';}
  else{
    var vis=LINHAS.filter(function(l){return VER_ENVIADAS||!l.enviado;});
    h+='<div class="tabela"><table><tr><th style="width:36px"><input type="checkbox" onchange="todas(this.checked)"></th><th>Linha</th><th>Data do pedido</th><th>Nome / Tomador</th><th>E-mail do hóspede</th><th>Nota dividida</th><th>Situação</th></tr>'+
      (vis.length?vis.map(function(l){return '<tr class="'+(l.enviado?'enviada':'')+(MARCADAS[l.linha]?' marcada':'')+'"><td><input type="checkbox" '+(MARCADAS[l.linha]?'checked':'')+
        ' onchange="marcar('+l.linha+',this.checked)"></td><td>'+l.linha+'</td><td>'+esc(l.data)+'</td><td>'+esc(l.nome)+'</td><td>'+esc(l.email)+'</td><td>'+(esc(l.dividida)||'—')+
        '</td><td>'+(l.enviado?'✔ já enviada':'pendente')+'</td></tr>';}).join(''):'<tr><td colspan="7" class="vazio">Nenhuma solicitação pendente neste hotel. Marque "mostrar também as já enviadas" pra reenviar alguma.</td></tr>')+
      '</table></div>';
  }
  var sel=selecionadas(), reenv=sel.some(function(n){return LINHAS.some(function(l){return l.linha===n&&l.enviado;});});
  var pode=!problema && sel.length && (HOTEL.destino==='ok'||HOTEL.destino==='teste'||HOTEL.destino==='fora_filtro');
  h+='<div class="rodape"><div class="sub">'+sel.length+' selecionada(s)'+(reenv?' · <b>inclui reenvio de solicitação já enviada</b>':'')+'</div>'+
    '<button id="enviar" class="btn '+(CONFIRMANDO?'perigo':'principal')+'" '+(pode?'':'disabled')+' onclick="enviar()">'+
    (CONFIRMANDO?'Confirmar: enviar '+sel.length+' de '+esc(HOTEL.hotel)+' e marcar TRUE':'Enviar '+sel.length+' selecionada(s)')+'</button></div>';
  document.getElementById('direita').innerHTML=h;
}
function selecionadas(){return Object.keys(MARCADAS).filter(function(k){return MARCADAS[k];}).map(Number).sort(function(a,b){return a-b;});}
function marcar(n,v){MARCADAS[n]=v;CONFIRMANDO=false;tabela();}
function todas(v){LINHAS.forEach(function(l){if(VER_ENVIADAS||!l.enviado)MARCADAS[l.linha]=v;});CONFIRMANDO=false;tabela();}

function enviar(){
  if(!CONFIRMANDO){CONFIRMANDO=true;tabela();return;}
  var sel=selecionadas(), reenv=sel.some(function(n){return LINHAS.some(function(l){return l.linha===n&&l.enviado;});});
  document.getElementById('enviar').disabled=true;
  google.script.run.withSuccessHandler(acompanhar).withFailureHandler(function(e){alert(e.message);CONFIRMANDO=false;tabela();})
    .pedirEnvioSeparado(HOTEL.aba, sel, reenv);
}

function acompanhar(){
  var inicio=Date.now();
  var tela=function(etapa,texto){
    var nomes=['Pedido registrado','Robô enviando','Concluído'], fim=etapa===2;
    document.getElementById('tela').innerHTML='<div class="rotulo">Rede Andrade · Solicitações NF</div><h1>'+(fim?'Envio separado concluído':'Enviando '+esc(HOTEL.hotel)+'...')+'</h1>'+
      '<div class="etapas">'+nomes.map(function(n,i){var f=i<etapa||fim;return '<div class="etapa '+(f?'feita':(i===etapa?'agora':''))+'">'+(f?'✔ ':'')+n+'</div>';}).join('')+'</div>'+
      '<div class="resposta">'+esc(semEmoji(texto))+'</div>'+
      '<div class="rotulo" style="margin-top:16px;">O que o robô está fazendo (ao vivo)</div>'+htmlLog(ANDAMENTO)+
      (fim?'<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:14px;"><button class="btn" onclick="google.script.run.abrirLogDeEnvios();google.script.host.close()">☰ Ver no Log de Envios</button>'+
            '<button class="btn principal" onclick="google.script.host.close()">Fechar</button></div>'
          :'<div class="sub" style="margin-top:10px;">Pode fechar esta janela: o robô continua sozinho e o resultado fica no Log de Envios.</div>');
    rolarLog();
  };
  tela(0,'Pedido gravado. Aguardando o robô pegar (ele olha a cada 10 segundos)...');
  var perguntar=function(){
    google.script.run.withSuccessHandler(function(s){
      ANDAMENTO=s.andamento||'';
      if(s.comando==='ENVIAR_SEPARADO'){tela(0,s.resposta);}
      else if(s.comando==='EM ANDAMENTO'){tela(1,s.resposta);}
      else {tela(2,s.resposta);return;}
      if(Date.now()-inicio>15*60*1000){tela(1,'Está demorando mais que o normal. Confira a aba Status e o Log de Envios.');return;}
      setTimeout(perguntar,3000);
    }).withFailureHandler(function(){setTimeout(perguntar,5000);}).lerRespostaClaudio();
  };
  setTimeout(perguntar,2500);
}
</script></body></html>`;
}


// --- 📊 Cota de Envio ---
function abrirCotaEnvio() {
  var html = HtmlService.createHtmlOutput(_htmlCota()).setWidth(1800).setHeight(900);
  SpreadsheetApp.getUi().showModalDialog(html, 'Cota de Envio');
}

function lerCotaEnvio() {
  var aba = _abaStatus();
  var bruto = aba ? aba.getRange(LINHA_STATUS.COTA, 2).getDisplayValue() : '';
  var cota = null;
  try { cota = bruto ? JSON.parse(bruto) : null; } catch (e) { cota = null; }
  if (cota && cota.atualizado) cota.minutosAtras = Math.round((new Date() - new Date(cota.atualizado)) / 60000);
  var robo = _lerStatusRobo();
  return { cota: cota, online: robo.online, minutosSinal: robo.minutosSinal };
}

function _htmlCota() {
  return String.raw`<!DOCTYPE html><html><head><base target="_top">` + _cssBase() + String.raw`<style>
body{overflow:hidden;}
.tela{height:100%;display:flex;flex-direction:column;padding:22px 34px 16px;}
.topo{display:flex;justify-content:space-between;align-items:flex-end;}
.meio{display:grid;grid-template-columns:1.1fr 1fr;gap:34px;margin-top:22px;flex:1;min-height:0;}
.grande{font-size:120px;font-weight:700;line-height:1;}
.de{font-size:26px;color:var(--apagado);}
.barra{height:16px;border-radius:10px;background:rgba(213,189,161,.12);overflow:hidden;margin:18px 0 8px;}
.barra div{height:100%;background:#d5bda1;border-radius:10px;transition:width .6s;}
.frase{font-size:16px;line-height:1.5;margin-top:14px;}
.cartoes{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-top:22px;}
.cartao{background:var(--card);border-radius:14px;padding:14px 16px;}
.cartao .n{font-size:28px;font-weight:700;} .cartao .t{color:var(--apagado);font-size:12px;margin-top:2px;}
.grafico{display:flex;align-items:flex-end;gap:5px;height:300px;margin-top:10px;}
.col{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:flex-end;height:100%;}
.col .b{width:100%;background:#d5bda1;border-radius:4px 4px 0 0;min-height:2px;}
.col .v{font-size:10px;color:var(--apagado);margin-bottom:3px;}
.col .h{font-size:9.5px;color:var(--apagado);margin-top:5px;writing-mode:vertical-rl;transform:rotate(180deg);}
.explica{color:var(--apagado);font-size:12px;line-height:1.6;margin-top:14px;}
</style></head><body><div class="tela" id="tela"><div class="carregando"><div class="giro"></div>Lendo a cota...</div></div>
<script>
function esc(t){return String(t==null?'':t).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function carregar(){google.script.run.withSuccessHandler(desenhar).withFailureHandler(function(e){
  document.getElementById('tela').innerHTML='<div class="carregando"><div class="erro">Erro: '+esc(e.message)+'</div><button class="btn" onclick="carregar()">Tentar de novo</button></div>';}).lerCotaEnvio();}
function desenhar(d){
  var c=d.cota, t=document.getElementById('tela');
  if(!c){t.innerHTML='<div class="carregando"><div class="rotulo">Cota de envio</div><h1>O robô ainda não mediu a cota</h1>'+
    '<div class="sub">Quem conta é o conferente no computador (Bat\\conferente.bat). Assim que ele estiver ligado, a medição aparece aqui em até 1 minuto.</div>'+
    '<button class="btn principal" onclick="google.script.host.close()">Fechar</button></div>';return;}
  var pct=Math.min(100,Math.round(100*c.usados_hora/c.limite_hora));
  var velho=c.minutosAtras!=null&&c.minutosAtras>5;
  var frase=c.sobra_hora===0
    ?'<b>A cota desta hora acabou.</b> Se enviar agora, o servidor bloqueia por 1 hora.'+(c.proxima_liberacao?' Volta a liberar às <b>'+esc(c.proxima_liberacao)+'</b>.':'')
    :'Dá pra enviar mais <b>'+c.sobra_hora+' e-mail(s)</b> agora sem risco de bloqueio.'+(c.proxima_liberacao?' A cota vai subindo a partir das <b>'+esc(c.proxima_liberacao)+'</b>, quando o envio mais antigo da última hora faz 1 hora.':'');
  var max=Math.max.apply(null,c.por_hora.map(function(x){return x.n;}).concat([1]));
  var cols=c.por_hora.map(function(x){return '<div class="col"><div class="v">'+(x.n||'')+'</div><div class="b" style="height:'+Math.round(100*x.n/max)+'%"></div><div class="h">'+esc(x.hora)+'</div></div>';}).join('');
  t.innerHTML='<div class="topo"><div><div class="rotulo">Rede Andrade · Solicitações NF</div><h1>Cota de envio do e-mail</h1>'+
      '<div class="sub">'+esc(c.conta)+' · '+esc(c.provedor||'servidor')+' · limite de '+c.limite_hora+' e-mails por hora</div></div>'+
      '<div><span class="chip '+(velho?'aviso':'ok')+'">'+(velho?'⚠ medição de '+c.minutosAtras+' min atrás — o robô parou de medir?':'medido há '+(c.minutosAtras||0)+' min')+'</span> '+
      '<button class="btn" onclick="carregar()">↻ Atualizar</button> <button class="btn principal" onclick="google.script.host.close()">Fechar</button></div></div>'+
    '<div class="meio"><div><div class="rotulo">Sobram nesta hora</div>'+
      '<div><span class="grande">'+c.sobra_hora+'</span> <span class="de">de '+c.limite_hora+'</span></div>'+
      '<div class="barra"><div style="width:'+pct+'%"></div></div><div class="sub">'+c.usados_hora+' usado(s) na última hora ('+pct+'%)</div>'+
      '<div class="frase">'+frase+'</div>'+
      '<div class="cartoes"><div class="cartao"><div class="n">'+c.usados_hora+'</div><div class="t">enviados na última hora</div></div>'+
        '<div class="cartao"><div class="n">'+c.usados_24h+'</div><div class="t">enviados nas últimas 24 horas</div></div>'+
        '<div class="cartao"><div class="n">'+(c.proxima_liberacao||'—')+'</div><div class="t">começa a liberar às</div></div></div>'+
      '<div class="explica">Como funciona: o servidor de e-mail aceita até '+c.limite_hora+' e-mails a cada 1 hora (a hora vai andando — o que saiu há mais de 60 minutos já não conta). '+
        'Cada destinatário conta 1. Passou do limite, o servidor bloqueia o envio por 1 hora e depois libera sozinho. '+
        'O robô só enxerga o que sai por este Outlook: e-mails enviados por outras caixas do mesmo domínio também gastam a cota.</div></div>'+
    '<div><div class="rotulo">Envios nas últimas 24 horas (por hora)</div><div class="grafico">'+cols+'</div></div></div>';
}
carregar(); setInterval(carregar,60000);
</script></body></html>`;
}


// --- 🔍 Conferir Cópia dos Hotéis — o robô (no computador) passa hotel por hotel ---
var ABA_CONFERENCIA = 'Conferência da Cópia';

function abrirConferenciaCopia() {
  var html = HtmlService.createHtmlOutput(_htmlConferencia()).setWidth(1800).setHeight(900);
  SpreadsheetApp.getUi().showModalDialog(html, 'Conferir Cópia dos Hotéis');
}

/** Resultado da última conferência (aba escrita pelo robô) + situação do robô. */
function lerResultadoConferencia() {
  var aba = SpreadsheetApp.getActiveSpreadsheet().getSheetByName(ABA_CONFERENCIA);
  var linhas = [];
  if (aba && aba.getLastRow() > 1) {
    linhas = aba.getRange(2, 1, aba.getLastRow() - 1, 12).getDisplayValues().map(function (l) {
      return { hotel: l[0], resultado: l[1], frase: l[2], planilha: l[3], aba: l[4], noHotel: l[5], naCentral: l[6],
               faltando: l[7], diferentes: l[8], trueSumiu: l[9], soCentral: l[10], quando: l[11] };
    });
  }
  var robo = _lerStatusRobo();
  return { linhas: linhas, online: robo.online, minutosSinal: robo.minutosSinal, comando: robo.comando };
}

function pedirConferenciaCopia() {
  var trava = LockService.getDocumentLock();
  if (!trava.tryLock(10000)) throw new Error('Outra pessoa está pedindo algo ao robô agora. Tente de novo em alguns segundos.');
  try {
    var robo = _lerStatusRobo();
    if (!robo.existe) throw new Error('A aba Status ainda não existe.');
    if (robo.comando) throw new Error('O robô está ocupado agora ("' + robo.comando + '"). Espere terminar e tente de novo.');
    var quem = Session.getActiveUser().getEmail() || 'menu';
    _escreverStatus(LINHA_STATUS.PEDIDO, quem + ' | ' + new Date().toISOString());
    _escreverStatus(LINHA_STATUS.CONFERENCIA, '');
    _escreverStatus(LINHA_STATUS.RESPOSTA, '⏳ Conferência pedida — aguardando o robô pegar (até 10 segundos)...');
    _escreverStatus(LINHA_STATUS.COMANDO, 'CONFERIR_COPIA');
    return true;
  } finally {
    trava.releaseLock();
  }
}

/** A tela pergunta isto a cada 3s enquanto o robô confere. */
function lerConferenciaAoVivo() {
  var robo = _lerStatusRobo();
  var aba = _abaStatus();
  var log = aba ? aba.getRange(LINHA_STATUS.CONFERENCIA, 2).getDisplayValue() : '';
  return { comando: robo.comando, resposta: robo.resposta, log: log, online: robo.online };
}

function _htmlConferencia() {
  return String.raw`<!DOCTYPE html><html><head><base target="_top">` + _cssBase() + String.raw`<style>
body{overflow:hidden;}
.tela{height:100%;display:flex;flex-direction:column;padding:18px 26px 12px;}
.topo{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;}
.cartoes{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:14px 0 12px;}
.cartao{background:var(--card);border-radius:14px;padding:12px 16px;}
.cartao .n{font-size:26px;font-weight:700;line-height:1.1;} .cartao .t{color:var(--apagado);font-size:11.5px;margin-top:2px;}
.cartao.destaque{background:#d5bda1;} .cartao.destaque .n,.cartao.destaque .t{color:#173f39;}
.barra{display:flex;gap:10px;align-items:center;margin-bottom:10px;}
#busca{flex:1;padding:11px 14px;font-size:14px;color:var(--texto);background:var(--card);border:none;border-radius:10px;outline:none;font-family:inherit;}
.filtro{border:1px solid rgba(213,189,161,.6);background:transparent;color:var(--apagado);border-radius:20px;padding:7px 14px;cursor:pointer;font-family:inherit;}
.filtro.ativo{background:#d5bda1;color:#173f39;border-color:#d5bda1;font-weight:700;}
#conteudo{flex:1;overflow-y:auto;padding-right:6px;}
.hot{display:grid;grid-template-columns:210px 150px 1fr 120px;gap:14px;align-items:start;padding:11px 14px;border-radius:12px;margin-bottom:6px;background:var(--card);}
.hot.dif{border-left:5px dashed #d5bda1;} .hot.nov{border-left:5px solid rgba(213,189,161,.5);} .hot.ok{border-left:5px solid #d5bda1;}
.hot b{font-size:14px;} .hot small{display:block;color:var(--apagado);font-size:11px;margin-top:2px;}
.selo{font-size:11.5px;font-weight:700;padding:4px 10px;border-radius:20px;white-space:nowrap;display:inline-block;}
.selo.ok{background:#d5bda1;color:#173f39;} .selo.dif{border:1.5px dashed #d5bda1;} .selo.nov{border:1px solid rgba(213,189,161,.6);}
.num{text-align:right;font-size:12px;color:var(--apagado);} .num b{font-size:14px;color:var(--texto);}
.frase{font-size:12.5px;line-height:1.5;}
.log{max-height:none;flex:1;margin-top:10px;}
.log .l.ok{font-weight:400;} .log .l.dif{font-weight:700;background:rgba(213,189,161,.1);border-radius:6px;padding:2px 6px;}
.vazio{color:var(--apagado);text-align:center;padding:60px 20px;}
</style></head><body><div class="tela" id="tela"><div class="carregando"><div class="giro"></div><div>Carregando...</div></div></div>
<script>
var R=null, FILTRO='dif';
function esc(t){return String(t==null?'':t).replace(/[&<>"']/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c];});}
function normalizar(t){return String(t||'').normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/\s+/g,' ').trim();}
function tipo(r){r=normalizar(r);return r.indexOf('igual')!==-1?'ok':r.indexOf('novidade')!==-1?'nov':'dif';}
function limparEmoji(t){return String(t||'').replace(/✅/g,'✔').replace(/❌/g,'✖').replace(/⚠️?/g,'⚠').replace(/⏳/g,'…').replace(/[\u{1F000}-\u{1FAFF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}\u{FE0F}]/gu,'').replace(/\s{2,}/g,'  ');}

function carregar(){
  google.script.run.withSuccessHandler(function(r){R=r; if(r.comando==='CONFERINDO'||r.comando==='CONFERIR_COPIA'){acompanhar();return;} desenhar();})
    .withFailureHandler(erro).lerResultadoConferencia();
}
function erro(e){document.getElementById('tela').innerHTML='<div class="carregando"><div class="erro">Erro: '+esc(e.message)+'</div><button class="btn" onclick="carregar()">Tentar de novo</button></div>';}

function desenhar(){
  var L=R.linhas, c={ok:0,nov:0,dif:0};
  L.forEach(function(x){c[tipo(x.resultado)]++;});
  if(!c[FILTRO]&&FILTRO!=='todos') FILTRO='todos';
  var quando=L.length?L[0].quando:'';
  document.getElementById('tela').innerHTML=
    '<div class="topo"><div><div class="rotulo">Rede Andrade · Solicitações NF</div><h1>Conferência da cópia dos hotéis</h1>'+
    '<div class="sub">O robô compara a planilha original de cada hotel (pasta do Drive) com a aba dele na Planilha Central — linha por linha, coluna por coluna. Só lê: não altera nada.</div></div>'+
    '<div style="display:flex;gap:10px;"><button class="btn principal" onclick="conferir()" '+(R.online?'':'title="O robô está sem sinal"')+'>🔍 Conferir agora</button>'+
    '<button class="btn" onclick="google.script.host.close()">Fechar</button></div></div>'+
    (R.online?'':'<div class="chip mal" style="margin-top:10px;">○ O robô está sem sinal'+(R.minutosSinal!=null?' há '+R.minutosSinal+' min':'')+' — o pedido fica esperando até ele voltar.</div>')+
    (L.length?'<div class="cartoes">'+cartao(L.length,'hotéis conferidos · '+esc(quando),'destaque')+cartao(c.ok,'iguais à planilha do hotel')+
      cartao(c.nov,'com novidade pra próxima cópia')+cartao(c.dif,'com diferença')+'</div>'+
      '<div class="barra"><input id="busca" placeholder="Buscar hotel..." oninput="lista()">'+
      [['dif','✖ Com diferença ('+c.dif+')'],['nov','… Novidade ('+c.nov+')'],['ok','✔ Iguais ('+c.ok+')'],['todos','Todos']].map(function(f){
        return '<button class="filtro'+(FILTRO===f[0]?' ativo':'')+'" onclick="FILTRO=\''+f[0]+'\';desenhar()">'+f[1]+'</button>';}).join('')+'</div>'+
      '<div id="conteudo"></div>'
    :'<div class="vazio">Ainda não houve nenhuma conferência. Clique em <b>Conferir agora</b>.</div>');
  if(L.length) lista();
}
function cartao(n,t,cl){return '<div class="cartao '+(cl||'')+'"><div class="n">'+n+'</div><div class="t">'+t+'</div></div>';}
function lista(){
  var el=document.getElementById('busca'), termos=normalizar(el?el.value:'').split(' ').filter(Boolean);
  var vis=R.linhas.filter(function(x){return (FILTRO==='todos'||tipo(x.resultado)===FILTRO)&&termos.every(function(t){return normalizar(x.hotel+' '+x.planilha).indexOf(t)!==-1;});});
  var nome={ok:'✔ Igual',nov:'… Novidade',dif:'✖ Diferente'};
  document.getElementById('conteudo').innerHTML=vis.length?vis.map(function(x){var t=tipo(x.resultado);
    return '<div class="hot '+t+'"><div><b>'+esc(x.hotel)+'</b><small>'+esc(x.planilha)+'</small></div>'+
      '<div><span class="selo '+t+'">'+nome[t]+'</span></div><div class="frase">'+esc(x.frase)+'</div>'+
      '<div class="num">hotel <b>'+esc(x.noHotel)+'</b><br>Central <b>'+esc(x.naCentral)+'</b></div></div>';}).join('')
    :'<div class="vazio">'+(FILTRO==='dif'?'Nenhum hotel com diferença ✔':'Nada aqui.')+'</div>';
}

function conferir(){
  google.script.run.withSuccessHandler(acompanhar).withFailureHandler(function(e){alert(e.message);}).pedirConferenciaCopia();
}
function acompanhar(){
  var inicio=Date.now();
  document.getElementById('tela').innerHTML='<div class="rotulo">Rede Andrade · Solicitações NF</div><h1 id="titulo">Conferindo a cópia hotel por hotel...</h1>'+
    '<div class="sub" id="sub">Pedido enviado. Aguardando o robô pegar (ele olha a cada 10 segundos)...</div>'+
    '<div class="progresso"><div id="barra"></div></div><div class="log" id="log"><span class="vazio">Aguardando o robô começar...</span></div>';
  var perguntar=function(){
    google.script.run.withSuccessHandler(function(s){
      var linhas=String(s.log||'').split('\n').filter(function(l){return l.trim();});
      var feitos=0,total=0,ok=0,dif=0,nov=0;
      linhas.forEach(function(l){var m=/\[(\d+)\/(\d+)\]/.exec(l);if(m&&!/não consegui ler/.test(l)){feitos=+m[1];total=+m[2];if(/✅/.test(l))ok++;else if(/⏳/.test(l))nov++;else if(/❌/.test(l))dif++;}});
      if(linhas.length){
        var el=document.getElementById('log');
        el.innerHTML=linhas.map(function(l){var cl=/❌|⚠/.test(l)?' dif':(/✅/.test(l)?' ok':'');return '<div class="l'+cl+'">'+esc(limparEmoji(l))+'</div>';}).join('');
        el.scrollTop=el.scrollHeight;
      }
      if(total){var pct=Math.round(100*feitos/total);document.getElementById('barra').style.width=pct+'%';
        document.getElementById('sub').textContent=feitos+' de '+total+' hotéis conferidos ('+pct+'%) · '+ok+' iguais · '+nov+' com novidade · '+dif+' com diferença';}
      if(s.comando==='CONFERIR_COPIA'||s.comando==='CONFERINDO'){
        if(Date.now()-inicio>20*60*1000){document.getElementById('sub').textContent='Está demorando mais que o normal. Confira se o robô está ligado.';return;}
        setTimeout(perguntar,3000);return;
      }
      document.getElementById('titulo').textContent='Conferência terminada';
      document.getElementById('barra').style.width='100%';
      document.getElementById('sub').textContent=limparEmoji(s.resposta||'');
      var b=document.createElement('div');b.style.cssText='display:flex;gap:10px;justify-content:flex-end;margin-top:12px;';
      b.innerHTML='<button class="btn principal" onclick="FILTRO=\'dif\';carregar()">Ver o resultado por hotel</button><button class="btn" onclick="google.script.host.close()">Fechar</button>';
      document.getElementById('tela').appendChild(b);
    }).withFailureHandler(function(){setTimeout(perguntar,5000);}).lerConferenciaAoVivo();
  };
  setTimeout(perguntar,2500);
}
carregar();
</script></body></html>`;
}
