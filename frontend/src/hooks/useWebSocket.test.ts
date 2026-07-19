import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from './useWebSocket';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';

describe('useWebSocket', () => {
  let wsInstances: any[] = [];
  let originalWebSocket: any;

  class MockWebSocket {
    url: string;
    readyState: number;
    onopen: any = null;
    onclose: any = null;
    onmessage: any = null;
    send: any;
    close: any;

    static OPEN = 1;
    static CONNECTING = 0;
    static CLOSED = 3;

    constructor(url: string) {
      this.url = url;
      this.readyState = MockWebSocket.CONNECTING;
      this.send = vi.fn();
      this.close = vi.fn(() => {
        this.readyState = MockWebSocket.CLOSED;
        if (this.onclose) this.onclose({});
      });
      wsInstances.push(this);
    }
  }

  beforeEach(() => {
    wsInstances = [];
    originalWebSocket = globalThis.WebSocket;
    // @ts-ignore
    globalThis.WebSocket = MockWebSocket;
    vi.useFakeTimers();
  });

  afterEach(() => {
    // @ts-ignore
    globalThis.WebSocket = originalWebSocket;
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.restoreAllMocks();
  });

  it('should connect and update state', () => {
    const { result } = renderHook(() => useWebSocket());
    
    expect(result.current.connectionState).toBe('connecting');
    expect(wsInstances.length).toBe(1);
    
    // Simulate open
    act(() => {
      wsInstances[0].readyState = 1; // OPEN
      wsInstances[0].onopen({});
    });
    
    expect(result.current.connectionState).toBe('connected');
  });

  it('should handle incoming valid ServerMessage', () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket({ onMessage }));
    
    act(() => {
      wsInstances[0].readyState = 1;
      wsInstances[0].onopen({});
    });

    act(() => {
      wsInstances[0].onmessage({
        data: JSON.stringify({
          type: 'COMMAND_RESULT',
          requestId: '123',
          success: true,
          message: 'OK'
        })
      });
    });

    expect(onMessage).toHaveBeenCalledTimes(1);
    expect(onMessage.mock.calls[0][0].requestId).toBe('123');
  });
  
  it('should ignore incoming invalid messages', () => {
    const onMessage = vi.fn();
    renderHook(() => useWebSocket({ onMessage }));
    
    act(() => {
      wsInstances[0].readyState = 1;
      wsInstances[0].onopen({});
    });

    act(() => {
      wsInstances[0].onmessage({
        data: JSON.stringify({
          type: 'SOME_GARBAGE',
          field: 'value'
        })
      });
    });

    expect(onMessage).not.toHaveBeenCalled();
  });

  it('should reconnect with exponential backoff on close and respect limits', () => {
    const { result } = renderHook(() => useWebSocket({ maxRetries: 2 }));
    
    // Simulate open
    act(() => {
      wsInstances[0].readyState = 1;
      wsInstances[0].onopen({});
    });
    
    // Simulate disconnect
    act(() => {
      wsInstances[0].close();
    });
    
    expect(result.current.connectionState).toBe('disconnected');
    
    // Retry 1 (delay ~1000ms)
    act(() => { vi.advanceTimersByTime(1000); });
    expect(wsInstances.length).toBe(2);
    
    // Simulate disconnect on retry 1
    act(() => { wsInstances[1].close(); });
    
    // Retry 2 (delay ~1500ms)
    act(() => { vi.advanceTimersByTime(1500); });
    expect(wsInstances.length).toBe(3);
    
    // Simulate disconnect on retry 2
    act(() => { wsInstances[2].close(); });
    
    // Should go to error because maxRetries is 2
    expect(result.current.connectionState).toBe('error');
    
    // Should not create a 4th instance
    act(() => { vi.advanceTimersByTime(3000); });
    expect(wsInstances.length).toBe(3);
  });

  it('should not allow sending when disconnected', () => {
    const { result } = renderHook(() => useWebSocket());
    
    // Not connected yet
    let sent = false;
    act(() => {
      sent = result.current.sendMessage({
        type: 'TEXT_COMMAND',
        requestId: '1',
        payload: { query: 'test' }
      });
    });
    expect(sent).toBe(false);
  });
  
  it('should clean up on unmount', () => {
    const { unmount } = renderHook(() => useWebSocket());
    
    expect(wsInstances.length).toBe(1);
    const closeSpy = wsInstances[0].close;
    
    unmount();
    
    expect(closeSpy).toHaveBeenCalled();
  });
  
  it('should not reconnect if unmounted while disconnected', () => {
    const { unmount } = renderHook(() => useWebSocket());
    
    act(() => {
      wsInstances[0].readyState = 1;
      wsInstances[0].onopen({});
    });
    
    act(() => {
      wsInstances[0].close(); // Triggers a reconnect timer
    });
    
    unmount(); // Should clear the timer
    
    act(() => {
      vi.advanceTimersByTime(5000);
    });
    
    // Should not have created a second instance
    expect(wsInstances.length).toBe(1);
  });
  
  it('should not create duplicate connections if connect is called twice', () => {
    const { result } = renderHook(() => useWebSocket());
    
    act(() => {
      result.current.reconnect();
    });
    
    // Should still only have 1 instance because it was CONNECTING
    expect(wsInstances.length).toBe(1);
  });
});
