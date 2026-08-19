import {
  ERROR_CODES,
  LAUNCH_STRATEGIES,
  MEDIA_ACTIONS,
  NAVIGATION_ACTIONS,
  VOLUME_ACTIONS,
  VOLUME_SCOPES,
  POINTER_ACTIONS,
  SCREEN_ACTIONS,
  isPlatform,
  isSearchablePlatform,
  type ErrorCode,
  type NavigationAction,
  type ScreenAction,
  type VolumeScope,
  type ServerMessage,
  type ServerState,
} from './types'


const SERVER_STATES: readonly ServerState[] = [
  'AUTH_REQUIRED',
  'PAIRING',
  'READY',
  'BUSY',
]

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function hasOnlyKeys(
  value: Record<string, unknown>,
  keys: readonly string[],
  optional: readonly string[] = [],
): boolean {
  const allowed = new Set([...keys, ...optional])
  return Object.keys(value).every((key) => allowed.has(key)) && keys.every((key) => key in value)
}

function isRequestId(value: unknown): value is string {
  return typeof value === 'string' && value.length >= 1 && value.length <= 128
}

function isMessage(value: unknown): value is string {
  return typeof value === 'string' && value.length > 0
}

export function isErrorCode(value: unknown): value is ErrorCode {
  return typeof value === 'string' && ERROR_CODES.includes(value as ErrorCode)
}

function isPlatformData(value: unknown): boolean {
  return isRecord(value)
    && hasOnlyKeys(value, ['intent', 'platform', 'executed', 'strategy'])
    && value.intent === 'OPEN_PLATFORM'
    && isPlatform(value.platform)
    && value.executed === true
    && typeof value.strategy === 'string'
    && LAUNCH_STRATEGIES.includes(value.strategy as (typeof LAUNCH_STRATEGIES)[number])
}

function isSearchMediaData(value: unknown): boolean {
  return isRecord(value)
    && hasOnlyKeys(value, ['intent', 'platform', 'executed', 'strategy'])
    && value.intent === 'SEARCH_MEDIA'
    && isSearchablePlatform(value.platform)
    && value.executed === true
    && typeof value.strategy === 'string'
    && LAUNCH_STRATEGIES.includes(value.strategy as (typeof LAUNCH_STRATEGIES)[number])
}

function isHelpData(value: unknown): boolean {
  return isRecord(value)
    && hasOnlyKeys(value, ['intent', 'commands', 'executed'])
    && value.intent === 'SHOW_HELP'
    && Array.isArray(value.commands)
    && value.commands.length > 0
    && value.commands.every((command) => typeof command === 'string' && command.length > 0)
    && value.executed === false
}

function isMediaData(value: unknown): boolean {
  return isRecord(value)
    && hasOnlyKeys(
      value,
      ['intent', 'action', 'platform', 'session', 'executed'],
      ['focused'],
    )
    && (value.focused === undefined || typeof value.focused === 'boolean')
    && value.intent === 'MEDIA_CONTROL'
    && typeof value.action === 'string'
    && MEDIA_ACTIONS.includes(value.action as (typeof MEDIA_ACTIONS)[number])
    && isPlatform(value.platform)
    && (value.session === 'WEB' || value.session === 'APP')
    && value.executed === true
}

function isVolumeData(value: unknown): boolean {
  return isRecord(value)
    && hasOnlyKeys(value, [
      'intent', 'action', 'level', 'muted', 'scope', 'target', 'executed',
    ])
    && value.intent === 'SYSTEM_VOLUME'
    && typeof value.scope === 'string'
    && VOLUME_SCOPES.includes(value.scope as VolumeScope)
    && (value.target === null || typeof value.target === 'string')
    && typeof value.action === 'string'
    && VOLUME_ACTIONS.includes(value.action as (typeof VOLUME_ACTIONS)[number])
    && typeof value.level === 'number'
    && Number.isInteger(value.level)
    && value.level >= 0
    && value.level <= 100
    && typeof value.muted === 'boolean'
    && value.executed === true
}

function isPointerData(value: unknown): boolean {
  return isRecord(value)
    && hasOnlyKeys(value, ['intent', 'action', 'executed'])
    && value.intent === 'POINTER_CONTROL'
    && typeof value.action === 'string'
    && POINTER_ACTIONS.includes(value.action as (typeof POINTER_ACTIONS)[number])
    && value.executed === true
}

