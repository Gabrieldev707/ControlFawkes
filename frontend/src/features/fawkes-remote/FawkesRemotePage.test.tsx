import { act, fireEvent, render, screen, within } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { ConnectionState, ServerMessage } from './types'
import { FawkesRemotePage } from './FawkesRemotePage'


const websocketMock = vi.hoisted(() => ({
  connectionState: 'connected' as ConnectionState,
  onMessage: undefined as ((message: ServerMessage) => void) | undefined,
  sendMessage: vi.fn<(message: unknown) => boolean>(),
  reconnect: vi.fn(),
}))

vi.mock('../../hooks/useWebSocket', () => ({
  useWebSocket: (options: { onMessage?: (message: ServerMessage) => void }) => {
    websocketMock.onMessage = options.onMessage
    return {
      connectionState: websocketMock.connectionState,
      sendMessage: websocketMock.sendMessage,
      reconnect: websocketMock.reconnect,
    }
  },
}))

vi.mock('../../components/fawkes-remote/RemoteOrb', () => ({
  RemoteOrb: ({ state }: { state: string }) => (
    <div aria-label="Orb do Fawkes" data-state={state} />
  ),
}))


describe('FawkesRemotePage authentication', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
    localStorage.clear()
    websocketMock.connectionState = 'connected'
    websocketMock.onMessage = undefined
    websocketMock.sendMessage.mockReset()
    websocketMock.sendMessage.mockReturnValue(true)
  })

  it('shows pairing when the connected device has no credentials', () => {
    render(<FawkesRemotePage />)

    expect(screen.getByRole('heading', { name: 'Parear este dispositivo' })).toBeTruthy()
  })

  it('authenticates once with stored credentials', () => {
    localStorage.setItem('controlfawkes.deviceId', 'device-1')
    localStorage.setItem('controlfawkes.token', 'stored-secure-token')

    render(<FawkesRemotePage />)

    expect(websocketMock.sendMessage).toHaveBeenCalledTimes(1)
    expect(websocketMock.sendMessage).toHaveBeenCalledWith({
      protocolVersion: 1,
      type: 'AUTH',
      requestId: expect.any(String),
      payload: {
        deviceId: 'device-1',
        token: 'stored-secure-token',
      },
    })
  })

  it('submits the PIN with a local device name', () => {
    render(<FawkesRemotePage />)
    fireEvent.change(screen.getByLabelText('PIN de pareamento'), {
      target: { value: '123456' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Parear dispositivo' }))

    expect(websocketMock.sendMessage).toHaveBeenCalledWith({
      protocolVersion: 1,
      type: 'PAIR_DEVICE',
      requestId: expect.any(String),
      payload: {
        pin: '123456',
        deviceName: expect.any(String),
      },
    })
  })

  it('persists successful pairing and waits for READY before enabling commands', () => {
    render(<FawkesRemotePage />)

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
    })

    expect(localStorage.getItem('controlfawkes.deviceId')).toBe('device-1')
    expect(localStorage.getItem('controlfawkes.token')).toBe('new-secure-token-value')
    expect(screen.getByText('Dispositivo autenticado')).toBeTruthy()
    expect((screen.getByRole('button', { name: 'Netflix' }) as HTMLButtonElement).disabled).toBe(true)

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })

    expect((screen.getByRole('button', { name: 'Netflix' }) as HTMLButtonElement).disabled).toBe(false)
  })

  it('removes rejected credentials and returns to pairing', () => {
    localStorage.setItem('controlfawkes.deviceId', 'device-1')
    localStorage.setItem('controlfawkes.token', 'revoked-secure-token')
    render(<FawkesRemotePage />)

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'ERROR',
        requestId: 'auth-1',
        code: 'INVALID_TOKEN',
        message: 'Token inválido.',
      })
    })

    expect(localStorage.getItem('controlfawkes.deviceId')).toBeNull()
    expect(localStorage.getItem('controlfawkes.token')).toBeNull()
    expect(screen.getByRole('heading', { name: 'Parear este dispositivo' })).toBeTruthy()
  })

  it('sends trimmed text and displays the backend success message', () => {
    render(<FawkesRemotePage />)
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })

    const input = screen.getByLabelText('Comando de texto') as HTMLInputElement
    fireEvent.change(input, { target: { value: '  abre spotify  ' } })
    fireEvent.submit(input.closest('form')!)

    const sentMessage = websocketMock.sendMessage.mock.calls
      .map(([message]) => message as Record<string, unknown>)
      .find((message) => message.type === 'TEXT_COMMAND')
    expect(sentMessage).toMatchObject({
      protocolVersion: 1,
      type: 'TEXT_COMMAND',
      payload: { query: 'abre spotify' },
    })
    expect(input.value).toBe('')

    const requestId = sentMessage?.requestId as string
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'BUSY',
        message: 'Processando comando...',
      })
    })
    expect(screen.getByText('Processando comando...')).toBeTruthy()

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'COMMAND_RESULT',
        requestId,
        success: true,
        message: 'Spotify aberto.',
        data: {
          intent: 'OPEN_PLATFORM',
          platform: 'SPOTIFY',
          executed: true,
          strategy: 'SPOTIFY_APP',
        },
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })

    expect(screen.getByText('Spotify aberto.')).toBeTruthy()
  })

  it('displays the backend unknown-command error as an alert', () => {
    render(<FawkesRemotePage />)
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })

    const input = screen.getByLabelText('Comando de texto')
    fireEvent.change(input, { target: { value: 'escolhe um filme' } })
    fireEvent.submit(input.closest('form')!)
    const sentMessage = websocketMock.sendMessage.mock.calls
      .map(([message]) => message as Record<string, unknown>)
      .find((message) => message.type === 'TEXT_COMMAND')

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'ERROR',
        requestId: sentMessage?.requestId as string,
        code: 'UNKNOWN_COMMAND',
        message: 'Não entendi esse comando.',
      })
    })

    expect(screen.getByRole('alert').textContent).toBe('Não entendi esse comando.')
  })

  it('navigates from Home to the control screen and back without sending a command', () => {
    render(<FawkesRemotePage />)
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
    })

    expect(screen.getByRole('button', { name: 'Controle' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Touchpad' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Teclado' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Volume' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Plataformas' })).toBeTruthy()
    expect(screen.getByRole('button', { name: 'Configurações' })).toBeTruthy()

    fireEvent.click(screen.getByRole('button', { name: 'Controle' }))

    expect(screen.getByRole('heading', { name: 'Mídia' })).toBeTruthy()
    expect(screen.queryByLabelText('Comando de texto')).toBeNull()
    expect(websocketMock.sendMessage).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole('button', { name: 'Voltar' }))

    expect(screen.getByLabelText('Comando de texto')).toBeTruthy()

    const destinations = [
      ['Touchpad', 'Touchpad'],
      ['Teclado', 'Teclado'],
      ['Volume', 'Volume'],
      ['Plataformas', 'Plataformas'],
      ['Configurações', 'Configurações'],
    ] as const

    for (const [buttonName, headingName] of destinations) {
      fireEvent.click(screen.getByRole('button', { name: buttonName }))
      expect(screen.getByRole('heading', { name: headingName })).toBeTruthy()
      fireEvent.click(screen.getByRole('button', { name: 'Voltar' }))
    }

    expect(websocketMock.sendMessage).not.toHaveBeenCalled()
  })

  it('shows all orb states only when the development preview is requested', () => {
    window.history.pushState({}, '', '/?orb-preview=1')
    render(<FawkesRemotePage />)
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
    })

    const preview = screen.getByRole('group', { name: 'Teste visual da orb' })
    const labels = [
      'idle',
      'listening',
      'transcribing',
      'needs_selection',
      'executing',
      'success',
      'error',
    ]

    for (const label of labels) {
      expect(preview.querySelector(`[aria-label="Testar estado ${label}"]`)).toBeTruthy()
    }

    fireEvent.click(screen.getByRole('button', { name: 'Testar estado listening' }))
    expect(screen.getByLabelText('Orb do Fawkes').getAttribute('data-state')).toBe('listening')
  })

  it('sends an authenticated platform selection from the Platforms screen', () => {
    render(<FawkesRemotePage />)
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })

    fireEvent.click(screen.getByRole('button', { name: 'Plataformas' }))
    fireEvent.click(screen.getByRole('button', { name: 'Netflix' }))

    expect(websocketMock.sendMessage).toHaveBeenCalledWith({
      protocolVersion: 1,
      type: 'PLATFORM_SELECTED',
      requestId: expect.any(String),
      payload: { platform: 'NETFLIX' },
    })
  })

  it('sends an allowlisted media action from the Control screen', () => {
    render(<FawkesRemotePage />)
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })

    fireEvent.click(screen.getByRole('button', { name: 'Controle' }))
    fireEvent.click(screen.getByRole('button', { name: 'Play/Pause' }))

    expect(websocketMock.sendMessage).toHaveBeenCalledWith({
      protocolVersion: 1,
      type: 'MEDIA_PLAY_PAUSE',
      requestId: expect.any(String),
    })
  })

  it('loads and changes the real Windows volume through bounded messages', () => {
    render(<FawkesRemotePage />)
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })

    fireEvent.click(screen.getByRole('button', { name: 'Volume' }))
    const getMessage = websocketMock.sendMessage.mock.calls
      .map(([message]) => message as Record<string, unknown>)
      .find((message) => message.type === 'SYSTEM_VOLUME_GET')
    expect(getMessage).toMatchObject({
      protocolVersion: 1,
      type: 'SYSTEM_VOLUME_GET',
      requestId: expect.any(String),
    })

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'COMMAND_RESULT',
        requestId: getMessage?.requestId as string,
        success: true,
        message: 'Volume: 42%.',
        data: {
          intent: 'SYSTEM_VOLUME',
          action: 'SYSTEM_VOLUME_GET',
          level: 42,
          muted: false,
          executed: true,
        },
      })
    })

    const slider = screen.getByRole('slider', { name: 'Volume do computador' })
    expect((slider as HTMLInputElement).value).toBe('42')
    fireEvent.change(slider, { target: { value: '73' } })
    expect(websocketMock.sendMessage).toHaveBeenCalledWith({
      protocolVersion: 1,
      type: 'SYSTEM_VOLUME_SET',
      requestId: expect.any(String),
      payload: { level: 73 },
    })
  })

  it('sends only an allowlisted touchpad action after explicit activation', () => {
    render(<FawkesRemotePage />)
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })

    fireEvent.click(screen.getByRole('button', { name: 'Touchpad' }))
    fireEvent.click(screen.getByRole('button', { name: 'Ativar touchpad' }))
    fireEvent.click(screen.getByRole('button', { name: 'Clique duplo' }))

    expect(websocketMock.sendMessage).toHaveBeenCalledWith({
      protocolVersion: 1,
      type: 'POINTER_DOUBLE_CLICK',
      requestId: expect.any(String),
    })
  })

  it('sends remote text without history and only allowlisted special keys', () => {
    render(<FawkesRemotePage />)
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })

    fireEvent.click(screen.getByRole('button', { name: 'Teclado' }))
    const input = screen.getByLabelText('Texto para enviar')
    fireEvent.change(input, { target: { value: 'Olá' } })
    fireEvent.submit(input.closest('form')!)

    expect(websocketMock.sendMessage).toHaveBeenCalledWith({
      protocolVersion: 1,
      type: 'KEYBOARD_TEXT',
      requestId: expect.any(String),
      payload: { text: 'Olá' },
    })
  })
})


