import { useCallback, useEffect, useRef, useState } from 'react'

import type {
  ClientMessage,
  ConnectionState,
  ServerMessage,
} from '../features/fawkes-remote/types'
import { parseServerMessage } from '../features/fawkes-remote/protocol'


interface UseWebSocketOptions {
  onMessage?: (message: ServerMessage) => void
}

const INITIAL_RECONNECT_DELAY = 1000
const RECONNECT_MULTIPLIER = 1.5
const MAX_RECONNECT_DELAY = 15000

export function buildWebSocketUrl(
  configuredUrl: string | undefined,
  hostname: string,
  pageProtocol: string,
  port: string,
): string {
  const protocol = pageProtocol === 'https:' ? 'wss' : 'ws'
  return configuredUrl || `${protocol}://${hostname}:${port}/ws`
}

function reconnectDelay(attempt: number): number {
  return Math.min(
    INITIAL_RECONNECT_DELAY * Math.pow(RECONNECT_MULTIPLIER, attempt),
    MAX_RECONNECT_DELAY,
  )
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected')
  const socketRef = useRef<WebSocket | null>(null)
  const reconnectTimerRef = useRef<number | null>(null)
  const retryCountRef = useRef(0)
  const activeRef = useRef(false)
  const onMessageRef = useRef(options.onMessage)
  const connectRef = useRef<() => void>(() => undefined)

  useEffect(() => {
    onMessageRef.current = options.onMessage
  }, [options.onMessage])

  const clearReconnectTimer = useCallback(() => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
  }, [])

  const scheduleReconnect = useCallback(() => {
    if (!activeRef.current || reconnectTimerRef.current !== null) return
    const delay = reconnectDelay(retryCountRef.current)
    retryCountRef.current += 1
    reconnectTimerRef.current = window.setTimeout(() => {
      reconnectTimerRef.current = null
      connectRef.current()
    }, delay)
  }, [])

  const connect = useCallback(() => {
    if (!activeRef.current) return

    const currentSocket = socketRef.current
    if (
      currentSocket?.readyState === WebSocket.OPEN
      || currentSocket?.readyState === WebSocket.CONNECTING
    ) {
      return
    }

    clearReconnectTimer()
    setConnectionState('connecting')

    const url = buildWebSocketUrl(
      import.meta.env.VITE_WS_URL,
      window.location.hostname,
      window.location.protocol,
      import.meta.env.VITE_WS_PORT ?? '8100',
    )
    const socket = new WebSocket(url)
    socketRef.current = socket

    socket.onopen = () => {
      if (!activeRef.current || socketRef.current !== socket) return
      retryCountRef.current = 0
      setConnectionState('connected')
    }

    socket.onmessage = (event) => {
      if (!activeRef.current || socketRef.current !== socket) return
      const message = typeof event.data === 'string' ? parseServerMessage(event.data) : null
      if (!message) {
        console.warn('[WS] Invalid server message ignored')
        return
      }
      onMessageRef.current?.(message)
    }

    socket.onerror = () => {
      if (!activeRef.current || socketRef.current !== socket) return
      setConnectionState('error')
    }

    socket.onclose = () => {
      if (socketRef.current !== socket) return
      socketRef.current = null
      if (!activeRef.current) return
      setConnectionState('disconnected')
      scheduleReconnect()
    }
  }, [clearReconnectTimer, scheduleReconnect])

  connectRef.current = connect

  const reconnect = useCallback(() => {
    if (!activeRef.current) return
    clearReconnectTimer()
    connectRef.current()
  }, [clearReconnectTimer])

  useEffect(() => {
    activeRef.current = true
    connectRef.current()

    const handleOnline = () => reconnect()
    const handleVisibilityChange = () => {
      if (document.visibilityState === 'visible') reconnect()
    }
    window.addEventListener('online', handleOnline)
    document.addEventListener('visibilitychange', handleVisibilityChange)

    return () => {
      activeRef.current = false
      clearReconnectTimer()
      window.removeEventListener('online', handleOnline)
      document.removeEventListener('visibilitychange', handleVisibilityChange)

      const socket = socketRef.current
      socketRef.current = null
      if (socket) {
        socket.onopen = null
        socket.onmessage = null
        socket.onerror = null
        socket.onclose = null
        socket.close()
      }
    }
  }, [clearReconnectTimer, reconnect])

  const sendMessage = useCallback((message: ClientMessage): boolean => {
    const socket = socketRef.current
    if (socket?.readyState !== WebSocket.OPEN) return false
    socket.send(JSON.stringify(message))
    return true
  }, [])

  return { connectionState, sendMessage, reconnect }
}
