import { act, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { MediaControlPanel } from './MediaControlPanel';

function renderPanel(overrides: Partial<React.ComponentProps<typeof MediaControlPanel>> = {}) {
  const props = {
    volume: 55,
    isMuted: false,
    onSetVolume: vi.fn(),
    onStep: vi.fn(),
    onToggleMute: vi.fn(),
    onOpenSearch: vi.fn(),
    disabled: false,
    ...overrides,
  };

  const result = render(<MediaControlPanel {...props} />);
  return { ...result, props };
}

describe('MediaControlPanel', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
  });

  it('compõe volumes laterais, transporte, voz e pesquisa em uma única carcaça', () => {
    const { container } = renderPanel();
    const shells = container.querySelectorAll('.cosmic-remote-shell');

    expect(shells).toHaveLength(1);
    const shell = shells[0];
    expect(shell.querySelector('.control-circuit-layer')).not.toBeNull();
    expect(shell.querySelector('.cosmic-remote-shell__pc [data-testid="pc-volume-rail"]')).not.toBeNull();
    expect(shell.querySelector('.cosmic-remote-shell__center > .transport-cluster')).not.toBeNull();
    expect(shell.querySelector('.cosmic-remote-shell__player [data-testid="player-volume-rail"]')).not.toBeNull();
    expect(shell.querySelector('.cosmic-remote-shell__footer .voice-preview')).not.toBeNull();
    expect(shell.querySelector('.cosmic-remote-shell__footer .cosmic-remote-shell__search')).not.toBeNull();

    expect(Array.from(shell.children).map((element) => element.getAttribute('class'))).toEqual([
      'control-circuit-layer',
      'cosmic-remote-shell__pc',
      'cosmic-remote-shell__center',
      'cosmic-remote-shell__player',
    ]);
  });

  it('começa sem feedback e reinicia o pulso do PC em interações repetidas', () => {
    const { container, props } = renderPanel();
    const shell = container.querySelector('.cosmic-remote-shell') as HTMLElement;
    const increase = screen.getByRole('button', { name: 'Aumentar volume do computador' });

    expect(shell.dataset.activeZone).toBe('none');
    expect(shell.dataset.pulseId).toBe('0');

    fireEvent.click(increase);
    expect(shell.dataset.activeZone).toBe('pc-volume');
    expect(shell.dataset.pulseId).toBe('1');

    act(() => vi.advanceTimersByTime(300));
    fireEvent.click(increase);
    expect(shell.dataset.activeZone).toBe('pc-volume');
    expect(shell.dataset.pulseId).toBe('2');
    expect(props.onStep).toHaveBeenCalledTimes(2);

    act(() => vi.advanceTimersByTime(449));
    expect(shell.dataset.activeZone).toBe('pc-volume');
    act(() => vi.advanceTimersByTime(1));
    expect(shell.dataset.activeZone).toBe('none');
    expect(shell.dataset.pulseId).toBe('2');
  });

  it('aciona feedback do PC ao iniciar e alterar o slider, mas não nos previews desabilitados', () => {
    const { container, props } = renderPanel();
    const shell = container.querySelector('.cosmic-remote-shell') as HTMLElement;
    const pcSlider = screen.getByRole('slider', { name: 'Volume do computador' });

    fireEvent.pointerDown(pcSlider);
    fireEvent.change(pcSlider, { target: { value: '61' } });

    expect(shell.dataset.activeZone).toBe('pc-volume');
    expect(shell.dataset.pulseId).toBe('2');
    expect(props.onSetVolume).toHaveBeenCalledWith(61);

    for (const button of screen.getAllByRole('button')) {
      if ((button as HTMLButtonElement).disabled && !button.closest('.vertical-volume-rail--violet')) {
        fireEvent.click(button);
      }
    }

    expect(shell.dataset.activeZone).toBe('pc-volume');
    expect(shell.dataset.pulseId).toBe('2');
    expect(props.onStep).not.toHaveBeenCalled();
    expect(props.onToggleMute).not.toHaveBeenCalled();
  });

  it('não pulsa nem envia comandos do PC quando os controles reais estão desabilitados', () => {
    const { container, props } = renderPanel({ disabled: true });
    const shell = container.querySelector('.cosmic-remote-shell') as HTMLElement;
    const slider = screen.getByRole('slider', { name: 'Volume do computador' });

    fireEvent.pointerDown(slider);
    fireEvent.change(slider, { target: { value: '80' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aumentar volume do computador' }));
    fireEvent.click(screen.getByRole('button', { name: 'Ativar mudo do computador' }));

    expect(shell.dataset.activeZone).toBe('none');
    expect(shell.dataset.pulseId).toBe('0');
    expect(props.onSetVolume).not.toHaveBeenCalled();
    expect(props.onStep).not.toHaveBeenCalled();
    expect(props.onToggleMute).not.toHaveBeenCalled();
  });

  it('abre a pesquisa local sem enviar comandos nem depender dos controles do PC', () => {
    const { container, props } = renderPanel({ disabled: true });

    fireEvent.click(screen.getByRole('button', { name: 'Teclado/Pesquisa' }));

    expect(props.onOpenSearch).toHaveBeenCalledTimes(1);
    expect(props.onSetVolume).not.toHaveBeenCalled();
    expect(props.onStep).not.toHaveBeenCalled();
    expect(props.onToggleMute).not.toHaveBeenCalled();
    expect((container.querySelector('.cosmic-remote-shell') as HTMLElement).dataset.activeZone).toBe('none');
  });

  it('cancela o timer de feedback ao desmontar', () => {
    const { unmount } = renderPanel();

    fireEvent.click(screen.getByRole('button', { name: 'Aumentar volume do computador' }));
    expect(vi.getTimerCount()).toBe(1);

    unmount();
    expect(vi.getTimerCount()).toBe(0);
  });

  it('mantém ordem de tab coerente e ícones decorativos fora da árvore acessível', () => {
    const { container } = renderPanel();
    const enabledTabStops = Array.from(
      container.querySelectorAll<HTMLButtonElement | HTMLInputElement>('button, input'),
    ).filter((control) => !control.disabled && control.tabIndex >= 0);

    expect(enabledTabStops.map((control) => control.getAttribute('aria-label'))).toEqual([
      'Aumentar volume do computador',
      'Volume do computador',
      'Diminuir volume do computador',
      'Ativar mudo do computador',
      null,
    ]);
    expect(enabledTabStops[4]?.textContent).toContain('Teclado/Pesquisa');

    for (const icon of container.querySelectorAll('button svg')) {
      expect(icon.getAttribute('aria-hidden')).toBe('true');
    }
  });
});
