import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { HoldToTalkButton } from './HoldToTalkButton';

describe('HoldToTalkButton', () => {
  it('é um preview circular com somente o SVG dentro do botão e o label abaixo', () => {
    const getUserMedia = vi.fn();
    Object.defineProperty(navigator, 'mediaDevices', { configurable: true, value: { getUserMedia } });
    render(<HoldToTalkButton />);

    const button = screen.getByRole('button', { name: 'Segure para falar' });
    expect((button as HTMLButtonElement).disabled).toBe(true);
    expect(button.getAttribute('aria-disabled')).toBe('true');
    expect(button.classList).toContain('hold-to-talk-button--circular');
    expect(button.children).toHaveLength(1);
    expect(button.firstElementChild?.tagName.toLowerCase()).toBe('svg');
    expect(button.textContent).toBe('');
    expect(button.nextElementSibling?.classList).toContain('hold-to-talk-button__label');
    expect(button.nextElementSibling?.textContent).toBe('Segure para falar');
    expect(screen.queryByText('Disponível no Bloco F — Voz')).toBeNull();
    fireEvent.click(button);
    expect(getUserMedia).not.toHaveBeenCalled();
  });
});
