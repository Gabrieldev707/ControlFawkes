export type ProtocolVersion = 1
export const PROTOCOL_VERSION: ProtocolVersion = 1

export type ConnectionState =
  | 'disconnected'
  | 'connecting'
  | 'connected'
  | 'error'

export type ServerState =
  | 'AUTH_REQUIRED'
  | 'PAIRING'
  | 'READY'
  | 'BUSY'

export type AuthState =
  | 'checking'
  | 'pairing_required'
  | 'pairing'
  | 'authenticated'
  | 'rejected'

export const ORB_STATES = [
  'idle',
  'listening',
  'transcribing',
  'needs_selection',
  'executing',
  'success',
  'error',
] as const

export type OrbState = (typeof ORB_STATES)[number]

export const PLATFORMS = [
  'NETFLIX',
  'MAX',
  'PRIME_VIDEO',
  'DISNEY_PLUS',
  'YOUTUBE',
  'SPOTIFY',
] as const

export type Platform = (typeof PLATFORMS)[number]

// Plataformas com URL de busca estável e verificada. Max e Disney+ ficam de
// fora: nenhuma das duas expõe URL de busca confiável hoje. Oferecê-las na
// escolha levaria a um beco sem saída. Ver docs/PHASE2_PROGRESS.md.
export const SEARCHABLE_PLATFORMS = [
  'NETFLIX',
  'PRIME_VIDEO',
  'YOUTUBE',
  'SPOTIFY',
] as const

export type SearchablePlatform = (typeof SEARCHABLE_PLATFORMS)[number]

export function isSearchablePlatform(value: unknown): value is SearchablePlatform {
  return typeof value === 'string'
    && SEARCHABLE_PLATFORMS.includes(value as SearchablePlatform)
}

export const LAUNCH_STRATEGIES = [
  'CHROME',
  'SPOTIFY_APP',
  'SPOTIFY_WEB_CHROME',
] as const

export type LaunchStrategy = (typeof LAUNCH_STRATEGIES)[number]

export function isPlatform(value: unknown): value is Platform {
  return typeof value === 'string' && PLATFORMS.includes(value as Platform)
}

export const ERROR_CODES = [
  'INVALID_JSON',
  'INVALID_PAYLOAD',
  'UNSUPPORTED_MESSAGE',
  'NOT_IMPLEMENTED',
  'UNKNOWN_COMMAND',
  'UNAUTHORIZED',
  'INVALID_TOKEN',
  'PAIRING_REQUIRED',
  'PIN_INVALID',
  'PIN_EXPIRED',
  'TOO_MANY_ATTEMPTS',
  'PROTOCOL_VERSION_MISMATCH',
  'PLATFORM_OPEN_FAILED',
  'MEDIA_SEARCH_FAILED',
  'MEDIA_LINK_FAILED',
  'MEDIA_CONTROL_FAILED',
  'MEDIA_SESSION_NOT_FOUND',
  'MEDIA_ACTION_UNSUPPORTED',
  'SYSTEM_VOLUME_FAILED',
  'POINTER_CONTROL_FAILED',
  'POINTER_RATE_LIMITED',
  'RATE_LIMITED',
  'KEYBOARD_CONTROL_FAILED',
  'NAVIGATION_FAILED',
  'NAVIGATION_RATE_LIMITED',
  'INTERNAL_ERROR',
] as const

export type ErrorCode = (typeof ERROR_CODES)[number]

interface ClientMessageBase {
  protocolVersion: ProtocolVersion
  requestId: string
}

export interface AuthMessage extends ClientMessageBase {
  type: 'AUTH'
  payload: { deviceId: string; token: string }
}

export interface PairDeviceMessage extends ClientMessageBase {
  type: 'PAIR_DEVICE'
  payload: { pin: string; deviceName: string }
}

export interface PlatformSelectedMessage extends ClientMessageBase {
  type: 'PLATFORM_SELECTED'
  payload: { platform: Platform }
}

