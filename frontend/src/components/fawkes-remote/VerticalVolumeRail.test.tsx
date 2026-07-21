import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { VerticalVolumeRail } from './VerticalVolumeRail';

function renderRail(overrides: Partial<React.ComponentProps<typeof VerticalVolumeRail>> = {}) {
  const props = {
    id: 'pc-volume',
    label: 'PC',
    value: 45,
    muted: false,
    accent: 'violet' as const,
    onChange: vi.fn(),
    onStep: vi.fn(),
    onToggleMute: vi.fn(),
    onInteraction: vi.fn(),
    ...overrides,
  };

  render(<VerticalVolumeRail {...props} />);
  return props;
}

describe('VerticalVolumeRail', () => {
  it('renderiza um range vertical real, acessível e na ordem +, trilho, −, mudo', () => {
    renderRail();

    expect(screen.getByRole('heading', { name: 'Volume do computador' }).textContent).toBe('PC');
    expect(screen.getByText('45%')).toBeTruthy();

    const slider = screen.getByRole('slider', { name: 'Volume do computador' });
    expect(slider.getAttribute('type')).toBe('range');
    expect(slider.getAttribute('aria-orientation')).toBe('vertical');

    const controls = screen.getByTestId('pc-volume-controls').children;
    expect(controls[0]).toBe(screen.getByRole('button', { name: 'Aumentar volume do computador' }));
    expect(controls[1]).toBe(slider);
    expect(controls[2]).toBe(screen.getByRole('button', { name: 'Diminuir volume do computador' }));
    expect(controls[3]).toBe(screen.getByRole('button', { name: 'Ativar mudo do computador' }));
  });

  it('encaminha mudança, passos exatos e mudo com feedback de interação', () => {
    const props = renderRail();
    const slider = screen.getByRole('slider', { name: 'Volume do computador' });

    fireEvent.pointerDown(slider);
    fireEvent.change(slider, { target: { value: '61' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aumentar volume do computador' }));
    fireEvent.click(screen.getByRole('button', { name: 'Diminuir volume do computador' }));
    fireEvent.click(screen.getByRole('button', { name: 'Ativar mudo do computador' }));

    expect(props.onChange).toHaveBeenCalledWith(61);
    expect(props.onStep).toHaveBeenNthCalledWith(1, 5);
    expect(props.onStep).toHaveBeenNthCalledWith(2, -5);
    expect(props.onToggleMute).toHaveBeenCalledTimes(1);
    expect(props.onInteraction).toHaveBeenCalledTimes(5);
  });

  it('bloqueia passos nos limites de 0 a 100', () => {
    const props = renderRail({ value: 0 });
    const decrease = screen.getByRole('button', { name: 'Diminuir volume do computador' });
    expect((decrease as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(decrease);
    expect(props.onStep).not.toHaveBeenCalled();
    expect(props.onInteraction).not.toHaveBeenCalled();
  });

  it.each([
    { value: 98, label: 'Aumentar volume do computador' },
    { value: 2, label: 'Diminuir volume do computador' },
  ])('bloqueia o passo inteiro de 5 em $value', ({ value, label }) => {
    const props = renderRail({ value });
    const step = screen.getByRole('button', { name: label });

    expect((step as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(step);

    expect(props.onStep).not.toHaveBeenCalled();
    expect(props.onInteraction).not.toHaveBeenCalled();
  });

  it('não executa callbacks quando desabilitado e expõe a razão acessível', () => {
    const props = renderRail({
      id: 'player-volume',
      label: 'PLAYER',
      value: undefined,
      disabled: true,
      accent: 'champagne',
      unavailableReason: 'Disponível após conexão com o navegador',
    });

    expect(screen.getByText('—')).toBeTruthy();
    expect(screen.getByText('Disponível após conexão com o navegador')).toBeTruthy();
    const slider = screen.getByRole('slider', { name: 'Volume do player' });
    expect((slider as HTMLInputElement).disabled).toBe(true);
    expect(slider.getAttribute('aria-describedby')).toBe('player-volume-reason');

    for (const button of screen.getAllByRole('button')) {
      expect((button as HTMLButtonElement).disabled).toBe(true);
      expect(button.getAttribute('aria-disabled')).toBe('true');
    }

    fireEvent.pointerDown(slider);
    fireEvent.change(slider, { target: { value: '70' } });
    fireEvent.click(screen.getByRole('button', { name: 'Aumentar volume do player' }));
    fireEvent.click(screen.getByRole('button', { name: 'Ativar mudo do player' }));

    expect(props.onChange).not.toHaveBeenCalled();
    expect(props.onStep).not.toHaveBeenCalled();
    expect(props.onToggleMute).not.toHaveBeenCalled();
    expect(props.onInteraction).not.toHaveBeenCalled();
  });

  it('mantém o range nativo do PC focável e operável por teclado', () => {
    const props = renderRail();
    const slider = screen.getByRole('slider', {
      name: 'Volume do computador',
    }) as HTMLInputElement;

    slider.focus();
    expect(document.activeElement).toBe(slider);
    expect(slider.tabIndex).toBe(0);
    expect(slider.getAttribute('aria-orientation')).toBe('vertical');

    fireEvent.change(slider, { target: { value: '46' } });
    expect(props.onChange).toHaveBeenLastCalledWith(46);
  });
});
