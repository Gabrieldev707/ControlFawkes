import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { RemoteStatusText } from './RemoteStatusText'


describe('RemoteStatusText', () => {
  it('announces a backend success politely', () => {
    render(<RemoteStatusText message="Comando reconhecido: abrir Spotify." error={false} />)

    const status = screen.getByText('Comando reconhecido: abrir Spotify.')
    expect(status.getAttribute('aria-live')).toBe('polite')
    expect(status.getAttribute('role')).toBeNull()
  })

  it('uses alert semantics for a backend error', () => {
    render(<RemoteStatusText message="Não entendi esse comando." error />)

    expect(screen.getByRole('alert').textContent).toBe('Não entendi esse comando.')
  })
})
