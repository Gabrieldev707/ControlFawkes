import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PlatformGrid } from './PlatformGrid';

describe('PlatformGrid', () => {
  it('renderiza seis logos locais em cards inicialmente ociosos', () => {
    render(<PlatformGrid selectedPlatform={null} activeState="idle" disabled={false} onSelect={vi.fn()} />);
    const cards = screen.getAllByRole('button');
    expect(cards).toHaveLength(6);
    expect(cards.every((card) => card.getAttribute('data-state') === 'idle')).toBe(true);
    for (const image of screen.getAllByRole('img')) {
      expect(image.getAttribute('src')?.startsWith('/platforms/')).toBe(true);
    }
  });

  it('aplica executing, success e error somente ao card selecionado', () => {
    const { rerender } = render(<PlatformGrid selectedPlatform="NETFLIX" activeState="executing" disabled={false} onSelect={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Netflix' }).getAttribute('data-state')).toBe('executing');
    expect(screen.getByRole('button', { name: 'HBO Max' }).getAttribute('data-state')).toBe('idle');

    rerender(<PlatformGrid selectedPlatform="NETFLIX" activeState="success" disabled={false} onSelect={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Netflix' }).getAttribute('data-state')).toBe('success');

    rerender(<PlatformGrid selectedPlatform="NETFLIX" activeState="error" disabled={false} onSelect={vi.fn()} />);
    expect(screen.getByRole('button', { name: 'Netflix' }).getAttribute('data-state')).toBe('error');
  });

  it('bloqueia todos os cards desconectados e envia apenas plataforma conhecida', () => {
    const onSelect = vi.fn();
    const { rerender } = render(<PlatformGrid selectedPlatform={null} activeState="idle" disabled onSelect={onSelect} />);
    expect(screen.getAllByRole('button').every((card) => (card as HTMLButtonElement).disabled)).toBe(true);
    expect(screen.getAllByRole('button').every((card) => card.getAttribute('data-state') === 'disabled')).toBe(true);

    rerender(<PlatformGrid selectedPlatform={null} activeState="idle" disabled={false} onSelect={onSelect} />);
    fireEvent.click(screen.getByRole('button', { name: 'YouTube' }));
    expect(onSelect).toHaveBeenCalledWith('YOUTUBE', expect.objectContaining({ left: 0, width: 0 }));
  });
});