describe('FawkesRemotePage command feedback', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
    localStorage.clear()
    websocketMock.connectionState = 'connected'
    websocketMock.onMessage = undefined
    websocketMock.sendMessage.mockReset()
    websocketMock.sendMessage.mockReturnValue(true)
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
  })

  function authenticate(): void {
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })
  }

  function selectNetflix(): string {
    fireEvent.click(screen.getByRole('button', { name: 'Plataformas' }))
    fireEvent.click(screen.getByRole('button', { name: 'Netflix' }))
    const sent = websocketMock.sendMessage.mock.calls.at(-1)?.[0] as { requestId: string }
    // O orb só é renderizado na Home, então voltamos para poder observar o feedback.
    fireEvent.click(screen.getByRole('button', { name: /Início/ }))
    return sent.requestId
  }

  function orbState(): string | null {
    return screen.getByLabelText('Orb do Fawkes').getAttribute('data-state')
  }

  it('enters the executing state while a platform selection is in flight', () => {
    render(<FawkesRemotePage />)
    authenticate()

    selectNetflix()

    expect(orbState()).toBe('executing')
  })

  it('ignores responses that do not match the current requestId', () => {
    render(<FawkesRemotePage />)
    authenticate()
    selectNetflix()

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'COMMAND_RESULT',
        requestId: 'stale-request',
        success: true,
        message: 'Resposta antiga.',
        data: {
          intent: 'OPEN_PLATFORM',
          platform: 'NETFLIX',
          executed: true,
          strategy: 'CHROME',
        },
      })
    })

    expect(orbState()).toBe('executing')
  })

  it('transitions to success and back to idle after a COMMAND_RESULT', () => {
    render(<FawkesRemotePage />)
    authenticate()
    const requestId = selectNetflix()

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'COMMAND_RESULT',
        requestId,
        success: true,
        message: 'Netflix aberto.',
        data: {
          intent: 'OPEN_PLATFORM',
          platform: 'NETFLIX',
          executed: true,
          strategy: 'CHROME',
        },
      })
    })
    expect(orbState()).toBe('success')

    act(() => vi.advanceTimersByTime(2000))
    expect(orbState()).toBe('idle')
  })

  it('transitions to error and back to idle after an ERROR response', () => {
    render(<FawkesRemotePage />)
    authenticate()
    const requestId = selectNetflix()

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'ERROR',
        requestId,
        code: 'PLATFORM_OPEN_FAILED',
        message: 'Não foi possível abrir o Netflix.',
      })
    })
    expect(orbState()).toBe('error')
    expect(screen.getByRole('alert').textContent).toBe('Não foi possível abrir o Netflix.')

    act(() => vi.advanceTimersByTime(3000))
    expect(orbState()).toBe('idle')
  })

  it('enters the error state when the socket refuses the message', () => {
    render(<FawkesRemotePage />)
    authenticate()
    websocketMock.sendMessage.mockReturnValue(false)

    selectNetflix()

    expect(orbState()).toBe('error')
  })

  it('clears pending feedback timers on unmount', () => {
    const clearTimeoutSpy = vi.spyOn(window, 'clearTimeout')
    const { unmount } = render(<FawkesRemotePage />)
    authenticate()
    const requestId = selectNetflix()

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'ERROR',
        requestId,
        code: 'PLATFORM_OPEN_FAILED',
        message: 'Não foi possível abrir o Netflix.',
      })
    })

    unmount()

    expect(clearTimeoutSpy).toHaveBeenCalled()
  })
})