function isKeyboardData(value: unknown): boolean {
  return isRecord(value)
    && hasOnlyKeys(value, ['intent', 'action', 'executed'])
    && value.intent === 'KEYBOARD_CONTROL'
    && (value.action === 'KEYBOARD_TEXT' || value.action === 'KEYBOARD_KEY')
    && value.executed === true
}

function isMediaLinkData(value: unknown): boolean {
  return isRecord(value)
    && hasOnlyKeys(value, ['intent', 'platform', 'executed', 'strategy'])
    && value.intent === 'OPEN_ALLOWED_MEDIA_LINK'
    && value.platform === 'YOUTUBE'
    && value.executed === true
    && typeof value.strategy === 'string'
    && LAUNCH_STRATEGIES.includes(value.strategy as (typeof LAUNCH_STRATEGIES)[number])
}

function isScreenData(value: unknown): boolean {
  return isRecord(value)
    && hasOnlyKeys(value, ['intent', 'action', 'platform', 'executed'])
    && value.intent === 'SCREEN_CONTROL'
    && typeof value.action === 'string'
    && SCREEN_ACTIONS.includes(value.action as ScreenAction)
    && isPlatform(value.platform)
    && value.executed === true
}

function isNavigationData(value: unknown): boolean {
  return isRecord(value)
    && hasOnlyKeys(value, ['intent', 'action', 'executed'])
    && value.intent === 'NAVIGATION'
    && typeof value.action === 'string'
    && NAVIGATION_ACTIONS.includes(value.action as NavigationAction)
    && value.executed === true
}

function isNowPlayingSession(value: unknown): boolean {
  // Nulo é o estado "nada tocando", e precisa chegar: sem ele o cartão
  // anterior ficaria congelado na tela depois de o filme acabar.
  if (value === null) return true
  return isRecord(value)
    && hasOnlyKeys(
      value,
      [
        'title', 'artist', 'app', 'platform', 'playing',
        'positionSeconds', 'durationSeconds', 'thumbnailId',
      ],
      // Opcionais: campos que o servidor pode não mandar. `hasOnlyKeys` fecha a
      // lista, então um campo novo no backend que não passe por aqui derruba a
      // mensagem INTEIRA — e o cartão fica em "nada tocando" para sempre, sem
      // erro nenhum na tela nem no log. Foi o que aconteceu com `episode`.
      ['posterUrl', 'episode', 'positionStale', 'titleIsWork'],
    )
    && (
      value.positionStale === undefined
      || typeof value.positionStale === 'boolean'
    )
    && (
      value.titleIsWork === undefined
      || typeof value.titleIsWork === 'boolean'
    )
    // O pôster vira o `src` de uma imagem: aceitar qualquer texto deixaria um
    // `javascript:` entrar na página.
    && (
      value.posterUrl === undefined
      || value.posterUrl === null
      || (typeof value.posterUrl === 'string' && value.posterUrl.startsWith('https://'))
    )
    && typeof value.title === 'string'
    && value.title.length > 0
    && (
      value.episode === undefined
      || value.episode === null
      || typeof value.episode === 'string'
    )
    && (value.artist === null || typeof value.artist === 'string')
    && (value.app === null || typeof value.app === 'string')
    && (value.platform === null || isPlatform(value.platform))
    && typeof value.playing === 'boolean'
    && isOptionalSeconds(value.positionSeconds)
    && isOptionalSeconds(value.durationSeconds)
    && (value.thumbnailId === null || typeof value.thumbnailId === 'string')
}

function isOptionalSeconds(value: unknown): boolean {
  return value === null
    || (typeof value === 'number' && Number.isFinite(value) && value >= 0)
}

