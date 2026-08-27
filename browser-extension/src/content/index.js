/**
 * O content script — e é aqui que mora o relógio.
 *
 * Não é preferência de organização: no MV3 o service worker morre por
 * inatividade, e um `setInterval` lá dentro simplesmente para de existir sem
 * avisar. O content script vive enquanto a aba viver, então é o único lugar
 * onde um relógio é honesto. Master Loop, critério de implementação incorreta
 * nº 4.
 *
 * Medido nesta máquina: uma porta de Native Messaging aberta MANTÉM o worker
 * vivo (17 minutos sem outra atividade). Isso torna a morte do worker RARA, não
 * impossível — e é exatamente o tipo de coisa que passa em teste e falha em
 * produção. O relógio continua aqui.
 *
 * SEM `import`, de propósito: um content script declarado no manifesto NÃO é
 * módulo, e `import` ali é erro de sintaxe — a aba fica sem script e nada
 * acusa. `video-observer.js` é carregado antes no manifesto e deixa
 * `criarObservador` visível neste escopo (mundo isolado, não vaza para a
 * página). A decisão de introduzir um bundler segue adiada.
 */

const PROTOCOL_VERSION = 1

/**
 * Batimento esparso, e não um por segundo.
 *
 * A posição real é observada continuamente aqui dentro; o que é caro é
 * ATRAVESSAR as fronteiras — `sendMessage` até o worker, stdio até o host. Com
 * `currentTime` de verdade disponível, o consumidor extrapola entre um
 * batimento e outro e corrige quando o próximo chega. Um por segundo por aba
 * seria gastar tráfego constante para dizer o que o relógio já sabe.
 */
const SEGUNDOS_ENTRE_BATIMENTOS = 10

/** Eventos do elemento que merecem envio IMEDIATO, sem esperar o batimento. */
const IMEDIATOS = {
  play: 'PLAY',
  pause: 'PAUSE',
  ended: 'ENDED',
  seeked: 'SEEK',
  bound: 'SESSION_STARTED',
  detached: 'MEDIA_CHANGED',
}

let sequencia = 0

/**
 * Identifica a REPRODUÇÃO, não a aba.
 *
 * Muda quando a mídia muda — é o embrião da `PlaybackIdentity` da Fase 11, e o
 * que vai permitir distinguir "mesmo episódio retomado" de "próximo episódio".
 * Hoje o histórico não tem essa distinção, e é dela que nasce o bug de mostrar
 * progresso de um episódio antigo na linha da obra.
 */
let sessionId = novaSessao()

