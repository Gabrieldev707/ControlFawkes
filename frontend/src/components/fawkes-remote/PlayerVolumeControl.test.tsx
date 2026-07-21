import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { PlayerVolumeControl } from './PlayerVolumeControl';

describe('PlayerVolumeControl', () => {
  it('reutiliza o trilho champagne sem fingir valor nem capacidade', () => {
    render(<PlayerVolumeControl />);

    expect(screen.getByRole('heading', { name: 'Volume do player' }).textContent).toBe('PLAYER');
    expect(screen.getByText('—')).toBeTruthy();
    expect(screen.queryByText(/disponível após conexão com o navegador/i)).toBeNull();
    expect(screen.getByTestId('player-volume-rail').getAttribute('data-accent')).toBe('champagne');
    expect((screen.getByRole('slider', { name: 'Volume do player' }) as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Diminuir volume do player' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Aumentar volume do player' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: 'Ativar mudo do player' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('não possui controle executável', () => {
    render(<PlayerVolumeControl />);
    const slider = screen.getByRole('slider', { name: 'Volume do player' });
    const increase = screen.getByRole('button', { name: 'Aumentar volume do player' });
    const mute = screen.getByRole('button', { name: 'Ativar mudo do player' });

    fireEvent.pointerDown(slider);
    fireEvent.change(slider, { target: { value: '70' } });
    fireEvent.click(increase);
    fireEvent.click(mute);

    expect((slider as HTMLInputElement).value).toBe('0');
    expect((increase as HTMLButtonElement).disabled).toBe(true);
    expect((mute as HTMLButtonElement).disabled).toBe(true);
  });
});
