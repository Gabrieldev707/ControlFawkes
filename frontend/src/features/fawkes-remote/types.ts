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

export type OrbState =
  | 'idle'
  | 'listening'
  | 'transcribing'
  | 'needs_selection'
  | 'executing'
  | 'success'
  | 'error'

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

export type ClientMessage =
  | AuthMessage
  | PairDeviceMessage
  | PlatformSelectedMessage
  | TextCommandMessage

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
  executed: false
}

export interface CommandResultMessage {
  protocolVersion: ProtocolVersion
  type: 'COMMAND_RESULT'
  requestId: string
  success: true
  message: string
  data: PlatformCommandData
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
