import { useState, useEffect, useCallback, useRef } from 'react';
import type { ConnectionState, ClientMessage, ServerMessage } from '../features/fawkes-remote/types';

interface UseWebSocketOptions {
  onMessage?: (message: ServerMessage) => void;
  maxRetries?: number;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const [connectionState, setConnectionState] = useState<ConnectionState>('disconnected');
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<number | null>(null);
  const retryCount = useRef(0);
  
  const { onMessage, maxRetries = 10 } = options;
  
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN || wsRef.current?.readyState === WebSocket.CONNECTING) {
      return;
    }
    
    setConnectionState('connecting');
    
    const configuredUrl = import.meta.env.VITE_WS_URL;
    const hostname = window.location.hostname;
    const port = import.meta.env.VITE_WS_PORT ?? '8100';
    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws';
    const wsUrl = configuredUrl ?? `${protocol}://${hostname}:${port}/ws`;
    
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;
    
    ws.onopen = () => {
      if (import.meta.env.DEV) console.log('[WS] Connected to', wsUrl);
      setConnectionState('connected');
      retryCount.current = 0;
    };
    
    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (import.meta.env.DEV) console.log('[WS] Received:', data);
        
        // Let the controller handle specific messages
        if (onMessage) {
          onMessage(data as ServerMessage);
        }
      } catch (e) {
        console.error('[WS] Failed to parse message', e);
      }
    };
    
    ws.onclose = () => {
      if (import.meta.env.DEV) console.log('[WS] Disconnected');
      
      // If we are unmounting, we don't want to reconnect
      if (!wsRef.current) return;
      
      setConnectionState('disconnected');
      
      // Exponential backoff reconnect
      if (retryCount.current < maxRetries) {
        const delay = Math.min(1000 * Math.pow(1.5, retryCount.current), 10000);
        retryCount.current += 1;
        
        if (import.meta.env.DEV) console.log(`[WS] Reconnecting in ${delay}ms (attempt ${retryCount.current})...`);
        reconnectTimeoutRef.current = window.setTimeout(() => {
          connect();
        }, delay);
      } else {
        setConnectionState('error');
      }
    };
    
    ws.onerror = (err) => {
      if (import.meta.env.DEV) console.error('[WS] Error:', err);
      // onclose will handle the reconnection
    };
    
  }, [maxRetries, onMessage]);
  
  useEffect(() => {
    connect();
    
    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect]);
  
  const sendMessage = useCallback((message: ClientMessage) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      if (import.meta.env.DEV) console.log('[WS] Sending:', message);
      wsRef.current.send(JSON.stringify(message));
      return true;
    } else {
      console.warn('[WS] Cannot send message, not connected');
      return false;
    }
  }, []);
  
  return {
    connectionState,
    sendMessage,
    reconnect: connect
  };
}
