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
  RemoteOrb: () => <div aria-label="Orb do Fawkes" />,
}))


describe('FawkesRemotePage authentication', () => {
  beforeEach(() => {
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
})