describe('FawkesRemotePage directional navigation', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
    localStorage.clear()
    websocketMock.connectionState = 'connected'
    websocketMock.onMessage = undefined
    websocketMock.sendMessage.mockReset()
    websocketMock.sendMessage.mockReturnValue(true)
  })

  function authenticate(): void {
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })
  }

  it('sends an allowlisted directional action from the Navigation screen', () => {
    render(<FawkesRemotePage />)
    authenticate()

    fireEvent.click(screen.getByRole('button', { name: 'Abrir Navegar' }))
    fireEvent.pointerDown(screen.getByRole('button', { name: 'Cima' }))

    expect(websocketMock.sendMessage).toHaveBeenCalledWith({
      protocolVersion: 1,
      type: 'NAVIGATE_UP',
      requestId: expect.any(String),
    })
  })

  it('keeps sending while an arrow is held, without waiting for each reply', () => {
    render(<FawkesRemotePage />)
    authenticate()
    fireEvent.click(screen.getByRole('button', { name: 'Abrir Navegar' }))
    websocketMock.sendMessage.mockClear()

    const down = screen.getByRole('button', { name: 'Baixo' })
    fireEvent.pointerDown(down)
    fireEvent.pointerDown(down)

    // Sem resposta do servidor entre os dois: o direcional não bloqueia.
    expect(websocketMock.sendMessage).toHaveBeenCalledTimes(2)
    fireEvent.pointerUp(down)
  })

  it('reports a real failure when the socket refuses the directional command', () => {
    render(<FawkesRemotePage />)
    authenticate()
    fireEvent.click(screen.getByRole('button', { name: 'Abrir Navegar' }))
    websocketMock.sendMessage.mockReturnValue(false)

    fireEvent.pointerDown(screen.getByRole('button', { name: 'Cima' }))

    expect(screen.getByRole('alert').textContent).toBe('Navegação indisponível.')
  })

  it('shows the backend confirmation for a directional command', () => {
    render(<FawkesRemotePage />)
    authenticate()
    fireEvent.click(screen.getByRole('button', { name: 'Abrir Navegar' }))
    // OK responde a click, não a pointerDown: é o botão que não repete.
    fireEvent.click(screen.getByRole('button', { name: 'OK' }))
    const sent = websocketMock.sendMessage.mock.calls.at(-1)?.[0] as { requestId: string }

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'COMMAND_RESULT',
        requestId: sent.requestId,
        success: true,
        message: 'OK enviado.',
        data: { intent: 'NAVIGATION', action: 'NAVIGATE_CONFIRM', executed: true },
      })
    })

    expect(screen.getByText('OK enviado.')).toBeTruthy()
  })
})


