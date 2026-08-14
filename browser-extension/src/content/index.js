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

function envelope(messageType, payload) {
  return { protocolVersion: PROTOCOL_VERSION, messageType, timestamp: Date.now(), payload }
}

async function enviar(messageType, payload) {
  try {
    // O `tabId` NÃO vai daqui: quem o preenche é o worker, a partir do
    // `sender`. Uma página não pode ter voz sobre qual aba ela é.
    const resposta = await chrome.runtime.sendMessage(
      envelope(messageType, { ...payload, seq: sequencia++ }),
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
  return { provider: location.hostname }
}

const observador = criarObservador((tipo, leitura) => {
  const messageType = IMEDIATOS[tipo]
  // Eventos sem envio imediato (`loadedmetadata`, `durationchange`,
  // `ratechange`, `seeking`, `emptied`) não somem: o próximo batimento leva o
  // estado já atualizado. Mandar um por evento encheria o cano com o que o
  // batimento diria de qualquer jeito.
  if (messageType === undefined) return
  void enviar(messageType, { ...contexto(), ...(leitura ?? {}) })
})

// O relógio. Sobrevive ao worker reiniciar porque não é o worker que o mantém.
const relogio = setInterval(() => {
  const leitura = observador.ler()
  // Sem elemento não há o que sincronizar. Mandar um batimento vazio faria o
  // backend achar que a aba tem mídia parada, em vez de mídia nenhuma.
  if (leitura === null) return
  void enviar('POSITION_SYNC', { ...contexto(), ...leitura })
}, SEGUNDOS_ENTRE_BATIMENTOS * 1000)

// A aba indo embora encerra a sessão de forma explícita, em vez de deixar o
// backend adivinhar por silêncio.
addEventListener('pagehide', () => {
  clearInterval(relogio)
  observador.parar()
  void enviar('SESSION_ENDED', { ...contexto(), motivo: 'pagehide' })
}, { once: true })