function isAvailability(value: unknown): boolean {
  // Ausente é o caso normal: catálogo desligado, sem chave ou sem resultado.
  if (value === undefined || value === null) return true
  return isRecord(value)
    && hasOnlyKeys(value, ['title', 'year', 'posterUrl', 'platforms'], ['kind'])
    && (value.kind === undefined || value.kind === 'MOVIE' || value.kind === 'TV')
    && typeof value.title === 'string'
    && value.title.length > 0
    && (value.year === null || (typeof value.year === 'number' && Number.isInteger(value.year)))
    // A URL do pôster vem do servidor, mas ela vira o `src` de uma imagem:
    // aceitar qualquer texto deixaria um `javascript:` entrar na página.
    && (
      value.posterUrl === null
      || (typeof value.posterUrl === 'string' && value.posterUrl.startsWith('https://'))
    )
    && Array.isArray(value.platforms)
    && value.platforms.every(isPlatform)
}

export function isServerMessage(value: unknown): value is ServerMessage {
  if (!isRecord(value) || value.protocolVersion !== 1 || typeof value.type !== 'string') {
    return false
  }

  switch (value.type) {
    case 'STATE_UPDATE':
      return hasOnlyKeys(value, ['protocolVersion', 'type', 'state', 'message'])
        && typeof value.state === 'string'
        && SERVER_STATES.includes(value.state as ServerState)
        && isMessage(value.message)
    case 'AUTH_RESULT':
      return hasOnlyKeys(value, ['protocolVersion', 'type', 'requestId', 'success', 'message'])
        && isRequestId(value.requestId)
        && value.success === true
        && isMessage(value.message)
    case 'PAIR_RESULT':
      return hasOnlyKeys(value, [
        'protocolVersion', 'type', 'requestId', 'success', 'message', 'deviceId', 'token',
      ])
        && isRequestId(value.requestId)
        && value.success === true
        && isMessage(value.message)
        && typeof value.deviceId === 'string'
        && value.deviceId.length > 0
        && typeof value.token === 'string'
        && value.token.length >= 16
    case 'COMMAND_RESULT':
      return hasOnlyKeys(value, [
        'protocolVersion', 'type', 'requestId', 'success', 'message', 'data',
      ])
        && isRequestId(value.requestId)
        && value.success === true
        && isMessage(value.message)
        && (
          isPlatformData(value.data)
          || isSearchMediaData(value.data)
          || isHelpData(value.data)
          || isMediaData(value.data)
          || isVolumeData(value.data)
          || isPointerData(value.data)
          || isKeyboardData(value.data)
          || isNavigationData(value.data)
          || isMediaLinkData(value.data)
          || isScreenData(value.data)
        )
    case 'NEEDS_PLATFORM':
      // `openOnlyPlatforms` é opcional: a validação rejeita a mensagem inteira
      // quando encontra uma chave que não conhece, então exigi-la quebraria o
      // controle contra um backend anterior — e foi assim que a tela travou em
      // "Processando comando..." quando o campo apareceu só de um lado.
      return hasOnlyKeys(
        value,
        ['protocolVersion', 'type', 'requestId', 'query', 'suggestedPlatforms'],
        ['openOnlyPlatforms', 'availability', 'availabilityAlternative'],
      )
        && isAvailability(value.availability)
        && isAvailability(value.availabilityAlternative)
        && isRequestId(value.requestId)
        && typeof value.query === 'string'
        && value.query.length > 0
        && value.query.length <= 200
        && Array.isArray(value.suggestedPlatforms)
        && value.suggestedPlatforms.length > 0
        && value.suggestedPlatforms.every(isSearchablePlatform)
        && (
          value.openOnlyPlatforms === undefined
          || (Array.isArray(value.openOnlyPlatforms) && value.openOnlyPlatforms.every(isPlatform))
        )
    case 'HEARTBEAT':
      return hasOnlyKeys(value, ['protocolVersion', 'type'])
    case 'NOW_PLAYING':
      return hasOnlyKeys(value, ['protocolVersion', 'type', 'session'])
        && isNowPlayingSession(value.session)
    case 'ERROR':
      return hasOnlyKeys(value, ['protocolVersion', 'type', 'requestId', 'code', 'message'])
        && isRequestId(value.requestId)
        && isErrorCode(value.code)
        && isMessage(value.message)
    default:
      return false
  }
}

export function parseServerMessage(raw: string): ServerMessage | null {
  if (raw.length > 8192) return null
  try {
    const value: unknown = JSON.parse(raw)
    return isServerMessage(value) ? value : null
  } catch {
    return null
  }
}
