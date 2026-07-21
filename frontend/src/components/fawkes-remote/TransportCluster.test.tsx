import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { TransportCluster } from './TransportCluster';

describe('TransportCluster', () => {
  it('organiza os controles principais e utilitários na ordem semântica', () => {
    render(<TransportCluster />);

    expect(screen.getAllByRole('button').map((button) => button.getAttribute('aria-label'))).toEqual([
      'Voltar 15 segundos',
      'Play ou pausa',
      'Avançar 15 segundos',
      'Tela cheia',
      'Sair da tela cheia',
      'Voltar',
    ]);
  });

  it('mantém os seis comandos indisponíveis com rótulos acessíveis completos', () => {
    render(<TransportCluster />);

    for (const name of [
      'Voltar 15 segundos',
      'Play ou pausa',
      'Avançar 15 segundos',
      'Tela cheia',
      'Sair da tela cheia',
      'Voltar',
    ]) {
      const button = screen.getByRole('button', { name }) as HTMLButtonElement;
      expect(button.disabled).toBe(true);
      expect(button.getAttribute('aria-disabled')).toBe('true');
    }
  });

  it('destaca o play ou pausa e preserva os textos visíveis dos avanços de 15 segundos', () => {
    render(<TransportCluster />);

    expect(screen.getByRole('button', { name: 'Play ou pausa' }).classList).toContain('transport-cluster__primary');
    expect(screen.getAllByText('15s')).toHaveLength(2);
    expect(screen.getByText('Sair')).toBeTruthy();
    expect(screen.getAllByText('Player disponível após conexão com o navegador')).toHaveLength(1);
  });

  it('não expõe Esc nem callbacks de ação', () => {
    render(<TransportCluster />);

    expect(screen.queryByRole('button', { name: 'Esc' })).toBeNull();
    for (const button of screen.getAllByRole('button')) {
      expect((button as HTMLButtonElement).onclick).toBeNull();
      fireEvent.click(button);
    }
  });
});