describe('FawkesRemotePage platform choice', () => {
  beforeEach(() => {
    window.history.replaceState({}, '', '/')
    localStorage.clear()
    websocketMock.connectionState = 'connected'
    websocketMock.onMessage = undefined
    websocketMock.sendMessage.mockReset()
    websocketMock.sendMessage.mockReturnValue(true)
  })

  function authenticate(): void {
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'PAIR_RESULT',
        requestId: 'pair-1',
        success: true,
        message: 'Pareamento concluído.',
        deviceId: 'device-1',
        token: 'new-secure-token-value',
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })
  }

  function askForContent(query = 'Interestelar'): string {
    const input = screen.getByLabelText('Comando de texto')
    fireEvent.change(input, { target: { value: query } })
    fireEvent.submit(input.closest('form')!)
    const sent = websocketMock.sendMessage.mock.calls.at(-1)?.[0] as { requestId: string }
    return sent.requestId
  }

  function offerPlatforms(requestId: string, query = 'Interestelar'): void {
    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'NEEDS_PLATFORM',
        requestId,
        query,
        suggestedPlatforms: ['NETFLIX', 'PRIME_VIDEO', 'YOUTUBE', 'SPOTIFY'],
      })
    })
  }

  it('asks where to search instead of failing on content without a platform', () => {
    render(<FawkesRemotePage />)
    authenticate()

    offerPlatforms(askForContent())

    expect(screen.getByText('Onde você quer procurar “Interestelar”?')).toBeTruthy()
    // Escopo no grupo: a grade da Home também tem um botão "Netflix".
    const choice = screen.getByRole('group', { name: /Onde você quer procurar/ })
    expect(within(choice).getByRole('button', { name: 'Netflix' })).toBeTruthy()
  })

  it('offers only platforms that actually have search', () => {
    render(<FawkesRemotePage />)
    authenticate()
    offerPlatforms(askForContent())

    const choice = screen.getByRole('group', { name: /Onde você quer procurar/ })
    // Max e Disney+ não têm busca: oferecê-los levaria a um beco sem saída.
    expect(within(choice).queryByRole('button', { name: 'Max' })).toBeNull()
    expect(within(choice).queryByRole('button', { name: 'Disney+' })).toBeNull()
  })

  it('sends only platform and query when the user chooses', () => {
    render(<FawkesRemotePage />)
    authenticate()
    offerPlatforms(askForContent())
    websocketMock.sendMessage.mockClear()

    const choice = screen.getByRole('group', { name: /Onde você quer procurar/ })
    fireEvent.click(within(choice).getByRole('button', { name: 'Netflix' }))

    expect(websocketMock.sendMessage).toHaveBeenCalledWith({
      protocolVersion: 1,
      type: 'SEARCH_MEDIA',
      requestId: expect.any(String),
      payload: { platform: 'NETFLIX', query: 'Interestelar' },
    })
  })

  it('keeps the query intact through the choice', () => {
    render(<FawkesRemotePage />)
    authenticate()
    offerPlatforms(askForContent('Stranger Things'), 'Stranger Things')
    websocketMock.sendMessage.mockClear()

    const choice = screen.getByRole('group', { name: /Onde você quer procurar/ })
    fireEvent.click(within(choice).getByRole('button', { name: 'YouTube' }))

    const sent = websocketMock.sendMessage.mock.calls.at(-1)?.[0] as {
      payload: { query: string }
    }
    expect(sent.payload.query).toBe('Stranger Things')
  })

  it('lets the user cancel without sending anything', () => {
    render(<FawkesRemotePage />)
    authenticate()
    offerPlatforms(askForContent())
    websocketMock.sendMessage.mockClear()

    fireEvent.click(screen.getByRole('button', { name: 'Cancelar busca' }))

    expect(screen.queryByText('Onde você quer procurar “Interestelar”?')).toBeNull()
    expect(websocketMock.sendMessage).not.toHaveBeenCalled()
  })

  it('dismisses the choice when the command finishes', () => {
    render(<FawkesRemotePage />)
    authenticate()
    offerPlatforms(askForContent())
    const choice = screen.getByRole('group', { name: /Onde você quer procurar/ })
    fireEvent.click(within(choice).getByRole('button', { name: 'Netflix' }))
    const sent = websocketMock.sendMessage.mock.calls.at(-1)?.[0] as { requestId: string }

    act(() => {
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'COMMAND_RESULT',
        requestId: sent.requestId,
        success: true,
        message: 'Pesquisa aberta no Netflix.',
        data: {
          intent: 'SEARCH_MEDIA',
          platform: 'NETFLIX',
          executed: true,
          strategy: 'CHROME',
        },
      })
    })

    expect(screen.queryByText(/Onde você quer procurar/)).toBeNull()
    expect(screen.getByText('Pesquisa aberta no Netflix.')).toBeTruthy()
  })

  it('ignores a platform choice offered for an older request', () => {
    render(<FawkesRemotePage />)
    authenticate()
    askForContent()

    offerPlatforms('request-antigo')

    expect(screen.queryByText(/Onde você quer procurar/)).toBeNull()
  })
})
