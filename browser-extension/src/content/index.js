/**
 * O content script — e é aqui que mora o relógio.
 *
 * Não é preferência de organização: no MV3 o service worker morre por
 * inatividade, e um `setInterval` lá dentro simplesmente para de existir sem
 * avisar. O content script vive enquanto a aba viver, então é o único lugar
 * onde um relógio é honesto. Master Loop, critério de implementação incorreta
 * nº 4.
 *
 * O que ele faz na Fase 4: prova que roda, e prova que o relógio dele sobrevive
 * ao worker reiniciar. A observação do `<video>` entra na Fase 5.
 *
 * SEM `import`, de propósito: um content script declarado no manifesto NÃO é
 * módulo, e `import` ali é erro de sintaxe — a aba fica sem script e nada
 * acusa. As três constantes abaixo são a duplicação mínima de
 * `../messaging/messages.js`, e a decisão de introduzir um passo de build (que
 * acabaria com a duplicação) está adiada de propósito: um bundler na Fase 4
 * seria complexidade antes de necessidade.
 */

const PROTOCOL_VERSION = 1
const SEGUNDOS_ENTRE_BATIMENTOS = 10

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

void enviar('PORT_CONNECTED', { href: location.href, origem: location.origin })

// O relógio. Sobrevive ao worker reiniciar porque não é o worker que o mantém.
const relogio = setInterval(() => {
  void enviar('POSITION_SYNC', {
    // A Fase 5 troca isto pela leitura real do elemento. Aqui só prova que o
    // batimento continua saindo com o worker indo e voltando.
    observadoEm: Date.now(),
  })
}, SEGUNDOS_ENTRE_BATIMENTOS * 1000)

// A aba indo embora encerra a sessão de forma explícita, em vez de deixar o
// backend adivinhar por silêncio.
addEventListener('pagehide', () => {
  clearInterval(relogio)
  void enviar('SESSION_ENDED', { motivo: 'pagehide' })
}, { once: true })
