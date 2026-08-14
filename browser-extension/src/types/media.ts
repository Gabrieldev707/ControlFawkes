/**
 * O que a extensão envia — e só isso.
 *
 * Espelho do contrato em `backend/app/bridge/contratos.py`, que é a
 * AUTORIDADE: o Media Merger vive no Python, e um contrato com dois donos
 * diverge. Campo novo aqui sem o par de lá é o mesmo defeito que já custou
 * caro no protocolo do celular, onde uma lista fechada de campos fazia a
 * mensagem inteira ser descartada em silêncio.
 *
 * O que a extensão NÃO envia, de propósito:
 *
 *   consumptionState   é DERIVADO, e derivado no backend. A extensão não sabe
 *                      o suficiente para responder "isto conta como assistido"
 *                      — ela vê uma aba, não o computador.
 *   trustworthy        quem decide autoridade é a tabela de capabilities do
 *                      backend, não a fonte falando de si mesma. Uma fonte que
 *                      se declara confiável não é um contrato, é uma opinião.
 */

/** O estado TÉCNICO do elemento. Não responde "a pessoa está assistindo". */
export type EstadoDeReproducao = 'playing' | 'paused' | 'ended' | 'unknown'

export type TipoDeMidia = 'movie' | 'episode' | 'video' | 'unknown'

/**
 * Uma sessão de mídia vista de dentro de uma aba.
 *
 * Tudo opcional menos o que a aba sempre sabe de si: quem ela é e quando falou.
 * Ausente e `null` querem dizer coisas diferentes — ausente é "não observei",
 * `null` é "observei e não existe".
 */
export interface BrowserMediaSession {
  /** Identifica a REPRODUÇÃO, não a aba: muda quando a mídia muda. */
  sessionId: string
  tabId: number
  windowId: number

  provider: string
  mediaType?: TipoDeMidia

  workTitle?: string | null
  episodeTitle?: string | null
  seasonNumber?: number | null
  episodeNumber?: number | null

  /** Do `<video>`: `paused`, `ended`. */
  playbackState: EstadoDeReproducao
  /** Da aba (`chrome.tabs.Tab.audible`) — pergunta diferente da de cima. */
  audible?: boolean
  muted?: boolean

  currentTime?: number
  /** Pode ser `Infinity` (ao vivo) ou `NaN` (ainda carregando) no elemento;
   *  os dois viram `null` aqui, porque nenhum dos dois é uma duração. */
  duration?: number | null
  playbackRate?: number

  /** Quando a leitura foi feita, para o backend julgar frescor. */
  timestamp: number
}

/** Envelope de tudo que atravessa o Native Messaging. */
export interface Envelope<T = unknown> {
  protocolVersion: 1
  messageType: string
  timestamp: number
  payload?: T
}
