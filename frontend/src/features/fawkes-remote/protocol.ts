import {
  ERROR_CODES,
  LAUNCH_STRATEGIES,
  MEDIA_ACTIONS,
  VOLUME_ACTIONS,
  POINTER_ACTIONS,
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
    && hasOnlyKeys(value, ['intent', 'platform', 'executed', 'strategy'])
    && value.intent === 'OPEN_PLATFORM'
    && isPlatform(value.platform)
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
    && hasOnlyKeys(value, ['intent', 'action', 'executed'])
    && value.intent === 'MEDIA_CONTROL'
    && typeof value.action === 'string'
    && MEDIA_ACTIONS.includes(value.action as (typeof MEDIA_ACTIONS)[number])
    && value.executed === true
}

function isVolumeData(value: unknown): boolean {
  return isRecord(value)
    && hasOnlyKeys(value, ['intent', 'action', 'level', 'muted', 'executed'])
    && value.intent === 'SYSTEM_VOLUME'
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
          || isHelpData(value.data)
          || isMediaData(value.data)
          || isVolumeData(value.data)
          || isPointerData(value.data)
          || isKeyboardData(value.data)
        )
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
