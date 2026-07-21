
import { render, screen, fireEvent, act } from '@testing-library/react';
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { PairingScreen } from './PairingScreen';

describe('PairingScreen', () => {
  const mockOnPair = vi.fn();

  beforeEach(() => {
    mockOnPair.mockClear();
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders six empty indicators', () => {
    render(<PairingScreen onPair={mockOnPair} />);
    const indicators = document.querySelectorAll('.indicator');
    expect(indicators).toHaveLength(6);
    indicators.forEach(ind => {
      expect(ind.classList.contains('filled')).toBe(false);
    });
  });

  it('fills indicators on touch/click', () => {
    render(<PairingScreen onPair={mockOnPair} />);
    const btn1 = screen.getByRole('button', { name: 'Número 1' });
    fireEvent.click(btn1);
    
    const indicators = document.querySelectorAll('.indicator');
    expect(indicators[0].classList.contains('filled')).toBe(true);
    expect(indicators[1].classList.contains('filled')).toBe(false);
  });

  it('removes last digit on backspace', () => {
    render(<PairingScreen onPair={mockOnPair} />);
    const btn1 = screen.getByRole('button', { name: 'Número 1' });
    const btnDel = screen.getByRole('button', { name: 'Apagar último número' });
    
    fireEvent.click(btn1);
    expect(document.querySelectorAll('.indicator.filled')).toHaveLength(1);
    
    fireEvent.click(btnDel);
    expect(document.querySelectorAll('.indicator.filled')).toHaveLength(0);
  });

  it('auto-submits on the sixth digit', () => {
    render(<PairingScreen onPair={mockOnPair} />);
    const btn1 = screen.getByRole('button', { name: 'Número 1' });
    
    for (let i = 0; i < 6; i++) {
      fireEvent.click(btn1);
    }
    
    expect(mockOnPair).toHaveBeenCalledTimes(1);
    expect(mockOnPair).toHaveBeenCalledWith('111111', expect.any(String)); // deviceName varies
  });

  it('does not send duplicate requests on re-render', () => {
    const { rerender } = render(<PairingScreen onPair={mockOnPair} />);
    const btn1 = screen.getByRole('button', { name: 'Número 1' });
    
    for (let i = 0; i < 6; i++) {
      fireEvent.click(btn1);
    }
    
    expect(mockOnPair).toHaveBeenCalledTimes(1);
    
    rerender(<PairingScreen onPair={mockOnPair} isPairing={true} />);
    expect(mockOnPair).toHaveBeenCalledTimes(1);
  });

  it('blocks keypad during pairing request', () => {
    render(<PairingScreen onPair={mockOnPair} isPairing={true} />);
    const btn1 = screen.getByRole('button', { name: 'Número 1' }) as HTMLButtonElement;
    expect(btn1.disabled).toBe(true);
  });

  it('clears pin and shakes on PIN error', () => {
    const { rerender } = render(<PairingScreen onPair={mockOnPair} />);
    const btn1 = screen.getByRole('button', { name: 'Número 1' });
    
    for (let i = 0; i < 6; i++) {
      fireEvent.click(btn1);
    }
    
    rerender(<PairingScreen onPair={mockOnPair} errorMsg="PIN incorreto" />);
    
    // Indicators should be clear
    expect(document.querySelectorAll('.indicator.filled')).toHaveLength(0);
    
    // Shake class applied
    expect(document.querySelector('.pin-indicators')?.classList.contains('shake')).toBe(true);
    
    // Advance timer to remove shake
    act(() => {
      vi.advanceTimersByTime(500);
    });
    expect(document.querySelector('.pin-indicators')?.classList.contains('shake')).toBe(false);
  });

  it('network error shows disconnected and does not shake', () => {
    render(<PairingScreen onPair={mockOnPair} errorMsg="Computador desconectado" />);
    
    expect(screen.getAllByText('Computador desconectado').length).toBeGreaterThan(0);
    expect(document.querySelector('.pin-indicators')?.classList.contains('shake')).toBe(false);
    
    const btn1 = screen.getByRole('button', { name: 'Número 1' }) as HTMLButtonElement;
    expect(btn1.disabled).toBe(true); // Should block input
  });

  it('supports physical keyboard input', () => {
    render(<PairingScreen onPair={mockOnPair} />);
    
    fireEvent.keyDown(window, { key: '1' });
    fireEvent.keyDown(window, { key: '2' });
    expect(document.querySelectorAll('.indicator.filled')).toHaveLength(2);
    
    fireEvent.keyDown(window, { key: 'Backspace' });
    expect(document.querySelectorAll('.indicator.filled')).toHaveLength(1);
  });

  it('escapes and clears PIN on Escape key', () => {
    render(<PairingScreen onPair={mockOnPair} />);
    fireEvent.keyDown(window, { key: '1' });
    expect(document.querySelectorAll('.indicator.filled')).toHaveLength(1);
    
    fireEvent.keyDown(window, { key: 'Escape' });
    expect(document.querySelectorAll('.indicator.filled')).toHaveLength(0);
  });

  it('cleans up event listener on unmount', () => {
    const { unmount } = render(<PairingScreen onPair={mockOnPair} />);
    unmount();
    
    // Typing should not throw or do anything
    fireEvent.keyDown(window, { key: '1' });
  });
});
