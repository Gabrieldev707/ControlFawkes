import { act, fireEvent, render, screen } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

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
        message: 'Comando reconhecido: abrir Spotify.',
        data: { intent: 'OPEN_PLATFORM', platform: 'SPOTIFY', executed: false },
      })
      websocketMock.onMessage?.({
        protocolVersion: 1,
        type: 'STATE_UPDATE',
        state: 'READY',
        message: 'Computador pronto.',
      })
    })

    expect(screen.getByText('Comando reconhecido: abrir Spotify.')).toBeTruthy()
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

    expect(screen.getByRole('heading', { name: 'Controle remoto' })).toBeTruthy()
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
})
