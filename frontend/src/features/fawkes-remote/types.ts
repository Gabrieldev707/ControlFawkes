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
  'MEDIA_CONTROL_FAILED',
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

export type ClientMessage =
  | AuthMessage
  | PairDeviceMessage
  | PlatformSelectedMessage
  | TextCommandMessage
  | MediaControlMessage

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
  executed: boolean
}

export interface HelpCommandData {
  intent: 'SHOW_HELP'
  commands: string[]
  executed: false
}

export interface MediaCommandData {
  intent: 'MEDIA_CONTROL'
  action: MediaAction
  executed: true
}

export interface CommandResultMessage {
  protocolVersion: ProtocolVersion
  type: 'COMMAND_RESULT'
  requestId: string
  success: true
  message: string
  data: PlatformCommandData | HelpCommandData | MediaCommandData
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
  | ErrorMessage
