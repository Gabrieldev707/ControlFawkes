/**
 * O envelope, e as duas fronteiras que ele atravessa.
 *
 *   content script  ──(chrome.runtime.sendMessage)──►  service worker
 *   service worker  ──(chrome.runtime.connectNative)─►  native host
 *
 * O mesmo formato nas duas, de propósito: um envelope só significa um lugar só
 * para validar versão, e é o backend quem valida de verdade — a extensão não é
 * tratada como fonte confiável só porque é nossa.
 */

export const PROTOCOL_VERSION = 1

/** Eventos de ciclo de vida. Existem para MEDIR o MV3, não para assumi-lo. */
export const CicloDeVida = {
  WORKER_STARTED: 'WORKER_STARTED',
  WORKER_STOPPING: 'WORKER_STOPPING',
  PORT_CONNECTED: 'PORT_CONNECTED',
  PORT_DISCONNECTED: 'PORT_DISCONNECTED',
  TRANSPORT_CONNECTED: 'TRANSPORT_CONNECTED',
  TRANSPORT_DISCONNECTED: 'TRANSPORT_DISCONNECTED',
}

/** Eventos de mídia. A lista curta da Fase 6 — nada de inventar antes de haver
 *  consumidor. */
export const Midia = {
  SESSION_STARTED: 'SESSION_STARTED',
  MEDIA_CHANGED: 'MEDIA_CHANGED',
  PLAY: 'PLAY',
  PAUSE: 'PAUSE',
  SEEK: 'SEEK',
  ENDED: 'ENDED',
  POSITION_SYNC: 'POSITION_SYNC',
  SESSION_ENDED: 'SESSION_ENDED',
}

export function envelope(messageType, payload) {
  return {
    protocolVersion: PROTOCOL_VERSION,
    messageType,
    timestamp: Date.now(),
    payload,
  }
}

/**
 * O envelope tem a forma mínima esperada?
 *
 * Barato de propósito: a validação séria é do backend. O que esta função evita
 * é o service worker repassar lixo adiante e o erro aparecer três camadas
 * depois, sem quem o produziu.
 */
export function envelopeValido(valor) {
  return (
    typeof valor === 'object'
    && valor !== null
    && valor.protocolVersion === PROTOCOL_VERSION
    && typeof valor.messageType === 'string'
    && valor.messageType.length > 0
    && typeof valor.timestamp === 'number'
  )
}
