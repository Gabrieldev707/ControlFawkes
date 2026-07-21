import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';
import { RemoteStatusText } from './RemoteStatusText';

describe('RemoteStatusText', () => {
  it('anuncia mudanças de estado sem interromper o usuário', () => {
    render(<RemoteStatusText text="Aguardando um comando" state="idle" />);
    const status = screen.getByRole('status');
    expect(status.getAttribute('aria-live')).toBe('polite');
    expect(status.getAttribute('data-state')).toBe('idle');
    expect(status.textContent).toBe('Aguardando um comando');
  });
});
