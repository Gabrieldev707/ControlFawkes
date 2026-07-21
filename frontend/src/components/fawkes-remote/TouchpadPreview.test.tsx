import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TouchpadPreview } from './TouchpadPreview';

describe('TouchpadPreview', () => {
  it('renderiza a superfície cósmica de preview com orientação e quatro marcas de canto', () => {
    render(<TouchpadPreview />);

    expect(screen.getByRole('heading', { name: 'Touchpad' })).toBeTruthy();
    expect(screen.getByText('Preview — sem envio')).toBeTruthy();
    expect(screen.getByTestId('touchpad-orientation-lines')).toBeTruthy();
    expect(screen.getByTestId('touchpad-core')).toBeTruthy();
    expect(screen.getAllByTestId('touchpad-corner-mark')).toHaveLength(4);
  });

  it('expõe a área de gesto como desabilitada e sem handlers de transporte', () => {
    render(<TouchpadPreview />);

    const surface = screen.getByTestId('touchpad-surface') as HTMLDivElement;
    expect(surface.getAttribute('aria-disabled')).toBe('true');
    expect(surface.getAttribute('aria-label') ?? '').toMatch(/área de gesto.*preview.*sem envio/i);
    expect(surface.onclick).toBeNull();
    expect(surface.onpointermove).toBeNull();
    expect(surface.ontouchmove).toBeNull();
    expect(surface.onwheel).toBeNull();
    expect(surface.querySelector('[data-testid="touchpad-cursor"]')).toBeNull();
    expect(surface.querySelector('[class*="mouse-pointer"]')).toBeNull();
  });

  it.each(['Enter', 'Esc', 'Teclado'])('mantém a ação %s tátil, legível e desabilitada', (name) => {
    render(<TouchpadPreview />);

    const button = screen.getByRole('button', { name });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(button.getAttribute('aria-disabled')).toBe('true');
  });
});
