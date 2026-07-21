import { describe, expect, it } from 'vitest'

import { isErrorCode, isServerMessage, parseServerMessage } from './protocol'


describe('protocol v1 runtime validation', () => {
  it('accepts a complete state update', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'STATE_UPDATE',
      state: 'AUTH_REQUIRED',
      message: 'Autenticação necessária.',
    })).toBe(true)
  })

  it('rejects a protocol version mismatch', () => {
    expect(isServerMessage({
      protocolVersion: 2,
      type: 'STATE_UPDATE',
      state: 'AUTH_REQUIRED',
      message: 'Autenticação necessária.',
    })).toBe(false)
  })

  it('rejects a boolean protocol version and accepts numeric one', () => {
    expect(isServerMessage({
      protocolVersion: true,
      type: 'AUTH_RESULT',
      requestId: 'auth-1',
      success: true,
      message: 'Autenticado.',
    })).toBe(false)
    expect(isServerMessage({
      protocolVersion: 1.0,
      type: 'AUTH_RESULT',
      requestId: 'auth-1',
      success: true,
      message: 'Autenticado.',
    })).toBe(true)
  })

  it('accepts pairing and authentication results', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'PAIR_RESULT',
      requestId: 'pair-1',
      success: true,
      message: 'Pareamento concluído.',
      deviceId: 'device-1',
      token: 'a-secure-token-value',
    })).toBe(true)
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'AUTH_RESULT',
      requestId: 'auth-1',
      success: true,
      message: 'Autenticação concluída.',
    })).toBe(true)
  })

  it('accepts typed help command data', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'text-1',
      success: true,
      message: 'Estes são os comandos disponíveis.',
      data: {
        intent: 'SHOW_HELP',
        commands: ['abre netflix'],
        executed: false,
      },
    })).toBe(true)
  })

  it('accepts only the closed error-code set', () => {
    expect(isErrorCode('PIN_EXPIRED')).toBe(true)
    expect(isErrorCode('ANY_STRING')).toBe(false)
  })

  it('rejects malformed and oversized serialized messages', () => {
    expect(parseServerMessage('{broken')).toBeNull()
    expect(parseServerMessage('x'.repeat(8193))).toBeNull()
  })

  it('rejects unexpected fields', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'AUTH_RESULT',
      requestId: 'auth-1',
      success: true,
      message: 'Autenticado.',
      token: 'must-not-be-here',
    })).toBe(false)
  })
})
