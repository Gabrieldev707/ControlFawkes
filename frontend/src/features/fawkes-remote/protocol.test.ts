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

  it('accepts a platform result that confirms real execution', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'platform-1',
      success: true,
      message: 'Spotify aberto.',
      data: {
        intent: 'OPEN_PLATFORM',
        platform: 'SPOTIFY',
        executed: true,
        strategy: 'SPOTIFY_APP',
      },
    })).toBe(true)
  })

  it('rejects platform success without a known launch strategy', () => {
    const base = {
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'platform-1',
      success: true,
      message: 'Spotify aberto.',
    }

    expect(isServerMessage({
      ...base,
      data: { intent: 'OPEN_PLATFORM', platform: 'SPOTIFY', executed: true },
    })).toBe(false)
    expect(isServerMessage({
      ...base,
      data: {
        intent: 'OPEN_PLATFORM',
        platform: 'SPOTIFY',
        executed: true,
        strategy: 'DEFAULT_BROWSER',
      },
    })).toBe(false)
  })

  it('accepts a structured media-search result for supported platforms', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'search-1',
      success: true,
      message: 'Pesquisa aberta no YouTube.',
      data: {
        intent: 'SEARCH_MEDIA',
        platform: 'YOUTUBE',
        executed: true,
        strategy: 'CHROME',
      },
    })).toBe(true)
  })

  it('accepts an allowlisted media-control result', () => {
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'media-1',
      success: true,
      message: 'Play/pause executado.',
      data: {
        intent: 'MEDIA_CONTROL',
        action: 'MEDIA_PLAY_PAUSE',
        executed: true,
      },
    })).toBe(true)
    expect(isServerMessage({
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'media-2',
      success: true,
      message: 'Tecla enviada.',
      data: {
        intent: 'MEDIA_CONTROL',
        action: 'PRESS_ARBITRARY_KEY',
        executed: true,
      },
    })).toBe(false)
    expect(isErrorCode('MEDIA_CONTROL_FAILED')).toBe(true)
  })

  it('accepts only bounded real Windows volume state', () => {
    const message = {
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'volume-1',
      success: true,
      message: 'Volume: 42%.',
      data: {
        intent: 'SYSTEM_VOLUME',
        action: 'SYSTEM_VOLUME_GET',
        level: 42,
        muted: false,
        executed: true,
      },
    }

    expect(isServerMessage(message)).toBe(true)
    expect(isServerMessage({
      ...message,
      data: { ...message.data, level: 101 },
    })).toBe(false)
    expect(isServerMessage({
      ...message,
      data: { ...message.data, action: 'SYSTEM_VOLUME_RAW' },
    })).toBe(false)
    expect(isErrorCode('SYSTEM_VOLUME_FAILED')).toBe(true)
  })

  it('accepts only allowlisted pointer-control confirmations', () => {
    const message = {
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'pointer-1',
      success: true,
      message: 'Comando do touchpad executado.',
      data: {
        intent: 'POINTER_CONTROL',
        action: 'POINTER_CLICK',
        executed: true,
      },
    }

    expect(isServerMessage(message)).toBe(true)
    expect(isServerMessage({
      ...message,
      data: { ...message.data, action: 'POINTER_ABSOLUTE_MOVE' },
    })).toBe(false)
    expect(isErrorCode('POINTER_CONTROL_FAILED')).toBe(true)
    expect(isErrorCode('POINTER_RATE_LIMITED')).toBe(true)
  })

  it('accepts keyboard confirmations without text or key echoes', () => {
    const message = {
      protocolVersion: 1,
      type: 'COMMAND_RESULT',
      requestId: 'keyboard-1',
      success: true,
      message: 'Texto enviado.',
      data: {
        intent: 'KEYBOARD_CONTROL',
        action: 'KEYBOARD_TEXT',
        executed: true,
      },
    }

    expect(isServerMessage(message)).toBe(true)
    expect(isServerMessage({
      ...message,
      data: { ...message.data, text: 'não pode ecoar' },
    })).toBe(false)
    expect(isServerMessage({
      ...message,
      data: { ...message.data, action: 'KEYBOARD_SHORTCUT' },
    })).toBe(false)
    expect(isErrorCode('KEYBOARD_CONTROL_FAILED')).toBe(true)
  })

  it('accepts only the closed error-code set', () => {
    expect(isErrorCode('PIN_EXPIRED')).toBe(true)
    expect(isErrorCode('PLATFORM_OPEN_FAILED')).toBe(true)
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
