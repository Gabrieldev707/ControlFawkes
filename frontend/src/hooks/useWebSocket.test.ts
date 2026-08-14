import { act, renderHook } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import { buildWebSocketUrl, useWebSocket } from './useWebSocket'
import { PROTOCOL_VERSION, type ClientMessage } from '../features/fawkes-remote/types'


class FakeWebSocket {
  static readonly CONNECTING = 0
  static readonly OPEN = 1
  static readonly CLOSING = 2
  static readonly CLOSED = 3
  static instances: FakeWebSocket[] = []

  readonly url: string
  readyState = FakeWebSocket.CONNECTING
  onopen: ((event: Event) => void) | null = null
  onmessage: ((event: MessageEvent) => void) | null = null
  onclose: ((event: CloseEvent) => void) | null = null
  onerror: ((event: Event) => void) | null = null
  send = vi.fn<(data: string) => void>()

  constructor(url: string | URL) {
    this.url = String(url)
    FakeWebSocket.instances.push(this)
  }

  open(): void {
    this.readyState = FakeWebSocket.OPEN
    this.onopen?.(new Event('open'))
  }

  serverClose(): void {
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.(new CloseEvent('close'))
  }

  close(): void {
    if (this.readyState === FakeWebSocket.CLOSED) return
    this.readyState = FakeWebSocket.CLOSED
    this.onclose?.(new CloseEvent('close'))
  }
}


describe('buildWebSocketUrl', () => {
  it('uses the page hostname without the Vite port', () => {
    expect(buildWebSocketUrl(undefined, '192.168.0.20', 'http:', '8100'))
      .toBe('ws://192.168.0.20:8100/ws')
  })

  it('uses wss on an HTTPS page', () => {
    expect(buildWebSocketUrl(undefined, 'fawkes.local', 'https:', '8100'))
      .toBe('wss://fawkes.local:8100/ws')
  })

  it('prefers a configured override', () => {
    expect(buildWebSocketUrl('ws://10.0.0.5:9000/ws', 'ignored', 'https:', '8100'))
      .toBe('ws://10.0.0.5:9000/ws')
  })
})


describe('useWebSocket lifecycle', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('reconnects with 1.5x backoff and a 15 second cap without stopping', () => {
    const timeoutSpy = vi.spyOn(window, 'setTimeout')
    renderHook(() => useWebSocket())

    for (let attempt = 0; attempt < 13; attempt += 1) {
      act(() => {
        FakeWebSocket.instances.at(-1)?.serverClose()
        vi.runOnlyPendingTimers()
      })
    }

    const reconnectDelays = timeoutSpy.mock.calls
      .map(([, delay]) => Number(delay))
      .filter((delay) => delay >= 1000)
    expect(reconnectDelays.slice(0, 4)).toEqual([1000, 1500, 2250, 3375])
    expect(Math.max(...reconnectDelays)).toBe(15000)
    expect(FakeWebSocket.instances).toHaveLength(14)
  })

  it('resets the backoff after a successful connection', () => {
    const timeoutSpy = vi.spyOn(window, 'setTimeout')
    renderHook(() => useWebSocket())
    act(() => {
      FakeWebSocket.instances[0].serverClose()
      vi.runOnlyPendingTimers()
      FakeWebSocket.instances[1].open()
      FakeWebSocket.instances[1].serverClose()
    })

    const delays = timeoutSpy.mock.calls.map(([, delay]) => Number(delay))
    expect(delays.at(-1)).toBe(1000)
  })

  it('reconnects immediately when the network returns', () => {
    renderHook(() => useWebSocket())
    act(() => FakeWebSocket.instances[0].serverClose())
    expect(FakeWebSocket.instances).toHaveLength(1)

    act(() => window.dispatchEvent(new Event('online')))

    expect(FakeWebSocket.instances).toHaveLength(2)
  })

  it('reconnects immediately when the page becomes visible', () => {
    renderHook(() => useWebSocket())
    act(() => FakeWebSocket.instances[0].serverClose())
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    })

    act(() => document.dispatchEvent(new Event('visibilitychange')))

    expect(FakeWebSocket.instances).toHaveLength(2)
  })

  it('supports manual reconnect without creating duplicate sockets', () => {
    const { result } = renderHook(() => useWebSocket())

    act(() => result.current.reconnect())
    expect(FakeWebSocket.instances).toHaveLength(1)

    act(() => {
      FakeWebSocket.instances[0].serverClose()
      result.current.reconnect()
    })
    expect(FakeWebSocket.instances).toHaveLength(2)
  })

  it('cancels timers and listeners on unmount', () => {
    const { unmount } = renderHook(() => useWebSocket())
    act(() => FakeWebSocket.instances[0].serverClose())

    unmount()
    act(() => {
      vi.runOnlyPendingTimers()
      window.dispatchEvent(new Event('online'))
      document.dispatchEvent(new Event('visibilitychange'))
    })

    expect(FakeWebSocket.instances).toHaveLength(1)
  })

  it('updates the connection state on open and close', () => {
    const { result } = renderHook(() => useWebSocket())
    expect(result.current.connectionState).toBe('connecting')

    act(() => FakeWebSocket.instances[0].open())
    expect(result.current.connectionState).toBe('connected')

    act(() => FakeWebSocket.instances[0].serverClose())
    expect(result.current.connectionState).toBe('disconnected')
  })

  it('delivers valid server messages to the consumer', () => {
    const onMessage = vi.fn()
    renderHook(() => useWebSocket({ onMessage }))
    const payload = {
      protocolVersion: PROTOCOL_VERSION,
      type: 'STATE_UPDATE',
      state: 'READY',
      message: 'Computador pronto.',
    }

    act(() => {
      FakeWebSocket.instances[0].open()
      FakeWebSocket.instances[0].onmessage?.(
        new MessageEvent('message', { data: JSON.stringify(payload) }),
      )
    })

    expect(onMessage).toHaveBeenCalledWith(payload)
  })

  it('ignores malformed or unknown server messages', () => {
    const onMessage = vi.fn()
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    renderHook(() => useWebSocket({ onMessage }))

    act(() => {
      FakeWebSocket.instances[0].open()
      for (const data of ['{ quebrado', '"texto"', '{"type":"MAGIC"}']) {
        FakeWebSocket.instances[0].onmessage?.(new MessageEvent('message', { data }))
      }
    })

    expect(onMessage).not.toHaveBeenCalled()
  })

  it('sends only while the active socket is open', () => {
    const { result } = renderHook(() => useWebSocket())
    const message: ClientMessage = {
      protocolVersion: PROTOCOL_VERSION,
      type: 'TEXT_COMMAND',
      requestId: 'text-1',
      payload: { query: 'ajuda' },
    }

    expect(result.current.sendMessage(message)).toBe(false)
    act(() => FakeWebSocket.instances[0].open())
    expect(result.current.sendMessage(message)).toBe(true)
    expect(FakeWebSocket.instances[0].send).toHaveBeenCalledWith(JSON.stringify(message))
  })
})