export interface TextCommandMessage extends ClientMessageBase {
  type: 'TEXT_COMMAND'
  payload: { query: string }
}

export const MEDIA_ACTIONS = [
  'MEDIA_PLAY_PAUSE',
  'MEDIA_PREVIOUS',
  'MEDIA_NEXT',
  'MEDIA_SEEK_BACK',
  'MEDIA_SEEK_FORWARD',
  'MEDIA_FULLSCREEN',
  'MEDIA_EXIT_FULLSCREEN',
] as const

export type MediaAction = (typeof MEDIA_ACTIONS)[number]

export interface MediaControlMessage extends ClientMessageBase {
  type: MediaAction
}

export const VOLUME_ACTIONS = [
  'SYSTEM_VOLUME_GET',
  'SYSTEM_VOLUME_SET',
  'SYSTEM_VOLUME_DELTA',
  'SYSTEM_MUTE_TOGGLE',
] as const

export type VolumeAction = (typeof VOLUME_ACTIONS)[number]

export interface VolumeGetMessage extends ClientMessageBase {
  type: 'SYSTEM_VOLUME_GET'
}

export interface VolumeSetMessage extends ClientMessageBase {
  type: 'SYSTEM_VOLUME_SET'
  payload: { level: number }
}

export interface VolumeDeltaMessage extends ClientMessageBase {
  type: 'SYSTEM_VOLUME_DELTA'
  payload: { delta: -5 | 5 }
}

export interface VolumeMuteToggleMessage extends ClientMessageBase {
  type: 'SYSTEM_MUTE_TOGGLE'
}

export const POINTER_ACTIONS = [
  'POINTER_MOVE',
  'POINTER_CLICK',
  'POINTER_DOUBLE_CLICK',
  'POINTER_RIGHT_CLICK',
  'POINTER_SCROLL',
  'POINTER_DOWN',
  'POINTER_UP',
] as const

export type PointerAction = (typeof POINTER_ACTIONS)[number]

export type PointerPayload = { dx: number; dy: number } | { delta: -120 | 120 }

export interface PointerMoveMessage extends ClientMessageBase {
  type: 'POINTER_MOVE'
  payload: { dx: number; dy: number }
}

export interface PointerScrollMessage extends ClientMessageBase {
  type: 'POINTER_SCROLL'
  payload: { delta: -120 | 120 }
}

export interface PointerButtonMessage extends ClientMessageBase {
  type: Exclude<PointerAction, 'POINTER_MOVE' | 'POINTER_SCROLL'>
}

export const SAFE_KEYS = [
  'ENTER',
  'BACKSPACE',
  'ESCAPE',
  'ARROW_UP',
  'ARROW_DOWN',
  'ARROW_LEFT',
  'ARROW_RIGHT',
  'TAB',
  'SPACE',
] as const

export type SafeKey = (typeof SAFE_KEYS)[number]
export type KeyboardAction = 'KEYBOARD_TEXT' | 'KEYBOARD_KEY'

export interface KeyboardTextMessage extends ClientMessageBase {
  type: 'KEYBOARD_TEXT'
  payload: { text: string }
}

export interface KeyboardKeyMessage extends ClientMessageBase {
  type: 'KEYBOARD_KEY'
  payload: { key: SafeKey }
}

// Direcional: contrato separado do teclado porque repete ao segurar a seta e
// tem limite de taxa próprio. NAVIGATE_HOME ainda não existe.
export const NAVIGATION_ACTIONS = [
  'NAVIGATE_UP',
  'NAVIGATE_DOWN',
  'NAVIGATE_LEFT',
  'NAVIGATE_RIGHT',
  'NAVIGATE_CONFIRM',
  'NAVIGATE_BACK',
] as const

export type NavigationAction = (typeof NAVIGATION_ACTIONS)[number]

