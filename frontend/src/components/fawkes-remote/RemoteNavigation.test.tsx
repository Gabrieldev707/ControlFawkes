import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { RemoteNavigation } from './RemoteNavigation';

describe('RemoteNavigation', () => {
  it('navega entre início, controle e touchpad', () => {
    const onNavigate = vi.fn();
    render(<RemoteNavigation currentView="home" onNavigate={onNavigate} />);
    fireEvent.click(screen.getByRole('button', { name: 'Controle' }));
    fireEvent.click(screen.getByRole('button', { name: 'Touchpad' }));
    fireEvent.click(screen.getByRole('button', { name: 'Início' }));
    expect(onNavigate.mock.calls).toEqual([['control'], ['touchpad'], ['home']]);
  });

  it('mantém todos os destinos locais habilitados', () => {
    render(<RemoteNavigation currentView="home" onNavigate={vi.fn()} />);
    for (const label of ['Início', 'Controle', 'Touchpad']) {
      expect((screen.getByRole('button', { name: label }) as HTMLButtonElement).disabled).toBe(false);
    }
  });
});
