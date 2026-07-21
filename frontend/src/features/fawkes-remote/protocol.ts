import {
  ERROR_CODES,
  isPlatform,
  type ErrorCode,
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

function hasOnlyKeys(value: Record<string, unknown>, keys: readonly string[]): boolean {
  const allowed = new Set(keys)
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
    && hasOnlyKeys(value, ['intent', 'platform', 'executed'])
    && value.intent === 'OPEN_PLATFORM'
    && isPlatform(value.platform)
    && typeof value.executed === 'boolean'
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
        && (isPlatformData(value.data) || isHelpData(value.data))
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