function novaSessao() {
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`
}

function envelope(messageType, payload) {
  return { protocolVersion: PROTOCOL_VERSION, messageType, timestamp: Date.now(), payload }
}

async function enviar(messageType, payload) {
  try {
    // O `tabId` NÃO vai daqui: quem o preenche é o worker, a partir do
    // `sender`. Uma página não pode ter voz sobre qual aba ela é.
    const resposta = await chrome.runtime.sendMessage(
      envelope(messageType, { ...payload, sessionId, seq: sequencia++ }),
    )
    return resposta?.ok === true
  } catch {
    // O worker pode estar morto neste instante. Não é erro: ele volta na
    // próxima mensagem, e é justamente por isso que o relógio não mora lá.
    return false
  }
}

/** O que a aba sempre sabe de si. Sem `href`: não coletamos navegação. */
function contexto() {
  return {
    provider: location.hostname,
    // O titulo da ABA, cru. O backend ja sabe limpar cada servico.
    //
    // A janela do Chrome publica so o titulo da aba ATIVA, e por isso quatro
    // dos cinco servicos ficavam sem nome assim que a pessoa trocava de aba —
    // Prime Video, Disney+, Max e YouTube nao capturavam nada em segundo
    // plano. A extensao esta DENTRO de cada aba e le o titulo dela sempre.
    //
    // Cru de proposito: `limpar_titulo_de_janela` no backend conhece o formato
    // de cada servico, custou caro para acertar e tem teste para cada caso.
    // Limpar aqui seria uma segunda verdade sobre a mesma string.
    documentTitle: document.title || null,
    ...ondeEstaOVideo(),
    ...ondeEstaOBotaoDeTelaCheia(),
    ...telemetriaDaPagina(),
    ...metadataAtual(),
  }
}

/**
 * Onde o vídeo está na JANELA, em fração — para a tela cheia acertar nele.
 *
 * A tela cheia é um duplo clique, e não uma tecla: o atalho de teclado é de
 * cada site e nenhum aplica igual (no Max, com a janela em foco, o F não fazia
 * absolutamente nada — medido). Mas o clique mirava o CENTRO DA JANELA, e isso
 * só acerta o vídeo enquanto ele ocupa o meio da tela.
 *
 * Medido no Prime em 26/08/2026: o vídeo toca em `/detail/`, com a lista de
 * episódios e a sinopse em volta. O centro da janela cai no conteúdo da
 * página — não no vídeo.
 *
 * Em FRAÇÃO da janela, e não em pixels, por dois motivos: o backend já sabe
 * clicar assim (`_clicar_na_janela`, o mesmo caminho do toque na tela
 * espelhada), e a fração sobrevive ao escalonamento do Windows — 150% de zoom
 * muda os pixels e não muda a proporção.
 *
 * A conversão soma a barra do navegador: `getBoundingClientRect` conta a
 * partir do viewport, e a janela começa acima dele.
 */
/**
 * Quanto da janela o viewport pode deixar de ocupar e a conta ainda valer.
 *
 * A conversão abaixo supõe bordas laterais simétricas — é a suposição padrão, e
 * ela quebra quando há um painel ancorado. Medido no Max em 26/08/2026, com o
 * DevTools aberto à direita:
 *
 *     innerW: 322    outerW: 1284
 *
 * Com esses números, "metade da diferença" daria 481 pixels de borda de cada
 * lado, e o clique erraria o alvo por centenas de pixels — com a mesma
 * confiança de acertar. Quando a proporção não fecha, é melhor não afirmar
 * posição nenhuma e deixar o backend cair para o centro da janela.
 */
const PROPORCAO_MINIMA_DO_VIEWPORT = 0.8

/** O centro de um retângulo, em fração da JANELA. `null` quando não dá. */
function emFracaoDaJanela(r) {
  if (!r || !(r.width > 0) || !(r.height > 0)) return null
  const largura = window.outerWidth || window.innerWidth
  const altura = window.outerHeight || window.innerHeight
  if (!(largura > 0) || !(altura > 0)) return null
  // Painel ancorado: a suposição de bordas simétricas não vale mais.
  if (window.innerWidth / largura < PROPORCAO_MINIMA_DO_VIEWPORT) return null

  const lateral = Math.max(0, (largura - window.innerWidth) / 2)
  const topo = Math.max(0, altura - window.innerHeight - lateral)
  const x = (lateral + r.left + r.width / 2) / largura
  const y = (topo + r.top + r.height / 2) / altura
  // Fora da janela não é alvo: acontece com o elemento rolado para fora.
  if (!(x >= 0 && x <= 1 && y >= 0 && y <= 1)) return null
  return { x: Number(x.toFixed(4)), y: Number(y.toFixed(4)) }
}

function ondeEstaOVideo() {
  const video = observador.elemento()
  if (video === null) return {}
  let ponto = null
  try {
    ponto = emFracaoDaJanela(video.getBoundingClientRect())
  } catch {
    return {}
  }
  if (ponto === null) return {}
  return { videoCentroX: ponto.x, videoCentroY: ponto.y }
}

/**
 * Onde está o BOTÃO de tela cheia do player.
 *
 * A tela cheia era um duplo clique no vídeo, e isso funciona em quem
 * implementa duplo clique — Netflix e Disney+, onde foi testado quando o
 * código nasceu. Prime e Max não implementam, e o resultado descrito pelo
 * usuário em 26/08/2026 é exatamente o de dois cliques SIMPLES chegando:
 *
 *     "apertei 1 vez nada, 2 vezes nada, na 3ª um clique rápido no pausa e
 *      despausa na mesma hora"
 *
 * Clicar no botão é determinístico: não depende de timing entre dois cliques
 * e não tem efeito colateral de play/pause.
 *
 * ## O casamento, e por que ele é por RÓTULO
 *
 * Medido no Max:
 *
 *     button  data-testid="player-ux-fullscreen-button"
 *             aria-label="Tela cheia"   title="Tela cheia (F)"
 *
 * O `data-testid` é o mais específico e vem primeiro. Mas ele é de um serviço
 * só, e escrever quatro seletores dos quais três não foram medidos é o erro
 * que quebrou Prime, Disney+ e Max nesta mesma noite.
 *
 * Então a rede é o RÓTULO — e não é chute: foi exatamente o predicado que
 * encontrou o botão do Max na sonda. Ele é traduzido, por isso a lista tem
 * português, inglês e espanhol.
 *
 * `expandir` fica FORA da lista de propósito. A sonda o incluiu e ele casou
 * com os botões "Expandir Episódios" e "Expandir Você também pode gostar" —
 * clicar neles abriria a bandeja de recomendações em vez da tela cheia.
 */
const ROTULO_DE_TELA_CHEIA = /full[\s-]?screen|tela\s*cheia|pantalla\s*completa/i

/** Um botão de controle tem tamanho de botão. Fora disso é outra coisa. */
const LADO_MINIMO_DO_BOTAO = 16
const LADO_MAXIMO_DO_BOTAO = 200

function raizesDaPagina() {
  // `raizesComShadow` vem de `providers/disney.js`, carregado antes no
  // manifesto: content scripts compartilham o mesmo mundo isolado. Sem ele, a
  // busca ainda funciona — só não atravessa Shadow DOM, e aí o Disney+ fica
  // com o duplo clique de sempre, que nele funciona.
  if (typeof raizesComShadow === 'function') return raizesComShadow(document)
  return [document]
}

function ondeEstaOBotaoDeTelaCheia() {
  let melhor = null
  for (const raiz of raizesDaPagina()) {
    let elementos
    try {
      elementos = raiz.querySelectorAll(
        '[data-testid*="fullscreen"],[data-uia*="fullscreen"],[aria-label],[title]',
      )
    } catch {
      continue
    }
    for (const elemento of elementos) {
      const testid = elemento.getAttribute('data-testid') || elemento.getAttribute('data-uia') || ''
      const rotulo = `${elemento.getAttribute('aria-label') || ''} ${elemento.getAttribute('title') || ''}`
      const casa = /fullscreen/i.test(testid) || ROTULO_DE_TELA_CHEIA.test(rotulo)
      if (!casa) continue
      // SAIR da tela cheia não é entrar. O rótulo muda quando ela está ativa,
      // e clicar no botão errado desfaria o que a pessoa pediu.
      if (/exit|sair|salir/i.test(`${testid} ${rotulo}`)) continue

      let r
      try {
        r = elemento.getBoundingClientRect()
      } catch {
        continue
      }
      const lado = Math.min(r.width, r.height)
      if (lado < LADO_MINIMO_DO_BOTAO || Math.max(r.width, r.height) > LADO_MAXIMO_DO_BOTAO) continue
      if (!elemento.getClientRects().length) continue

      const ponto = emFracaoDaJanela(r)
      if (ponto === null) continue
      // O que tem `data-testid` de tela cheia vence o que só tem rótulo: o
      // atributo é escolhido pelo serviço, o rótulo é traduzido.
      const forca = /fullscreen/i.test(testid) ? 2 : 1
      if (melhor === null || forca > melhor.forca) melhor = { ...ponto, forca }
    }
  }
  if (melhor === null) return {}
  return { telaCheiaX: melhor.x, telaCheiaY: melhor.y }
}

/** Quando o último `play` aconteceu, e quando qualquer evento de mídia. */
let ultimoPlay = null
let ultimoEventoDeMidia = null

/**
 * O que só a PÁGINA sabe de si — Fase 14.
 *
 * Aba ativa, audível e muda vêm do `sender` no worker, porque o Chrome é quem
 * pode afirmá-las. Estas três não têm equivalente lá:
 *
 *   pictureInPicture   o vídeo saiu para a janelinha flutuante. A aba pode
 *                      estar em segundo plano e a pessoa assistindo mesmo
 *                      assim — é o caso que quebra "aba ativa = quem assiste".
 *   visible            a aba está sendo desenhada? Diferente de `active`:
 *                      uma aba ativa numa janela minimizada não é visível.
 *   lastPlay           há quanto tempo alguém mandou tocar. É o desempate
 *                      mais honesto entre duas abas que dizem estar tocando.
 *
 * Em MILISSEGUNDOS desde o evento, e não como carimbo absoluto: o relógio da
 * aba pode estar torto, e o backend não tem como corrigir um carimbo que não é
 * dele. Um intervalo, ele consegue usar.
 */
function telemetriaDaPagina() {
  const desde = (marca) => (marca === null ? null : Math.max(0, Date.now() - marca))
  return {
    pictureInPicture: document.pictureInPictureElement !== null
      && document.pictureInPictureElement !== undefined,
    visible: document.visibilityState === 'visible',
    msDesdeUltimoPlay: desde(ultimoPlay),
    msDesdeUltimoEvento: desde(ultimoEventoDeMidia),
  }
}

/**
 * A metadata do serviço, quando existe adapter para ele.
 *
 * `provider-adapter` é a fonte de MAIOR autoridade para nome de obra na tabela
 * do Merger, e é a única saída para a Netflix: lá a SMTC publica "Netflix" e a
 * janela publica "Netflix", então nenhuma fonte do Windows sabe o que está
 * tocando. Ver `providers/netflix.js`.
 *
 * Sem adapter para o host, devolve vazio — e vazio é diferente de errado: os
 * serviços que nomeiam a obra na janela seguem pelo caminho de sempre.
 */
function metadataAtual() {
  if (typeof lerMetadata !== 'function') return {}
  const lida = lerMetadata(document, location)
  return lida === null ? {} : lida
}

let ultimaMetadata = null

const observador = criarObservador((tipo, leitura) => {
  // Os carimbos são atualizados para TODO evento, inclusive os que não geram
  // envio imediato — é o que faz `msDesdeUltimoEvento` medir atividade real da
  // aba, e não só a atividade que por acaso atravessou a ponte.
  ultimoEventoDeMidia = Date.now()
  if (tipo === 'play') ultimoPlay = Date.now()
  // Elemento trocado é reprodução nova: episódio seguinte, ou outra obra. A
  // identidade tem de virar ANTES do evento sair, ou o `MEDIA_CHANGED` chegaria
  // marcado com a identidade do que acabou.
  if (tipo === 'detached') sessionId = novaSessao()
  const messageType = IMEDIATOS[tipo]
  // Eventos sem envio imediato (`loadedmetadata`, `durationchange`,
  // `ratechange`, `seeking`, `emptied`) não somem: o próximo batimento leva o
  // estado já atualizado. Mandar um por evento encheria o cano com o que o
  // batimento diria de qualquer jeito.
  if (messageType === undefined) return
  void enviar(messageType, { ...contexto(), ...(leitura ?? {}) })
})

/**
 * A metadata muda sem o `<video>` trocar.
 *
 * O autoplay do próximo episódio às vezes reaproveita o mesmo elemento: o
 * `detached` não dispara, o observador não vê nada, e o sistema seguiria
 * reportando o episódio anterior. Quem percebe é a página, e olhar para ela é
 * barato — um `querySelector`, sem atravessar fronteira nenhuma.
 *
 * Só o ENVIO custa, e ele só acontece quando algo mudou de verdade.
 */
function olharAMetadata() {
  if (typeof mesmaMetadata !== 'function') return
  const agora = typeof lerMetadata === 'function' ? lerMetadata(document, location) : null
  if (mesmaMetadata(agora, ultimaMetadata)) return
  ultimaMetadata = agora
  const leitura = observador.ler()
  void enviar('MEDIA_CHANGED', { ...contexto(), ...(leitura ?? {}) })
}

/**
 * Os COMANDOS que descem — Fase 16.
 *
 * Até aqui a ponte só falava para cima. O play/pause era uma TECLA: o
 * ControlFawkes focava a janela do Chrome e apertava a barra de espaço. Isso
 * funciona e continua sendo o plano B, mas tem três limites medidos:
 *
 *   rouba o foco       focar a janela tira o foco de onde a pessoa estava.
 *   erra de aba        a barra de espaço vai para a aba ATIVA, e a ativa nem
 *                      sempre é a que toca. Medido na Fase 14: em 6 dos 18
 *                      instantes com duas abas tocando havia MAIS DE UMA aba
 *                      ativa — janelas diferentes, cada uma com a sua.
 *   não sabe posição   não existe tecla para "pular para 1h23".
 *
 * Comandar o elemento resolve os três. E o elemento é o do OBSERVADOR, não um
 * `querySelector` novo: se fossem dois elementos diferentes, o cartão
 * descreveria um vídeo e o botão comandaria outro.
 *
 * `sessionId` é conferido antes de executar. Um comando é sobre o AGORA, e se
 * a aba já trocou de reprodução entre o pedido e a chegada, executá-lo
 * pausaria o episódio seguinte porque o anterior foi pedido.
 */
const ACOES = {
  PLAY: (video) => video.play(),
  PAUSE: (video) => video.pause(),
  SEEK_TO: (video, valor) => { video.currentTime = valor },
  SEEK_BY: (video, valor) => { video.currentTime = video.currentTime + valor },
}

function executarComando(payload) {
  if (payload === null || typeof payload !== 'object') {
    return { ok: false, detalhe: 'comando sem payload' }
  }
  // A reprodução mudou entre o pedido e a chegada.
  if (payload.sessionId != null && payload.sessionId !== sessionId) {
    return { ok: false, detalhe: 'outra reprodução' }
  }
  const executar = ACOES[payload.acao]
  if (executar === undefined) return { ok: false, detalhe: `ação desconhecida: ${payload.acao}` }

  const video = observador.elemento()
  if (video === null) return { ok: false, detalhe: 'sem elemento' }

  const numero = typeof payload.valor === 'number' && Number.isFinite(payload.valor)
    ? payload.valor
    : null
  if ((payload.acao === 'SEEK_TO' || payload.acao === 'SEEK_BY') && numero === null) {
    return { ok: false, detalhe: 'seek sem valor' }
  }

  try {
    // `play()` devolve uma promessa que rejeita quando o navegador bloqueia o
    // autoplay. Não dá para esperar por ela aqui — a resposta ao worker é
    // síncrona —, e o batimento seguinte conta o estado real de qualquer jeito.
    const talvez = executar(video, numero)
    if (talvez && typeof talvez.catch === 'function') talvez.catch(() => {})
  } catch (erro) {
    return { ok: false, detalhe: String(erro) }
  }
  return { ok: true }
}

chrome.runtime.onMessage.addListener((mensagem, _remetente, responder) => {
  if (mensagem?.messageType !== 'COMANDO') return false
  responder(executarComando(mensagem.payload))
  return false
})

let vigiaDaMetadata = setInterval(olharAMetadata, 2000)

// O relógio. Sobrevive ao worker reiniciar porque não é o worker que o mantém.
let relogio = null

function baterAgora() {
  const leitura = observador.ler()
  // Sem elemento não há o que sincronizar. Mandar um batimento vazio faria o
  // backend achar que a aba tem mídia parada, em vez de mídia nenhuma.
  if (leitura === null) return
  void enviar('POSITION_SYNC', { ...contexto(), ...leitura })
}

function ligarRelogio() {
  if (relogio === null) relogio = setInterval(baterAgora, SEGUNDOS_ENTRE_BATIMENTOS * 1000)
}

function desligarRelogio() {
  if (relogio !== null) clearInterval(relogio)
  relogio = null
}

ligarRelogio()

/**
 * A aba indo embora — e as DUAS formas de ir embora.
 *
 * `pagehide` dispara em duas situações que exigem tratamento oposto, e tratá-las
 * igual deixava a aba surda para sempre:
 *
 *   persisted === false   a página está sendo DESTRUÍDA. Navegou para outro
 *                         lugar, fechou a aba, fechou o navegador. Desmontar é
 *                         o certo, e o `SESSION_ENDED` avisa o backend em vez
 *                         de deixá-lo adivinhar por silêncio.
 *
 *   persisted === true    a página está indo para o BFCACHE. Ela é congelada,
 *                         não destruída, e volta inteira quando a pessoa aperta
 *                         "voltar" — SEM reexecutar script nenhum.
 *
 * A versão anterior desmontava nos dois casos, e com `{ once: true }`. No
 * segundo, a aba voltava viva, com vídeo tocando, e o content script já tinha
 * parado o relógio, o vigia e o observador — para sempre, porque o listener
 * também já tinha sido removido. Nada acusava: nem erro, nem log, nem porta
 * caída. Só silêncio.
 *
 * É o candidato mais forte para os silêncios medidos em 25/08/2026, em que a
 * ponte parava de mandar eventos sem motivo aparente e voltava só depois de um
 * F5 na aba.
 */
addEventListener('pagehide', (evento) => {
  // Congelada não deve bater: um batimento de página congelada descreveria um
  // instante que não está acontecendo.
  desligarRelogio()
  clearInterval(vigiaDaMetadata)
  void enviar('SESSION_ENDED', {
    ...contexto(),
    motivo: evento.persisted ? 'bfcache' : 'pagehide',
  })
  // Só solta o observador quando a página não volta. No bfcache o `<video>`
  // continua lá, e reencontrá-lo depois seria trabalho à toa.
  if (!evento.persisted) observador.parar()
})

// E a volta. Sem isto, tudo acima é despedida sem reencontro.
addEventListener('pageshow', (evento) => {
  if (!evento.persisted) return
  vigiaDaMetadata = setInterval(olharAMetadata, 2000)
  ligarRelogio()
  // Um batimento imediato: esperar dez segundos para dizer "voltei" deixaria o
  // cartão mostrando o que estava tocando antes da congelada.
  ultimaMetadata = null
  baterAgora()
})