describe('useWebSocket sinal de vida', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    FakeWebSocket.instances = []
    vi.stubGlobal('WebSocket', FakeWebSocket as unknown as typeof WebSocket)
    Object.defineProperty(document, 'visibilityState', {
      configurable: true,
      value: 'visible',
    })
  })

  afterEach(() => {
    vi.clearAllTimers()
    vi.useRealTimers()
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  function conectar(onMessage = vi.fn()) {
    const hook = renderHook(() => useWebSocket({ onMessage }))
    const socket = FakeWebSocket.instances[0]
    act(() => socket.open())
    return { hook, socket, onMessage }
  }

  function receber(socket: FakeWebSocket, payload: object) {
    act(() => {
      socket.onmessage?.(new MessageEvent('message', { data: JSON.stringify(payload) }))
    })
  }

  it('não repassa o batimento para a aplicação', () => {
    // Ele existe só para provar que a conexão está viva; repassá-lo obrigaria
    // o resto do app a saber que ele existe.
    const { socket, onMessage } = conectar()

    receber(socket, { protocolVersion: PROTOCOL_VERSION, type: 'HEARTBEAT' })

    expect(onMessage).not.toHaveBeenCalled()
  })

  it('derruba a conexão que ficou muda tempo demais', () => {
    // Wi-Fi que troca de rede deixa o socket meio aberto: o `onclose` nunca
    // chega e o controle seguiria dizendo "conectado" com tudo falhando calado.
    const { hook, socket } = conectar()
    expect(hook.result.current.connectionState).toBe('connected')

    act(() => { vi.advanceTimersByTime(26000) })

    expect(socket.readyState).toBe(FakeWebSocket.CLOSED)
  })

  it('o batimento renova a confiança na conexão', () => {
    const { hook, socket } = conectar()

    act(() => { vi.advanceTimersByTime(20000) })
    receber(socket, { protocolVersion: PROTOCOL_VERSION, type: 'HEARTBEAT' })
    act(() => { vi.advanceTimersByTime(20000) })

    expect(socket.readyState).toBe(FakeWebSocket.OPEN)
    expect(hook.result.current.connectionState).toBe('connected')
  })

  it('qualquer mensagem serve de sinal de vida, não só o batimento', () => {
    const { socket } = conectar()

    act(() => { vi.advanceTimersByTime(20000) })
    receber(socket, {
      protocolVersion: PROTOCOL_VERSION,
      type: 'STATE_UPDATE',
      state: 'READY',
      message: 'Computador pronto.',
    })
    act(() => { vi.advanceTimersByTime(20000) })

    expect(socket.readyState).toBe(FakeWebSocket.OPEN)
  })

  it('distingue reconectar de conectar pela primeira vez', () => {
    // Na abertura do app o que acontece é uma conexão; depois de uma queda, é
    // recuperação — e a interface tem o que dizer sobre isso.
    const { hook, socket } = conectar()

    act(() => { socket.serverClose() })
    expect(hook.result.current.connectionState).toBe('disconnected')

    act(() => { vi.advanceTimersByTime(1100) })
    expect(hook.result.current.connectionState).toBe('reconnecting')
  })

  it('anuncia quando vem a próxima tentativa', () => {
    const { hook, socket } = conectar()

    act(() => { socket.serverClose() })

    // "Sem conexão" sozinho não diz se algo ainda vai acontecer.
    expect(hook.result.current.nextRetryAt).toBeGreaterThan(Date.now())
  })
})