// Só as setas repetem: confirmar/voltar repetindo entrariam em vários itens
// ou sairiam de várias telas.
export const REPEATABLE_NAVIGATION_ACTIONS: readonly NavigationAction[] = [
  'NAVIGATE_UP',
  'NAVIGATE_DOWN',
  'NAVIGATE_LEFT',
  'NAVIGATE_RIGHT',
]

export interface NavigationMessage extends ClientMessageBase {
  type: NavigationAction
}

export interface SearchMediaMessage extends ClientMessageBase {
  type: 'SEARCH_MEDIA'
  payload: { platform: SearchablePlatform; query: string }
}

export type ClientMessage =
  | AuthMessage
  | PairDeviceMessage
  | PlatformSelectedMessage
  | TextCommandMessage
  | MediaControlMessage
  | VolumeGetMessage
  | VolumeSetMessage
  | VolumeDeltaMessage
  | VolumeMuteToggleMessage
  | PointerMoveMessage
  | PointerScrollMessage
  | PointerButtonMessage
  | KeyboardTextMessage
  | KeyboardKeyMessage
  | NavigationMessage
  | SearchMediaMessage

export interface StateUpdateMessage {
  protocolVersion: ProtocolVersion
  type: 'STATE_UPDATE'
  state: ServerState
  message: string
}

export interface AuthResultMessage {
  protocolVersion: ProtocolVersion
  type: 'AUTH_RESULT'
  requestId: string
  success: true
  message: string
}

export interface PairResultMessage {
  protocolVersion: ProtocolVersion
  type: 'PAIR_RESULT'
  requestId: string
  success: true
  message: string
  deviceId: string
  token: string
}

export interface PlatformCommandData {
  intent: 'OPEN_PLATFORM'
  platform: Platform
  executed: true
  strategy: LaunchStrategy
}

export interface SearchMediaCommandData {
  intent: 'SEARCH_MEDIA'
  platform: SearchablePlatform
  executed: true
  strategy: LaunchStrategy
}

export interface HelpCommandData {
  intent: 'SHOW_HELP'
  commands: string[]
  executed: false
}

export interface MediaCommandData {
  intent: 'MEDIA_CONTROL'
  action: MediaAction
  platform: Platform
  session: 'WEB' | 'APP'
  executed: true
}

export interface VolumeCommandData {
  intent: 'SYSTEM_VOLUME'
  action: VolumeAction
  level: number
  muted: boolean
  executed: true
}

export interface MediaLinkCommandData {
  intent: 'OPEN_ALLOWED_MEDIA_LINK'
  platform: 'YOUTUBE'
  executed: true
  strategy: LaunchStrategy
}

export interface NavigationCommandData {
  intent: 'NAVIGATION'
  action: NavigationAction
  executed: true
}

export interface NeedsPlatformMessage {
  protocolVersion: ProtocolVersion
  type: 'NEEDS_PLATFORM'
  requestId: string
  query: string
  suggestedPlatforms: SearchablePlatform[]
}

export interface PointerCommandData {
  intent: 'POINTER_CONTROL'
  action: PointerAction
  executed: true
}

export interface KeyboardCommandData {
  intent: 'KEYBOARD_CONTROL'
  action: KeyboardAction
  executed: true
}

export interface CommandResultMessage {
  protocolVersion: ProtocolVersion
  type: 'COMMAND_RESULT'
  requestId: string
  success: true
  message: string
  data: PlatformCommandData
    | SearchMediaCommandData
    | HelpCommandData
    | MediaCommandData
    | VolumeCommandData
    | PointerCommandData
    | KeyboardCommandData
    | NavigationCommandData
    | MediaLinkCommandData
}

export interface ErrorMessage {
  protocolVersion: ProtocolVersion
  type: 'ERROR'
  requestId: string
  code: ErrorCode
  message: string
}

export type ServerMessage =
  | StateUpdateMessage
  | AuthResultMessage
  | PairResultMessage
  | CommandResultMessage
  | NeedsPlatformMessage
  | ErrorMessage
