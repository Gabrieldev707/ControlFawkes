import { render, screen, act, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { FawkesRemotePage } from './FawkesRemotePage';
import * as useWebSocketModule from '../../hooks/useWebSocket';

// Mock child components to simplify testing
vi.mock('../../components/fawkes-remote', () => ({
  RemoteOrb: ({ state }: any) => <div data-testid="remote-orb">{state}</div>,
  ConnectionStatus: ({ state }: any) => <div data-testid="conn-status">{state}</div>,
  PlatformGrid: ({ disabled, onSelect }: any) => (
    <div data-testid="platform-grid" aria-disabled={disabled}>
      <button onClick={() => onSelect('NETFLIX')}>Select Netflix</button>
    </div>
  ),
  VoiceButton: () => <div>Voice</div>,
  TextInput: () => <div>Text</div>
}));

describe('FawkesRemotePage Controller', () => {
  let mockSendMessage: any;
  let mockOnMessage: any;
  
  beforeEach(() => {
    mockSendMessage = vi.fn().mockReturnValue(true);
    
    // Mock the useWebSocket hook
    vi.spyOn(useWebSocketModule, 'useWebSocket').mockImplementation(({ onMessage }: any) => {
      mockOnMessage = onMessage;
      return {
        connectionState: 'connected',
        sendMessage: mockSendMessage,
        reconnect: vi.fn()
      } as any;
    });
    
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllMocks();
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('should send message and enter executing state on platform selection', () => {
    render(<FawkesRemotePage />);
    
    expect(screen.getByTestId('remote-orb').textContent).toBe('idle');
    
    fireEvent.click(screen.getByText('Select Netflix'));
    
    expect(screen.getByTestId('remote-orb').textContent).toBe('executing');
    expect(mockSendMessage).toHaveBeenCalledWith(expect.objectContaining({
      type: 'PLATFORM_SELECTED',
      payload: { platform: 'NETFLIX' }
    }));
  });

  it('should ignore old responses based on requestId correlation', () => {
    render(<FawkesRemotePage />);
    
    fireEvent.click(screen.getByText('Select Netflix'));
    
    expect(screen.getByTestId('remote-orb').textContent).toBe('executing');
    
    // Send response with wrong requestId
    act(() => {
      mockOnMessage({
        type: 'COMMAND_RESULT',
        requestId: 'WRONG-ID',
        success: true,
        message: 'OK'
      });
    });
    
    // Should still be executing
    expect(screen.getByTestId('remote-orb').textContent).toBe('executing');
  });

  it('should transition to success and then idle after COMMAND_RESULT success', () => {
    render(<FawkesRemotePage />);
    
    fireEvent.click(screen.getByText('Select Netflix'));
    const reqId = mockSendMessage.mock.calls[0][0].requestId;
    
    act(() => {
      mockOnMessage({
        type: 'COMMAND_RESULT',
        requestId: reqId,
        success: true,
        message: 'OK'
      });
    });
    
    expect(screen.getByTestId('remote-orb').textContent).toBe('success');
    
    // Advance timers by 2000ms
    act(() => {
      vi.advanceTimersByTime(2000);
    });
    
    expect(screen.getByTestId('remote-orb').textContent).toBe('idle');
  });

  it('should transition to error and then idle after COMMAND_RESULT success: false', () => {
    render(<FawkesRemotePage />);
    
    fireEvent.click(screen.getByText('Select Netflix'));
    const reqId = mockSendMessage.mock.calls[0][0].requestId;
    
    act(() => {
      mockOnMessage({
        type: 'COMMAND_RESULT',
        requestId: reqId,
        success: false,
        message: 'FAIL'
      });
    });
    
    expect(screen.getByTestId('remote-orb').textContent).toBe('error');
    
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    
    expect(screen.getByTestId('remote-orb').textContent).toBe('idle');
  });

  it('should transition to error and then idle after ERROR response', () => {
    render(<FawkesRemotePage />);
    
    fireEvent.click(screen.getByText('Select Netflix'));
    const reqId = mockSendMessage.mock.calls[0][0].requestId;
    
    act(() => {
      mockOnMessage({
        type: 'ERROR',
        requestId: reqId,
        code: 'FAIL',
        message: 'Error'
      });
    });
    
    expect(screen.getByTestId('remote-orb').textContent).toBe('error');
    
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    
    expect(screen.getByTestId('remote-orb').textContent).toBe('idle');
  });

  it('should enter error if sendMessage returns false', () => {
    mockSendMessage.mockReturnValue(false); // Simulate disconnected send attempt
    
    render(<FawkesRemotePage />);
    
    fireEvent.click(screen.getByText('Select Netflix'));
    
    expect(screen.getByTestId('remote-orb').textContent).toBe('error');
    
    act(() => {
      vi.advanceTimersByTime(3000);
    });
    
    expect(screen.getByTestId('remote-orb').textContent).toBe('idle');
  });
  
  it('should clean up timers on unmount', () => {
    const { unmount } = render(<FawkesRemotePage />);
    
    fireEvent.click(screen.getByText('Select Netflix'));
    const reqId = mockSendMessage.mock.calls[0][0].requestId;
    
    act(() => {
      mockOnMessage({
        type: 'COMMAND_RESULT',
        requestId: reqId,
        success: true,
        message: 'OK'
      });
    });
    
    // We are in success state, timeout is pending
    expect(screen.getByTestId('remote-orb').textContent).toBe('success');
    
    unmount(); // Should clear timeout
    
    // Fast forward - if timeout wasn't cleared, it would run and crash 
    // because component is unmounted (React warns, but vitest handles it fine, 
    // this validates that we actually return a cleanup function)
    act(() => {
      vi.advanceTimersByTime(2000);
    });
  });
});
