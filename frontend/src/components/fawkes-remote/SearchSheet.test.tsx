import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { SearchSheet } from './SearchSheet';

describe('SearchSheet', () => {
  it('não ocupa a tela principal quando está fechada', () => {
    render(<SearchSheet open={false} onClose={vi.fn()} />);
    expect(screen.queryByRole('dialog')).toBeNull();
    expect(screen.queryByRole('textbox')).toBeNull();
  });

  it('permite editar e fechar, mas não envia pesquisa futura', () => {
    const onClose = vi.fn();
    render(<SearchSheet open onClose={onClose} />);
    expect(screen.getByRole('dialog', { name: 'Busca digitada' })).toBeTruthy();
    const input = screen.getByRole('textbox', { name: 'O que deseja procurar?' });
    fireEvent.change(input, { target: { value: 'Harry Potter' } });
    expect(input).toHaveProperty('value', 'Harry Potter');
    const submit = screen.getByRole('button', { name: 'Pesquisar' }) as HTMLButtonElement;
    const reason = screen.getByText('Pesquisa disponível após conexão com o navegador');
    expect(submit.disabled).toBe(true);
    expect(submit.getAttribute('aria-disabled')).toBe('true');
    expect(submit.getAttribute('aria-describedby')).toBe(reason.id);
    fireEvent.click(screen.getByRole('button', { name: 'Cancelar' }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('preserva fechamento pelo botão e pelo backdrop, sem fechar ao editar', () => {
    const onClose = vi.fn();
    const { container } = render(<SearchSheet open onClose={onClose} />);
    const input = screen.getByRole('textbox', { name: 'O que deseja procurar?' });

    fireEvent.mouseDown(input);
    expect(onClose).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Fechar busca' }));
    expect(onClose).toHaveBeenCalledTimes(1);

    fireEvent.mouseDown(container.querySelector('.search-sheet-backdrop') as HTMLElement);
    expect(onClose).toHaveBeenCalledTimes(2);
  });
});
